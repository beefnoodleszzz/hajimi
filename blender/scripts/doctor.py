"""Blender background entrypoint for the Hajimi doctor contract."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("HAJIMI_PROJECT_ROOT", Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0, str(ROOT))

from studio.blender_stack import run_blender_command  # noqa: E402


if __name__ == "__main__":
    print(run_blender_command(ROOT, "doctor"))
