"""Codex image_gen artifact boundary.

This module never calls an image API. The Codex agent owns the actual
``image_gen`` invocation; Hajimi owns the job contract, local artifact path,
hash, and provenance sidecar.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..skills import shared_skill_identity

IMAGE_BACKEND = "codex_image_gen"
MODEL_FAMILY = "gpt-image"
# One candidate is the normal production pass. A variation is an explicit
# recovery action, not an automatic batch cost.
ROLE_BUDGETS = {"HERO": 1, "STORY": 1, "CONNECTOR": 1}
SHOT_ID_RE = re.compile(r"^S\d{3}$")
IMAGE_STYLE_SKILL = "gpt-image-2-style-library"


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
    destination_dir = (root / "shots" / shot_id / "images").resolve()
    if not destination_dir.is_relative_to(root):
        raise ValueError("artifact destination must remain inside the episode directory")
    return root, destination_dir


def _source_file_hashes(episode_root: Path, source_files: list[str | Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for value in source_files:
        path = Path(value)
        if not path.is_absolute():
            path = episode_root / path
        path = path.resolve()
        if not path.is_file() or not path.is_relative_to(episode_root.resolve()):
            raise ValueError(f"image prompt reference must exist inside the episode: {value}")
        hashes[path.relative_to(episode_root.resolve()).as_posix()] = _sha256(path)
    return hashes


def write_image_prompt_artifact(
    episode_root: str | Path,
    shot_id: str,
    prompt: str,
    style_decision: Mapping[str, Any],
    source_files: list[str | Path],
) -> dict[str, Any]:
    """Record an agent-authored final prompt without creative rewriting."""

    root, _ = _safe_shot_directory(episode_root, shot_id)
    shot_dir = root / "shots" / shot_id
    contract_path = shot_dir / "shot.yaml"
    if not contract_path.is_file():
        raise FileNotFoundError(f"Shot Contract is missing: {contract_path}")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("agent-authored image prompt must be non-empty")
    if not isinstance(style_decision, Mapping) or not style_decision:
        raise ValueError("style_decision from gpt-image-2-style-library is required")
    skill_source = shared_skill_identity(IMAGE_STYLE_SKILL)
    artifact = {
        "schema_version": "hajimi-image-prompt-artifact-v1",
        "shot_id": shot_id,
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "style_decision": dict(style_decision),
        "source_shot_contract_sha256": _sha256(contract_path),
        "source_reference_hashes": _source_file_hashes(root, source_files),
        "source_skill": dict(skill_source),
        "created_at": _utc_now(),
    }
    artifact_dir = shot_dir / "images"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = artifact_dir / "prompt.md"
    metadata_path = artifact_dir / "prompt.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    metadata_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**artifact, "path": prompt_path.relative_to(root).as_posix(), "metadata_path": metadata_path.relative_to(root).as_posix()}


def load_image_prompt_artifact(episode_root: str | Path, shot_id: str) -> dict[str, Any]:
    root, artifact_dir = _safe_shot_directory(episode_root, shot_id)
    prompt_path = artifact_dir / "prompt.md"
    metadata_path = artifact_dir / "prompt.json"
    if not prompt_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"image prompt artifact is required: {prompt_path} and {metadata_path}")
    try:
        artifact = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"image prompt metadata is invalid JSON: {metadata_path}") from exc
    prompt = prompt_path.read_text(encoding="utf-8")
    contract_path = root / "shots" / shot_id / "shot.yaml"
    if artifact.get("schema_version") != "hajimi-image-prompt-artifact-v1":
        raise ValueError("Unsupported image prompt artifact schema_version")
    if artifact.get("shot_id") != shot_id or artifact.get("prompt") != prompt:
        raise ValueError("image prompt artifact text or shot ID does not match prompt.md")
    if artifact.get("prompt_sha256") != hashlib.sha256(prompt.encode("utf-8")).hexdigest():
        raise ValueError("image prompt artifact prompt hash is stale")
    if not contract_path.is_file() or artifact.get("source_shot_contract_sha256") != _sha256(contract_path):
        raise ValueError("image prompt artifact Shot Contract hash is stale")
    source_skill = artifact.get("source_skill")
    if not isinstance(source_skill, Mapping) or dict(source_skill) != shared_skill_identity(IMAGE_STYLE_SKILL):
        raise ValueError("image prompt artifact is missing verified GPT Image skill provenance")
    hashes = artifact.get("source_reference_hashes", {})
    if not isinstance(hashes, Mapping):
        raise ValueError("image prompt artifact source_reference_hashes must be a mapping")
    for relative, digest in hashes.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or _sha256(path) != digest:
            raise ValueError(f"image prompt artifact reference hash is stale: {relative}")
    return {**artifact, "path": prompt_path.relative_to(root).as_posix(), "metadata_path": metadata_path.relative_to(root).as_posix()}


def prepare_image_job(
    shot: Mapping[str, Any],
    *,
    prompt_artifact: Mapping[str, Any] | None = None,
    references: Mapping[str, Any] | list[Any] | None = None,
) -> dict[str, Any]:
    contract = shot.get("shot_contract")
    if not isinstance(contract, Mapping):
        raise ValueError("shot_contract is required")
    plan = shot.get("image_candidate_plan") if isinstance(shot.get("image_candidate_plan"), Mapping) else {}
    count = int(plan["candidates"]) if plan.get("candidates") is not None else ROLE_BUDGETS.get(str(shot.get("role")), 1)
    if count < 1:
        raise ValueError("image candidate count must be positive")
    if not isinstance(prompt_artifact, Mapping):
        raise ValueError("final agent-authored image prompt artifact is required")
    prompt = prompt_artifact.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("final agent-authored image prompt artifact is required")
    if prompt_artifact.get("schema_version") != "hajimi-image-prompt-artifact-v1":
        raise ValueError("unsupported image prompt artifact schema")
    if not prompt_artifact.get("path") or not prompt_artifact.get("metadata_path") or not prompt_artifact.get("source_skill"):
        raise ValueError("image prompt artifact must include its files and upstream skill provenance")
    return {
        "schema_version": "hajimi-image-job-v1",
        "backend": IMAGE_BACKEND,
        "model_family": MODEL_FAMILY,
        "shot_id": shot.get("id"),
        "role": shot.get("role"),
        "candidate_count": count,
        "candidate_round_policy": "round_1_then_director_inspection",
        "prompt": prompt,
        "prompt_artifact": {
            "path": prompt_artifact.get("path"),
            "metadata_path": prompt_artifact.get("metadata_path"),
            "prompt_sha256": prompt_artifact.get("prompt_sha256"),
            "source_shot_contract_sha256": prompt_artifact.get("source_shot_contract_sha256"),
            "source_reference_hashes": prompt_artifact.get("source_reference_hashes", {}),
            "source_skill": prompt_artifact.get("source_skill"),
        },
        "references": references or shot.get("reference_pack", {}),
        "shot_contract": dict(contract),
        "artifact_dir": str(plan.get("artifact_dir") or f"shots/{shot.get('id')}/images"),
        "created_at": _utc_now(),
    }


def register_image_candidate(
    episode_root: str | Path,
    shot_id: str,
    source_path: str | Path,
    job: Mapping[str, Any],
    *,
    candidate_number: int,
    status: str = "candidate",
) -> Path:
    """Copy a Codex-produced image into the shot artifact directory and record it."""

    source = Path(source_path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Codex image result not found: {source}")
    if candidate_number < 1:
        raise ValueError("candidate_number must be positive")
    prompt_artifact = job.get("prompt_artifact")
    if not isinstance(prompt_artifact, Mapping) or not prompt_artifact.get("path"):
        raise ValueError("candidate provenance requires the validated image prompt artifact")
    root, destination_dir = _safe_shot_directory(episode_root, shot_id)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"candidate_{candidate_number:02d}{source.suffix.lower()}"
    metadata_path = destination.with_suffix(".json")
    if destination.exists() or metadata_path.exists():
        raise FileExistsError(f"image candidate already exists: {destination}")
    shutil.copy2(source, destination)
    metadata = {
        "schema_version": "hajimi-image-candidate-v1",
        "backend": IMAGE_BACKEND,
        "model_family": job.get("model_family", MODEL_FAMILY),
        "shot_id": shot_id,
        "candidate_id": f"{shot_id}_image_{candidate_number:02d}",
        "prompt": job.get("prompt"),
        "prompt_artifact": dict(prompt_artifact),
        "references": job.get("references", []),
        "created_at": _utc_now(),
        "shot_contract_hash": hashlib.sha256(json.dumps(job.get("shot_contract", {}), sort_keys=True).encode()).hexdigest(),
        "status": status,
        "output_asset": str(destination.relative_to(root)),
        "sha256": _sha256(destination),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination
