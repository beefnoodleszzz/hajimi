"""Build a deterministic, watchable local rough master from selected H3 shots."""

from __future__ import annotations

import ast
import html
import json
import subprocess
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageDraw, ImageFont

from .config import dump_yaml, load_yaml, write_json
from .manifest import assert_valid_manifest, load_manifest
from .media.hashing import sha256_file
from .media.probe import executable, ffprobe_json
from .voice.manifest import production_voice_check
from .remote.contract import H3_BACKEND


def _inside_episode(episode_root: Path, value: Any, label: str, *, required: bool = True) -> Path | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a path relative to the episode directory")
    path = (episode_root / value).resolve()
    if not path.is_relative_to(episode_root.resolve()):
        raise ValueError(f"{label} must stay inside the episode directory")
    if not path.is_file():
        raise FileNotFoundError(f"{label} does not exist: {value}")
    return path


def _overlay_position(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a simple expression using w, h, text_w, and text_h")
    try:
        parsed = ast.parse(value, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"{label} must be a simple expression using w, h, text_w, and text_h") from exc

    def validate(node: ast.AST) -> None:
        if isinstance(node, ast.Expression):
            validate(node.body)
        elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return
        elif isinstance(node, ast.Name) and node.id in {"w", "h", "text_w", "text_h"}:
            return
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv)):
            validate(node.left)
            validate(node.right)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            validate(node.operand)
        else:
            raise ValueError(f"{label} contains unsupported expression syntax")

    validate(parsed)
    return value


def _evaluate_position(expression: str, label: str, variables: Mapping[str, float]) -> float:
    parsed = ast.parse(expression, mode="eval")

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name):
            return float(variables[node.id])
        if isinstance(node, ast.UnaryOp):
            value = evaluate(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
        raise ValueError(f"{label} contains unsupported expression syntax")

    try:
        result = evaluate(parsed)
    except (KeyError, ZeroDivisionError) as exc:
        raise ValueError(f"{label} cannot be evaluated") from exc
    if not result == result or abs(result) > 100_000:
        raise ValueError(f"{label} is outside the supported canvas range")
    return result


def _subtitle_cues(path: Path, total_duration: float) -> list[dict[str, Any]]:
    if path.suffix.lower() not in {".srt", ".vtt"}:
        raise ValueError("Pillow subtitle rendering currently supports SRT and VTT")
    timestamp = re.compile(r"^(?:(\d+):)?(\d{2}):(\d{2})[,.](\d{1,3})$")
    cues: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        time_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if time_index is None:
            continue
        start_text, end_text = [part.strip().split()[0] for part in lines[time_index].split("-->", 1)]

        def seconds(value: str) -> float:
            match = timestamp.fullmatch(value)
            if not match:
                raise ValueError(f"Invalid subtitle timestamp: {value}")
            hours = float(match.group(1) or 0)
            minutes, seconds_value = float(match.group(2)), float(match.group(3))
            milliseconds = float(match.group(4).ljust(3, "0"))
            return hours * 3600 + minutes * 60 + seconds_value + milliseconds / 1000

        start, end = seconds(start_text), seconds(end_text)
        text = html.unescape("\n".join(lines[time_index + 1:]))
        text = re.sub(r"</?(?:i|b|u|font)(?:\s+[^>]*)?>", "", text, flags=re.IGNORECASE)
        if not text or end <= start or start >= total_duration:
            continue
        cues.append({"text": text, "start_sec": max(0.0, start), "end_sec": min(total_duration, end)})
        if len(cues) > 500:
            raise ValueError("Roughcut subtitles exceed the 500-cue limit")
    return cues


def _font(font_size: int, configured_path: Any = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [configured_path] if isinstance(configured_path, str) else []
    candidates.extend((
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, font_size)
            except OSError:
                continue
    return ImageFont.load_default()


def _render_text_overlay(
    output: Path,
    *,
    width: int,
    height: int,
    text: str,
    font_size: int,
    x_expression: str,
    y_expression: str,
    font_path: Any = None,
    font_color: str = "white",
    box_color: tuple[int, int, int, int] = (0, 0, 0, 150),
) -> None:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _font(font_size, font_path)
    padding = max(8, round(height * 0.012))
    max_text_width = width - 2 * (padding + 4)
    wrapped_lines: list[str] = []
    for line in text.splitlines() or [text]:
        current = ""
        for character in line:
            if current and draw.textlength(current + character, font=font) > max_text_width:
                wrapped_lines.append(current.rstrip())
                current = character.lstrip()
            else:
                current += character
        wrapped_lines.append(current)
    text = "\n".join(wrapped_lines)
    bounds = draw.multiline_textbbox((0, 0), text, font=font, spacing=4, stroke_width=1)
    text_width, text_height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    variables = {"w": float(width), "h": float(height), "text_w": float(text_width), "text_h": float(text_height)}
    x = round(_evaluate_position(x_expression, "overlay x", variables))
    y = round(_evaluate_position(y_expression, "overlay y", variables))
    if x < 0 or y < 0 or x + text_width > width or y + text_height > height:
        raise ValueError("Text overlay does not fit inside the output frame")
    draw.rounded_rectangle(
        (x - padding, y - padding, x + text_width + padding, y + text_height + padding),
        radius=max(4, round(height * 0.008)),
        fill=box_color,
    )
    draw.multiline_text(
        (x - bounds[0], y - bounds[1]),
        text,
        font=font,
        fill=font_color,
        spacing=4,
        stroke_width=1,
        stroke_fill=(0, 0, 0, 230),
    )
    image.save(output, format="PNG")


def _fps(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        if isinstance(value, str) and "/" in value:
            numerator, denominator = value.split("/", 1)
            return float(numerator) / float(denominator)
        raise ValueError(f"Invalid frame rate: {value!r}")


def _approved_h3_clip(episode_root: Path, item: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    if item.get("status") != "approved" or item.get("remote_status") != "SELECTED":
        raise RuntimeError(f"{item.get('id')} must have a locally selected and approved H3 candidate")
    relative = item.get("active_media")
    media = _inside_episode(episode_root, relative, f"{item.get('id')} active_media")
    assert media is not None
    metadata_path = media.with_suffix(".json")
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Selected H3 metadata is missing: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("backend") != H3_BACKEND or metadata.get("sha256") != sha256_file(media):
        raise ValueError(f"{item.get('id')} selected media is not a verified H3 candidate")
    probe = ffprobe_json(media)
    if not probe.get("ok"):
        raise RuntimeError(f"ffprobe failed for {media}: {probe.get('error', 'unknown error')}")
    streams = probe.get("streams", [])
    if not any(stream.get("codec_type") == "video" for stream in streams):
        raise ValueError(f"Selected H3 candidate has no video stream: {media}")
    if not any(stream.get("codec_type") == "audio" for stream in streams):
        raise ValueError(f"Selected H3 candidate has no native audio stream: {media}")
    return media, probe


def _next_output(episode_root: Path, episode_id: str) -> Path:
    master_dir = episode_root / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    revision = 1
    while True:
        path = master_dir / f"{episode_id}_rough_v{revision:03d}.mp4"
        if not path.exists():
            return path
        revision += 1


def build_roughcut(episode_root: str | Path) -> Path:
    episode_root = Path(episode_root).resolve()
    manifest_path = episode_root / "episode.yaml"
    manifest = load_manifest(manifest_path)
    assert_valid_manifest(manifest, manifest_path)
    gate_path = episode_root / "animatic" / "gate.json"
    if not gate_path.is_file():
        raise RuntimeError("Animatic gate is missing; roughcut cannot start")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if gate.get("production_gate") != "PASS":
        raise RuntimeError("Animatic production_gate is not PASS")
    voice_check = production_voice_check(episode_root)
    if not voice_check.get("pass"):
        raise RuntimeError(f"Roughcut requires local VoxCPM2 production narration: {voice_check.get('reason', 'voice check failed')}")

    shots = manifest.get("shots", [])
    if not shots or any(not isinstance(item.get("time_start"), (int, float)) or not isinstance(item.get("time_end"), (int, float)) for item in shots):
        raise ValueError("Every shot needs a timeline start and end before roughcut")
    shots = sorted(shots, key=lambda item: float(item["time_start"]))
    if abs(float(shots[0]["time_start"])) > 1e-6:
        raise ValueError("Roughcut timeline must start at 0 seconds")
    for previous, current in zip(shots, shots[1:]):
        if abs(float(current["time_start"]) - float(previous["time_end"])) > 0.05:
            raise ValueError(f"Roughcut timeline has a gap or overlap between {previous['id']} and {current['id']}")

    voice = _inside_episode(episode_root, "audio/production/narration.wav", "production narration")
    assert voice is not None
    roughcut_config_path = episode_root / "edit" / "roughcut.yaml"
    if not roughcut_config_path.is_file():
        raise FileNotFoundError(f"Roughcut sound/subtitle plan is missing: {roughcut_config_path}")
    config = load_yaml(roughcut_config_path)
    if config.get("schema_version") != "hajimi-roughcut-v1":
        raise ValueError("edit/roughcut.yaml has an unsupported schema_version")
    music = _inside_episode(episode_root, config.get("music"), "roughcut music")
    subtitles = _inside_episode(episode_root, config.get("subtitles"), "roughcut subtitles")
    sfx = config.get("sfx", [])
    overlays = config.get("overlays", [])
    if not isinstance(sfx, list) or not isinstance(overlays, list):
        raise ValueError("roughcut sfx and overlays must be lists")
    if subtitles and subtitles.suffix.lower() not in {".srt", ".vtt"}:
        raise ValueError("Pillow subtitle rendering supports SRT and VTT")
    music_gain_db = config.get("music_gain_db", -18)
    if not isinstance(music_gain_db, (int, float)) or not -60 <= music_gain_db <= 6:
        raise ValueError("music_gain_db must be from -60 to 6 dB")

    clip_data = [_approved_h3_clip(episode_root, item) for item in shots]
    ffmpeg_bin = executable("HAJIMI_FFMPEG", "ffmpeg")
    ffprobe_bin = executable("HAJIMI_FFPROBE", "ffprobe")
    if not ffmpeg_bin or not ffprobe_bin:
        raise RuntimeError("ffmpeg and ffprobe are required for roughcut")
    output = _next_output(episode_root, manifest["episode_id"])
    width = int(manifest["master"]["width"])
    height = int(manifest["master"]["height"])
    fps = _fps(manifest["master"]["fps"])
    sample_rate = int(manifest["master"]["sample_rate"])
    total_duration = float(shots[-1]["time_end"])
    subtitle_cues = _subtitle_cues(subtitles, total_duration)
    if not subtitle_cues:
        raise ValueError("Roughcut subtitle file contains no cues inside the timeline")
    subtitle_font_size = config.get("subtitle_font_size", max(22, round(height * 0.032)))
    if not isinstance(subtitle_font_size, int) or not 16 <= subtitle_font_size <= 180:
        raise ValueError("subtitle_font_size must be from 16 to 180")
    subtitle_x = _overlay_position(config.get("subtitle_x", "(w-text_w)/2"), "subtitle_x")
    subtitle_y = _overlay_position(config.get("subtitle_y", "h*0.78"), "subtitle_y")
    font_path = config.get("font_path")

    text_items: list[dict[str, Any]] = []
    for cue in subtitle_cues:
        text_items.append({
            **cue,
            "x": subtitle_x,
            "y": subtitle_y,
            "font_size": subtitle_font_size,
            "font_color": "white",
        })
    for index, overlay in enumerate(overlays):
        if not isinstance(overlay, dict) or not isinstance(overlay.get("text"), str) or not overlay["text"].strip():
            raise ValueError(f"overlays[{index}] needs non-empty text, start_sec, and end_sec")
        start, end = overlay.get("start_sec"), overlay.get("end_sec")
        x = _overlay_position(overlay.get("x", "(w-text_w)/2"), f"overlays[{index}].x")
        y = _overlay_position(overlay.get("y", "h*0.78"), f"overlays[{index}].y")
        if not isinstance(start, (int, float)) or isinstance(start, bool) or not isinstance(end, (int, float)) or isinstance(end, bool) or start < 0 or end <= start or end > total_duration:
            raise ValueError(f"overlays[{index}] has invalid time bounds")
        font_size = overlay.get("font_size", 58)
        if not isinstance(font_size, int) or not 16 <= font_size <= 180:
            raise ValueError(f"overlays[{index}].font_size must be from 16 to 180")
        text_items.append({
            "text": overlay["text"],
            "start_sec": float(start),
            "end_sec": float(end),
            "x": x,
            "y": y,
            "font_size": font_size,
            "font_color": str(overlay.get("font_color", "white")),
        })

    command = [ffmpeg_bin, "-y", "-hide_banner", "-nostdin"]
    for media, _ in clip_data:
        command += ["-i", str(media)]
    voice_index = len(clip_data)
    command += ["-i", str(voice)]
    music_index = len(clip_data) + 1
    command += ["-stream_loop", "-1", "-i", str(music)]
    sfx_paths: list[tuple[Path, float, float]] = []
    for index, cue in enumerate(sfx):
        if not isinstance(cue, dict):
            raise ValueError(f"sfx[{index}] must be a mapping")
        path = _inside_episode(episode_root, cue.get("path"), f"sfx[{index}].path")
        assert path is not None
        start = cue.get("start_sec")
        gain_db = cue.get("gain_db", 0)
        if not isinstance(start, (int, float)) or start < 0 or start >= total_duration:
            raise ValueError(f"sfx[{index}].start_sec must be within the timeline")
        if not isinstance(gain_db, (int, float)) or not -60 <= gain_db <= 12:
            raise ValueError(f"sfx[{index}].gain_db must be from -60 to 12 dB")
        sfx_paths.append((path, float(start), float(gain_db)))
    sfx_indices: list[int] = []
    for path, _, _ in sfx_paths:
        sfx_indices.append(len(clip_data) + 2 + len(sfx_indices))
        command += ["-i", str(path)]

    overlay_input_start = len(clip_data) + 2 + len(sfx_paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hajimi-roughcut-overlay-") as temporary:
        for index, item in enumerate(text_items):
            overlay_path = Path(temporary) / f"overlay_{index:03d}.png"
            _render_text_overlay(
                overlay_path,
                width=width,
                height=height,
                text=item["text"],
                font_size=item["font_size"],
                x_expression=item["x"],
                y_expression=item["y"],
                font_path=font_path,
                font_color=item.get("font_color", "white"),
            )
            command += ["-loop", "1", "-framerate", f"{fps:.6f}", "-i", str(overlay_path)]

        filters: list[str] = []
        concat_inputs: list[str] = []
        for index, (shot, (_, probe)) in enumerate(zip(shots, clip_data)):
            duration = float(shot["time_end"]) - float(shot["time_start"])
            media_duration = float(probe.get("format", {}).get("duration", 0.0) or 0.0)
            if media_duration + 0.05 < duration:
                raise ValueError(f"{shot['id']} selected H3 video is shorter than its timeline slot")
            filters.append(
                f"[{index}:v:0]trim=duration={duration:.6f},setpts=PTS-STARTPTS,"
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,fps={fps:.6f},setsar=1,format=yuv420p[v{index}]"
            )
            filters.append(
                f"[{index}:a:0]atrim=duration={duration:.6f},asetpts=PTS-STARTPTS,"
                f"aresample={sample_rate},aformat=sample_fmts=fltp:channel_layouts=stereo[a{index}]"
            )
            concat_inputs.extend((f"[v{index}]", f"[a{index}]"))
        filters.append("".join(concat_inputs) + f"concat=n={len(shots)}:v=1:a=1[vbase][ambience]")
        video_label = "[vbase]"
        for index, item in enumerate(text_items):
            overlay_input = overlay_input_start + index
            overlay_label = f"[text{index}]"
            output_label = f"[video{index}]"
            start, end = item["start_sec"], item["end_sec"]
            filters.append(f"[{overlay_input}:v:0]format=rgba,setpts=PTS-STARTPTS{overlay_label}")
            filters.append(
                f"{video_label}{overlay_label}overlay=x=0:y=0:eof_action=pass:shortest=1:"
                f"enable='between(t,{start:.6f},{end:.6f})'{output_label}"
            )
            video_label = output_label
        filters.append(f"{video_label}null[videoout]")
        filters.append(
            f"[{voice_index}:a:0]aresample={sample_rate},aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"apad=whole_dur={total_duration:.6f},atrim=duration={total_duration:.6f},asplit=2[voice_mix][voice_sc]"
        )
        filters.append(f"[{music_index}:a:0]atrim=duration={total_duration:.6f},asetpts=PTS-STARTPTS,volume={music_gain_db:.2f}dB[music]")
        filters.append("[music][voice_sc]sidechaincompress=threshold=0.025:ratio=7:attack=20:release=400[ducked]")
        mix_inputs = ["[ambience]", "[voice_mix]", "[ducked]"]
        for cue_index, (input_index, (_, start, gain_db)) in enumerate(zip(sfx_indices, sfx_paths)):
            delay_ms = round(start * 1000)
            filters.append(f"[{input_index}:a:0]aresample={sample_rate},volume={gain_db:.2f}dB,adelay={delay_ms}|{delay_ms}[sfx{cue_index}]")
            mix_inputs.append(f"[sfx{cue_index}]")
        target_lufs = float(manifest.get("audio", {}).get("target_lufs", -14))
        true_peak_max = float(manifest.get("audio", {}).get("true_peak_max_db", -1))
        filters.append(
            "".join(mix_inputs) + f"amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=1:normalize=0,"
            f"loudnorm=I={target_lufs:.1f}:TP={true_peak_max:.1f}:LRA=11[audioout]"
        )
        command += [
            "-filter_complex", ";".join(filters),
            "-map", "[videoout]", "-map", "[audioout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", str(sample_rate), "-b:a", "192k", "-t", f"{total_duration:.6f}",
            "-movflags", "+faststart", str(output),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        output.unlink(missing_ok=True)
        raise RuntimeError(completed.stderr.strip()[-3500:] or "FFmpeg roughcut failed")
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("FFmpeg returned success without producing a roughcut")
    probe = ffprobe_json(output, ffprobe_bin=ffprobe_bin)
    if not probe.get("ok") or not any(item.get("codec_type") == "audio" for item in probe.get("streams", [])):
        output.unlink(missing_ok=True)
        raise RuntimeError("Roughcut output failed ffprobe validation")

    report = {
        "schema_version": "hajimi-roughcut-manifest-v1",
        "episode_id": manifest["episode_id"],
        "source": "ffmpeg",
        "output": str(output.relative_to(episode_root)),
        "output_sha256": sha256_file(output),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "timeline": [
            {"shot_id": shot["id"], "start_sec": shot["time_start"], "end_sec": shot["time_end"], "duration_sec": shot["time_end"] - shot["time_start"], "source": shot["active_media"]}
            for shot in shots
        ],
        "inputs": {
            **{shot["id"]: {"path": item[0].relative_to(episode_root).as_posix(), "sha256": sha256_file(item[0])} for shot, item in zip(shots, clip_data)},
            "narration": {"path": voice.relative_to(episode_root).as_posix(), "sha256": sha256_file(voice)},
            "music": {"path": music.relative_to(episode_root).as_posix(), "sha256": sha256_file(music)},
            "subtitles": {"path": subtitles.relative_to(episode_root).as_posix(), "sha256": sha256_file(subtitles)},
            "roughcut_plan": {"path": roughcut_config_path.relative_to(episode_root).as_posix(), "sha256": sha256_file(roughcut_config_path)},
            "sfx": [{"path": path.relative_to(episode_root).as_posix(), "sha256": sha256_file(path), "start_sec": start, "gain_db": gain} for path, start, gain in sfx_paths],
        },
        "mix": {"native_ambience": "H3 candidate audio", "music_ducking": "sidechaincompress", "music_gain_db": music_gain_db, "target_lufs": target_lufs, "true_peak_db": true_peak_max},
        "probe": probe,
    }
    write_json(report, episode_root / "edit" / "roughcut_manifest.json")
    manifest["master"]["source"] = "ffmpeg"
    manifest["master"]["path"] = str(output.relative_to(episode_root))
    dump_yaml({key: value for key, value in manifest.items() if key != "_path"}, manifest_path)
    return output
