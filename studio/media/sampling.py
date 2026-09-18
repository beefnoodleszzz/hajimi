"""Shot-aware low-volume frame sampling."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .probe import executable


@dataclass(frozen=True)
class FrameSample:
    scene_index: int
    position: float
    timestamp: float
    path: Path


def sample_positions(duration: float, short_threshold: float = 1.2) -> list[float]:
    return [0.25, 0.75] if duration < short_threshold else [0.10, 0.50, 0.90]


def scene_samples(scenes: list[dict], short_threshold: float = 1.2) -> list[tuple[int, float, float]]:
    samples: list[tuple[int, float, float]] = []
    for index, scene in enumerate(scenes):
        start = float(scene.get("start", 0.0))
        end = max(start, float(scene.get("end", start)))
        duration = end - start
        for position in sample_positions(duration, short_threshold):
            timestamp = start + duration * position
            samples.append((index, position, timestamp))
    return samples


def extract_frame(source: str | Path, timestamp: float, destination: str | Path, width: int = 540) -> Path:
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Preserve still-image sampling without requiring ffmpeg to seek an image.
    if source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        from PIL import Image

        with Image.open(source) as image:
            thumbnail = image.convert("RGB")
            thumbnail.thumbnail((width, width * 16 // 9))
            thumbnail.save(destination, quality=90)
        return destination
    ffmpeg_bin = executable("HAJIMI_FFMPEG", "ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found; cannot extract frame")
    completed = subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-nostdin",
            "-ss",
            f"{max(0.0, timestamp):.3f}",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:-2:flags=lanczos",
            "-q:v",
            "3",
            str(destination),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-2000:] or "ffmpeg frame extraction failed")
    return destination


def extract_scene_samples(
    source: str | Path,
    scenes: list[dict],
    destination_dir: str | Path,
    width: int = 540,
    short_threshold: float = 1.2,
    max_samples: int | None = None,
) -> list[FrameSample]:
    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    samples: list[FrameSample] = []
    plan = scene_samples(scenes, short_threshold=short_threshold)
    if max_samples is not None and max_samples > 0 and len(plan) > max_samples:
        indexes = [round(index * (len(plan) - 1) / (max_samples - 1)) for index in range(max_samples)] if max_samples > 1 else [len(plan) // 2]
        plan = [plan[index] for index in indexes]
    for scene_index, position, timestamp in plan:
        path = destination_dir / f"scene_{scene_index + 1:03d}_{int(position * 100):02d}.jpg"
        extract_frame(source, timestamp, path, width=width)
        samples.append(FrameSample(scene_index, position, timestamp, path))
    return samples
