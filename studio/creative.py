"""Creative Runtime contracts for agent-produced episode packages.

Python owns context collection, artifact IO, validation, provenance, and
manifest synchronization. Creative judgments are supplied by the agents in
``creative/agent_output`` (or by a caller passing ``agent_outputs``); this
module never invents a topic-specific candidate, rank, winner, hero shot, or
beat script.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .config import dump_yaml, load_yaml
from .manifest import load_manifest, write_manifest
from .paths import StudioPaths, project_root

CREATIVE_FILES = (
    "idea_analysis.yaml",
    "angle_tournament.yaml",
    "creative_direction.yaml",
    "visual_concept.yaml",
    "beat_script.yaml",
    "generation_plan.yaml",
)
AGENT_STAGES = (
    "idea_discovery",
    "angle_mutation",
    "idea_tournament",
    "creative_direction",
    "visual_concept",
    "beat_script",
    "generation_plan",
)
SHOT_TIERS = {"HERO", "STORY", "CONNECTOR"}
GENERATION_METHODS = {
    "ai_image",
    "ai_i2v",
    "ai_video",
    "ai_multiframe",
    "ai_extend",
    "ai_repair",
    "fusion",
    "footage",
    "hybrid_ai",
}
IMAGE_REQUIRED_METHODS = {"ai_image", "ai_i2v", "ai_multiframe", "hybrid_ai"}
VIDEO_REQUIRED_METHODS = {"ai_i2v", "ai_video", "ai_multiframe", "ai_extend", "ai_repair", "hybrid_ai"}


class CreativeAgentInputRequired(RuntimeError):
    """Raised when a package has no agent-produced artifacts to consume."""


def _text(path: Path, limit: int = 16_000) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")[:limit]


def _json_or_text(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _text(path)


def load_creative_history(root: str | Path, *, channel: str | None = None) -> list[dict[str, Any]]:
    """Load prior analytics as evidence for agents, never as an answer key."""

    root = Path(root).resolve()
    history: list[dict[str, Any]] = []
    for path in sorted((root / "episodes").glob("*/analytics.json")):
        value = _json_or_text(path)
        if not isinstance(value, dict):
            continue
        if channel and value.get("channel") not in {None, channel}:
            continue
        creative = value.get("creative") if isinstance(value.get("creative"), dict) else {}
        timeline = value.get("timeline_metrics") if isinstance(value.get("timeline_metrics"), dict) else {}
        history.append(
            {
                "episode_id": path.parent.name,
                "source": str(path.relative_to(root)),
                "hook_pattern": creative.get("hook_type"),
                "topic_type": creative.get("topic_type"),
                "visual_motif": creative.get("visual_motif"),
                "hero_shot_type": creative.get("hero_shot_type"),
                "retention": value.get("retention", value.get("retention_metrics")),
                "completion": value.get("completion", value.get("completion_rate")),
                "timeline_metrics": timeline,
            }
        )
    return history


def load_creative_context(root: str | Path, episode_id: str) -> dict[str, Any]:
    """Collect the dynamic inputs shared by every creative agent."""

    paths = StudioPaths(Path(root).resolve() if root else project_root())
    episode_root = paths.episode(episode_id)
    manifest_path = paths.manifest(episode_id)
    manifest = load_manifest(manifest_path)
    research_root = episode_root / "research"
    topic_brief = _text(research_root / "topic_brief.md")
    fact_pack = _text(research_root / "fact_pack.md")
    references = _json_or_text(research_root / "reference_deconstruction.json")
    creative = manifest.get("creative") if isinstance(manifest.get("creative"), dict) else {}
    channel = manifest.get("channel") or "The World You Never Knew"
    duration = creative.get("target_duration_sec")
    return {
        "schema_version": "creative-context-v2",
        "episode": {
            "id": episode_id,
            "channel": channel,
            "format": manifest.get("format"),
            "language": manifest.get("language"),
            "aspect_ratio": manifest.get("aspect_ratio"),
            "topic": creative.get("topic") or creative.get("promise") or episode_id,
        },
        "research_summary": {"topic_brief": topic_brief, "fact_pack": fact_pack},
        "reference_findings": references,
        "channel_identity": {
            "name": channel,
            "promise": "knowledge entertainment with a visible causal reveal",
            "language": manifest.get("language"),
        },
        "duration": duration,
        "visual_constraints": {
            "first_anomaly_seconds": 1.5,
            "meaningful_visual_change_seconds": [1, 3],
            "hero_required": True,
            "mute_read_required": True,
        },
        "available_tools": [
            "codex_image_gen",
            "google_flow_browser",
            "ego-browser",
            "fusion",
            "resolve",
            "voxcpm2_local",
        ],
        "historical_patterns": load_creative_history(root, channel=channel),
        "current_manifest": manifest,
        "provenance": {
            "manifest": str(manifest_path.relative_to(paths.root)),
            "research_files": [
                str(path.relative_to(paths.root))
                for path in (
                    research_root / "topic_brief.md",
                    research_root / "fact_pack.md",
                    research_root / "reference_deconstruction.json",
                )
                if path.is_file()
            ],
        },
    }


def build_creative_brief(context: Mapping[str, Any]) -> dict[str, Any]:
    """Build a neutral handoff brief; agents still supply all creative answers."""

    return {
        "schema_version": "creative-brief-v2",
        "episode": context.get("episode", {}),
        "research_summary": context.get("research_summary", {}),
        "reference_findings": context.get("reference_findings"),
        "duration": context.get("duration"),
        "visual_constraints": context.get("visual_constraints", {}),
        "available_tools": context.get("available_tools", []),
        "historical_patterns": context.get("historical_patterns", []),
        "agent_sequence": list(AGENT_STAGES),
        "decision_policy": {
            "discovery": "explore mutually different candidates before rejecting generic angles",
            "tournament": "pairwise reasoning with counterarguments and composite winner support",
            "direction": "challenge the apparent winner and preserve only one primary promise",
            "visual": "design information-bearing visuals before generation prompts",
            "generation": "route by shot information, continuity, physics, and production fit",
        },
        "provenance": {"source": "creative_context", "agent_owned_fields": True},
    }


def build_agent_context(context: Mapping[str, Any], stage: str) -> dict[str, Any]:
    """Return stage-scoped input for an external/sub-agent runner."""

    if stage not in AGENT_STAGES:
        raise ValueError(f"unknown creative agent stage: {stage}")
    return {
        "schema_version": "creative-agent-context-v2",
        "stage": stage,
        "brief": build_creative_brief(context),
        "inputs": {
            "episode": context.get("episode", {}),
            "research": context.get("research_summary", {}),
            "references": context.get("reference_findings"),
            "history": context.get("historical_patterns", []),
            "manifest": context.get("current_manifest", {}),
        },
        "constraints": {
            "no_fixed_episode_answer": True,
            "no_python_winner": True,
            "no_unsupported_facts": True,
            "no_narration_only_visuals": True,
        },
    }


def save_creative_artifact(payload: Mapping[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    dump_yaml(dict(payload), destination)
    return destination


def discover_ideas(context: Mapping[str, Any], agent_output: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Accept the Idea Discovery agent's result; never create a seed in Python."""

    if agent_output is None:
        return {"status": "AGENT_INPUT_REQUIRED", "agent_context": build_agent_context(context, "idea_discovery")}
    errors = validate_idea_analysis(agent_output)
    if errors:
        raise ValueError("Invalid idea discovery artifact: " + "; ".join(errors))
    return dict(agent_output)


def run_tournament(analysis: Mapping[str, Any], agent_output: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Accept the Tournament agent's pairwise/composite result."""

    if agent_output is None:
        return {"status": "AGENT_INPUT_REQUIRED", "input_candidate_count": len(analysis.get("candidates", []))}
    errors = validate_tournament(agent_output)
    if errors:
        raise ValueError("Invalid tournament artifact: " + "; ".join(errors))
    return dict(agent_output)


def validate_idea_analysis(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("schema_version") != "idea-analysis-v2":
        errors.append("idea_analysis.schema_version must be idea-analysis-v2")
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append("idea_analysis.candidates must be a non-empty list")
        return errors
    required = {
        "id", "title_working", "premise", "viewer_question", "surprising_fact",
        "emotional_driver", "hook_potential", "visual_potential", "story_potential",
        "production_fit", "novelty", "risk", "evidence",
    }
    nested = {"hook_potential", "visual_potential", "story_potential", "production_fit", "novelty", "risk", "evidence"}
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            errors.append(f"candidates[{index}] must be a mapping")
            continue
        missing = sorted(required - set(candidate))
        if missing:
            errors.append(f"candidates[{index}] missing {missing}")
        for key in nested:
            if not isinstance(candidate.get(key), dict):
                errors.append(f"candidates[{index}].{key} must be a mapping")
    return errors


def validate_tournament(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("schema_version") != "angle-tournament-v2":
        errors.append("angle_tournament.schema_version must be angle-tournament-v2")
    if not isinstance(value.get("comparisons"), list) or not value.get("comparisons"):
        errors.append("angle_tournament.comparisons must be a non-empty list")
    for index, comparison in enumerate(value.get("comparisons", [])):
        if not isinstance(comparison, dict):
            errors.append(f"comparisons[{index}] must be a mapping")
            continue
        for key in ("left", "right", "stronger", "reasoning", "dimensions"):
            if not comparison.get(key):
                errors.append(f"comparisons[{index}] missing {key}")
        if not isinstance(comparison.get("dimensions"), dict):
            errors.append(f"comparisons[{index}].dimensions must be a mapping")
    selected = value.get("selected_direction")
    if not isinstance(selected, dict):
        errors.append("selected_direction must be a mapping")
    else:
        for key in ("hook_from", "visual_motif_from", "escalation_from", "payoff_from", "ending_from", "rationale"):
            if not selected.get(key):
                errors.append(f"selected_direction missing {key}")
    if not isinstance(value.get("angle_mutations"), list) or not value.get("angle_mutations"):
        errors.append("angle_mutations must be a non-empty list")
    return errors


def validate_creative_direction(value: Mapping[str, Any]) -> list[str]:
    required = ("core_question", "one_sentence_promise", "opening", "narrative_engine", "visual_peaks", "hero_shot", "ending", "reject")
    return [f"creative_direction missing {key}" for key in required if not value.get(key)]


def validate_visual_concept(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("visual_language", "hero_frames", "shots", "rejections"):
        if not value.get(key):
            errors.append(f"visual_concept missing {key}")
    for index, shot in enumerate(value.get("shots", [])):
        if not isinstance(shot, dict):
            errors.append(f"visual_concept.shots[{index}] must be a mapping")
            continue
        for key in ("shot_id", "tier", "visual_goal", "composition", "focal_subject", "camera", "action", "transition", "method_candidates"):
            if not shot.get(key):
                errors.append(f"visual_concept.shots[{index}] missing {key}")
        if shot.get("tier") not in SHOT_TIERS:
            errors.append(f"visual_concept.shots[{index}].tier invalid")
        if not isinstance(shot.get("method_candidates"), list):
            errors.append(f"visual_concept.shots[{index}].method_candidates must be a list")
    return errors


def validate_beat_script(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    beats = value.get("beats")
    if not isinstance(beats, list) or not beats:
        return ["beat_script.beats must be a non-empty list"]
    required = ("id", "purpose", "narration", "visual_action", "visual_information", "camera_event", "sound_event", "emotional_change", "duration_target")
    for index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            errors.append(f"beats[{index}] must be a mapping")
            continue
        for key in required:
            if beat.get(key) in (None, ""):
                errors.append(f"beats[{index}] missing {key}")
        if not isinstance(beat.get("duration_target"), (int, float)) or beat.get("duration_target", 0) <= 0:
            errors.append(f"beats[{index}].duration_target must be positive")
        if beat.get("narration") and not beat.get("visual_action") and not beat.get("visual_information"):
            errors.append(f"beats[{index}] narration has no visual reason")
    return errors


def validate_generation_plan(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    shots = value.get("shots")
    if not isinstance(shots, list) or not shots:
        return ["generation_plan.shots must be a non-empty list"]
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            errors.append(f"generation_plan.shots[{index}] must be a mapping")
            continue
        if shot.get("tier") not in SHOT_TIERS:
            errors.append(f"generation_plan.shots[{index}] invalid tier")
        if shot.get("method") not in GENERATION_METHODS:
            errors.append(f"generation_plan.shots[{index}] invalid method")
        method = shot.get("method")
        image_candidates = shot.get("image_candidates", 0)
        video_candidates = shot.get("video_candidates", 0)
        if type(image_candidates) is not int or image_candidates < 0:
            errors.append(f"generation_plan.shots[{index}].image_candidates must be a non-negative integer")
        elif (method in IMAGE_REQUIRED_METHODS or (method == "ai_video" and shot.get("keyframe_first") is True)) and image_candidates < 1:
            errors.append(f"generation_plan.shots[{index}].image_candidates must be positive for this image-first route")
        if type(video_candidates) is not int or video_candidates < 0:
            errors.append(f"generation_plan.shots[{index}].video_candidates must be a non-negative integer")
        elif method in VIDEO_REQUIRED_METHODS and video_candidates < 1:
            errors.append(f"generation_plan.shots[{index}].video_candidates must be positive for {method}")
        if not isinstance(shot.get("fusion_graphics"), list):
            errors.append(f"generation_plan.shots[{index}].fusion_graphics must be a list")
        if not isinstance(shot.get("forbidden"), list) or not shot["forbidden"]:
            errors.append(f"generation_plan.shots[{index}] missing forbidden constraints")
    return errors


def validate_creative_package(package_dir: str | Path) -> list[str]:
    package_dir = Path(package_dir)
    errors: list[str] = []
    for filename in CREATIVE_FILES:
        if not (package_dir / filename).is_file():
            errors.append(f"missing {filename}")
    if errors:
        return errors
    try:
        values = {filename: load_yaml(package_dir / filename) for filename in CREATIVE_FILES}
    except (OSError, ValueError) as exc:
        return [f"invalid creative package YAML: {exc}"]
    validators = {
        "idea_analysis.yaml": validate_idea_analysis,
        "angle_tournament.yaml": validate_tournament,
        "creative_direction.yaml": validate_creative_direction,
        "visual_concept.yaml": validate_visual_concept,
        "beat_script.yaml": validate_beat_script,
        "generation_plan.yaml": validate_generation_plan,
    }
    for filename, validator in validators.items():
        errors.extend(f"{filename}: {error}" for error in validator(values[filename]))
    return errors


def _load_agent_outputs(agent_dir: Path) -> dict[str, dict[str, Any]]:
    outputs: dict[str, dict[str, Any]] = {}
    for filename in CREATIVE_FILES:
        path = agent_dir / filename
        if path.is_file():
            outputs[filename] = load_yaml(path)
    return outputs


def _hero_shot_id(direction: Mapping[str, Any], generation: Mapping[str, Any]) -> str | None:
    hero = direction.get("hero_shot")
    if isinstance(hero, str):
        return hero
    if isinstance(hero, dict) and hero.get("shot_id"):
        return str(hero["shot_id"])
    for shot in generation.get("shots", []):
        if isinstance(shot, dict) and shot.get("tier") == "HERO" and shot.get("shot_id"):
            return str(shot["shot_id"])
    return None


def _sync_manifest(manifest: dict[str, Any], direction: Mapping[str, Any], visual: Mapping[str, Any], beats: Mapping[str, Any], generation: Mapping[str, Any]) -> None:
    creative = manifest.setdefault("creative", {})
    hero_id = _hero_shot_id(direction, generation)
    creative.update(
        {
            "promise": direction.get("one_sentence_promise"),
            "core_question": direction.get("core_question"),
            "hero_shot": hero_id,
            "target_duration_sec": beats.get("duration_sec") or sum(float(item.get("duration_target", 0)) for item in beats.get("beats", []) if isinstance(item, dict)),
            "visual_motif": (visual.get("visual_language") or {}).get("motif"),
            "creative_package": "creative/",
            "creative_provenance": "agent_runtime",
        }
    )
    if direction.get("hook_type"):
        creative["hook_type"] = direction["hook_type"]
    if direction.get("hero_shot_type"):
        creative["hero_shot_type"] = direction["hero_shot_type"]


def generate_creative_package(
    root: str | Path,
    episode_id: str,
    *,
    force: bool = False,
    agent_dir: str | Path | None = None,
    agent_outputs: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Consume an agent-produced package and persist the canonical artifacts."""

    paths = StudioPaths(Path(root).resolve() if root else project_root())
    manifest_path = paths.manifest(episode_id)
    manifest = load_manifest(manifest_path)
    creative_dir = paths.episode(episode_id) / "creative"
    if any((creative_dir / filename).exists() for filename in CREATIVE_FILES) and not force:
        raise FileExistsError(f"creative package exists; pass --force to rebuild: {creative_dir}")

    context = load_creative_context(paths.root, episode_id)
    context_path = creative_dir / "context_pack.yaml"
    save_creative_artifact(context, context_path)
    outputs = {
        key: dict(value)
        for key, value in (agent_outputs or {}).items()
        if key in CREATIVE_FILES and isinstance(value, Mapping)
    }
    source_dir = Path(agent_dir) if agent_dir else creative_dir / "agent_output"
    if not outputs:
        outputs = _load_agent_outputs(source_dir)
    missing = [filename for filename in CREATIVE_FILES if filename not in outputs]
    if missing:
        return {
            "status": "BLOCKED_AGENT_INPUT",
            "episode_id": episode_id,
            "context_pack": str(context_path),
            "agent_context": str(context_path),
            "agent_output_dir": str(source_dir),
            "missing": missing,
        }

    validation_errors: list[str] = []
    validators = {
        "idea_analysis.yaml": validate_idea_analysis,
        "angle_tournament.yaml": validate_tournament,
        "creative_direction.yaml": validate_creative_direction,
        "visual_concept.yaml": validate_visual_concept,
        "beat_script.yaml": validate_beat_script,
        "generation_plan.yaml": validate_generation_plan,
    }
    for filename, validator in validators.items():
        validation_errors.extend(f"{filename}: {error}" for error in validator(outputs[filename]))
    if validation_errors:
        return {"status": "BLOCKED_AGENT_OUTPUT", "episode_id": episode_id, "errors": validation_errors, "context_pack": str(context_path)}

    for filename in CREATIVE_FILES:
        save_creative_artifact(outputs[filename], creative_dir / filename)
    generation = outputs["generation_plan.yaml"]
    dump_yaml(generation, paths.episode(episode_id) / "production" / "generation_plan.yaml")
    _sync_manifest(manifest, outputs["creative_direction.yaml"], outputs["visual_concept.yaml"], outputs["beat_script.yaml"], generation)
    write_manifest(manifest, manifest_path)
    package_errors = validate_creative_package(creative_dir)
    if package_errors:
        return {"status": "BLOCKED_AGENT_OUTPUT", "episode_id": episode_id, "errors": package_errors, "context_pack": str(context_path)}
    return {
        "status": "PASS",
        "episode_id": episode_id,
        "package_dir": str(creative_dir),
        "context_pack": str(context_path),
        "files": [str(creative_dir / filename) for filename in CREATIVE_FILES],
        "agent_output_dir": str(source_dir),
        "hero_shot": manifest.get("creative", {}).get("hero_shot"),
        "candidate_count": len(outputs["idea_analysis.yaml"].get("candidates", [])),
        "provenance": {"source": "agent_runtime", "stages": list(AGENT_STAGES)},
    }
