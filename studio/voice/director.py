"""Voice Director: turn beat intent into executable VoxCPM2 line controls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import dump_yaml, load_yaml
from ..manifest import load_manifest, write_manifest
from ..paths import StudioPaths, project_root
from .manifest import MODEL_REPO, VOICE_PROVIDER, script_hash, write_voice_manifest
from .voxcpm2 import inspect_voice, route_emotion, emotion_instruction, select_voice

KEY_BEAT_PURPOSES = {"hook", "hero", "payoff", "ending", "loop"}


def _beat_direction(beat: dict[str, Any], voice: dict[str, Any]) -> dict[str, Any]:
    requested = beat.get("voice_direction") or beat.get("direction") or {}
    if not isinstance(requested, dict):
        requested = {}
    intent = str(requested.get("emotional_intent") or beat.get("emotional_change") or "neutral")
    emotion = route_emotion(str(requested.get("emotion") or requested.get("voxcpm2_emotion") or intent))
    available_styles = set(voice.get("styles", []))
    requested_style = str(requested.get("style") or emotion)
    exact_requested = requested.get("mode") == "ultimate" or requested.get("exact_performance") is True
    exact = exact_requested and requested_style in available_styles
    style = requested_style if exact else "neutral"
    mode = "ultimate" if exact else "controllable"
    instruction = requested.get("instruct") or emotion_instruction(emotion)
    if mode == "controllable":
        performance = ", ".join(
            item
            for item in (
                f"energy: {requested.get('energy', 'controlled')}",
                f"pace: {requested.get('pace', 'medium')}",
                f"emphasis: {', '.join(str(item) for item in requested.get('emphasis', []))}",
            )
            if item and not item.endswith(": ")
        )
        if performance:
            instruction = f"{instruction}; {performance}"
    purpose = str(beat.get("purpose", "narration")).lower()
    candidate_count = int(requested.get("candidate_count") or (3 if purpose in KEY_BEAT_PURPOSES else 2))
    return {
        "id": beat.get("id"),
        "text": beat.get("narration", ""),
        "direction": {
            "energy": requested.get("energy", "controlled"),
            "pace": requested.get("pace", "medium"),
            "emotional_intent": intent,
            "emphasis": requested.get("emphasis", []),
            "pause_before_ms": int(requested.get("pause_before_ms", 80)),
            "pause_after_ms": int(requested.get("pause_after_ms", 80)),
        },
        "voxcpm2": {
            "emotion": emotion,
            "style": style,
            "mode": mode,
            "instruct": None if exact else instruction,
            "candidate_count": max(1, min(candidate_count, 5)),
        },
    }


def build_voice_plan(root: str | Path, episode_id: str, *, narrator: str | None = None) -> dict[str, Any]:
    paths = StudioPaths(Path(root).resolve() if root else project_root())
    episode_root = paths.episode(episode_id)
    manifest_path = paths.manifest(episode_id)
    manifest = load_manifest(manifest_path)
    beat_path = episode_root / "creative" / "beat_script.yaml"
    if not beat_path.is_file():
        raise FileNotFoundError(f"Creative beat script is missing: {beat_path}")
    selection = select_voice(manifest, narrator=narrator)
    if selection.get("status") != "READY":
        return selection
    voice = inspect_voice(str(selection["id"]))
    beats = load_yaml(beat_path).get("beats", [])
    directions = [_beat_direction(beat, voice) for beat in beats if isinstance(beat, dict) and beat.get("id")]
    voice_direction = {
        "schema_version": "voice-direction-v2",
        "narrator": selection["id"],
        "provider": VOICE_PROVIDER,
        "mode": "per_line",
        "voice_identity": {
            "name": voice.get("name"),
            "language": voice.get("language"),
            "styles": voice.get("styles", []),
            "authorization_status": voice.get("authorization_status"),
            "commercial_use": voice.get("commercial_use"),
        },
        "beats": directions,
    }
    manifest_value = {
        "schema_version": "voice-manifest-v2",
        "provider": VOICE_PROVIDER,
        "narrator": selection["id"],
        "language": voice.get("language"),
        "script_hash": script_hash(episode_root),
        "model": MODEL_REPO,
        "reference_voice": f"{selection['id']}/{voice.get('default_style', 'neutral')}",
        "reference_hash": voice.get("reference_hash"),
        "voice_direction": voice_direction,
        "selection_policy": {
            "key_beat_candidate_count": 3,
            "normal_beat_candidate_count": "1-2",
            "human_listening_required": True,
            "automatic_selection": "screening_only",
        },
        "takes": {
            str(item["id"]): {
                "selected": None,
                "screened_candidate": None,
                "candidates": [],
                "selection_status": "AWAITING_RENDER",
            }
            for item in directions
        },
        "production_voice": {
            "provider": VOICE_PROVIDER,
            "status": "PLANNED",
            "temporary": False,
            "path": None,
            "sha256": None,
            "script_hash": script_hash(episode_root),
            "voice_id": selection["id"],
            "reference_hash": voice.get("reference_hash"),
            "model_identity": selection.get("model_identity"),
        },
        "provenance": {"voice_library": selection.get("voice_json"), "runtime": "voxcpm2_local"},
    }
    audio_root = episode_root / "audio"
    audio_root.mkdir(parents=True, exist_ok=True)
    dump_yaml(voice_direction, audio_root / "voice_plan.yaml")
    write_voice_manifest(episode_root, manifest_value)
    audio = manifest.setdefault("audio", {})
    audio.update(
        {
            "narrator": selection["id"],
            "voice_mode": "per_line",
            "voice_policy": "production_voxcpm2_local",
            "production_voice_provider": VOICE_PROVIDER,
            "reference_voice": f"{selection['id']}/{voice.get('default_style', 'neutral')}",
        }
    )
    write_manifest(manifest, manifest_path)
    return {
        "status": "PLANNED",
        "episode_id": episode_id,
        "provider": VOICE_PROVIDER,
        "narrator": selection["id"],
        "voice_plan": str(audio_root / "voice_plan.yaml"),
        "voice_manifest": str(audio_root / "voice_manifest.yaml"),
        "beats": len(directions),
        "candidate_policy": {item["id"]: item["voxcpm2"]["candidate_count"] for item in directions},
    }
