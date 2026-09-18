#!/usr/bin/env python3
"""Build a contact sheet from labelled `label=path` inputs."""

from __future__ import annotations

import argparse

from studio.media.contact_sheet import build_contact_sheet


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination")
    parser.add_argument("items", nargs="+")
    args = parser.parse_args()
    rows = []
    for item in args.items:
        if "=" not in item:
            raise SystemExit(f"item must be label=path: {item}")
        label, path = item.split("=", 1)
        rows.append((label, path))
    print(build_contact_sheet(rows, args.destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
