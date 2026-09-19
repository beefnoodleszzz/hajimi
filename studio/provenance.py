"""Validation for traceable shot-production provenance sidecars."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import load_yaml
from .manifest import load_shot_manifest, validate_shot_manifest
from .media.hashing import sha256_file


def _resolve_evidence_path(root: Path, episode_root: Path, shot_root: Path, value: str | Path) -> Path:
    """Resolve sidecar paths using the three documented path conventions."""

    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve(strict=False)
    candidates = [
        shot_root / path,
        episode_root / path,
        root / path,
    ]
    text = str(path)
    if text.startswith("episodes/"):
        candidates.insert(0, root / path)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    # Return the most local convention for a useful missing-path diagnostic.
    return (shot_root / path).resolve(strict=False)


def validate_shot_provenance(
    root: str | Path,
    episode_id: str,
    shot: dict[str, Any],
) -> dict[str, Any]:
    """Validate the sidecar named by a shot's output contract.

    The validator checks evidence and hashes only. It does not approve a
    candidate or replace director review.
    """

    root = Path(root).resolve()
    shot_id = str(shot.get("id", ""))
    episode_root = root / "episodes" / episode_id
    shot_root = episode_root / "shots" / shot_id
    provenance_value = shot.get("output", {}).get("provenance") if isinstance(shot.get("output"), dict) else None
    errors: list[str] = []
    if not isinstance(provenance_value, str) or not provenance_value:
        return {"valid": False, "errors": ["output.provenance is required"], "shot_id": shot_id}
    provenance_path = _resolve_evidence_path(root, episode_root, shot_root, provenance_value)
    if not provenance_path.is_file():
        return {"valid": False, "errors": [f"missing provenance: {provenance_path}"], "shot_id": shot_id}
    try:
        value = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"valid": False, "errors": [f"unreadable provenance: {type(exc).__name__}"], "shot_id": shot_id}
    if not isinstance(value, dict):
        return {"valid": False, "errors": ["provenance must be a mapping"], "shot_id": shot_id}

    for field in ("schema_version", "candidate_id", "media_type", "output_asset", "output_sha256", "qc", "license"):
        if field not in value:
            errors.append(field)
    if value.get("episode_id") not in {None, episode_id}:
        errors.append("episode_id")
    if value.get("shot_id") not in {None, shot_id}:
        errors.append("shot_id")
    output_asset = value.get("output_asset")
    output_path = _resolve_evidence_path(root, episode_root, shot_root, output_asset) if isinstance(output_asset, str) else None
    if output_path is None or not output_path.is_file():
        errors.append("output_asset_missing")
    elif not isinstance(value.get("output_sha256"), str) or sha256_file(output_path) != value.get("output_sha256"):
        errors.append("output_sha256")

    source_asset = value.get("source_asset")
    if isinstance(source_asset, str):
        source_path = _resolve_evidence_path(root, episode_root, shot_root, source_asset)
        if not source_path.is_file():
            errors.append("source_asset_missing")
        elif value.get("source_sha256") and sha256_file(source_path) != value.get("source_sha256"):
            errors.append("source_sha256")

    if shot.get("method") in {"ai_image", "ai_i2v", "ai_video", "ai_multiframe", "ai_extend", "ai_repair", "hybrid_ai"}:
        generation_record = value
        continuity_source = value.get("continuity_source")
        if isinstance(continuity_source, str):
            source_record_path = _resolve_evidence_path(root, episode_root, shot_root, continuity_source)
            try:
                source_record = json.loads(source_record_path.read_text(encoding="utf-8"))
                if isinstance(source_record, dict):
                    generation_record = {**source_record, **value}
            except (OSError, json.JSONDecodeError):
                errors.append("continuity_source")
        backend = generation_record.get("backend")
        if shot.get("method") == "ai_image" or generation_record.get("media_type") == "image":
            if backend != "codex_image_gen":
                errors.append("backend must be codex_image_gen")
            if not generation_record.get("model_family"):
                errors.append("model_family")
        else:
            if backend != "google_flow_browser":
                errors.append("backend must be google_flow_browser")
            if not generation_record.get("generation_mode"):
                errors.append("generation_mode")
            downloaded_file = generation_record.get("downloaded_file")
            if not isinstance(downloaded_file, str) or not downloaded_file:
                errors.append("downloaded_file")
            else:
                downloaded_path = _resolve_evidence_path(root, episode_root, shot_root, downloaded_file)
                if not downloaded_path.is_file():
                    errors.append("downloaded_file_missing")
                elif generation_record.get("output_asset") not in {downloaded_file, str(downloaded_path)}:
                    errors.append("output_asset_must_match_downloaded_file")
        if "prompt" not in generation_record and "prompt_summary" not in generation_record:
            errors.append("prompt")
        if "references" not in generation_record:
            errors.append("references")
    qc = value.get("qc")
    if not isinstance(qc, dict):
        errors.append("qc")
    elif qc.get("fast_qc") not in {None, "PASS", "REVIEW", "pending"}:
        errors.append("qc.fast_qc")
    if not isinstance(value.get("license"), dict):
        errors.append("license")
    if "references" in value and not isinstance(value.get("references"), list):
        errors.append("references")
    return {
        "valid": not errors,
        "errors": errors,
        "shot_id": shot_id,
        "path": str(provenance_path),
        "candidate_id": value.get("candidate_id"),
        "output_asset": str(output_path) if output_path else None,
    }


def validate_episode_provenance(root: str | Path, episode_id: str) -> dict[str, Any]:
    root = Path(root).resolve()
    manifest_path = root / "episodes" / episode_id / "episode.yaml"
    manifest = load_yaml(manifest_path)
    results: list[dict[str, Any]] = []
    for manifest_shot in manifest.get("shots", []):
        shot_id = str(manifest_shot.get("id"))
        shot_path = root / "episodes" / episode_id / "shots" / shot_id / "shot.yaml"
        if shot_path.exists():
            try:
                shot = load_shot_manifest(
                    shot_path,
                    expected_episode_id=episode_id,
                    expected_shot_id=shot_id,
                )
            except (OSError, ValueError) as exc:
                results.append(
                    {
                        "valid": False,
                        "errors": [f"shot_manifest: {type(exc).__name__}: {exc}"],
                        "shot_id": shot_id,
                        "path": str(shot_path),
                    }
                )
                continue
        else:
            shot = manifest_shot
            contract_errors = validate_shot_manifest(
                shot,
                expected_episode_id=episode_id,
                expected_shot_id=shot_id,
            )
            if contract_errors:
                results.append(
                    {
                        "valid": False,
                        "errors": [f"shot_manifest: {error}" for error in contract_errors],
                        "shot_id": shot_id,
                    }
                )
                continue
        results.append(validate_shot_provenance(root, episode_id, shot))
    return {
        "episode_id": episode_id,
        "decision": "PASS" if results and all(item["valid"] for item in results) else "FAIL",
        "shots": results,
    }
