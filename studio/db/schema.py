"""SQLite schema for incremental production state."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS episodes (
  episode_id TEXT PRIMARY KEY,
  manifest_path TEXT NOT NULL,
  manifest_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shots (
  episode_id TEXT NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
  shot_id TEXT NOT NULL,
  role TEXT NOT NULL,
  method TEXT NOT NULL,
  status TEXT NOT NULL,
  duration_target REAL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (episode_id, shot_id)
);

CREATE TABLE IF NOT EXISTS assets (
  asset_hash TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  kind TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS qc_results (
  asset_hash TEXT NOT NULL REFERENCES assets(asset_hash) ON DELETE CASCADE,
  scope TEXT NOT NULL,
  profile_version TEXT NOT NULL,
  decision TEXT NOT NULL,
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (asset_hash, scope, profile_version)
);

CREATE TABLE IF NOT EXISTS publish_events (
  episode_id TEXT NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
  event_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (episode_id, event_id)
);

CREATE TABLE IF NOT EXISTS analytics_records (
  episode_id TEXT PRIMARY KEY REFERENCES episodes(episode_id) ON DELETE CASCADE,
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_qc_scope ON qc_results(scope, profile_version);
"""


def initialize_database(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        connection.commit()
