#!/usr/bin/env python3
"""Build and gate the current episode animatic."""

from studio.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["animatic", *__import__("sys").argv[1:]]))
