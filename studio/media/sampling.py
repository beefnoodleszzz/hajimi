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


def _bounded_positions(values: list[float], max_samples: int | None) -> list[float]:
    """Return an evenly distributed position list for one scene.

    The cap is deliberately applied to the positions of a single scene.  A
    caller processing ten scenes must still receive up to ``N`` samples for
    each scene, rather than ``N`` samples for the entire source.
    """

    positions = [min(1.0, max(0.0, float(value))) for value in values]
    if not max_samples or max_samples <= 0 or len(positions) <= max_samples:
        return positions
    if max_samples == 1:
        return [positions[len(positions) // 2]]
    indexes = [round(index * (len(positions) - 1) / (max_samples - 1)) for index in range(max_samples)]
    return [positions[index] for index in indexes]


def sample_positions(
    duration: float,
    short_threshold: float = 1.2,
    long_threshold: float = 8.0,
    *,
    short_positions: list[float] | None = None,
    default_positions: list[float] | None = None,
    long_positions: list[float] | None = None,
    max_samples_per_scene: int | None = None,
) -> list[float]:
    """Choose configured representative positions for one scene.

    Short, normal, and long scenes have distinct policies so configuration is
    observable in the resulting evidence.  ``max_samples_per_scene`` is
    applied here, before scenes are concatenated by :func:`scene_samples`.
    """

    short = short_positions or [0.25, 0.75]
    normal = default_positions or [0.10, 0.50, 0.90]
    long = long_positions or [0.0, 0.25, 0.50, 0.75, 1.0]
    if duration < short_threshold:
        selected = short
    elif duration >= long_threshold:
        selected = long
    else:
        selected = normal
    return _bounded_positions(selected, max_samples_per_scene)


def scene_samples(
    scenes: list[dict],
    short_threshold: float = 1.2,
    long_threshold: float = 8.0,
    *,
    short_positions: list[float] | None = None,
    default_positions: list[float] | None = None,
    long_positions: list[float] | None = None,
    max_samples_per_scene: int | None = None,
) -> list[tuple[int, float, float]]:
    samples: list[tuple[int, float, float]] = []
    for index, scene in enumerate(scenes):
        start = float(scene.get("start", 0.0))
        end = max(start, float(scene.get("end", start)))
        duration = end - start
        for position in sample_positions(
            duration,
            short_threshold,
            long_threshold,
            short_positions=short_positions,
            default_positions=default_positions,
            long_positions=long_positions,
            max_samples_per_scene=max_samples_per_scene,
        ):
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
    long_threshold: float = 8.0,
    short_positions: list[float] | None = None,
    default_positions: list[float] | None = None,
    long_positions: list[float] | None = None,
    max_samples_per_scene: int | None = None,
) -> list[FrameSample]:
    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    samples: list[FrameSample] = []
    plan = scene_samples(
        scenes,
        short_threshold=short_threshold,
        long_threshold=long_threshold,
        short_positions=short_positions,
        default_positions=default_positions,
        long_positions=long_positions,
        max_samples_per_scene=max_samples_per_scene,
    )
    for scene_index, position, timestamp in plan:
        path = destination_dir / f"scene_{scene_index + 1:03d}_{int(position * 100):02d}.jpg"
        extract_frame(source, timestamp, path, width=width)
        samples.append(FrameSample(scene_index, position, timestamp, path))
    return samples
