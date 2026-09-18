"""Thin, explicit SQLite repository used by CLI and QC workers."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import initialize_database


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        initialize_database(self.path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=60)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 60000")
        return connection

    def sync_manifest(self, manifest: dict[str, Any], manifest_path: str | Path, manifest_hash: str) -> None:
        episode_id = str(manifest["episode_id"])
        timestamp = now_iso()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO episodes(episode_id, manifest_path, manifest_hash, status, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(episode_id) DO UPDATE SET manifest_path=excluded.manifest_path,
                   manifest_hash=excluded.manifest_hash, status=excluded.status, updated_at=excluded.updated_at""",
                (episode_id, str(Path(manifest_path).resolve()), manifest_hash, str(manifest.get("status", "planned")), timestamp),
            )
            for shot in manifest.get("shots", []):
                connection.execute(
                    """INSERT INTO shots(episode_id, shot_id, role, method, status, duration_target, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(episode_id, shot_id) DO UPDATE SET role=excluded.role, method=excluded.method,
                       status=excluded.status, duration_target=excluded.duration_target, updated_at=excluded.updated_at""",
                    (
                        episode_id,
                        str(shot["id"]),
                        str(shot.get("role", "")),
                        str(shot.get("method", "")),
                        str(shot.get("status", "planned")),
                        shot.get("duration_target"),
                        timestamp,
                    ),
                )
            shot_ids = [str(shot["id"]) for shot in manifest.get("shots", [])]
            if shot_ids:
                placeholders = ",".join("?" for _ in shot_ids)
                connection.execute(
                    f"DELETE FROM shots WHERE episode_id=? AND shot_id NOT IN ({placeholders})",
                    (episode_id, *shot_ids),
                )
            else:
                connection.execute("DELETE FROM shots WHERE episode_id=?", (episode_id,))
            connection.commit()

    def upsert_asset(self, asset_hash: str, path: str | Path, kind: str, metadata: dict[str, Any]) -> None:
        timestamp = now_iso()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO assets(asset_hash, path, kind, metadata_json, first_seen_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(asset_hash) DO UPDATE SET path=excluded.path, kind=excluded.kind,
                   metadata_json=excluded.metadata_json, last_seen_at=excluded.last_seen_at""",
                (asset_hash, str(Path(path).resolve()), kind, json.dumps(metadata, ensure_ascii=False), timestamp, timestamp),
            )
            connection.commit()

    def get_cached_qc(self, asset_hash: str, scope: str, profile_version: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT decision, result_json, created_at FROM qc_results WHERE asset_hash=? AND scope=? AND profile_version=?",
                (asset_hash, scope, profile_version),
            ).fetchone()
        if row is None:
            return None
        result = json.loads(row["result_json"])
        result["decision"] = row["decision"]
        result["cached_at"] = row["created_at"]
        result["cache_hit"] = True
        return result

    def put_qc(self, asset_hash: str, scope: str, profile_version: str, decision: str, result: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO qc_results(asset_hash, scope, profile_version, decision, result_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(asset_hash, scope, profile_version) DO UPDATE SET decision=excluded.decision,
                   result_json=excluded.result_json, created_at=excluded.created_at""",
                (asset_hash, scope, profile_version, decision, json.dumps(result, ensure_ascii=False), now_iso()),
            )
            connection.commit()

    def update_shot_status(self, episode_id: str, shot_id: str, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE shots SET status=?, updated_at=? WHERE episode_id=? AND shot_id=?",
                (status, now_iso(), episode_id, shot_id),
            )
            connection.commit()

    def episode(self, episode_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM episodes WHERE episode_id=?", (episode_id,)).fetchone()
        return dict(row) if row else None

    def shots(self, episode_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM shots WHERE episode_id=? ORDER BY shot_id", (episode_id,)).fetchall()
        return [dict(row) for row in rows]

    def record_publish(self, episode_id: str, event_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO publish_events(episode_id, event_id, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (episode_id, event_id, json.dumps(payload, ensure_ascii=False), now_iso()),
            )
            connection.commit()

    def upsert_analytics(self, episode_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO analytics_records(episode_id, payload_json, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT(episode_id) DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at""",
                (episode_id, json.dumps(payload, ensure_ascii=False), now_iso()),
            )
            connection.commit()
