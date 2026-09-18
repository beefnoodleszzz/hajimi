"""Register Hajimi's project-local Asset Browser libraries when Blender starts."""

from __future__ import annotations

import os
from pathlib import Path


def register_asset_libraries() -> dict[str, str]:
    try:
        import bpy  # type: ignore
    except ImportError:
        return {"status": "BLOCKED", "reason": "bpy is only available inside Blender"}
    root = Path(os.environ.get("HAJIMI_PROJECT_ROOT", Path(__file__).resolve().parents[3])).resolve()
    libraries = {
        "Hajimi Curated": root / "blender/assets/curated",
        "Hajimi Cameras": root / "blender/assets/cameras",
        "Hajimi Materials": root / "blender/assets/materials",
        "Hajimi Environments": root / "blender/assets/environments",
        "Hajimi FX": root / "blender/assets/fx",
    }
    registered: dict[str, str] = {}
    for name, path in libraries.items():
        path.mkdir(parents=True, exist_ok=True)
        entry = bpy.context.preferences.filepaths.asset_libraries.get(name)
        if entry is None:
            entry = bpy.context.preferences.filepaths.asset_libraries.new()
            entry.name = name
        entry.path = str(path)
        registered[name] = str(path)
    return registered


def register() -> dict[str, str]:
    """Blender startup hook; keep registration cheap and side-effect scoped."""

    return register_asset_libraries()


def unregister() -> None:
    """Startup libraries are project preferences and need no destructive cleanup."""

    return None


register()
