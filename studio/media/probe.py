"""Deterministic metadata and decode checks using ffprobe/ffmpeg."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def executable(name: str, fallback: str) -> str | None:
    return os.environ.get(name) or shutil.which(fallback)


def _run(command: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)
    return completed.returncode, completed.stdout, completed.stderr


def ffprobe_json(path: str | Path, ffprobe_bin: str | None = None) -> dict[str, Any]:
    ffprobe_bin = ffprobe_bin or executable("HAJIMI_FFPROBE", "ffprobe")
    if not ffprobe_bin:
        return {"ok": False, "error": "ffprobe not found"}
    code, stdout, stderr = _run(
        [ffprobe_bin, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]
    )
    if code != 0:
        return {"ok": False, "error": stderr.strip()[-1000:] or "ffprobe failed"}
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "ffprobe returned invalid JSON"}
    value["ok"] = True
    return value


def _has_stream(probe: dict[str, Any], codec_type: str) -> bool:
    return any(stream.get("codec_type") == codec_type for stream in probe.get("streams", []))


def decode_check(path: str | Path, probe: dict[str, Any] | None = None, ffmpeg_bin: str | None = None) -> dict[str, Any]:
    ffmpeg_bin = ffmpeg_bin or executable("HAJIMI_FFMPEG", "ffmpeg")
    if not ffmpeg_bin:
        return {"ok": False, "error": "ffmpeg not found"}
    probe = probe or ffprobe_json(path)
    args = [ffmpeg_bin, "-hide_banner", "-nostdin", "-v", "error", "-i", str(path)]
    if _has_stream(probe, "video"):
        args += ["-map", "0:v:0"]
    elif _has_stream(probe, "audio"):
        args += ["-map", "0:a:0"]
    args += ["-f", "null", "-"]
    code, stdout, stderr = _run(args)
    return {"ok": code == 0, "stderr": stderr.strip()[-2000:], "stdout": stdout.strip()[-500:]}


def filter_check(path: str | Path, probe: dict[str, Any], ffmpeg_bin: str | None = None) -> dict[str, Any]:
    """Run black/freeze/silence/loudness filters without decoding frames into Python."""
    ffmpeg_bin = ffmpeg_bin or executable("HAJIMI_FFMPEG", "ffmpeg")
    if not ffmpeg_bin:
        return {"ok": False, "error": "ffmpeg not found"}
    results: dict[str, Any] = {"ok": True, "blackdetect": "", "freezedetect": "", "audio": ""}
    # `pix_th` is a luminance threshold, not a black-pixel ratio. The previous
    # V1-style value of 0.98 would classify the dark navy brand canvas as black.
    video_filters = "blackdetect=d=0.10:pix_th=0.08,freezedetect=n=0.003:d=0.8"
    if _has_stream(probe, "video"):
        code, _, stderr = _run(
            [
                ffmpeg_bin,
                "-hide_banner",
                "-nostdin",
                "-i",
                str(path),
                "-vf",
                video_filters,
                "-an",
                "-f",
                "null",
                "-",
            ],
            timeout=180,
        )
        results["ok"] = results["ok"] and code == 0
        results["video_events"] = [line.strip() for line in stderr.splitlines() if "black_" in line or "freeze_" in line][-32:]
    if _has_stream(probe, "audio"):
        code, _, stderr = _run(
            [
                ffmpeg_bin,
                "-hide_banner",
                "-nostdin",
                "-i",
                str(path),
                "-af",
                "silencedetect=n=-50dB:d=0.2,ebur128=peak=true,astats=metadata=1:reset=1",
                "-vn",
                "-f",
                "null",
                "-",
            ],
            timeout=180,
        )
        results["ok"] = results["ok"] and code == 0
        results["audio_events"] = [line.strip() for line in stderr.splitlines() if "silence_" in line or "Integrated loudness" in line or "True peak" in line][-32:]
        integrated = re.search(r"^\s*I:\s*([-+]?\d+(?:\.\d+)?)\s+LUFS", stderr, re.MULTILINE)
        true_peak = re.search(r"^\s*Peak:\s*([-+]?\d+(?:\.\d+)?)\s+dBFS", stderr, re.MULTILINE)
        results["integrated_lufs"] = float(integrated.group(1)) if integrated else None
        results["true_peak_dbfs"] = float(true_peak.group(1)) if true_peak else None
    return results


def probe_media(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"ok": False, "error": f"missing media: {path}"}
    probe = ffprobe_json(path)
    if not probe.get("ok"):
        # Images may be inspected without ffprobe when Pillow is available.
        try:
            from PIL import Image

            with Image.open(path) as image:
                return {
                    "ok": True,
                    "image_fallback": True,
                    "format": image.format,
                    "width": image.width,
                    "height": image.height,
                    "duration": 0.0,
                    "streams": [{"codec_type": "video", "width": image.width, "height": image.height}],
                    "decode": {"ok": True, "fallback": "Pillow"},
                }
        except Exception:
            return probe
    decode = decode_check(path, probe)
    filters = filter_check(path, probe)
    format_info = probe.get("format", {})
    video = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), {})
    return {
        "ok": bool(decode.get("ok")) and bool(filters.get("ok")),
        "format": {
            "name": format_info.get("format_name"),
            "duration": float(format_info.get("duration", 0.0) or 0.0),
            "size": int(format_info.get("size", 0) or 0),
        },
        "video": {
            "width": video.get("width"),
            "height": video.get("height"),
            "fps": video.get("r_frame_rate"),
            "pix_fmt": video.get("pix_fmt"),
            "sample_aspect_ratio": video.get("sample_aspect_ratio"),
            "display_aspect_ratio": video.get("display_aspect_ratio"),
        },
        "audio": {
            "sample_rate": audio.get("sample_rate"),
            "channels": audio.get("channels"),
            "codec": audio.get("codec_name"),
        },
        "decode": decode,
        "filters": filters,
        "streams": probe.get("streams", []),
    }


def duration_seconds(probe: dict[str, Any]) -> float:
    if probe.get("image_fallback"):
        return 0.0
    return float(probe.get("format", {}).get("duration", 0.0) or 0.0)
