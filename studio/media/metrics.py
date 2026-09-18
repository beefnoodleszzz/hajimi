"""Cheap image metrics for Tier 2 QC; VLM is deliberately not involved."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageStat


def _gray(path: str | Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("L").copy()


def _pixels(image: Image.Image) -> list[int]:
    flattened = getattr(image, "get_flattened_data", None)
    if flattened is not None:
        return list(flattened())
    return list(image.getdata())


def dhash(path: str | Path, size: int = 8) -> str:
    image = _gray(path).resize((size + 1, size))
    pixels = _pixels(image)
    bits = [pixels[row * (size + 1) + col] > pixels[row * (size + 1) + col + 1] for row in range(size) for col in range(size)]
    return "".join("1" if bit else "0" for bit in bits)


def hamming(left: str, right: str) -> int:
    return sum(a != b for a, b in zip(left, right)) + abs(len(left) - len(right))


def frame_metrics(path: str | Path) -> dict[str, Any]:
    gray = _gray(path)
    stat = ImageStat.Stat(gray)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_values = _pixels(edges)
    edge_density = sum(value > 48 for value in edge_values) / max(1, len(edge_values))
    sharpness = float(ImageStat.Stat(edges).var[0])
    return {
        "path": str(Path(path)),
        "dhash": dhash(path),
        "luma_mean": round(float(stat.mean[0]), 3),
        "luma_std": round(math.sqrt(float(stat.var[0])), 3),
        "edge_density": round(edge_density, 6),
        "laplacian_variance_approx": round(sharpness, 3),
        "optical_flow": {"status": "not_run", "reason": "only run for suspicious/high-motion shots"},
    }


def _optical_flow(frame_paths: list[str | Path]) -> dict[str, Any]:
    """Compute a small, deterministic flow summary for sampled proxy frames.

    This deliberately runs on the already sampled proxy frames, never on a
    full-resolution/full-frame stream.  OpenCV is optional; an unavailable
    dependency is explicit evidence rather than a fabricated zero motion.
    """

    if len(frame_paths) < 2:
        return {"status": "not_run", "reason": "fewer than two sampled frames"}
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return {"status": "unavailable", "reason": "opencv-python is optional"}

    magnitudes: list[float] = []
    horizontal: list[float] = []
    vertical: list[float] = []
    pairs = 0
    for left_path, right_path in zip(frame_paths, frame_paths[1:]):
        left = cv2.imread(str(left_path), cv2.IMREAD_GRAYSCALE)
        right = cv2.imread(str(right_path), cv2.IMREAD_GRAYSCALE)
        if left is None or right is None:
            continue
        # Keep the metric cheap and resolution-independent.
        width = min(320, left.shape[1], right.shape[1])
        if width <= 0:
            continue
        left = cv2.resize(left, (width, max(1, int(left.shape[0] * width / left.shape[1]))))
        right = cv2.resize(right, (width, max(1, int(right.shape[0] * width / right.shape[1]))))
        height = min(left.shape[0], right.shape[0])
        if height <= 1:
            continue
        left = left[:height]
        right = right[:height]
        flow = cv2.calcOpticalFlowFarneback(left, right, None, 0.5, 2, 15, 2, 5, 1.2, 0)
        magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        magnitudes.append(float(np.mean(magnitude)))
        horizontal.append(float(np.mean(flow[..., 0])))
        vertical.append(float(np.mean(flow[..., 1])))
        pairs += 1
    if not pairs:
        return {"status": "unavailable", "reason": "sampled frames could not be decoded"}
    return {
        "status": "PASS",
        "pairs": pairs,
        "mean_magnitude": round(sum(magnitudes) / pairs, 6),
        "mean_horizontal": round(sum(horizontal) / pairs, 6),
        "mean_vertical": round(sum(vertical) / pairs, 6),
        "purpose": "sampled-proxy motion-direction smoke metric",
    }


def aggregate_metrics(frame_paths: list[str | Path], *, compute_optical_flow: bool = False) -> dict[str, Any]:
    rows = [frame_metrics(path) for path in frame_paths]
    duplicate_pairs: list[dict[str, Any]] = []
    for index, left in enumerate(rows):
        for right in rows[index + 1 :]:
            distance = hamming(left["dhash"], right["dhash"])
            if distance <= 4:
                duplicate_pairs.append({"left": left["path"], "right": right["path"], "distance": distance})
    return {
        "frames": rows,
        "near_duplicate_pairs": duplicate_pairs,
        "frame_count": len(rows),
        "optical_flow": _optical_flow(frame_paths) if compute_optical_flow else {"status": "not_run", "reason": "not requested for this media"},
    }
