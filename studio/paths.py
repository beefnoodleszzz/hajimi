"""Canonical project paths.

The manifest is intentionally the only episode-level source of truth. This
module keeps path construction deterministic so each CLI command addresses the
same files without inventing temporary episode roots.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def project_root() -> Path:
    override = os.environ.get("HAJIMI_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class StudioPaths:
    root: Path

    @property
    def config(self) -> Path:
        return self.root / "config"

    @property
    def state_db(self) -> Path:
        return self.root / "studio" / "studio.sqlite3"

    @property
    def project_state(self) -> Path:
        return self.root / ".amv" / "project-state.json"

    @property
    def episodes(self) -> Path:
        return self.root / "episodes"

    def episode(self, episode_id: str) -> Path:
        return self.episodes / episode_id

    def manifest(self, episode_id: str) -> Path:
        return self.episode(episode_id) / "episode.yaml"

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path


PATHS = StudioPaths(project_root())
