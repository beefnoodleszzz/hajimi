"""Project-level state used by the Resolve orchestrator skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import write_json


def write_project_state(root: str | Path, state: dict[str, Any]) -> Path:
    path = Path(root) / ".amv" / "project-state.json"
    write_json(state, path)
    return path
