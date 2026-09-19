"""Command-line entrypoint for the deployed AutoDL H3 worker."""

from hajimi_h3_worker.worker import main

if __name__ == "__main__":
    raise SystemExit(main())
