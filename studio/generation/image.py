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

IMAGE_BACKEND = "codex_image_gen"
MODEL_FAMILY = "gpt-image"
# One candidate is the normal production pass. A variation is an explicit
# recovery action, not an automatic batch cost.
ROLE_BUDGETS = {"HERO": 1, "STORY": 1, "CONNECTOR": 1}
SHOT_ID_RE = re.compile(r"^S\d{3}$")


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


def compile_image_prompt(
    shot_contract: Mapping[str, Any],
    *,
    aspect_ratio: str = "9:16",
    references: Mapping[str, Any] | list[Any] | None = None,
) -> str:
    """Compile a structured GPT-Image prompt from the visual SSOT."""

    required = ("subject", "environment", "composition", "lighting", "palette", "forbidden")
    missing = [key for key in required if not shot_contract.get(key)]
    if missing:
        raise ValueError(f"shot_contract missing {missing}")
    lines = [
        "Create a cinematic vertical keyframe for a knowledge-entertainment short.",
        f"Subject identity: {shot_contract['subject']}",
        f"Environment: {shot_contract['environment']}",
        f"Composition and visual hierarchy: {shot_contract['composition']}",
        f"Camera/lens feel: {shot_contract.get('camera_height', 'eye-level')}; {shot_contract.get('lens_feel', 'natural perspective')}",
        f"Lighting/material/depth: {shot_contract['lighting']}",
        f"Palette and atmosphere: {shot_contract['palette']}; {shot_contract.get('atmosphere', 'layered atmospheric depth')}",
        f"Continuity anchors: {shot_contract.get('continuity', {})}",
        f"Frame intent: first frame {shot_contract.get('first_frame')}; end-state reference {shot_contract.get('end_frame')}",
        f"Aspect ratio: {aspect_ratio}.",
        f"Negative constraints: {shot_contract['forbidden']}",
        "Do not render exact labels, numbers, arrows, or scientific annotations; those belong in Fusion.",
    ]
    if references:
        lines.append(f"Use these reference roles without copying their artifacts: {references}")
    return "\n".join(lines)


def prepare_image_job(
    shot: Mapping[str, Any],
    *,
    aspect_ratio: str = "9:16",
    references: Mapping[str, Any] | list[Any] | None = None,
) -> dict[str, Any]:
    contract = shot.get("shot_contract")
    if not isinstance(contract, Mapping):
        raise ValueError("shot_contract is required")
    plan = shot.get("image_candidate_plan") if isinstance(shot.get("image_candidate_plan"), Mapping) else {}
    count = int(plan["candidates"]) if plan.get("candidates") is not None else ROLE_BUDGETS.get(str(shot.get("role")), 1)
    if count < 1:
        raise ValueError("image candidate count must be positive")
    return {
        "schema_version": "hajimi-image-job-v1",
        "backend": IMAGE_BACKEND,
        "model_family": MODEL_FAMILY,
        "shot_id": shot.get("id"),
        "role": shot.get("role"),
        "candidate_count": count,
        "candidate_round_policy": "round_1_then_director_inspection",
        "prompt": compile_image_prompt(contract, aspect_ratio=aspect_ratio, references=references),
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
        "references": job.get("references", []),
        "created_at": _utc_now(),
        "shot_contract_hash": hashlib.sha256(json.dumps(job.get("shot_contract", {}), sort_keys=True).encode()).hexdigest(),
        "status": status,
        "output_asset": str(destination.relative_to(root)),
        "sha256": _sha256(destination),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination
