"""Artifact and structure validation for locally authored MiniMax H3 prompts.

Creative prompt text is authored by the local H3 director using the vendored
official MiniMax skill. This module only records, validates, and loads it.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..config import write_json
from ..skills import canonical_skill_root, shared_skill_identity

H3_MODES = {"i2va", "fl2va", "ref2va"}

BASE_FIELDS = (
    "integrated_multimodal_description",
    "overall_soundscape",
    "non_diegetic_music",
)
REF_FIELDS = (
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
)
_SKILL_NAME = "h3-prompt-writing"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def official_skill_identity() -> dict[str, Any]:
    identity = shared_skill_identity(_SKILL_NAME)
    skill_dir = canonical_skill_root() / _SKILL_NAME
    required_files = (
        skill_dir / "SKILL.md",
        skill_dir / "references" / "base-en.txt",
        skill_dir / "references" / "ref-en.txt",
    )
    missing = [path.relative_to(skill_dir).as_posix() for path in required_files if not path.is_file()]
    if missing:
        raise FileNotFoundError("Shared official H3 prompt skill is incomplete: " + ", ".join(missing))
    return {
        "source": identity["repo"],
        "commit": identity["commit"],
        "skill_path": "skills/h3-prompt-writing",
        "content_sha256": identity["content_sha256"],
        "references_sha256": {
            path.relative_to(skill_dir).as_posix(): sha256_file(path)
            for path in required_files
        },
    }


def _sections(prompt: str, fields: Sequence[str]) -> tuple[list[str], dict[str, str]]:
    matches = [
        (match.start(), match.end(), field)
        for field in fields
        for match in re.finditer(rf"(?m)^{re.escape(field)}:\s*", prompt)
    ]
    matches.sort()
    names = [field for _, _, field in matches]
    values: dict[str, str] = {}
    for index, (start, end, field) in enumerate(matches):
        next_start = matches[index + 1][0] if index + 1 < len(matches) else len(prompt)
        values[field] = prompt[end:next_start].strip()
    return names, values


def validate_h3_prompt(
    mode: str,
    prompt: str,
    audio_intent: str,
    generation_duration_sec: float,
    *,
    allow_non_diegetic_music: bool = False,
    reference_image_count: int = 0,
) -> list[str]:
    errors: list[str] = []
    if mode not in H3_MODES:
        return [f"mode must be one of {sorted(H3_MODES)}"]
    if not isinstance(prompt, str) or not prompt.strip():
        return ["prompt must be a non-empty string"]
    if not isinstance(audio_intent, str) or not audio_intent.strip():
        return ["audio_intent must be a non-empty string"]
    fields = REF_FIELDS if mode == "ref2va" else BASE_FIELDS
    names, sections = _sections(prompt, fields)
    if names != list(fields):
        errors.append(f"{mode} prompt sections must appear once and in official order: {', '.join(fields)}")
    for field in fields:
        if not sections.get(field, "").strip():
            errors.append(f"{field} must have content")

    if mode == "i2va":
        expected = "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."
        if prompt.splitlines()[0] != expected:
            errors.append("i2va prompt must begin with the official first-frame alignment instruction")
        elif len(prompt.splitlines()) < 3 or prompt.splitlines()[1] != "":
            errors.append("i2va prompt must place one blank line after the official alignment instruction")
    elif mode == "fl2va":
        alignment = re.match(
            r"^How the reference pictures align with the target video — Picture 1 \(from Shot 1\) aligns with the 0\.00-second mark of the target video; Picture 2 \(from Shot 1\) aligns with the (\d+\.\d{2})-second mark of the target video\.$",
            prompt.splitlines()[0],
        )
        expected_duration = f"{generation_duration_sec:.2f}"
        if not alignment or alignment.group(1) != expected_duration:
            errors.append("fl2va prompt must use the official first/last image alignment instruction and generation duration")
        elif len(prompt.splitlines()) < 3 or prompt.splitlines()[1] != "":
            errors.append("fl2va prompt must place one blank line after the official alignment instruction")
    elif mode == "ref2va":
        definitions = sections.get("subject_definitions", "")
        for index in range(1, reference_image_count + 1):
            label = f"<Picture {index}>"
            if label not in definitions:
                errors.append(f"ref2va subject_definitions must identify {label}")

    integrated = sections.get("integrated_multimodal_description", sections.get("detailed_description", ""))
    integrated_lower = integrated.casefold()
    if "no narration" not in integrated_lower:
        errors.append("integrated description must explicitly say no narration")
    if "no dialogue" not in integrated_lower:
        errors.append("integrated description must explicitly say no dialogue")
    soundscape = sections.get("overall_soundscape", "")
    if soundscape.casefold() in {"n/a", "na"}:
        errors.append("overall_soundscape must describe the shot's native environment audio")
    if soundscape != audio_intent.strip():
        errors.append("overall_soundscape must exactly match the locally authored audio_intent")
    music = sections.get("non_diegetic_music", "")
    if not allow_non_diegetic_music and music != "N/A":
        errors.append("non_diegetic_music must be N/A unless the Shot Contract explicitly requests music")
    return errors


def _source_hashes(episode_root: Path, source_files: Sequence[str | Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in source_files:
        path = Path(value)
        if not path.is_absolute():
            path = episode_root / path
        path = path.resolve()
        if not path.is_file() or not path.is_relative_to(episode_root.resolve()):
            raise ValueError(f"H3 prompt source image must exist inside the episode: {value}")
        result[path.relative_to(episode_root.resolve()).as_posix()] = sha256_file(path)
    return result


def write_h3_prompt_artifact(
    episode_root: str | Path,
    shot_id: str,
    mode: str,
    prompt: str,
    audio_intent: str,
    source_files: Sequence[str | Path],
    generation_duration_sec: float,
    *,
    job_revision: int = 1,
    allow_non_diegetic_music: bool = False,
) -> dict[str, Any]:
    """Persist a finished agent prompt byte-for-byte with its source evidence."""

    episode_root = Path(episode_root).resolve()
    shot_dir = episode_root / "shots" / shot_id
    contract_path = shot_dir / "shot.yaml"
    if not contract_path.is_file():
        raise FileNotFoundError(f"Shot Contract is missing: {contract_path}")
    if not isinstance(job_revision, int) or isinstance(job_revision, bool) or job_revision < 1:
        raise ValueError("job_revision must be a positive integer")
    hashes = _source_hashes(episode_root, source_files)
    errors = validate_h3_prompt(
        mode,
        prompt,
        audio_intent,
        generation_duration_sec,
        allow_non_diegetic_music=allow_non_diegetic_music,
        reference_image_count=len(hashes) if mode == "ref2va" else 0,
    )
    if errors:
        raise ValueError("Invalid official H3 prompt:\n- " + "\n- ".join(errors))
    artifact = {
        "schema_version": "hajimi-h3-prompt-artifact-v1",
        "mode": mode,
        "prompt": prompt,
        "audio_intent": audio_intent,
        "generation_duration_sec": float(generation_duration_sec),
        "job_revision": job_revision,
        "source_shot_contract_sha256": sha256_file(contract_path),
        "source_keyframe_hashes": hashes,
        "official_skill": official_skill_identity(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    artifact_dir = shot_dir / "h3"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    write_json(artifact, artifact_dir / "prompt.json")
    return artifact


def load_h3_prompt_artifact(
    episode_root: str | Path,
    shot_id: str,
    mode: str,
    source_files: Sequence[str | Path],
    generation_duration_sec: float,
    *,
    allow_non_diegetic_music: bool = False,
) -> dict[str, Any]:
    episode_root = Path(episode_root).resolve()
    artifact_dir = episode_root / "shots" / shot_id / "h3"
    prompt_path = artifact_dir / "prompt.txt"
    metadata_path = artifact_dir / "prompt.json"
    if not prompt_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"H3 prompt artifact is required: {artifact_dir}/prompt.txt and prompt.json")
    try:
        artifact = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"H3 prompt artifact metadata is invalid JSON: {metadata_path}") from exc
    prompt = prompt_path.read_text(encoding="utf-8")
    contract_path = episode_root / "shots" / shot_id / "shot.yaml"
    expected_hashes = _source_hashes(episode_root, source_files)
    if artifact.get("schema_version") != "hajimi-h3-prompt-artifact-v1":
        raise ValueError("Unsupported H3 prompt artifact schema_version")
    if artifact.get("mode") != mode:
        raise ValueError("H3 prompt artifact mode does not match the Shot Contract")
    if artifact.get("prompt") != prompt:
        raise ValueError("H3 prompt.txt and prompt.json prompt text differ")
    if artifact.get("source_shot_contract_sha256") != sha256_file(contract_path):
        raise ValueError("H3 prompt artifact source Shot Contract hash is stale")
    if artifact.get("source_keyframe_hashes") != expected_hashes:
        raise ValueError("H3 prompt artifact source keyframe hashes are stale")
    if artifact.get("official_skill") != official_skill_identity():
        raise ValueError("H3 prompt artifact official skill version does not match the local synced skill")
    if not isinstance(artifact.get("job_revision"), int) or artifact["job_revision"] < 1:
        raise ValueError("H3 prompt artifact job_revision must be a positive integer")
    artifact_duration = artifact.get("generation_duration_sec")
    if not isinstance(artifact_duration, (int, float)) or abs(float(artifact_duration) - generation_duration_sec) > 1e-6:
        raise ValueError("H3 prompt artifact generation duration is stale")
    errors = validate_h3_prompt(
        mode,
        prompt,
        artifact.get("audio_intent"),
        generation_duration_sec,
        allow_non_diegetic_music=allow_non_diegetic_music,
        reference_image_count=len(expected_hashes) if mode == "ref2va" else 0,
    )
    if errors:
        raise ValueError("Invalid official H3 prompt artifact:\n- " + "\n- ".join(errors))
    return artifact
