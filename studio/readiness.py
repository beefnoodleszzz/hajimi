"""Read-only production readiness derived from canonical episode artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .config import load_yaml
from .creative import (
    validate_beat_script, validate_creative_direction, validate_hook_competition,
    validate_idea_analysis, validate_mute_read, validate_tournament,
    validate_visual_concept,
)
from .manifest import EPISODE_RE, load_manifest
from .production import validate_production_generation_plan
from .remote.h3 import h3_doctor
from .storyboard import validate_storyboard_gate
from .voice.manifest import production_voice_check


STAGE_ROUTES = {
    "research": "idea",
    "creative": "idea",
    "script": "script",
    "visual_concept": "visual_concept",
    "storyboard": "storyboard",
    "animatic": "animatic",
    "production_plan": "generation_plan",
    "image": "image",
    "video_prompt": "video_prompt",
    "video_generation": "video_generation",
    "shot_qc": "shot_qc",
    "voice": "voice",
    "sound": "sound",
    "editing": "editing",
    "master": "master",
    "publish": "publish",
    "analytics": "analytics",
}


def _route_skills(root: Path, route: str) -> list[str]:
    routing = load_yaml(root / "config" / "skill-routing.yaml")
    contract = routing.get("stages", {}).get(route, {})
    names: list[str] = []
    for key in ("specialists", "specialist", "director", "adapter", "methods", "contract", "qc", "optional_finish"):
        value = contract.get(key) if isinstance(contract, Mapping) else None
        values = value if isinstance(value, list) else [value]
        names.extend(str(item) for item in values if isinstance(item, str))
    return list(dict.fromkeys(names))


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _yaml_gate(directory: Path, contracts: Mapping[str, Callable[[Mapping[str, Any]], list[str]]]) -> list[str]:
    errors: list[str] = []
    for filename, validator in contracts.items():
        path = directory / filename
        if not path.is_file():
            errors.append(f"missing {filename}")
            continue
        try:
            errors.extend(f"{filename}: {error}" for error in validator(load_yaml(path)))
        except (OSError, ValueError) as exc:
            errors.append(f"invalid {filename}: {exc}")
    return errors


def episode_readiness(
    root: str | Path,
    episode_id: str,
    *,
    remote_doctor: Callable[[str | Path], dict[str, Any]] = h3_doctor,
) -> dict[str, Any]:
    root = Path(root).resolve()
    if not isinstance(episode_id, str) or not EPISODE_RE.fullmatch(episode_id):
        raise ValueError("episode_id is invalid")
    episode_root = (root / "episodes" / episode_id).resolve()
    if not episode_root.is_relative_to(root):
        raise ValueError("episode path escapes the project root")
    manifest = load_manifest(episode_root / "episode.yaml")
    missing_by_stage: dict[str, list[str]] = {}
    blockers_by_stage: dict[str, list[str]] = {}

    research_files = (
        "research/topic_brief.md", "research/fact_pack.md",
        "research/reference_deconstruction.json",
    )
    missing_by_stage["research"] = [item for item in research_files if not (episode_root / item).is_file()]
    creative_root = episode_root / "creative"
    blockers_by_stage["creative"] = _yaml_gate(creative_root, {
        "idea_analysis.yaml": validate_idea_analysis,
        "angle_tournament.yaml": validate_tournament,
        "creative_direction.yaml": validate_creative_direction,
    })
    blockers_by_stage["script"] = _yaml_gate(creative_root, {
        "hook_competition.yaml": validate_hook_competition,
        "mute_read.yaml": validate_mute_read,
        "beat_script.yaml": validate_beat_script,
    })
    blockers_by_stage["visual_concept"] = _yaml_gate(
        creative_root, {"visual_concept.yaml": validate_visual_concept}
    )
    blockers_by_stage["storyboard"] = validate_storyboard_gate(episode_root)

    gate_path = episode_root / "animatic" / "gate.json"
    gate = _json(gate_path)
    missing_by_stage["animatic"] = [] if gate_path.is_file() else ["animatic/gate.json"]
    blockers_by_stage["animatic"] = [] if gate.get("production_gate") == "PASS" else ["animatic production_gate is not PASS"]
    blockers_by_stage["production_plan"] = validate_production_generation_plan(episode_root)

    shots = [item for item in manifest.get("shots", []) if isinstance(item, Mapping)]
    image_methods = {"ai_image", "h3_i2v", "h3_fl2v", "h3_ref2v", "hybrid_ai"}
    h3_methods = {"h3_i2v", "h3_fl2v", "h3_ref2v", "hybrid_ai"}
    try:
        plan = load_yaml(episode_root / "production" / "generation_plan.yaml")
    except (OSError, ValueError):
        plan = {}
    plan_by_id = {
        str(item.get("shot_id")): item
        for item in plan.get("shots", [])
        if isinstance(item, Mapping)
    }
    image_missing: list[str] = []
    prompt_missing: list[str] = []
    remote_missing: list[str] = []
    for shot in shots:
        shot_id = str(shot.get("id"))
        if shot.get("method") in image_methods:
            required_images = [f"shots/{shot_id}/images/prompt.md", f"shots/{shot_id}/images/prompt.json"]
            if shot.get("method") == "ai_image":
                required_images.append(f"shots/{shot_id}/images/selected_keyframe.png")
            for relative in required_images:
                if not (episode_root / relative).is_file():
                    image_missing.append(relative)
        if shot.get("method") in h3_methods:
            for relative in (f"shots/{shot_id}/h3/prompt.txt", f"shots/{shot_id}/h3/prompt.json"):
                if not (episode_root / relative).is_file():
                    prompt_missing.append(relative)
            strategy = plan_by_id.get(shot_id, {}).get("input_strategy", {})
            if isinstance(strategy, Mapping):
                input_paths = [strategy.get("first_frame"), strategy.get("last_frame")]
                references = strategy.get("references", [])
                if isinstance(references, list):
                    input_paths.extend(references)
                for value in input_paths:
                    if isinstance(value, str) and value.strip() and not (episode_root / value).is_file():
                        image_missing.append(f"production input missing: {value}")
            if not shot.get("remote_job"):
                remote_missing.append(f"{shot_id}: remote job not prepared")
            elif shot.get("remote_status") != "SELECTED":
                remote_missing.append(f"{shot_id}: remote candidate not selected")
            active_media = shot.get("active_media")
            if not isinstance(active_media, str) or not (episode_root / active_media).is_file():
                remote_missing.append(f"{shot_id}: selected active media is missing")
    missing_by_stage["image"] = image_missing
    missing_by_stage["video_prompt"] = prompt_missing
    missing_by_stage["video_generation"] = remote_missing
    blockers_by_stage["shot_qc"] = [
        f"{shot.get('id')}: selected production shot is not approved"
        for shot in shots
        if shot.get("status") != "approved"
    ]

    voice = production_voice_check(episode_root)
    blockers_by_stage["voice"] = [] if voice.get("pass") else [str(voice.get("reason", "production voice is not ready"))]
    roughcut_manifest = episode_root / "edit" / "roughcut_manifest.json"
    missing_by_stage["sound"] = [] if (episode_root / "edit" / "roughcut.yaml").is_file() else ["edit/roughcut.yaml"]
    missing_by_stage["editing"] = [] if roughcut_manifest.is_file() else ["edit/roughcut_manifest.json"]
    master_report = _json(episode_root / "qc" / "master_report.json")
    blockers_by_stage["master"] = [] if master_report.get("decision") == "PASS" else ["master QC is not PASS"]
    preflight = _json(episode_root / "publish" / "preflight.json")
    blockers_by_stage["publish"] = [] if preflight.get("status") == "READY" else ["YouTube publish preflight is not READY"]
    missing_by_stage["analytics"] = [] if (episode_root / "analytics.json").is_file() else ["analytics.json"]

    stages = list(STAGE_ROUTES)
    current_stage = "complete"
    next_stage = "complete"
    missing: list[str] = []
    blocking: list[str] = []
    for stage in stages:
        stage_missing = missing_by_stage.get(stage, [])
        stage_blocking = blockers_by_stage.get(stage, [])
        if stage_missing or stage_blocking:
            current_stage = stage
            next_stage = stage
            missing = stage_missing
            blocking = stage_blocking
            break

    try:
        remote = remote_doctor(root)
    except Exception as exc:  # readiness must remain usable while AutoDL is off
        remote = {"status": "FAIL", "checks": [], "error": str(exc)}
    remote_ready = remote.get("status") == "PASS"
    local_preproduction_ready = not any(
        missing_by_stage.get(stage) or blockers_by_stage.get(stage)
        for stage in ("research", "creative", "script", "visual_concept", "storyboard", "animatic", "production_plan", "image", "video_prompt")
    )
    postproduction_ready = bool(shots) and all(shot.get("status") == "approved" for shot in shots) and voice.get("pass") is True
    remote_reason = None
    if not remote_ready:
        details = [str(item.get("detail")) for item in remote.get("checks", []) if isinstance(item, Mapping) and item.get("status") != "PASS" and item.get("detail")]
        remote_reason = details[-1] if details else str(remote.get("error") or "OFFLINE")
    return {
        "episode_id": episode_id,
        "LOCAL_PREPRODUCTION_READY": local_preproduction_ready,
        "REMOTE_H3_READY": remote_ready,
        "POSTPRODUCTION_READY": postproduction_ready,
        "remote_reason": remote_reason,
        "current_stage": current_stage,
        "next_stage": next_stage,
        "required_skills": _route_skills(root, STAGE_ROUTES.get(next_stage, "publish")),
        "missing_artifacts": missing,
        "blocking_gates": blocking,
    }
