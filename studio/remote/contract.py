"""Versioned H3 job contract and deterministic local job packaging."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from ..config import dump_yaml, load_yaml, write_json
from ..manifest import EPISODE_RE, assert_valid_manifest, load_manifest

H3_JOB_SCHEMA_VERSION = "hajimi-h3-remote-v1"
H3_RESULT_SCHEMA_VERSION = H3_JOB_SCHEMA_VERSION
H3_BACKEND = "comfyui_minimax_h3"
H3_METHODS = {"h3_i2v", "h3_fl2v", "h3_ref2v", "hybrid_ai"}
H3_MODES = {"i2va", "fl2va", "ref2va"}
JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,119}$")
SHOT_ID_RE = re.compile(r"^S\d{3}$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_contract_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or not value.startswith("assets/"):
        raise ValueError(f"{label} must stay inside the job assets directory")
    return value


def validate_h3_job(job: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if job.get("schema_version") != H3_JOB_SCHEMA_VERSION:
        errors.append("schema_version must be hajimi-h3-remote-v1")
    for field in ("job_id", "episode_id", "shot_id"):
        if not isinstance(job.get(field), str) or not job[field].strip():
            errors.append(f"{field} is required")
    if isinstance(job.get("job_id"), str) and not JOB_ID_RE.fullmatch(job["job_id"]):
        errors.append("job_id contains unsafe characters")
    if isinstance(job.get("shot_id"), str) and not SHOT_ID_RE.fullmatch(job["shot_id"]):
        errors.append("shot_id must match S001")
    if job.get("mode") not in H3_MODES:
        errors.append(f"mode must be one of {sorted(H3_MODES)}")
    count = job.get("candidate_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1 or count > 8:
        errors.append("candidate_count must be an integer from 1 to 8")
    duration = job.get("duration_sec")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0 or duration > 30:
        errors.append("duration_sec must be greater than 0 and at most 30")
    if job.get("aspect_ratio") not in {"9:16", "16:9", "1:1"}:
        errors.append("aspect_ratio must be 9:16, 16:9, or 1:1")
    if not isinstance(job.get("prompt"), str) or not job["prompt"].strip():
        errors.append("prompt is required")
    inputs = job.get("inputs")
    if not isinstance(inputs, Mapping):
        errors.append("inputs must be a mapping")
        inputs = {}
    for field in ("reference_images", "reference_videos", "reference_audio"):
        if not isinstance(inputs.get(field, []), list):
            errors.append(f"inputs.{field} must be a list")
    for field in ("first_frame", "last_frame"):
        value = inputs.get(field)
        if value is not None:
            try:
                _safe_contract_path(value, f"inputs.{field}")
            except ValueError as exc:
                errors.append(str(exc))
    for field in ("reference_images", "reference_videos", "reference_audio"):
        for index, value in enumerate(inputs.get(field, []) if isinstance(inputs.get(field, []), list) else []):
            try:
                _safe_contract_path(value, f"inputs.{field}[{index}]")
            except ValueError as exc:
                errors.append(str(exc))
    expected_assets = {inputs[field] for field in ("first_frame", "last_frame") if isinstance(inputs.get(field), str)}
    for field in ("reference_images", "reference_videos", "reference_audio"):
        values = inputs.get(field, [])
        if isinstance(values, list):
            expected_assets.update(value for value in values if isinstance(value, str))
    input_hashes = job.get("input_sha256")
    if not isinstance(input_hashes, Mapping):
        errors.append("input_sha256 must be a mapping")
    else:
        for path in input_hashes:
            try:
                _safe_contract_path(path, "input_sha256 path")
            except ValueError as exc:
                errors.append(str(exc))
        if set(input_hashes) != expected_assets:
            errors.append("input_sha256 keys must exactly match declared input assets")
        for path, digest in input_hashes.items():
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                errors.append(f"input_sha256[{path!r}] must be a lowercase SHA-256 digest")
    if job.get("mode") == "i2va" and not inputs.get("first_frame"):
        errors.append("i2va requires inputs.first_frame")
    if job.get("mode") == "fl2va" and not (inputs.get("first_frame") and inputs.get("last_frame")):
        errors.append("fl2va requires inputs.first_frame and inputs.last_frame")
    if job.get("mode") == "ref2va" and not any(inputs.get(field) for field in ("reference_images", "reference_videos", "reference_audio")):
        errors.append("ref2va requires at least one reference asset")
    audio = job.get("audio")
    if not isinstance(audio, Mapping) or audio.get("generate_native_audio") is not True:
        errors.append("audio.generate_native_audio must be true")
    elif not isinstance(audio.get("intent"), str) or not audio["intent"].strip():
        errors.append("audio.intent is required")
    output = job.get("output")
    if not isinstance(output, Mapping) or output.get("video") is not True or output.get("native_audio") is not True:
        errors.append("output must request video and native_audio")
    for field in ("preserve", "avoid"):
        if not isinstance(job.get(field), list) or any(not isinstance(item, str) for item in job[field]):
            errors.append(f"{field} must be a list of strings")
    return errors


def assert_valid_h3_job(job: Mapping[str, Any]) -> None:
    errors = validate_h3_job(job)
    if errors:
        raise ValueError("Invalid H3 job:\n- " + "\n- ".join(errors))


def _episode_relative_file(episode_root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    candidate = (episode_root / value).resolve()
    if not candidate.is_relative_to(episode_root.resolve()):
        raise ValueError(f"{label} must resolve inside the episode directory")
    if not candidate.is_file():
        raise FileNotFoundError(f"{label} does not exist: {value}")
    if candidate.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError(f"{label} must be an image: {value}")
    return candidate


def _as_text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;\n]", value) if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if isinstance(part, (str, int, float)) and str(part).strip()]
    return []


def _shot_prompt(shot: Mapping[str, Any]) -> str:
    contract = shot.get("shot_contract") if isinstance(shot.get("shot_contract"), Mapping) else {}
    motion = shot.get("motion_plan") if isinstance(shot.get("motion_plan"), Mapping) else {}
    sections: list[str] = []
    for label, value in (
        ("Visual goal", contract.get("visual_goal")),
        ("Subject and environment", "; ".join(str(contract.get(key)) for key in ("subject", "environment") if contract.get(key))),
        ("Composition", contract.get("composition")),
        ("Subject motion", motion.get("subject_motion") or contract.get("subject_motion")),
        ("Environmental motion", motion.get("environmental_motion") or contract.get("environmental_motion")),
        ("Camera motion", motion.get("camera_motion") or contract.get("camera_motion")),
        ("Start state", motion.get("start_state")),
        ("Middle state", motion.get("middle_state")),
        ("End state", motion.get("end_state")),
        ("Lighting and palette", "; ".join(str(contract.get(key)) for key in ("lighting", "palette") if contract.get(key))),
    ):
        if isinstance(value, str) and value.strip():
            sections.append(f"{label}: {value.strip()}")
    if not sections:
        raise ValueError(f"{shot.get('id', 'shot')} has no visual or motion prompt content")
    return "\n".join(sections)


def _asset_spec(episode_root: Path, shot: Mapping[str, Any], mode: str) -> tuple[list[tuple[str, Path]], dict[str, Any]]:
    motion = shot.get("motion_plan") if isinstance(shot.get("motion_plan"), Mapping) else {}
    output = shot.get("output") if isinstance(shot.get("output"), Mapping) else {}
    files: list[tuple[str, Path]] = []
    inputs: dict[str, Any] = {"first_frame": None, "last_frame": None, "reference_images": [], "reference_videos": [], "reference_audio": []}
    keyframes = motion.get("keyframes") if isinstance(motion.get("keyframes"), list) else []
    if mode == "fl2va":
        frame_values: list[tuple[str, Any]] = []
        if len(keyframes) >= 2:
            frame_values = [("first_frame", keyframes[0].get("image")), ("last_frame", keyframes[-1].get("image"))]
            for index, frame in enumerate(keyframes[1:-1], start=1):
                source = _episode_relative_file(episode_root, frame.get("image"), f"keyframes[{index}].image")
                destination = f"assets/reference_{index:02d}{source.suffix.lower()}"
                files.append((destination, source))
                inputs["reference_images"].append(destination)
        else:
            frame_values = [
                ("first_frame", motion.get("first_frame") or output.get("selected_keyframe")),
                ("last_frame", motion.get("last_frame") or shot.get("shot_contract", {}).get("end_keyframe")),
            ]
        for field, value in frame_values:
            source = _episode_relative_file(episode_root, value, f"inputs.{field}")
            destination = f"assets/{field}{source.suffix.lower()}"
            files.append((destination, source))
            inputs[field] = destination
    elif mode == "i2va":
        value = motion.get("source_keyframe") or output.get("selected_keyframe")
        source = _episode_relative_file(episode_root, value, "inputs.first_frame")
        destination = f"assets/first_frame{source.suffix.lower()}"
        files.append((destination, source))
        inputs["first_frame"] = destination
    else:
        references = shot.get("h3_references", [])
        if not isinstance(references, list) or not references:
            raise ValueError(f"{shot.get('id')} ref2va requires shot.h3_references")
        for index, value in enumerate(references, start=1):
            source = _episode_relative_file(episode_root, value, f"h3_references[{index - 1}]")
            destination = f"assets/reference_{index:02d}{source.suffix.lower()}"
            files.append((destination, source))
            inputs["reference_images"].append(destination)
    return files, inputs


def _select_mode(method: str, shot: Mapping[str, Any]) -> str:
    explicit = shot.get("h3_mode")
    if explicit in H3_MODES:
        return str(explicit)
    if method == "h3_i2v":
        return "i2va"
    if method == "h3_fl2v":
        return "fl2va"
    if method == "h3_ref2v":
        return "ref2va"
    motion = shot.get("motion_plan") if isinstance(shot.get("motion_plan"), Mapping) else {}
    frames = motion.get("keyframes") if isinstance(motion.get("keyframes"), list) else []
    return "fl2va" if len(frames) >= 2 else "i2va"


def _job_spec(episode_root: Path, episode_id: str, manifest_shot: Mapping[str, Any], shot: Mapping[str, Any], revision: int) -> tuple[dict[str, Any], list[tuple[str, Path]]]:
    shot_id = str(manifest_shot.get("id", ""))
    if not SHOT_ID_RE.fullmatch(shot_id) or shot.get("id") != shot_id:
        raise ValueError(f"shot contract id does not match manifest for {shot_id or 'unknown shot'}")
    method = str(manifest_shot.get("method", shot.get("method", "")))
    if method not in H3_METHODS:
        raise ValueError(f"{shot_id} method {method!r} does not route to H3")
    mode = _select_mode(method, shot)
    files, inputs = _asset_spec(episode_root, shot, mode)
    plan = shot.get("video_candidate_plan") if isinstance(shot.get("video_candidate_plan"), Mapping) else {}
    candidate_count = plan.get("candidates", 1)
    if not isinstance(candidate_count, int) or isinstance(candidate_count, bool):
        raise ValueError(f"{shot_id} video_candidate_plan.candidates must be an integer")
    duration = manifest_shot.get("duration_target")
    if not isinstance(duration, (int, float)):
        motion = shot.get("motion_plan") if isinstance(shot.get("motion_plan"), Mapping) else {}
        duration = motion.get("duration_target")
    if not isinstance(duration, (int, float)) or duration <= 0:
        raise ValueError(f"{shot_id} duration_target is required for H3")
    contract = shot.get("shot_contract") if isinstance(shot.get("shot_contract"), Mapping) else {}
    motion = shot.get("motion_plan") if isinstance(shot.get("motion_plan"), Mapping) else {}
    continuity = contract.get("continuity") if isinstance(contract.get("continuity"), Mapping) else {}
    preserve = _as_text_list(motion.get("preserve"))
    preserve.extend(_as_text_list(continuity.get("identity")))
    preserve.extend(_as_text_list(continuity.get("screen_direction")))
    avoid = _as_text_list(motion.get("avoid")) + _as_text_list(contract.get("forbidden"))
    environment = contract.get("environment")
    environment_motion = motion.get("environmental_motion") or contract.get("environmental_motion")
    audio_intent = "; ".join(value for value in (
        f"Natural ambience for {environment}" if isinstance(environment, str) and environment else None,
        f"Physical environmental sound: {environment_motion}" if isinstance(environment_motion, str) and environment_motion else None,
        "No dialogue and no music",
    ) if value)
    job_id = f"{episode_id}_{shot_id}_r{revision:02d}"
    job: dict[str, Any] = {
        "schema_version": H3_JOB_SCHEMA_VERSION,
        "job_id": job_id,
        "episode_id": episode_id,
        "shot_id": shot_id,
        "mode": mode,
        "candidate_count": candidate_count,
        "duration_sec": float(duration),
        "aspect_ratio": "9:16",
        "prompt": _shot_prompt(shot),
        "inputs": inputs,
        "audio": {"generate_native_audio": True, "intent": audio_intent},
        "preserve": preserve,
        "avoid": avoid,
        "output": {"video": True, "native_audio": True},
        "input_sha256": {destination: sha256_file(source) for destination, source in files},
    }
    assert_valid_h3_job(job)
    return job, files


def _read_shot_contract(episode_root: Path, shot_id: str) -> dict[str, Any]:
    path = episode_root / "shots" / shot_id / "shot.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Shot Contract is missing: {path}")
    shot = load_yaml(path)
    if shot.get("id") != shot_id:
        raise ValueError(f"Shot Contract id mismatch in {path}")
    return shot


def _same_job(directory: Path, job: Mapping[str, Any]) -> bool:
    path = directory / "job.json"
    if not path.is_file():
        return False
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return previous == job and all((directory / relative).is_file() for relative in job.get("input_sha256", {}))


def _write_job_package(episode_root: Path, job: dict[str, Any], files: list[tuple[str, Path]]) -> Path:
    jobs_root = episode_root / "remote_jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)
    base_id = f"{job['episode_id']}_{job['shot_id']}_r"
    revision = int(job["job_id"].rsplit("_r", 1)[1])
    while True:
        destination = jobs_root / job["job_id"]
        if destination.exists():
            if _same_job(destination, job):
                return destination
            revision += 1
            job["job_id"] = f"{base_id}{revision:02d}"
            continue
        break
    assert_valid_h3_job(job)
    with tempfile.TemporaryDirectory(prefix=".h3-job-", dir=jobs_root) as temporary:
        temporary_path = Path(temporary)
        for relative, source in files:
            target = temporary_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if sha256_file(target) != job["input_sha256"][relative]:
                raise IOError(f"H3 asset changed while packaging: {source}")
        write_json(job, temporary_path / "job.json")
        temporary_path.rename(destination)
    return destination


def prepare_h3_jobs(
    root: str | Path,
    episode_id: str,
    shot_ids: list[str] | None = None,
) -> list[Path]:
    """Package every eligible H3 shot and mark its canonical manifest REMOTE_READY."""

    root = Path(root).resolve()
    if not isinstance(episode_id, str) or not EPISODE_RE.fullmatch(episode_id):
        raise ValueError("episode_id is invalid")
    episode_root = root / "episodes" / episode_id
    if not episode_root.resolve().is_relative_to(root):
        raise ValueError("episode path escapes the project root")
    manifest_path = episode_root / "episode.yaml"
    manifest = load_manifest(manifest_path)
    assert_valid_manifest(manifest, manifest_path)
    gate_path = episode_root / "animatic" / "gate.json"
    if not gate_path.is_file():
        raise RuntimeError("Animatic gate is missing; H3 production cannot start")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if gate.get("production_gate") != "PASS":
        raise RuntimeError("Animatic production_gate is not PASS; director approval is required before H3 production")
    wanted = set(shot_ids or [])
    manifest_shots = manifest.get("shots", [])
    selected = [shot for shot in manifest_shots if (not wanted or shot.get("id") in wanted) and shot.get("method") in H3_METHODS]
    known_ids = {shot.get("id") for shot in manifest_shots}
    if wanted and not wanted.issubset(known_ids):
        raise ValueError("Unknown shot id(s): " + ", ".join(sorted(wanted - known_ids)))
    if wanted and len(selected) != len(wanted):
        local_only = sorted(wanted - {shot.get("id") for shot in selected})
        raise ValueError("Selected shot(s) do not use an H3 video method: " + ", ".join(local_only))
    if not selected:
        raise ValueError(f"Episode has no H3 shots: {episode_id}")

    prepared: list[tuple[dict[str, Any], list[tuple[str, Path]], dict[str, Any], Path | None]] = []
    for manifest_shot in selected:
        if manifest_shot.get("method") not in H3_METHODS:
            raise ValueError(f"{manifest_shot.get('id')} method is not an H3 production method")
        shot_id = str(manifest_shot.get("id", ""))
        shot = _read_shot_contract(episode_root, shot_id)
        job, files = _job_spec(episode_root, episode_id, manifest_shot, shot, revision=1)
        existing_package: Path | None = None
        existing_job_path = manifest_shot.get("remote_job")
        existing_state = manifest_shot.get("remote_status")
        if isinstance(existing_job_path, str):
            resolved = (episode_root / existing_job_path).resolve()
            if not resolved.is_relative_to(episode_root) or not resolved.is_file():
                raise ValueError(f"{shot_id} existing remote_job path is unsafe or missing")
            old_job = json.loads(resolved.read_text(encoding="utf-8"))
            old_identity = {key: value for key, value in old_job.items() if key != "job_id"}
            new_identity = {key: value for key, value in job.items() if key != "job_id"}
            protected_states = {"SUBMITTED", "COMPLETE", "FAILED", "CANDIDATES_IMPORTED", "SELECTED"}
            if existing_state in protected_states:
                if old_identity != new_identity:
                    raise RuntimeError(
                        f"{shot_id} already has a {existing_state} H3 job with different inputs; create a new shot version before rerendering"
                    )
                job = old_job
                existing_package = resolved.parent
        prepared.append((job, files, manifest_shot, existing_package))

    directories: list[Path] = []
    for job, files, _, existing_package in prepared:
        directories.append(existing_package or _write_job_package(episode_root, job, files))
    jobs_by_shot = {job["shot_id"]: job for job, _, _, _ in prepared}
    for item in manifest["shots"]:
        job = jobs_by_shot.get(item.get("id"))
        if job is None:
            continue
        if item.get("remote_status") not in {"SUBMITTED", "COMPLETE", "FAILED", "CANDIDATES_IMPORTED", "SELECTED"}:
            item["remote_status"] = "REMOTE_READY"
        item["remote_job"] = str((Path("remote_jobs") / job["job_id"] / "job.json").as_posix())
    dump_yaml({key: value for key, value in manifest.items() if key != "_path"}, manifest_path)
    return directories
