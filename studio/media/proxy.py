"""540p proxy generation; all first-pass QC uses this boundary."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from .probe import executable


def build_proxy(source: str | Path, destination: str | Path, height: int = 540, bitrate: str = "3M") -> Path:
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = executable("HAJIMI_FFMPEG", "ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found; cannot create proxy")
    command = [ffmpeg_bin, "-y", "-hide_banner", "-nostdin"]
    if platform.system() == "Darwin":
        command += ["-hwaccel", "videotoolbox"]
    command += [
        "-i",
        str(source),
        "-vf",
        f"scale=-2:{height}:flags=lanczos",
        "-c:v",
        "h264_videotoolbox" if platform.system() == "Darwin" else "libx264",
        "-b:v",
        bitrate,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0 and platform.system() == "Darwin":
        # VideoToolbox is preferred on macOS but never allowed to block QC.
        fallback = [item for item in command if item not in {"-hwaccel", "videotoolbox"}]
        codec_index = fallback.index("h264_videotoolbox")
        fallback[codec_index] = "libx264"
        completed = subprocess.run(fallback, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-2000:] or "ffmpeg proxy generation failed")
    return destination
