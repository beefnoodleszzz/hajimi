#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

uv sync
uv run hajimi status EP001_earth-stop
echo "Hajimi V2 bootstrap complete."
