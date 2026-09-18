"""Thin background render entrypoint; policy remains in ``studio.blender_stack``."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("HAJIMI_PROJECT_ROOT", Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0, str(ROOT))

from studio.blender_stack import run_blender_command  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("shot_id", nargs="?")
    parser.add_argument("--operation", choices=("build", "preview", "render", "qc"), default="render")
    parser.add_argument("--profile")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run_blender_command(ROOT, args.operation, args.target, args.shot_id, profile=args.profile, force=args.force)
    print(result)
    return 0 if result.get("decision", result.get("status")) not in {"FAIL", "BLOCKED", "BLOCKED_NO_SEQUENCE", "BLOCKED_PREFLIGHT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
