"""Google Flow browser artifact boundary.

The agent operates the real Google Flow UI through ``ego-browser``. This
module deliberately has no HTTP client, API key, or browser automation code.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

VIDEO_BACKEND = "google_flow_browser"
VIDEO_METHODS = {"ai_i2v", "ai_video", "ai_multiframe", "ai_extend", "ai_repair", "hybrid_ai"}
SHOT_ID_RE = re.compile(r"^S\d{3}$")
SEGMENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_shot_directory(episode_root: str | Path, shot_id: str) -> tuple[Path, Path]:
    if not isinstance(shot_id, str) or not SHOT_ID_RE.fullmatch(shot_id):
        raise ValueError("shot_id must match S001")
    root = Path(episode_root).expanduser().resolve()
    destination_dir = (root / "shots" / shot_id / "video").resolve()
    if not destination_dir.is_relative_to(root):
        raise ValueError("artifact destination must remain inside the episode directory")
    return root, destination_dir


def prepare_video_job(shot: Mapping[str, Any]) -> dict[str, Any]:
    method = shot.get("method")
    if method not in VIDEO_METHODS:
        raise ValueError(f"{method!r} is not a video-producing method")
    motion = shot.get("motion_plan")
    if not isinstance(motion, Mapping):
        raise ValueError("motion_plan is required")
    plan = shot.get("video_candidate_plan") if isinstance(shot.get("video_candidate_plan"), Mapping) else {}
    output = shot.get("output") if isinstance(shot.get("output"), Mapping) else {}
    source_keyframe = motion.get("source_keyframe") or output.get("selected_keyframe")
    mode = motion.get("generation_mode") or ("image_to_video" if source_keyframe else "text_to_video")
    if method == "ai_i2v" and not source_keyframe:
        raise ValueError("ai_i2v requires a source keyframe")
    if mode == "image_to_video" and not source_keyframe:
        raise ValueError("image_to_video requires a source keyframe")
    keyframes = motion.get("keyframes", [])
    candidate_count = int(plan["candidates"]) if plan.get("candidates") is not None else 2
    if candidate_count < 1:
        raise ValueError("video candidate count must be positive")
    segment_jobs = []
    if mode == "multi_keyframe_video":
        if not isinstance(keyframes, list) or len(keyframes) < 2:
            raise ValueError("multi_keyframe_video requires at least two keyframes")
        segments = motion.get("segments")
        if not isinstance(segments, list) or len(segments) != len(keyframes) - 1:
            raise ValueError("multi_keyframe_video requires one segment between each adjacent keyframe")
        keyframe_ids = [frame.get("id") for frame in keyframes if isinstance(frame, Mapping)]
        if (
            len(keyframe_ids) != len(keyframes)
            or any(not isinstance(frame.get("id"), str) or not frame.get("id") for frame in keyframes)
            or len(set(keyframe_ids)) != len(keyframes)
            or any(not isinstance(frame.get("image"), str) or not frame.get("image") for frame in keyframes)
        ):
            raise ValueError("each multi-keyframe state requires a unique id and local image path")
        for index, segment in enumerate(segments):
            if not isinstance(segment, Mapping):
                raise ValueError("each multi-keyframe segment must be a mapping")
            start_id = keyframes[index]["id"]
            end_id = keyframes[index + 1]["id"]
            if segment.get("from") != start_id or segment.get("to") != end_id:
                raise ValueError("multi-keyframe segments must connect adjacent keyframes in order")
            if not isinstance(segment.get("prompt"), str) or not segment["prompt"].strip():
                raise ValueError("each multi-keyframe segment requires a motion prompt")
            segment_jobs.append({
                "segment_id": segment.get("id", f"segment_{index + 1:02d}"),
                "source_keyframe": keyframes[index]["image"],
                "target_keyframe": keyframes[index + 1]["image"],
                "motion_prompt": segment["prompt"],
            })
    return {
        "schema_version": "hajimi-video-job-v1",
        "backend": VIDEO_BACKEND,
        "browser_tool": "ego-browser",
        "ui": "Google Flow",
        "shot_id": shot.get("id"),
        "generation_mode": mode,
        "candidate_count": candidate_count,
        "source_keyframe": source_keyframe,
        "keyframes": [dict(frame) for frame in keyframes] if isinstance(keyframes, list) else [],
        "segment_jobs": segment_jobs,
        "references": shot.get("reference_pack", {}),
        "motion_plan": dict(motion),
        "motion_prompt": motion.get("prompt") or " ".join(
            str(motion.get(key, "")) for key in ("subject_motion", "environmental_motion", "camera_motion", "preserve", "avoid")
        ).strip(),
        "download_target": output.get("download_target") or f"shots/{shot.get('id')}/video",
        "created_at": _utc_now(),
    }


def register_video_candidate(
    episode_root: str | Path,
    shot_id: str,
    downloaded_path: str | Path,
    job: Mapping[str, Any],
    *,
    candidate_number: int,
    status: str = "candidate",
    segment_id: str | None = None,
    generation_details: Mapping[str, Any] | None = None,
) -> Path:
    """Register only a video that the browser agent really downloaded locally."""

    source = Path(downloaded_path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Google Flow download not found: {source}")
    if source.suffix.lower() not in {".mp4", ".mov", ".webm", ".mkv"}:
        raise ValueError("Google Flow candidate must be a local video file")
    if candidate_number < 1:
        raise ValueError("candidate_number must be positive")
    segment = None
    if job.get("generation_mode") == "multi_keyframe_video":
        if not isinstance(segment_id, str) or not SEGMENT_ID_RE.fullmatch(segment_id):
            raise ValueError("multi-keyframe candidates require a safe segment_id")
        segment = next((
            item for item in job.get("segment_jobs", [])
            if isinstance(item, Mapping) and item.get("segment_id") == segment_id
        ), None)
        if not isinstance(segment, Mapping):
            raise ValueError(f"unknown multi-keyframe segment: {segment_id}")
    elif segment_id is not None:
        raise ValueError("segment_id is only valid for multi-keyframe candidates")
    root, destination_dir = _safe_shot_directory(episode_root, shot_id)
    destination_dir.mkdir(parents=True, exist_ok=True)
    stem = f"segment_{segment_id}_candidate_{candidate_number:02d}" if segment_id else f"candidate_{candidate_number:02d}"
    destination = destination_dir / f"{stem}{source.suffix.lower()}"
    metadata_path = destination.with_suffix(".json")
    if destination.exists() or metadata_path.exists():
        raise FileExistsError(f"video candidate already exists: {destination}")
    shutil.copy2(source, destination)
    metadata = {
        "schema_version": "hajimi-video-candidate-v1",
        "backend": VIDEO_BACKEND,
        "browser_tool": "ego-browser",
        "shot_id": shot_id,
        "candidate_id": f"{shot_id}_video_{segment_id + '_' if segment_id else ''}{candidate_number:02d}",
        "generation_mode": job.get("generation_mode"),
        "segment_id": segment_id,
        "source_image": segment.get("source_keyframe") if segment else job.get("source_keyframe"),
        "target_keyframe": segment.get("target_keyframe") if segment else None,
        "prompt": segment.get("motion_prompt") if segment else job.get("motion_prompt"),
        "references": job.get("references", []),
        "motion_plan": job.get("motion_plan", {}),
        "model": (generation_details or {}).get("model", "unknown"),
        "duration": (generation_details or {}).get("duration", "unknown"),
        "aspect_ratio": (generation_details or {}).get("aspect_ratio", "unknown"),
        "downloaded_file": str(destination.relative_to(root)),
        "sha256": _sha256(destination),
        "generated_at": _utc_now(),
        "status": status,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def approve_video_candidate(episode_root: str | Path, candidate_path: str | Path, *, reviewer: str) -> Path:
    """Approve a candidate only after its downloaded local file is present."""

    root = Path(episode_root).expanduser().resolve()
    candidate = Path(candidate_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("candidate must be inside the episode directory")
    if not candidate.is_file():
        raise FileNotFoundError(f"cannot approve missing local download: {candidate}")
    metadata_path = candidate.with_suffix(".json")
    if not metadata_path.is_file():
        raise FileNotFoundError(f"cannot approve candidate without provenance: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    downloaded_file = metadata.get("downloaded_file")
    if metadata.get("backend") != VIDEO_BACKEND or not isinstance(downloaded_file, str):
        raise ValueError("candidate is not a Google Flow browser artifact")
    recorded_path = Path(downloaded_file)
    if recorded_path.is_absolute() or ".." in recorded_path.parts:
        raise ValueError("candidate provenance contains an unsafe downloaded_file path")
    if (root / recorded_path).resolve() != candidate:
        raise ValueError("candidate provenance does not identify this local file")
    expected_hash = metadata.get("sha256")
    if not isinstance(expected_hash, str) or _sha256(candidate) != expected_hash:
        raise ValueError("candidate content does not match its recorded SHA-256")
    metadata["status"] = "approved"
    metadata["reviewer"] = reviewer
    metadata["approved_at"] = _utc_now()
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return candidate
