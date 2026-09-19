"""Post-animatic production planning contracts.

The generation director authors the plan.  This module verifies that the plan
is bound to the passed animatic, current Shot Contracts, and manifest timeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Mapping

from .config import dump_yaml, load_yaml
from .manifest import load_manifest
from .h3_constants import H3_FPS, H3_MAX_FRAMES, H3_MIN_FRAMES
from .storyboard import validate_storyboard_gate

SHOT_TIERS = {"HERO", "STORY", "CONNECTOR"}
GENERATION_METHODS = {
    "ai_image", "h3_i2v", "h3_fl2v", "h3_ref2v",
    "hybrid_ai", "fusion", "footage",
}
IMAGE_REQUIRED_METHODS = {"ai_image", "h3_i2v", "h3_fl2v", "h3_ref2v", "hybrid_ai"}
VIDEO_REQUIRED_METHODS = {"h3_i2v", "h3_fl2v", "h3_ref2v", "hybrid_ai"}
H3_METHODS = {"h3_i2v", "h3_fl2v", "h3_ref2v", "hybrid_ai"}


def _positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def validate_generation_plan(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("schema_version") != "generation-plan-v3":
        errors.append("generation_plan.schema_version must be generation-plan-v3")
    shots = value.get("shots")
    if not isinstance(shots, list) or not shots:
        errors.append("generation_plan.shots must be a non-empty list")
        return errors
    seen: set[str] = set()
    for index, shot in enumerate(shots):
        prefix = f"generation_plan.shots[{index}]"
        if not isinstance(shot, Mapping):
            errors.append(f"{prefix} must be a mapping")
            continue
        shot_id = shot.get("shot_id")
        if not isinstance(shot_id, str) or not shot_id:
            errors.append(f"{prefix}.shot_id is required")
        elif shot_id in seen:
            errors.append(f"{prefix}.shot_id is duplicated")
        else:
            seen.add(shot_id)
        if shot.get("tier") not in SHOT_TIERS:
            errors.append(f"{prefix}.tier must be one of {sorted(SHOT_TIERS)}")
        method = shot.get("method")
        if method not in GENERATION_METHODS:
            errors.append(f"{prefix}.method must be one of {sorted(GENERATION_METHODS)}")
        image_candidates = shot.get("image_candidates", 0)
        video_candidates = shot.get("video_candidates", 0)
        if type(image_candidates) is not int or image_candidates < 0:
            errors.append(f"{prefix}.image_candidates must be a non-negative integer")
        elif method in IMAGE_REQUIRED_METHODS and image_candidates < 1:
            errors.append(f"{prefix}.image_candidates must be positive for {method}")
        if type(video_candidates) is not int or not 0 <= video_candidates <= 8:
            errors.append(f"{prefix}.video_candidates must be an integer from 0 to 8")
        elif method in VIDEO_REQUIRED_METHODS and video_candidates < 1:
            errors.append(f"{prefix}.video_candidates must be positive for {method}")
        edit_duration = shot.get("edit_duration_sec")
        generation_duration = shot.get("generation_duration_sec")
        if not _positive_number(edit_duration):
            errors.append(f"{prefix}.edit_duration_sec must be positive")
        if not _positive_number(generation_duration):
            errors.append(f"{prefix}.generation_duration_sec must be positive")
        elif _positive_number(edit_duration) and float(generation_duration) < float(edit_duration):
            errors.append(f"{prefix}.generation_duration_sec must be >= edit_duration_sec")
        if method in H3_METHODS and _positive_number(generation_duration):
            frame_count = round(float(generation_duration) * H3_FPS)
            if frame_count < H3_MIN_FRAMES:
                errors.append(f"{prefix}.generation_duration_sec must use at least {H3_MIN_FRAMES} frames")
            elif frame_count > H3_MAX_FRAMES:
                errors.append(f"{prefix}.generation_duration_sec must use at most {H3_MAX_FRAMES} frames")
            if frame_count % 17 != 5 or abs(frame_count / H3_FPS - float(generation_duration)) > 1e-6:
                errors.append(f"{prefix}.generation_duration_sec must use H3 17k+5 frame alignment")
        strategy = shot.get("input_strategy")
        if method in H3_METHODS and not isinstance(strategy, Mapping):
            errors.append(f"{prefix}.input_strategy is required for H3")
        elif isinstance(strategy, Mapping):
            if method == "h3_i2v" and not strategy.get("first_frame"):
                errors.append(f"{prefix}.input_strategy.first_frame is required for h3_i2v")
            if method == "h3_fl2v" and (not strategy.get("first_frame") or not strategy.get("last_frame")):
                errors.append(f"{prefix}.input_strategy first_frame and last_frame are required for h3_fl2v")
            if method == "h3_ref2v" and (not isinstance(strategy.get("references"), list) or not strategy["references"]):
                errors.append(f"{prefix}.input_strategy.references must be a non-empty list for h3_ref2v")
            if method == "hybrid_ai" and not any(strategy.get(key) for key in ("first_frame", "last_frame", "references")):
                errors.append(f"{prefix}.input_strategy must define at least one frame or reference for hybrid_ai")
            for key in ("first_frame", "last_frame"):
                if key in strategy and (not isinstance(strategy[key], str) or not strategy[key].strip()):
                    errors.append(f"{prefix}.input_strategy.{key} must be a non-empty path")
                elif key in strategy:
                    path = PurePosixPath(strategy[key])
                    if path.is_absolute() or ".." in path.parts or "\\" in strategy[key]:
                        errors.append(f"{prefix}.input_strategy.{key} must be an episode-relative path")
            references = strategy.get("references")
            if references is not None and (
                not isinstance(references, list)
                or any(not isinstance(item, str) or not item.strip() for item in references)
            ):
                errors.append(f"{prefix}.input_strategy.references must contain non-empty paths")
            elif isinstance(references, list):
                for value in references:
                    path = PurePosixPath(value)
                    if path.is_absolute() or ".." in path.parts or "\\" in value:
                        errors.append(f"{prefix}.input_strategy.references must contain episode-relative paths")
        if not isinstance(shot.get("fusion_graphics", []), list):
            errors.append(f"{prefix}.fusion_graphics must be a list")
    return errors


def validate_production_generation_plan(episode_root: str | Path) -> list[str]:
    episode_root = Path(episode_root)
    errors: list[str] = []
    gate_path = episode_root / "animatic" / "gate.json"
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        gate = {}
    if gate.get("production_gate") != "PASS":
        errors.append("animatic production_gate must be PASS before generation planning")
    errors.extend(validate_storyboard_gate(episode_root))
    manifest_path = episode_root / "episode.yaml"
    if not manifest_path.is_file():
        return errors + ["episode.yaml is required"]
    manifest = load_manifest(manifest_path)
    manifest_shots = [shot for shot in manifest.get("shots", []) if isinstance(shot, Mapping)]
    manifest_ids = [str(shot.get("id")) for shot in manifest_shots]
    for shot_id in manifest_ids:
        shot_path = episode_root / "shots" / shot_id / "shot.yaml"
        if not shot_path.is_file():
            errors.append(f"shots/{shot_id}/shot.yaml is required")
        else:
            try:
                shot_value = load_yaml(shot_path)
                if not isinstance(shot_value.get("shot_contract"), Mapping):
                    errors.append(f"shots/{shot_id}/shot.yaml must contain the real Shot Contract")
            except (OSError, ValueError) as exc:
                errors.append(f"shots/{shot_id}/shot.yaml is invalid: {exc}")
    plan_path = episode_root / "production" / "generation_plan.yaml"
    if not plan_path.is_file():
        return errors + ["production/generation_plan.yaml is required"]
    try:
        plan = load_yaml(plan_path)
    except (OSError, ValueError) as exc:
        return errors + [f"production/generation_plan.yaml is invalid: {exc}"]
    errors.extend(validate_generation_plan(plan))
    plan_shots = plan.get("shots", []) if isinstance(plan, Mapping) else []
    plan_ids = [str(shot.get("shot_id")) for shot in plan_shots if isinstance(shot, Mapping)]
    if plan_ids != manifest_ids:
        errors.append("generation plan shot IDs and order must match current manifest Shot Contracts")
    by_id = {str(shot.get("shot_id")): shot for shot in plan_shots if isinstance(shot, Mapping)}
    for manifest_shot in manifest_shots:
        shot_id = str(manifest_shot.get("id"))
        plan_shot = by_id.get(shot_id)
        if not plan_shot:
            continue
        if manifest_shot.get("method") != plan_shot.get("method"):
            errors.append(f"{shot_id} manifest method must match production generation plan")
        shot_path = episode_root / "shots" / shot_id / "shot.yaml"
        if shot_path.is_file():
            try:
                shot_contract = load_yaml(shot_path)
                if shot_contract.get("method") != plan_shot.get("method"):
                    errors.append(f"{shot_id} shot.yaml method must match production generation plan")
            except (OSError, ValueError):
                pass
        start, end = manifest_shot.get("time_start"), manifest_shot.get("time_end")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end <= start:
            errors.append(f"episode.yaml timeline is required for {shot_id}")
            continue
        expected = float(end) - float(start)
        actual = plan_shot.get("edit_duration_sec")
        if not _positive_number(actual) or abs(float(actual) - expected) > 1e-6:
            errors.append(f"{shot_id} edit_duration_sec must match episode.yaml time_start/time_end")
    return errors


def record_generation_plan(episode_root: str | Path, value: Mapping[str, Any]) -> Path:
    """Record an agent-authored plan only after its upstream production gate passes."""

    episode_root = Path(episode_root)
    destination = episode_root / "production" / "generation_plan.yaml"
    manifest_path = episode_root / "episode.yaml"
    plan_errors = validate_generation_plan(value)
    if plan_errors:
        raise ValueError("Invalid production generation plan:\n- " + "\n- ".join(plan_errors))
    previous_plan = destination.read_bytes() if destination.is_file() else None
    manifest = load_manifest(manifest_path)
    previous_manifest = manifest_path.read_bytes()
    shot_backups: dict[Path, bytes] = {}
    by_id = {str(item.get("shot_id")): item for item in value.get("shots", []) if isinstance(item, Mapping)}
    try:
        dump_yaml(dict(value), destination)
        for manifest_shot in manifest.get("shots", []):
            if not isinstance(manifest_shot, dict):
                continue
            shot_id = str(manifest_shot.get("id"))
            plan_shot = by_id.get(shot_id)
            if not plan_shot:
                continue
            manifest_shot["method"] = plan_shot["method"]
            shot_path = episode_root / "shots" / shot_id / "shot.yaml"
            if shot_path.is_file():
                shot_backups[shot_path] = shot_path.read_bytes()
                shot = load_yaml(shot_path)
                shot["method"] = plan_shot["method"]
                dump_yaml(shot, shot_path)
        from .manifest import write_manifest
        write_manifest(manifest, manifest_path)
        errors = validate_production_generation_plan(episode_root)
        if errors:
            raise ValueError("Invalid production generation plan:\n- " + "\n- ".join(errors))
    except Exception:
        if previous_plan is None:
            destination.unlink(missing_ok=True)
        else:
            destination.write_bytes(previous_plan)
        manifest_path.write_bytes(previous_manifest)
        for path, content in shot_backups.items():
            path.write_bytes(content)
        raise
    return destination


def load_generation_plan_shot(episode_root: str | Path, shot_id: str) -> dict[str, Any]:
    episode_root = Path(episode_root)
    errors = validate_production_generation_plan(episode_root)
    if errors:
        raise ValueError("Production generation plan is not ready:\n- " + "\n- ".join(errors))
    plan = load_yaml(episode_root / "production" / "generation_plan.yaml")
    for shot in plan.get("shots", []):
        if isinstance(shot, Mapping) and shot.get("shot_id") == shot_id:
            return dict(shot)
    raise ValueError(f"production generation plan has no shot {shot_id}")
