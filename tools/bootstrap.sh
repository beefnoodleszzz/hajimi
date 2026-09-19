#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

uv sync
EPISODE_ID="${EPISODE_ID:?Set EPISODE_ID to an existing episode, for example EP001_cloud-weight}"
uv run hajimi status "${EPISODE_ID}"
echo "Hajimi V2 bootstrap complete."
