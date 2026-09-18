"""Voice manifest contracts shared by master, publish, and VoxCPM2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import dump_yaml, load_yaml
from ..media.hashing import sha256_file

VOICE_PROVIDER = "voxcpm2_local"
# Kept as a compatibility symbol for callers; an absent value is intentional.
DEFAULT_NARRATOR: str | None = None
DEFAULT_MODE = "controllable"
MODEL_REPO = "mlx-community/VoxCPM2-bf16"


def script_hash(episode_root: str | Path) -> str | None:
    path = Path(episode_root) / "creative" / "beat_script.yaml"
    return sha256_file(path) if path.is_file() else None


def load_voice_manifest(episode_root: str | Path) -> dict[str, Any] | None:
    path = Path(episode_root) / "audio" / "voice_manifest.yaml"
    if not path.is_file():
        return None
    try:
        value = load_yaml(path)
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def write_voice_manifest(episode_root: str | Path, value: dict[str, Any]) -> Path:
    path = Path(episode_root) / "audio" / "voice_manifest.yaml"
    dump_yaml(value, path)
    return path


def _resolve_episode_path(episode_root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else episode_root / path


def production_voice_check(episode_root: str | Path, *, explicit_user_override: bool = False) -> dict[str, Any]:
    """Require the current script, real joined WAV, voice, and reference identity."""

    if explicit_user_override:
        return {
            "pass": True,
            "status": "EXPLICIT_USER_OVERRIDE",
            "provider": None,
            "reason": "User explicitly authorized a non-default production voice for this delivery.",
        }
    episode_root = Path(episode_root).resolve()
    manifest = load_voice_manifest(episode_root)
    current_script = script_hash(episode_root)
    if manifest is None:
        return {"pass": False, "status": "BLOCKED", "provider": None, "reason": "missing_voice_manifest"}
    production = manifest.get("production_voice") if isinstance(manifest.get("production_voice"), dict) else {}
    provider = manifest.get("provider")
    reasons: list[str] = []
    joined = _resolve_episode_path(episode_root, production.get("path"))
    if provider != VOICE_PROVIDER:
        reasons.append("provider_must_be_voxcpm2_local")
    if not current_script or manifest.get("script_hash") != current_script:
        reasons.append("voice_script_hash_stale")
    if production.get("script_hash") != current_script:
        reasons.append("production_voice_script_hash_stale")
    if production.get("provider") != VOICE_PROVIDER:
        reasons.append("production_voice_provider_must_be_voxcpm2_local")
    if production.get("status") != "READY":
        reasons.append("production_voice_not_ready")
    if production.get("temporary") is True:
        reasons.append("temporary_voice_is_not_allowed")
    if joined is None or not joined.is_file():
        reasons.append("joined_narration_missing")
    else:
        joined_hash = sha256_file(joined)
        if production.get("sha256") != joined_hash or production.get("joined_narration_sha256") != joined_hash:
            reasons.append("joined_narration_hash_mismatch")
    narrator = manifest.get("narrator") or production.get("narrator")
    if not narrator:
        reasons.append("narrator_missing")
    current_reference_hash = None
    if narrator:
        try:
            from .voxcpm2 import inspect_voice

            inspected = inspect_voice(str(narrator))
            current_reference_hash = inspected.get("reference_hash")
            if production.get("reference_hash") != current_reference_hash:
                reasons.append("voice_reference_hash_stale")
        except (OSError, RuntimeError, ValueError):
            reasons.append("narrator_reference_unavailable")
    return {
        "pass": not reasons,
        "status": "READY" if not reasons else "BLOCKED",
        "provider": provider,
        "narrator": narrator,
        "reason": "; ".join(reasons) if reasons else "VoxCPM2 joined narration is bound to the current script and voice reference.",
        "script_hash": current_script,
        "joined_path": str(joined) if joined else None,
        "joined_sha256": production.get("sha256"),
        "reference_hash": current_reference_hash,
    }
