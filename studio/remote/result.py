"""Validation and local import of remote H3 video plus native ambience."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..config import dump_yaml, load_yaml, write_json
from ..manifest import EPISODE_RE, SHOT_RE, load_manifest
from ..media.probe import decode_check, ffprobe_json
from .contract import H3_BACKEND, H3_RESULT_SCHEMA_VERSION, JOB_ID_RE, sha256_file

_METADATA_FIELDS = (
    "candidate_id",
    "filename",
    "sha256",
    "duration",
    "width",
    "height",
    "fps",
    "has_audio",
    "audio_codec",
    "sample_rate",
    "channels",
    "workflow_id",
    "workflow_version",
    "h3_model_identity",
    "generation_parameters",
)
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _safe_filename(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) > 180 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) or Path(value).name != value:
        raise ValueError(f"{label} must be a filename without path components")
    return value


def validate_h3_result(result: Mapping[str, Any], job: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if result.get("schema_version") != H3_RESULT_SCHEMA_VERSION:
        errors.append("result schema_version must be hajimi-h3-remote-v1")
    if result.get("job_id") != job.get("job_id"):
        errors.append("result job_id does not match the submitted job")
    if result.get("status") != "COMPLETE":
        errors.append("result status must be COMPLETE")
    if result.get("backend") != H3_BACKEND:
        errors.append(f"result backend must be {H3_BACKEND}")
    candidates = result.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append("result candidates must be a non-empty list")
        return errors
    if len(candidates) != job.get("candidate_count"):
        errors.append("result candidate count does not match the job")
    seen: set[str] = set()
    seen_ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        label = f"candidates[{index}]"
        if not isinstance(candidate, Mapping):
            errors.append(f"{label} must be a mapping")
            continue
        try:
            video_file = _safe_filename(candidate.get("filename"), f"{label}.filename")
            metadata_file = _safe_filename(candidate.get("metadata_file"), f"{label}.metadata_file")
            if video_file == metadata_file or video_file in seen or metadata_file in seen:
                errors.append(f"{label} contains a duplicate result filename")
            seen.update((video_file, metadata_file))
        except ValueError as exc:
            errors.append(str(exc))
        if not isinstance(candidate.get("candidate_id"), str) or not candidate["candidate_id"].strip():
            errors.append(f"{label}.candidate_id is required")
        elif candidate["candidate_id"] in seen_ids:
            errors.append(f"{label}.candidate_id is duplicated")
        else:
            seen_ids.add(candidate["candidate_id"])
    return errors


def _result_file(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    resolved_directory = directory.resolve()
    if candidate.is_symlink() or not candidate.is_file() or not candidate.resolve().is_relative_to(resolved_directory):
        raise ValueError(f"Result file is unsafe, missing, or not a regular file: {filename}")
    return candidate


def _validate_metadata_types(metadata: Mapping[str, Any], filename: str) -> None:
    for field in ("duration", "width", "height"):
        value = metadata.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{filename}.{field} must be a positive number")
    if metadata.get("has_audio") is not True:
        raise ValueError(f"{filename}.has_audio must be true for an H3 candidate")
    if not isinstance(metadata.get("sha256"), str) or not _SHA256_RE.fullmatch(metadata["sha256"]):
        raise ValueError(f"{filename}.sha256 must be a lowercase SHA-256 digest")
    for field in ("audio_codec", "workflow_id", "workflow_version"):
        value = metadata.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{filename}.{field} must be a string or null")
    model_identity = metadata.get("h3_model_identity")
    if model_identity is not None and not isinstance(model_identity, (str, Mapping)):
        raise ValueError(f"{filename}.h3_model_identity must be a string, object, or null")
    for field in ("sample_rate", "channels"):
        value = metadata.get(field)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
            raise ValueError(f"{filename}.{field} must be a positive integer or null")
    fps = metadata.get("fps")
    if fps is not None and not isinstance(fps, (str, int, float)):
        raise ValueError(f"{filename}.fps must be a number, rational string, or null")
    parameters = metadata.get("generation_parameters")
    if parameters is not None and not isinstance(parameters, Mapping):
        raise ValueError(f"{filename}.generation_parameters must be an object or null")


def _load_result_directory(directory: Path, job: Mapping[str, Any]) -> tuple[dict[str, Any], list[tuple[dict[str, Any], dict[str, Any]]]]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("H3 result directory must be a real directory")
    result_path = _result_file(directory, "result.json")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("result.json must contain an object")
    errors = validate_h3_result(result, job)
    if errors:
        raise ValueError("Invalid H3 result:\n- " + "\n- ".join(errors))
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for index, candidate in enumerate(result["candidates"], start=1):
        video_name = _safe_filename(candidate.get("filename"), f"candidates[{index - 1}].filename")
        metadata_name = _safe_filename(candidate.get("metadata_file"), f"candidates[{index - 1}].metadata_file")
        video_path = _result_file(directory, video_name)
        metadata_path = _result_file(directory, metadata_name)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError(f"{metadata_name} must contain an object")
        missing = [field for field in _METADATA_FIELDS if field not in metadata]
        if missing:
            raise ValueError(f"{metadata_name} is missing metadata fields: {', '.join(missing)}")
        if metadata.get("filename") != video_name or metadata.get("candidate_id") != candidate.get("candidate_id"):
            raise ValueError(f"{metadata_name} does not describe {video_name}")
        _validate_metadata_types(metadata, metadata_name)
        if not isinstance(metadata.get("sha256"), str) or sha256_file(video_path) != metadata["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {video_name}")
        probe = ffprobe_json(video_path)
        if not probe.get("ok"):
            raise ValueError(f"ffprobe failed for H3 candidate {video_name}: {probe.get('error', 'unknown error')}")
        _compare_reported_metadata(metadata, probe)
        video_stream = next(item for item in probe.get("streams", []) if item.get("codec_type") == "video")
        width, height = video_stream.get("width"), video_stream.get("height")
        target_ratio = {"9:16": 9 / 16, "16:9": 16 / 9, "1:1": 1.0}.get(job.get("aspect_ratio"))
        if not isinstance(width, int) or not isinstance(height, int) or not target_ratio or abs(width / height - target_ratio) / target_ratio > 0.05:
            raise ValueError(f"Candidate {video_name} dimensions do not match the requested aspect ratio")
        pairs.append((dict(candidate), metadata))
    return result, pairs


def import_h3_result(
    root: str | Path,
    episode_id: str,
    shot_id: str,
    source_directory: str | Path,
) -> Path:
    """Validate a completed result, retain it locally, and update manifest state."""

    root = Path(root).resolve()
    if not isinstance(episode_id, str) or not EPISODE_RE.fullmatch(episode_id) or not isinstance(shot_id, str) or not SHOT_RE.fullmatch(shot_id):
        raise ValueError("episode_id or shot_id is invalid")
    episode_root = root / "episodes" / episode_id
    if not episode_root.resolve().is_relative_to(root):
        raise ValueError("episode path escapes the project root")
    manifest_path = episode_root / "episode.yaml"
    manifest = load_manifest(manifest_path)
    shot_item = next((shot for shot in manifest.get("shots", []) if shot.get("id") == shot_id), None)
    if shot_item is None:
        raise ValueError(f"Unknown shot id: {shot_id}")
    job_value = shot_item.get("remote_job")
    if not isinstance(job_value, str):
        raise RuntimeError(f"{shot_id} has no prepared H3 job")
    job_path = (episode_root / job_value).resolve()
    if not job_path.is_relative_to(episode_root) or not job_path.is_file():
        raise ValueError("Manifest remote_job path is unsafe or missing")
    job = json.loads(job_path.read_text(encoding="utf-8"))
    source = Path(source_directory).absolute()
    result, _ = _load_result_directory(source, job)
    destination = episode_root / "remote_results" / job["job_id"]
    if not destination.resolve().is_relative_to(episode_root):
        raise ValueError("H3 result destination escapes the episode directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        try:
            existing_result = json.loads((destination / "result.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing_result = None
        if existing_result != result:
            raise FileExistsError(f"A different result already exists: {destination}")
        _load_result_directory(destination, job)
    else:
        temporary = destination.with_name(f".{destination.name}.importing")
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir(parents=True)
        try:
            result_files = {"result.json"}
            for item in result["candidates"]:
                result_files.add(_safe_filename(item.get("filename"), "candidate.filename"))
                result_files.add(_safe_filename(item.get("metadata_file"), "candidate.metadata_file"))
            for filename in sorted(result_files):
                source_file = _result_file(source, filename)
                shutil.copy2(source_file, temporary / filename)
            _load_result_directory(temporary, job)
            temporary.rename(destination)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
    if shot_item.get("remote_status") != "SELECTED":
        shot_item["remote_status"] = "CANDIDATES_IMPORTED"
    dump_yaml({key: value for key, value in manifest.items() if key != "_path"}, manifest_path)
    return destination


def _compare_reported_metadata(metadata: Mapping[str, Any], probe: Mapping[str, Any]) -> None:
    video = next((item for item in probe.get("streams", []) if item.get("codec_type") == "video"), None)
    audio = next((item for item in probe.get("streams", []) if item.get("codec_type") == "audio"), None)
    if video is None or audio is None:
        raise ValueError("H3 candidate must include both video and native audio streams")
    checks = (
        ("width", video.get("width")),
        ("height", video.get("height")),
        ("audio_codec", audio.get("codec_name")),
        ("sample_rate", int(audio["sample_rate"]) if audio.get("sample_rate") else None),
        ("channels", audio.get("channels")),
    )
    for field, actual in checks:
        recorded = metadata.get(field)
        if recorded is not None and actual is not None and recorded != actual:
            raise ValueError(f"Candidate metadata mismatch for {field}: {recorded!r} != {actual!r}")
    fps = metadata.get("fps")
    if fps is not None:
        recorded_fps = _fps_value(fps)
        actual_fps = _fps_value(video.get("avg_frame_rate") or video.get("r_frame_rate"))
        if recorded_fps is not None and actual_fps is not None and abs(recorded_fps - actual_fps) > 0.02:
            raise ValueError("Candidate metadata frame rate does not match ffprobe")
    reported_duration = metadata.get("duration")
    actual_duration = float(probe.get("format", {}).get("duration", 0.0) or 0.0)
    if reported_duration is not None and abs(float(reported_duration) - actual_duration) > 0.15:
        raise ValueError("Candidate metadata duration does not match ffprobe")


def _fps_value(value: Any) -> float | None:
    try:
        if isinstance(value, str) and "/" in value:
            numerator, denominator = value.split("/", 1)
            return float(numerator) / float(denominator)
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def select_h3_candidate(
    root: str | Path,
    episode_id: str,
    shot_id: str,
    candidate_number: int,
    *,
    reviewer: str,
) -> Path:
    """Perform local deterministic stream checks and record explicit local selection."""

    if candidate_number < 1:
        raise ValueError("candidate number must be positive")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("reviewer is required for local candidate selection")
    root = Path(root).resolve()
    if not isinstance(episode_id, str) or not EPISODE_RE.fullmatch(episode_id) or not isinstance(shot_id, str) or not SHOT_RE.fullmatch(shot_id):
        raise ValueError("episode_id or shot_id is invalid")
    episode_root = root / "episodes" / episode_id
    if not episode_root.resolve().is_relative_to(root):
        raise ValueError("episode path escapes the project root")
    manifest_path = episode_root / "episode.yaml"
    manifest = load_manifest(manifest_path)
    shot_item = next((shot for shot in manifest.get("shots", []) if shot.get("id") == shot_id), None)
    if shot_item is None:
        raise ValueError(f"Unknown shot id: {shot_id}")
    job_value = shot_item.get("remote_job")
    if not isinstance(job_value, str):
        raise RuntimeError(f"{shot_id} has no prepared H3 job")
    job_path = (episode_root / job_value).resolve()
    if not job_path.is_relative_to(episode_root) or not job_path.is_file():
        raise ValueError("Manifest remote_job path is unsafe or missing")
    job = json.loads(job_path.read_text(encoding="utf-8"))
    results_directory = episode_root / "remote_results" / job["job_id"]
    _, candidate_pairs = _load_result_directory(results_directory, job)
    if candidate_number > len(candidate_pairs):
        raise ValueError(f"Candidate {candidate_number:02d} does not exist")
    remote_record, metadata = candidate_pairs[candidate_number - 1]
    source = results_directory / remote_record["filename"]
    probe = ffprobe_json(source)
    if not probe.get("ok"):
        raise RuntimeError(f"ffprobe failed for candidate: {probe.get('error', 'unknown error')}")
    _compare_reported_metadata(metadata, probe)
    requested_duration = shot_item.get("duration_target")
    actual_duration = float(probe.get("format", {}).get("duration", 0.0) or 0.0)
    if isinstance(requested_duration, (int, float)) and actual_duration + 0.05 < float(requested_duration):
        raise ValueError(f"Candidate duration is shorter than the {shot_id} timeline target")
    decode = decode_check(source, probe)
    if not decode.get("ok"):
        raise RuntimeError("H3 candidate failed deterministic decode validation")
    now = datetime.now(timezone.utc).isoformat()
    video_directory = episode_root / "shots" / shot_id / "video"
    if not video_directory.resolve().is_relative_to(episode_root):
        raise ValueError("Selected candidate destination escapes the episode directory")
    video_directory.mkdir(parents=True, exist_ok=True)
    selected = video_directory / "selected.mp4"
    digest = sha256_file(source)
    if selected.exists() and sha256_file(selected) != digest:
        raise FileExistsError(f"A different selected candidate exists; preserve/review it before replacing: {selected}")
    if not selected.exists():
        shutil.copy2(source, selected)
    selected_metadata = {
        **metadata,
        "schema_version": "hajimi-h3-candidate-v1",
        "backend": H3_BACKEND,
        "shot_id": shot_id,
        "selected_from": str(source.relative_to(episode_root)),
        "selected_file": str(selected.relative_to(episode_root)),
        "sha256": digest,
        "status": "selected",
        "reviewer": reviewer.strip(),
        "selected_at": now,
    }
    write_json(selected_metadata, selected.with_suffix(".json"))
    shot_contract = load_yaml(episode_root / "shots" / shot_id / "shot.yaml")
    motion = shot_contract.get("motion_plan", {}) if isinstance(shot_contract.get("motion_plan"), dict) else {}
    image_path = motion.get("source_keyframe") or shot_contract.get("output", {}).get("selected_keyframe")
    image_sha = None
    if isinstance(image_path, str):
        local_image = (episode_root / image_path).resolve()
        if local_image.is_relative_to(episode_root) and local_image.is_file():
            image_sha = sha256_file(local_image)
    provenance = {
        "schema_version": "hajimi-shot-provenance-v4",
        "episode_id": episode_id,
        "shot_id": shot_id,
        "candidate_id": metadata["candidate_id"],
        "media_type": "video",
        "method": shot_item.get("method"),
        "status": "selected",
        "backend": H3_BACKEND,
        "generation_mode": job["mode"],
        "source_asset": image_path,
        "source_sha256": image_sha,
        "prompt": job["prompt"],
        "references": list(job["inputs"].get("reference_images", [])),
        "downloaded_file": str(selected.relative_to(episode_root)),
        "output_asset": str(selected.relative_to(episode_root)),
        "output_sha256": digest,
        "remote_result": str((Path("remote_results") / job["job_id"] / "result.json").as_posix()),
        "candidate_metadata": metadata,
        "qc": {"ffprobe": "PASS", "decode": "PASS", "fast_qc": "pending", "director_review": "pending", "selected_by": reviewer.strip(), "selected_at": now},
        "license": {"status": "pending_master", "source": "Remote ComfyUI MiniMax H3 generation"},
        "created_at": now,
    }
    write_json(provenance, episode_root / "shots" / shot_id / "provenance.json")
    shot_item["active_media"] = str(selected.relative_to(episode_root))
    shot_item["status"] = "qc_pending"
    shot_item["remote_status"] = "SELECTED"
    dump_yaml({key: value for key, value in manifest.items() if key != "_path"}, manifest_path)
    return selected
