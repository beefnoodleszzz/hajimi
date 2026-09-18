"""Voice direction: decide how the approved beat script should be performed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import dump_yaml, load_yaml
from ..manifest import load_manifest
from ..paths import StudioPaths, project_root
from .manifest import DEFAULT_MODE, DEFAULT_NARRATOR, MODEL_REPO, VOICE_PROVIDER, script_hash, write_voice_manifest


def _beat_direction(beat: dict[str, Any]) -> dict[str, Any]:
    purpose = str(beat.get("purpose", "narration"))
    mapping = {
        "hook": ("controlled", "medium-fast", ["road freezes", "momentum"], 120, 80),
        "personal_scale": ("urgent", "medium", ["equator", "465 meters per second"], 80, 80),
        "mechanism": ("precise", "medium", ["eastward speed", "nowhere to go"], 80, 80),
        "measurement": ("astonished", "medium-slow", ["one second", "465 meters"], 100, 100),
        "atmosphere": ("ominous", "medium", ["air", "aligned"], 80, 80),
        "ocean": ("grave", "medium", ["ocean", "pavement", "water"], 90, 90),
        "hero": ("calm authority", "medium-slow", ["land restarts", "aligned system"], 120, 100),
        "correction": ("clear correction", "medium", ["gravity", "sideways"], 90, 100),
        "payoff": ("restrained cinematic", "medium-slow", ["disaster", "stop with the ground"], 110, 100),
        "loop": ("inviting question", "slow with final lift", ["one second", "465 meters", "which layer"], 100, 160),
    }
    energy, pace, emphasis, before, after = mapping.get(purpose, ("intelligent", "medium", [], 80, 80))
    return {
        "id": beat.get("id"),
        "text": beat.get("narration", ""),
        "energy": energy,
        "pace": pace,
        "emphasis": emphasis,
        "pause_before_ms": before,
        "pause_after_ms": after,
        "emotional_intent": beat.get("emotional_change"),
    }


def build_voice_plan(root: str | Path, episode_id: str, *, narrator: str | None = None) -> dict[str, Any]:
    paths = StudioPaths(Path(root).resolve() if root else project_root())
    episode_root = paths.episode(episode_id)
    manifest = load_manifest(paths.manifest(episode_id))
    beat_path = episode_root / "creative" / "beat_script.yaml"
    if not beat_path.is_file():
        raise FileNotFoundError(f"Creative beat script is missing: {beat_path}")
    beats = load_yaml(beat_path).get("beats", [])
    audio = manifest.get("audio", {}) if isinstance(manifest.get("audio"), dict) else {}
    selected_narrator = narrator or audio.get("narrator") or DEFAULT_NARRATOR
    voice_direction = {
        "schema_version": "voice-direction-v1",
        "narrator": selected_narrator,
        "provider": VOICE_PROVIDER,
        "mode": audio.get("voice_mode", DEFAULT_MODE),
        "global": {
            "character": ["intelligent", "cinematic", "confident", "restrained", "mature English female narrator"],
            "forbidden": ["whisper", "ASMR delivery", "seductive", "sleepy", "overacted", "radio-commercial"],
            "note": "Preserve identity from the authorized friend reference; style control must not erase identity.",
        },
        "beats": [_beat_direction(beat) for beat in beats if isinstance(beat, dict)],
    }
    manifest_value = {
        "schema_version": "voice-manifest-v1",
        "provider": VOICE_PROVIDER,
        "narrator": selected_narrator,
        "mode": audio.get("voice_mode", DEFAULT_MODE),
        "script_hash": script_hash(episode_root),
        "model": MODEL_REPO,
        "reference_voice": audio.get("reference_voice", f"{selected_narrator}/neutral"),
        "reference_hash": None,
        "selection_policy": {
            "candidate_count": 3,
            "selected_candidate": audio.get("selected_candidate", "candidate_02"),
            "selected_from": "previous same-reference VoxCPM2 Ultimate vs Qwen comparison; candidate 02 was the approved friend-voice production take",
            "human_listening_required": True,
        },
        "voice_direction": voice_direction,
        "takes": {
            str(beat.get("id")): {"selected": audio.get("selected_candidate", "candidate_02"), "candidates": [], "status": "PLANNED"}
            for beat in beats if isinstance(beat, dict) and beat.get("id")
        },
        "production_voice": {
            "provider": VOICE_PROVIDER,
            "status": "PLANNED",
            "temporary": False,
            "path": None,
            "sha256": None,
        },
    }
    audio_root = episode_root / "audio"
    audio_root.mkdir(parents=True, exist_ok=True)
    dump_yaml(voice_direction, audio_root / "voice_plan.yaml")
    write_voice_manifest(episode_root, manifest_value)
    return {"status": "PLANNED", "episode_id": episode_id, "provider": VOICE_PROVIDER, "narrator": selected_narrator, "voice_plan": str(audio_root / "voice_plan.yaml"), "voice_manifest": str(audio_root / "voice_manifest.yaml"), "beats": len(manifest_value["takes"])}

