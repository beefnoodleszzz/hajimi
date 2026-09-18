"""Describe Blender work without hiding it behind an opaque generator."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def blender_capability() -> dict[str, Any]:
    binary = shutil.which("blender")
    return {"available": bool(binary), "binary": binary, "renderer": "eevee", "scriptable": True}


def write_shot_handoff(shot_dir: str | Path, shot: dict[str, Any]) -> Path:
    shot_dir = Path(shot_dir)
    path = shot_dir / "blender_handoff.json"
    path.write_text(json.dumps({"shot": shot, "capability": blender_capability()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
