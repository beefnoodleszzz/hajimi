"""Voice manifest contracts shared by master, publish, and the adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import dump_yaml, load_yaml
from ..media.hashing import sha256_file

VOICE_PROVIDER = "voxcpm2_local"
DEFAULT_NARRATOR = "science_female_main"
DEFAULT_MODE = "ultimate"
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


def production_voice_check(episode_root: str | Path, *, explicit_user_override: bool = False) -> dict[str, Any]:
    """Require a real, non-temporary VoxCPM2 production voice before delivery."""

    if explicit_user_override:
        return {
            "pass": True,
            "status": "EXPLICIT_USER_OVERRIDE",
            "provider": None,
            "reason": "User explicitly authorized a non-default production voice for this delivery.",
        }
    episode_root = Path(episode_root)
    manifest = load_voice_manifest(episode_root)
    current_hash = script_hash(episode_root)
    if manifest is None:
        return {"pass": False, "status": "BLOCKED", "provider": None, "reason": "missing_voice_manifest"}
    production = manifest.get("production_voice") if isinstance(manifest.get("production_voice"), dict) else {}
    provider = manifest.get("provider")
    reasons: list[str] = []
    if provider != VOICE_PROVIDER:
        reasons.append("provider_must_be_voxcpm2_local")
    if manifest.get("script_hash") != current_hash:
        reasons.append("voice_script_hash_stale")
    if production.get("provider") != VOICE_PROVIDER:
        reasons.append("production_voice_provider_must_be_voxcpm2_local")
    if production.get("status") != "READY":
        reasons.append("production_voice_not_ready")
    if production.get("temporary") is True:
        reasons.append("temporary_voice_is_not_allowed")
    if not production.get("path"):
        reasons.append("production_voice_path_missing")
    return {
        "pass": not reasons,
        "status": "READY" if not reasons else "BLOCKED",
        "provider": provider,
        "narrator": manifest.get("narrator"),
        "reason": "; ".join(reasons) if reasons else "VoxCPM2 production voice is bound to the current beat script.",
        "script_hash": current_hash,
    }
