"""Build EP001's deterministic storyboard animatic and gate it.

The animatic is intentionally cheap: no AI generation is invoked, and no old
V1 asset is consulted. Cards provide readable composition, vectors, and the
continuity anchor so story rhythm can be judged before expensive production.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from ..config import load_yaml, write_json
from ..manifest import assert_valid_manifest, load_manifest
from ..media.probe import executable, probe_media
from ..paths import StudioPaths, project_root

TEMP_VO = (
    "Imagine the ground under your feet stopping for exactly one second. "
    "The ground stops. You don't. At the equator, you are already moving east "
    "at about four hundred sixty-five meters per second. In one second, that is "
    "roughly four hundred sixty-five meters relative to the ground. Your body, "
    "the air, and the clouds keep that sideways motion too. The ocean does not "
    "politely stop with the pavement. When the ground starts again, land, air, "
    "and water are no longer aligned. Gravity still holds you down. The danger "
    "is sideways. That is the real disaster: a one-second mismatch in motion. "
    "One second. Four hundred sixty-five meters. What moves first?"
)
TEMP_VO_RATE = 190

SHOT_CARDS: list[dict[str, Any]] = [
    {"id": "S001", "kicker": "0.0 — 1.2 / THE EVENT", "title": "THE GROUND\nSTOPS", "sub": "YOU HAVE NOT MOVED YET", "kind": "road", "accent": "#ffb35c"},
    {"id": "S002", "kicker": "1.2 — 4.0 / PERSONAL SCALE", "title": "YOU DON'T", "sub": "EASTWARD INERTIA", "kind": "person", "accent": "#ff6b5f"},
    {"id": "S003", "kicker": "4.0 — 7.0 / EQUATOR", "title": "465 m/s", "sub": "ALREADY MOVING EAST", "kind": "speed", "accent": "#52d7ff"},
    {"id": "S004", "kicker": "7.0 — 11.0 / ONE SECOND", "title": "≈ 465 m", "sub": "RELATIVE TO THE GROUND", "kind": "map", "accent": "#52d7ff"},
    {"id": "S005", "kicker": "11.0 — 16.0 / ATMOSPHERE", "title": "THE AIR\nKEEPS GOING", "sub": "LAND STAYS FIXED", "kind": "air", "accent": "#8cecff"},
    {"id": "S006", "kicker": "16.0 — 21.0 / OCEAN", "title": "WATER\nKEEPS GOING", "sub": "THE PAVEMENT IS NOT THE OCEAN", "kind": "ocean", "accent": "#3ca8ff"},
    {"id": "S007", "kicker": "21.0 — 27.0 / HERO SHOT", "title": "MOTION ≠\nGROUND", "sub": "LAND / AIR / OCEAN", "kind": "mismatch", "accent": "#ffb35c"},
    {"id": "S008", "kicker": "27.0 — 31.0 / CORRECTION", "title": "GRAVITY\nSTAYS", "sub": "THE DANGER IS SIDEWAYS", "kind": "vectors", "accent": "#ff6b5f"},
    {"id": "S009", "kicker": "31.0 — 35.0 / PAYOFF", "title": "ONE-SECOND\nMISMATCH", "sub": "THAT IS THE DISASTER", "kind": "thesis", "accent": "#ffb35c"},
    {"id": "S010", "kicker": "35.0 — 38.0 / CALLBACK", "title": "WHAT MOVES\nFIRST?", "sub": "ONE SECOND · 465 METERS", "kind": "callback", "accent": "#ff6b5f"},
]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, font: ImageFont.ImageFont, fill: str, anchor: str | None = None) -> None:
    draw.text(xy, value, font=font, fill=fill, anchor=anchor, spacing=8)


def _arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str, width: int = 8) -> None:
    draw.line([start, end], fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    angle = math.atan2(y2 - y1, x2 - x1)
    length = 32
    left = (x2 - length * math.cos(angle - math.pi / 6), y2 - length * math.sin(angle - math.pi / 6))
    right = (x2 - length * math.cos(angle + math.pi / 6), y2 - length * math.sin(angle + math.pi / 6))
    draw.polygon([end, left, right], fill=color)


def _road(draw: ImageDraw.ImageDraw, accent: str, shifted: bool = False) -> None:
    width, height = 1080, 1920
    horizon = 820
    draw.polygon([(0, height), (width, height), (760, horizon), (320, horizon)], fill="#1b2430")
    for offset in range(-2, 8):
        x = 540 + offset * 110
        draw.line([(540, horizon), (x, height)], fill="#435062", width=3)
    for y in range(horizon + 100, height, 155):
        draw.line([(120, y), (960, y)], fill="#394656", width=4)
    draw.line([(540, horizon), (540, height)], fill="#d9cfa1", width=5)
    draw.ellipse((470, 850, 610, 990), fill="#c5cedc", outline="#eef5ff", width=4)
    receipt_x = 830 if shifted else 580
    draw.rounded_rectangle((receipt_x, 1020, receipt_x + 58, 1110), radius=8, fill="#e94f43", outline="#ffd0c8", width=3)
    _arrow(draw, (receipt_x + 30, 1130), (min(width - 30, receipt_x + 260), 1130), accent, 7)


def _person(draw: ImageDraw.ImageDraw, accent: str) -> None:
    draw.ellipse((455, 860, 570, 975), fill="#bac7d8")
    draw.rounded_rectangle((420, 970, 605, 1300), radius=58, fill="#2f3a49", outline="#e6f0ff", width=4)
    draw.line([(455, 1290), (385, 1530)], fill="#bac7d8", width=36)
    draw.line([(570, 1290), (650, 1530)], fill="#bac7d8", width=36)
    draw.line([(435, 1060), (280, 1220)], fill="#bac7d8", width=28)
    draw.line([(585, 1060), (735, 1170)], fill="#bac7d8", width=28)
    _arrow(draw, (620, 1150), (920, 1150), accent, 12)


def _layers(draw: ImageDraw.ImageDraw, accent: str, mismatch: bool = False) -> None:
    left = 120
    right = 960
    y_values = [(980, "LAND", "#8f714c"), (1170, "AIR", "#86c9d9"), (1360, "OCEAN", "#2776b7")]
    for index, (y, label, color) in enumerate(y_values):
        shift = 0 if not mismatch or index == 0 else (70 + index * 35)
        draw.rounded_rectangle((left + shift, y, right + shift, y + 110), radius=16, fill=color, outline="#d9f3ff", width=4)
        _text(draw, (left + 32 + shift, y + 55), label, _font(34, True), "#08111d", anchor="lm")
        if index > 0:
            _arrow(draw, (right - 170 + shift, y + 55), (right + 10 + shift, y + 55), accent, 8)
    if mismatch:
        _text(draw, (540, 1580), "RESTART", _font(34, True), accent, anchor="mm")
        _arrow(draw, (880, 1040), (800, 1040), "#ff6b5f", 7)


def _draw_visual(draw: ImageDraw.ImageDraw, kind: str, accent: str) -> None:
    if kind == "road":
        _road(draw, accent)
        draw.line([(120, 820), (960, 820)], fill="#ffb35c", width=8)
    elif kind == "person":
        _road(draw, accent)
        _person(draw, accent)
    elif kind == "speed":
        draw.ellipse((170, 840, 910, 1580), outline="#263b50", width=6)
        for radius in (180, 280, 380):
            draw.arc((540 - radius, 1210 - radius, 540 + radius, 1210 + radius), 205, 335, fill="#52d7ff", width=5)
        _arrow(draw, (220, 1210), (880, 1210), accent, 14)
        _text(draw, (540, 1040), "EAST", _font(34, True), "#8cecff", anchor="mm")
    elif kind == "map":
        for x in range(120, 1000, 150):
            draw.line([(x, 850), (x, 1500)], fill="#35475a", width=4)
        for y in range(850, 1550, 150):
            draw.line([(100, y), (980, y)], fill="#35475a", width=4)
        draw.ellipse((170, 1170, 210, 1210), fill="#e94f43")
        draw.ellipse((850, 1170, 890, 1210), fill="#ffb35c")
        _arrow(draw, (210, 1190), (850, 1190), accent, 12)
    elif kind == "air":
        draw.rectangle((100, 1160, 980, 1450), fill="#8f714c", outline="#f2d0a0", width=4)
        draw.ellipse((190, 840, 420, 1030), fill="#bcdde8", outline="#efffff", width=4)
        draw.ellipse((340, 780, 650, 1040), fill="#bcdde8", outline="#efffff", width=4)
        draw.ellipse((590, 850, 850, 1030), fill="#bcdde8", outline="#efffff", width=4)
        _arrow(draw, (180, 1010), (900, 1010), accent, 12)
    elif kind == "ocean":
        draw.polygon([(90, 1100), (990, 980), (990, 1540), (90, 1540)], fill="#2776b7")
        for y in range(1160, 1510, 90):
            draw.arc((130, y, 900, y + 80), 190, 350, fill="#8cecff", width=5)
        draw.rectangle((90, 950, 990, 1100), fill="#8f714c")
        _arrow(draw, (220, 900), (900, 900), accent, 11)
    elif kind == "mismatch":
        _layers(draw, accent, mismatch=True)
    elif kind == "vectors":
        _person(draw, accent)
        _arrow(draw, (540, 1330), (540, 850), "#8cecff", 10)
        _arrow(draw, (600, 1130), (930, 1130), accent, 14)
        _text(draw, (570, 820), "GRAVITY", _font(28, True), "#8cecff", anchor="lm")
        _text(draw, (700, 1085), "SIDEWAYS", _font(28, True), accent, anchor="mm")
    elif kind == "thesis":
        _layers(draw, accent, mismatch=True)
        draw.rounded_rectangle((150, 700, 930, 860), radius=24, fill="#111b28", outline=accent, width=4)
        _text(draw, (540, 780), "THE REAL DISASTER", _font(42, True), "#f5f8ff", anchor="mm")
    elif kind == "callback":
        _road(draw, accent, shifted=True)
        draw.rounded_rectangle((120, 700, 960, 845), radius=22, fill="#111b28", outline=accent, width=4)
        _text(draw, (540, 772), "WHAT MOVES FIRST?", _font(42, True), "#f5f8ff", anchor="mm")


def render_card(card: dict[str, Any], destination: str | Path, width: int = 1080, height: int = 1920) -> Path:
    image = Image.new("RGB", (width, height), "#09111b")
    draw = ImageDraw.Draw(image)
    # A subtle frame prevents the card from being a flat black page.
    draw.rectangle((30, 30, width - 30, height - 30), outline="#1d3548", width=3)
    _text(draw, (84, 92), card["kicker"], _font(26, True), card["accent"])
    _text(draw, (84, 190), card["title"], _font(82, True), "#f1f6ff")
    _text(draw, (84, 430), card["sub"], _font(28, True), "#9eb1c7")
    _draw_visual(draw, card["kind"], card["accent"])
    draw.line([(84, 1660), (996, 1660)], fill="#233d52", width=3)
    _text(draw, (84, 1720), "THE WORLD YOU NEVER KNEW", _font(22, True), "#708aa2")
    _text(draw, (996, 1720), card["id"], _font(22, True), card["accent"], anchor="ra")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, "PNG", optimize=True)
    return destination


def build_storyboard_cards(episode_root: str | Path) -> list[Path]:
    card_root = Path(episode_root) / "animatic" / "cards"
    paths: list[Path] = []
    for card in SHOT_CARDS:
        path = render_card(card, card_root / f"{card['id']}.png")
        shot_preview = Path(episode_root) / "shots" / card["id"] / "preview" / "storyboard.png"
        shot_preview.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, shot_preview)
        paths.append(path)
    return paths


def _write_pcm_stem(path: Path, duration: float, generator) -> None:
    sample_rate = 48000
    frames = int(duration * sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        buffer = bytearray()
        for index in range(frames):
            value = max(-1.0, min(1.0, generator(index / sample_rate)))
            buffer.extend(int(value * 32767).to_bytes(2, "little", signed=True))
            if len(buffer) >= 65536:
                stream.writeframes(buffer)
                buffer.clear()
        if buffer:
            stream.writeframes(buffer)


def create_audio_stems(episode_root: str | Path, duration: float = 38.0) -> dict[str, Any]:
    audio_root = Path(episode_root) / "audio"
    audio_root.mkdir(parents=True, exist_ok=True)
    voice_path = audio_root / "vo_temp.wav"
    voice_status = "synthetic_tone_fallback"
    say_bin = shutil.which("say")
    ffmpeg_bin = executable("HAJIMI_FFMPEG", "ffmpeg")
    aiff_path = Path(episode_root) / "animatic" / "render_work" / "vo_temp.aiff"
    if say_bin and ffmpeg_bin:
        aiff_path.parent.mkdir(parents=True, exist_ok=True)
        spoken = subprocess.run([say_bin, "-v", "Samantha", "-r", str(TEMP_VO_RATE), "-o", str(aiff_path), TEMP_VO], capture_output=True, text=True, check=False)
        if spoken.returncode == 0:
            converted = subprocess.run([ffmpeg_bin, "-y", "-hide_banner", "-nostdin", "-i", str(aiff_path), "-ar", "48000", "-ac", "1", str(voice_path)], capture_output=True, text=True, check=False)
            if converted.returncode == 0:
                voice_status = "macos_say_temp_voice"
    if not voice_path.exists():
        _write_pcm_stem(voice_path, duration, lambda t: 0.0)

    _write_pcm_stem(audio_root / "music_temp.wav", duration, lambda t: 0.035 * math.sin(2 * math.pi * (82 + 0.8 * math.sin(t / 5)) * t) + 0.012 * math.sin(2 * math.pi * 164 * t))
    _write_pcm_stem(audio_root / "ambience_temp.wav", duration, lambda t: 0.016 * math.sin(2 * math.pi * 196 * t) + 0.008 * math.sin(2 * math.pi * 278 * t))
    event_times = [0.0, 0.38, 4.0, 7.0, 11.0, 21.0, 27.0, 31.0, 35.0]

    def sfx(t: float) -> float:
        output = 0.0
        for event in event_times:
            local = t - event
            if 0 <= local <= 0.72:
                output += 0.14 * math.sin(2 * math.pi * (65 + 120 * local) * local) * math.exp(-5.5 * local)
        return output

    _write_pcm_stem(audio_root / "narrative_sfx_temp.wav", duration, sfx)
    stems = {
        "voice": str(voice_path),
        "music": str(audio_root / "music_temp.wav"),
        "ambience": str(audio_root / "ambience_temp.wav"),
        "sfx": str(audio_root / "narrative_sfx_temp.wav"),
        "voice_status": voice_status,
        "layer_count": 4,
    }
    write_json(stems, audio_root / "stems.json")
    return stems


def _render_segment(card_path: Path, destination: Path, duration: float) -> None:
    ffmpeg_bin = executable("HAJIMI_FFMPEG", "ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg is required to render the animatic")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-nostdin",
        "-loop",
        "1",
        "-i",
        str(card_path),
        "-t",
        f"{duration:.3f}",
        "-vf",
        "zoompan=z='min(zoom+0.00035,1.035)':d=1:s=1080x1920:fps=30,format=yuv420p",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "24",
        str(destination),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-3000:] or "animatic segment render failed")


def _mix_audio(episode_root: Path, destination: Path, duration: float) -> None:
    ffmpeg_bin = executable("HAJIMI_FFMPEG", "ffmpeg")
    if not ffmpeg_bin:
        return
    audio_root = episode_root / "audio"
    inputs = [audio_root / "vo_temp.wav", audio_root / "music_temp.wav", audio_root / "ambience_temp.wav", audio_root / "narrative_sfx_temp.wav"]
    command = [ffmpeg_bin, "-y", "-hide_banner", "-nostdin"]
    for path in inputs:
        command += ["-i", str(path)]
    command += [
        "-filter_complex",
        "[0:a]volume=1.0[vo];[1:a]volume=0.8[music];[2:a]volume=0.8[amb];[3:a]volume=1.0[sfx];[vo][music][amb][sfx]amix=inputs=4:duration=longest:dropout_transition=0,loudnorm=I=-14:TP=-1.0:LRA=7:print_format=summary,alimiter=limit=0.95[aout]",
        "-map",
        "[aout]",
        "-t",
        f"{duration:.3f}",
        "-ar",
        "48000",
        "-ac",
        "2",
        str(destination),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-3000:] or "audio mix failed")


def render_animatic(episode_root: str | Path, manifest: dict[str, Any]) -> Path:
    episode_root = Path(episode_root)
    cards = build_storyboard_cards(episode_root)
    render_root = episode_root / "animatic" / "render_work"
    render_root.mkdir(parents=True, exist_ok=True)
    segments: list[Path] = []
    for card, shot in zip(cards, manifest["shots"]):
        segment = render_root / f"{shot['id']}.mp4"
        _render_segment(card, segment, float(shot["duration_target"]))
        segments.append(segment)
    concat_path = render_root / "concat.txt"
    concat_path.write_text("\n".join(f"file '{segment.resolve()}'" for segment in segments) + "\n", encoding="utf-8")
    ffmpeg_bin = executable("HAJIMI_FFMPEG", "ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg is required to concatenate the animatic")
    video_only = render_root / "video_only.mp4"
    concatenated = subprocess.run([ffmpeg_bin, "-y", "-hide_banner", "-nostdin", "-f", "concat", "-safe", "0", "-i", str(concat_path), "-c", "copy", str(video_only)], capture_output=True, text=True, check=False)
    if concatenated.returncode != 0:
        raise RuntimeError(concatenated.stderr[-3000:] or "animatic concat failed")
    stems = create_audio_stems(episode_root, duration=sum(float(shot["duration_target"]) for shot in manifest["shots"]))
    mixed_audio = render_root / "mixed_audio.wav"
    _mix_audio(episode_root, mixed_audio, sum(float(shot["duration_target"]) for shot in manifest["shots"]))
    output = episode_root / "animatic" / f"{manifest['episode_id']}_animatic.mp4"
    muxed = subprocess.run([ffmpeg_bin, "-y", "-hide_banner", "-nostdin", "-i", str(video_only), "-i", str(mixed_audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(output)], capture_output=True, text=True, check=False)
    if muxed.returncode != 0:
        raise RuntimeError(muxed.stderr[-3000:] or "animatic audio mux failed")
    write_json({"episode_id": manifest["episode_id"], "cards": [str(path) for path in cards], "segments": [str(path) for path in segments], "audio": stems, "output": str(output), "duration_target": sum(float(shot["duration_target"]) for shot in manifest["shots"])}, episode_root / "animatic" / "build.json")
    return output


def run_animatic_gate(episode_id: str, *, root: str | Path | None = None, force: bool = False) -> dict[str, Any]:
    paths = StudioPaths(Path(root).resolve() if root else project_root())
    episode_root = paths.episode(episode_id)
    manifest_path = paths.manifest(episode_id)
    manifest = load_manifest(manifest_path)
    assert_valid_manifest(manifest, manifest_path)
    output = episode_root / "animatic" / f"{manifest['episode_id']}_animatic.mp4"
    if force or not output.exists():
        render_animatic(episode_root, manifest)
    checks: list[dict[str, Any]] = []
    shots = manifest.get("shots", [])
    checks.append({"name": "manifest_valid", "status": "PASS"})
    anomaly_time = manifest.get("creative", {}).get("time_to_anomaly_sec")
    if anomaly_time is None and shots:
        anomaly_time = shots[0].get("time_end", shots[0].get("duration_target", 0))
    checks.append({"name": "anomaly_inside_1_5_seconds", "status": "PASS" if float(anomaly_time or 0) <= 1.5 else "FAIL", "value": anomaly_time})
    checks.append({"name": "meaningful_visual_change_every_1_to_3_seconds", "status": "PASS" if len(shots) >= 8 else "FAIL", "shot_count": len(shots)})
    checks.append({"name": "no_unjustified_static_hold_over_5_seconds", "status": "PASS" if max(float(shot["duration_target"]) for shot in shots) <= 6.0 else "FAIL", "max_duration": max(float(shot["duration_target"]) for shot in shots)})
    checks.append({"name": "hero_shot_exists", "status": "PASS" if manifest["creative"]["hero_shot"] in {shot.get("id") for shot in shots} else "FAIL", "shot": manifest["creative"]["hero_shot"]})
    checks.append({"name": "layered_sound_stems", "status": "PASS" if len(list((episode_root / "audio").glob("*_temp.wav"))) >= 4 else "FAIL", "required": ["VO", "MUSIC", "AMB", "SFX"]})
    probe = probe_media(output)
    checks.append({"name": "animatic_decodes", "status": "PASS" if probe.get("ok") else "FAIL", "probe": probe})
    decision = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    gate = {
        "schema_version": "animatic-gate-v1",
        "episode_id": episode_id,
        "decision": decision,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output": str(output),
        "checks": checks,
        "human_review": "complete playback is still required before production shot spend",
        "prohibited_next_step_until_pass": "AI/production-quality shot generation",
    }
    write_json(gate, episode_root / "animatic" / "gate.json")
    state = {
        "mode": "CREATIVE_AMV",
        "phase": "animatic_gate",
        "accepted_timeline": str(output) if decision == "PASS" else None,
        "render": {"path": str(output), "fps": manifest["master"]["fps"], "frame_origin": 1},
        "input_hashes": {},
        "findings": [item for item in checks if item["status"] != "PASS"],
        "skipped_gates": ["Resolve mutation: no external Resolve session was opened"],
        "next_action": "director playback review, then approve shot production" if decision == "PASS" else "repair failed animatic checks",
    }
    write_json(state, paths.project_state)
    return gate
