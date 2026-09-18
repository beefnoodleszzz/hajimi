#!/usr/bin/env python3
"""Compatibility-free wrapper around `hajimi qc`."""

from studio.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["qc", *__import__("sys").argv[1:]]))
