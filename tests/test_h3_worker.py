from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from remote.hajimi_h3_worker import worker


def test_worker_uses_bundled_versioned_workflows() -> None:
    for workflow_id in ("h3_i2va_api", "h3_fl2va_api", "h3_ref2va_api"):
        identity = worker._workflow_identity(workflow_id)
        assert identity["present"] is True
        assert identity["workflow_version"] == 1


def test_submit_cli_accepts_json_flag() -> None:
    root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, "PYTHONPATH": str(root / "remote")}
    result = subprocess.run(
        [sys.executable, str(root / "remote" / "worker.py"), "submit", "--help"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--json" in result.stdout
