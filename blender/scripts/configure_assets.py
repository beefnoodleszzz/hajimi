"""Project-local Asset Browser indexing entrypoint."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("HAJIMI_PROJECT_ROOT", Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0, str(ROOT))

from studio.blender_stack import configure_assets  # noqa: E402


if __name__ == "__main__":
    print(configure_assets(ROOT))
