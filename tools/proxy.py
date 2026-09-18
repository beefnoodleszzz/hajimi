#!/usr/bin/env python3
"""Thin CLI wrapper for the shared 540p proxy implementation."""

from __future__ import annotations

import argparse

from studio.media.proxy import build_proxy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--bitrate", default="3M")
    args = parser.parse_args()
    print(build_proxy(args.source, args.destination, args.height, args.bitrate))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
