#!/usr/bin/env python3
"""Safe publish preflight wrapper; never changes visibility by itself."""

from studio.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["publish", *__import__("sys").argv[1:]]))
