"""Deterministic storyboard continuity gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .config import load_yaml
from .manifest import load_manifest, validate_shot_manifest


CONTINUITY_FIELDS = (
    "receive", "action", "handoff", "screen_direction",
    "identity_state", "environment_state", "prop_state",
)


def validate_continuity_review(value: Mapping[str, Any], shot_ids: list[str]) -> list[str]:
    errors: list[str] = []
    if value.get("schema_version") != "continuity-review-v1":
        errors.append("continuity_review.schema_version must be continuity-review-v1")
    shots = value.get("shots")
    if not isinstance(shots, Mapping):
        return errors + ["continuity_review.shots must be a mapping"]
    if list(shots) != shot_ids:
        errors.append("continuity_review shot IDs and order must match episode.yaml")
    last_index = len(shot_ids) - 1
    for index, shot_id in enumerate(shot_ids):
        entry = shots.get(shot_id)
        prefix = f"continuity_review.shots.{shot_id}"
        if not isinstance(entry, Mapping):
            errors.append(f"{prefix} must be a mapping")
            continue
        missing = [field for field in CONTINUITY_FIELDS if field not in entry]
        if missing:
            errors.append(f"{prefix} missing {missing}")
            continue
        if index > 0 and entry.get("receive") in (None, "", [], {}):
            errors.append(f"{prefix}.receive is required for a non-first shot")
        if index < last_index and entry.get("handoff") in (None, "", [], {}):
            errors.append(f"{prefix}.handoff is required for a non-last shot")
        for field in ("action", "screen_direction", "identity_state", "environment_state", "prop_state"):
            if entry.get(field) in (None, "", [], {}):
                errors.append(f"{prefix}.{field} must be explicit")
    return errors


def validate_storyboard_gate(episode_root: str | Path) -> list[str]:
    episode_root = Path(episode_root)
    manifest_path = episode_root / "episode.yaml"
    if not manifest_path.is_file():
        return ["episode.yaml is required"]
    manifest = load_manifest(manifest_path)
    manifest_shots = [item for item in manifest.get("shots", []) if isinstance(item, Mapping)]
    shot_ids = [str(item.get("id")) for item in manifest_shots]
    errors: list[str] = []
    storyboard_path = episode_root / "storyboard" / "storyboard_v01.yaml"
    if not storyboard_path.is_file():
        errors.append("storyboard/storyboard_v01.yaml is required")
    else:
        try:
            storyboard = load_yaml(storyboard_path)
            storyboard_shots = storyboard.get("shots")
            if not isinstance(storyboard_shots, list):
                errors.append("storyboard.shots must be a list")
            else:
                storyboard_ids = [
                    str(item.get("id", item.get("shot_id")))
                    for item in storyboard_shots
                    if isinstance(item, Mapping)
                ]
                if storyboard_ids != shot_ids:
                    errors.append("storyboard shot IDs and order must match episode.yaml")
        except (OSError, ValueError) as exc:
            errors.append(f"storyboard_v01.yaml is invalid: {exc}")
    review_path = episode_root / "storyboard" / "continuity_review.yaml"
    if not review_path.is_file():
        errors.append("storyboard/continuity_review.yaml is required")
    else:
        try:
            errors.extend(validate_continuity_review(load_yaml(review_path), shot_ids))
        except (OSError, ValueError) as exc:
            errors.append(f"continuity_review.yaml is invalid: {exc}")
    last_index = len(shot_ids) - 1
    for index, shot_id in enumerate(shot_ids):
        path = episode_root / "shots" / shot_id / "shot.yaml"
        if not path.is_file():
            errors.append(f"shots/{shot_id}/shot.yaml is required")
            continue
        try:
            shot = load_yaml(path)
        except (OSError, ValueError) as exc:
            errors.append(f"shots/{shot_id}/shot.yaml is invalid: {exc}")
            continue
        errors.extend(f"{shot_id}: {error}" for error in validate_shot_manifest(
            shot,
            path,
            expected_episode_id=str(manifest.get("episode_id")),
            expected_shot_id=shot_id,
        ))
        contract = shot.get("shot_contract") if isinstance(shot, Mapping) and isinstance(shot.get("shot_contract"), Mapping) else {}
        if index > 0 and contract.get("continuity_receive") in (None, "", [], {}):
            errors.append(f"{shot_id}: continuity_receive is required for a non-first shot")
        if index < last_index and contract.get("continuity_handoff") in (None, "", [], {}):
            errors.append(f"{shot_id}: continuity_handoff is required for a non-last shot")
    return errors
