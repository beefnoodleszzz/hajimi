#!/usr/bin/env python3
"""Inspect and update the pinned Hajimi upstream skill set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio.skills import check_skill_updates, skills_doctor, skills_list, sync_skills, write_initial_skill_lock


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "verify", "check-updates", "sync", "lock"):
        command = sub.add_parser(name)
        if name == "sync":
            command.add_argument("skills", nargs="*")
        command.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command in {"status", "verify"}:
        result = skills_doctor() if args.command == "verify" else {"status": "PASS", "skills": skills_list()["skills"]}
    elif args.command == "check-updates":
        result = check_skill_updates()
    elif args.command == "sync":
        result = sync_skills(args.skills or None)
    else:
        result = write_initial_skill_lock()
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
