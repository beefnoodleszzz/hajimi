"""Episode manifest loading, validation, and canonical identifiers."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .config import dump_yaml, load_yaml

EPISODE_RE = re.compile(r"^[A-Z0-9]+_[a-z0-9][a-z0-9-]*$")
SHOT_RE = re.compile(r"^S\d{3}$")
SHOT_STATUSES = {
    "planned",
    "storyboard",
    "animatic",
    "qc_pending",
    "approved",
    "blocked",
    "rejected",
}
EPISODE_STATUSES = {
    "research",
    "creative_brief",
    "script_locked",
    "storyboard",
    "animatic",
    "production",
    "qc_pending",
    "master_qc",
    "uploaded_private",
    "checks_pending",
    "complete",
    "blocked",
}
METHODS = {
    "ai_image",
    "h3_i2v",
    "h3_fl2v",
    "h3_ref2v",
    "fusion",
    "footage",
    "hybrid_ai",
    # Pre-production cards are not production methods, but remain valid while
    # an episode is still in the animatic gate.
    "animatic_card",
}
AI_IMAGE_METHODS = {"ai_image"}
AI_VIDEO_METHODS = {"h3_i2v", "h3_fl2v", "h3_ref2v"}
AI_METHODS = AI_IMAGE_METHODS | AI_VIDEO_METHODS | {"hybrid_ai"}
REMOTE_SHOT_STATES = {"NOT_READY", "REMOTE_READY", "SUBMITTED", "COMPLETE", "FAILED", "CANDIDATES_IMPORTED", "SELECTED"}
SUPPORTED_SHORT_ASPECT_RATIO = "9:16"
PRODUCTION_PHASES = {"production", "qc_pending", "master_qc", "uploaded_private", "checks_pending", "complete"}


def load_manifest(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    manifest = load_yaml(path)
    manifest.setdefault("_path", str(path.resolve()))
    return manifest


def validate_manifest(manifest: dict[str, Any], path: str | Path | None = None) -> list[str]:
    errors: list[str] = []
    episode_id = manifest.get("episode_id")
    if not isinstance(episode_id, str) or not EPISODE_RE.fullmatch(episode_id):
        errors.append("episode_id must match e.g. EP001_cloud-weight")
    if path and Path(path).parent.name != episode_id:
        errors.append("manifest parent directory must equal episode_id")
    status = manifest.get("status")
    if status not in EPISODE_STATUSES:
        errors.append(f"status must be one of {sorted(EPISODE_STATUSES)}")

    for key in ("status", "channel", "format", "language", "aspect_ratio", "master", "creative", "script", "audio", "shots", "publish"):
        if key not in manifest:
            errors.append(f"missing top-level field: {key}")
    if manifest.get("format") != "youtube_short":
        errors.append("format must be youtube_short")
    if manifest.get("aspect_ratio") != SUPPORTED_SHORT_ASPECT_RATIO:
        errors.append(f"aspect_ratio must be {SUPPORTED_SHORT_ASPECT_RATIO!r}")

    master = manifest.get("master")
    if isinstance(master, dict):
        for key in ("width", "height", "fps", "sample_rate"):
            value = master.get(key)
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f"master.{key} must be positive")
        if master.get("path") is not None and not isinstance(master.get("path"), str):
            errors.append("master.path must be a string when provided")
        if master.get("source") is not None and master.get("source") not in {"ffmpeg", "resolve"}:
            errors.append("master.source must be ffmpeg or resolve when provided")
    else:
        errors.append("master must be a mapping")

    creative = manifest.get("creative")
    if isinstance(creative, dict):
        if not creative.get("promise"):
            errors.append("creative.promise is required")
        if not creative.get("hero_shot"):
            errors.append("creative.hero_shot is required")
        duration = creative.get("target_duration_sec")
        if not isinstance(duration, (int, float)) or duration <= 0:
            errors.append("creative.target_duration_sec must be positive")

    script = manifest.get("script")
    if isinstance(script, dict):
        if not script.get("path"):
            errors.append("script.path is required")
    audio = manifest.get("audio")
    if isinstance(audio, dict):
        for key in ("narrator", "target_lufs", "true_peak_max_db"):
            if key not in audio:
                errors.append(f"audio.{key} is required")

    shots = manifest.get("shots")
    if not isinstance(shots, list) or not shots:
        errors.append("shots must be a non-empty list")
    else:
        seen: set[str] = set()
        timed_shots: list[tuple[float, float, str]] = []
        has_timing = False
        hero = creative.get("hero_shot") if isinstance(creative, dict) else None
        for index, shot in enumerate(shots):
            prefix = f"shots[{index}]"
            if not isinstance(shot, dict):
                errors.append(f"{prefix} must be a mapping")
                continue
            shot_id = shot.get("id")
            if not isinstance(shot_id, str) or not SHOT_RE.fullmatch(shot_id):
                errors.append(f"{prefix}.id must match S001")
            elif shot_id in seen:
                errors.append(f"duplicate shot id: {shot_id}")
            else:
                seen.add(shot_id)
            if not isinstance(shot.get("role"), str) or not shot["role"]:
                errors.append(f"{prefix}.role is required")
            method = shot.get("method")
            if method not in METHODS:
                errors.append(f"{prefix}.method must be one of {sorted(METHODS)}")
            status = shot.get("status")
            if status not in SHOT_STATUSES:
                errors.append(f"{prefix}.status must be one of {sorted(SHOT_STATUSES)}")
            remote_status = shot.get("remote_status")
            if remote_status is not None and remote_status not in REMOTE_SHOT_STATES:
                errors.append(f"{prefix}.remote_status must be one of {sorted(REMOTE_SHOT_STATES)}")
            remote_job = shot.get("remote_job")
            if remote_job is not None and (
                not isinstance(remote_job, str)
                or not remote_job.startswith("remote_jobs/")
                or ".." in Path(remote_job).parts
            ):
                errors.append(f"{prefix}.remote_job must be a safe episode-relative remote_jobs path")
            duration_target = shot.get("duration_target")
            if duration_target is not None and (not isinstance(duration_target, (int, float)) or duration_target <= 0):
                errors.append(f"{prefix}.duration_target must be positive")
            if "time_start" in shot or "time_end" in shot:
                has_timing = True
                start = shot.get("time_start")
                end = shot.get("time_end")
                if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                    errors.append(f"{prefix}.time_start and time_end must both be numeric")
                elif end <= start:
                    errors.append(f"{prefix}.time_end must be greater than time_start")
                else:
                    timed_shots.append((float(start), float(end), str(shot_id)))
        if has_timing and len(timed_shots) != len(shots):
            errors.append("timed shot manifests must provide time_start and time_end for every shot")
        ordered = sorted(timed_shots)
        for previous, current in zip(ordered, ordered[1:]):
            if current[0] < previous[1] - 1e-6:
                errors.append(f"shot timing overlaps: {previous[2]} and {current[2]}")
        if hero and hero not in seen:
            errors.append("creative.hero_shot must reference a listed shot")

    publish = manifest.get("publish")
    if isinstance(publish, dict):
        if publish.get("visibility") not in {"private", "public", "scheduled"}:
            errors.append("publish.visibility must be private, public, or scheduled")
        if "ai_disclosure" in publish and not isinstance(publish.get("ai_disclosure"), bool):
            errors.append("publish.ai_disclosure must be boolean")
    errors.extend(validate_phase_contract(manifest))
    return errors


def validate_phase_contract(manifest: dict[str, Any]) -> list[str]:
    """Reject storyboard-only media when an episode enters production phases."""

    errors: list[str] = []
    if manifest.get("status") not in PRODUCTION_PHASES:
        return errors
    for index, shot in enumerate(manifest.get("shots", [])):
        if not isinstance(shot, dict) or shot.get("method") != "animatic_card":
            continue
        active = shot.get("active_media")
        output = shot.get("output") if isinstance(shot.get("output"), dict) else {}
        has_production_output = any(
            isinstance(value, str) and ("production" in value or "render" in value or "master" in value)
            for value in output.values()
        )
        if shot.get("status") == "approved" or active or has_production_output:
            errors.append(f"shots[{index}] animatic_card cannot be an active production shot")
    return errors


def assert_valid_manifest(manifest: dict[str, Any], path: str | Path | None = None) -> None:
    errors = validate_manifest(manifest, path)
    if errors:
        location = f" in {path}" if path else ""
        raise ValueError("Invalid episode manifest" + location + ":\n- " + "\n- ".join(errors))


def manifest_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_input_hash(manifest: dict[str, Any]) -> str:
    """Hash creative/production inputs while ignoring mutable derived status.

    Approval evidence is stored next to the asset it approves.  Excluding
    status-like fields prevents recording an approval from invalidating itself
    merely because the canonical manifest records that approval's phase.
    """

    ignored_keys = {"_path", "status", "approval", "qc_evidence", "director_review"}

    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in sorted(value.items()) if key not in ignored_keys}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    encoded = json.dumps(normalize(manifest), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def new_manifest(episode_id: str) -> dict[str, Any]:
    return {
        "episode_id": episode_id,
        "status": "research",
        "channel": "The World You Never Knew",
        "format": "youtube_short",
        "language": "en-US",
        "aspect_ratio": "9:16",
        "master": {"width": 1080, "height": 1920, "fps": 30, "sample_rate": 48000},
        "creative": {
            "promise": "",
            "emotion": [],
            "hero_shot": "S001",
            "target_duration_sec": 38,
        },
        "script": {"version": 1, "path": "script/script_v01.md", "locked": False},
        "audio": {"narrator": None, "target_lufs": -14, "true_peak_max_db": -1.0},
        "shots": [],
        "publish": {"title": None, "description": None, "ai_disclosure": True, "visibility": "private"},
    }


def write_manifest(manifest: dict[str, Any], path: str | Path) -> None:
    # ``load_manifest`` carries the resolved source path for callers that need
    # it, but that is runtime metadata, not part of the episode's single
    # source of truth.  Never serialize private/internal keys back into
    # episode.yaml.
    serializable = {key: value for key, value in manifest.items() if not str(key).startswith("_")}
    dump_yaml(serializable, path)


def validate_shot_manifest(
    shot: dict[str, Any],
    path: str | Path | None = None,
    *,
    expected_episode_id: str | None = None,
    expected_shot_id: str | None = None,
) -> list[str]:
    """Validate the per-shot contract used by AI generation, Fusion, and Resolve."""

    errors: list[str] = []
    if not isinstance(shot, dict):
        return ["shot manifest must be a mapping"]
    shot_id = shot.get("id")
    if not isinstance(shot_id, str) or not SHOT_RE.fullmatch(shot_id):
        errors.append("id must match S001")
    if expected_shot_id is not None and shot_id != expected_shot_id:
        errors.append(f"id must match parent shot {expected_shot_id}")
    episode = shot.get("episode")
    if episode is not None and not isinstance(episode, str):
        errors.append("episode must be a string when provided")
    if expected_episode_id is not None and episode not in {None, expected_episode_id}:
        errors.append(f"episode must match parent episode {expected_episode_id}")
    if not isinstance(shot.get("version"), int) or shot.get("version") < 1:
        errors.append("version must be a positive integer")
    if not isinstance(shot.get("role"), str) or not shot.get("role"):
        errors.append("role is required")
    if shot.get("method") not in METHODS:
        errors.append(f"method must be one of {sorted(METHODS)}")
    if not isinstance(shot.get("intent"), str) or not shot.get("intent"):
        errors.append("intent is required")
    renderer = shot.get("renderer")
    if renderer is not None:
        errors.append("renderer is not supported; use method-specific generation contracts")
    camera = shot.get("camera")
    if not isinstance(camera, dict):
        errors.append("camera must be a mapping")
    frames = shot.get("frames")
    if frames is not None:
        if not isinstance(frames, dict):
            errors.append("frames must be a mapping")
        else:
            start, end = frames.get("start"), frames.get("end")
            if not isinstance(start, int) or not isinstance(end, int) or end < start:
                errors.append("frames.start/end must be integers with end >= start")
    output = shot.get("output")
    if not isinstance(output, dict) or not output:
        errors.append("output must be a non-empty mapping")
    elif not any(isinstance(value, str) and value.strip() for value in output.values()):
        errors.append("output must contain at least one path")
    output = output if isinstance(output, dict) else {}
    method = shot.get("method")
    if method != "animatic_card":
        contract = shot.get("shot_contract")
        if not isinstance(contract, dict):
            errors.append("shot_contract must be a mapping")
        else:
            required_contract = {
                "shot_id", "role", "narrative_purpose", "visual_goal", "subject",
                "environment", "composition", "first_frame", "end_frame",
                "subject_motion", "environmental_motion", "camera_motion", "lighting",
                "palette", "continuity", "forbidden",
            }
            missing = sorted(required_contract - set(contract))
            if missing:
                errors.append(f"shot_contract missing {missing}")
            if contract.get("shot_id") != shot_id:
                errors.append("shot_contract.shot_id must match id")
            if contract.get("role") != shot.get("role"):
                errors.append("shot_contract.role must match role")
        reference_pack = shot.get("reference_pack")
        if not isinstance(reference_pack, (dict, list)):
            errors.append("reference_pack must be a mapping or list")
    if method in AI_IMAGE_METHODS or method == "hybrid_ai":
        plan = shot.get("image_candidate_plan")
        if not isinstance(plan, dict):
            errors.append("image_candidate_plan is required for image-producing shots")
        elif not isinstance(plan.get("candidates"), int) or plan["candidates"] < 1:
            errors.append("image_candidate_plan.candidates must be positive")
    if method in AI_VIDEO_METHODS or method == "hybrid_ai":
        motion = shot.get("motion_plan")
        if not isinstance(motion, dict):
            errors.append("motion_plan is required for video-producing shots")
        elif method == "h3_i2v" and not (motion.get("source_keyframe") or output.get("selected_keyframe")):
            errors.append("h3_i2v requires a source keyframe")
        elif method == "h3_fl2v":
            keyframes = motion.get("keyframes")
            if not isinstance(keyframes, list) or len(keyframes) < 2:
                errors.append("h3_fl2v requires at least two motion_plan.keyframes")
            elif any(not isinstance(frame, dict) or not isinstance(frame.get("image"), str) for frame in keyframes):
                errors.append("h3_fl2v keyframes require local image paths")
        elif method == "h3_ref2v":
            references = shot.get("h3_references")
            if not isinstance(references, list) or not references:
                errors.append("h3_ref2v requires h3_references")
        for key in ("video_dir", "download_target"):
            if not isinstance(output.get(key), str) or not output[key].strip():
                errors.append(f"output.{key} is required for video-producing shots")
        if not isinstance(shot.get("video_candidate_plan"), dict):
            errors.append("video_candidate_plan is required for video-producing shots")
    return errors


def load_shot_manifest(
    path: str | Path,
    *,
    expected_episode_id: str | None = None,
    expected_shot_id: str | None = None,
) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    shot = load_yaml(path)
    errors = validate_shot_manifest(
        shot,
        path,
        expected_episode_id=expected_episode_id,
        expected_shot_id=expected_shot_id,
    )
    if errors:
        raise ValueError("Invalid shot manifest" + f" in {path}" + ":\n- " + "\n- ".join(errors))
    return shot
