"""Analytics record shape for retention and production-method learning."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import load_yaml, write_json
from ..db import StateStore
from ..manifest import load_manifest, manifest_hash

ANALYTICS_TEMPLATE: dict[str, Any] = {
    "video": {
        "episode_id": None,
        "platform": "youtube",
        "published_at": None,
        "format": "youtube_short",
    },
    "metadata": {"title": None, "language": "en-US", "duration_sec": None},
    "creative": {"hook_type": "immediate_consequence", "hero_shot_type": "physics_mismatch", "time_to_anomaly": 0.38},
    "timeline_metrics": {"avg_shot_duration": None, "shot_count": None, "visual_peak_count": None, "audio_peak_count": None},
    "production_metrics": {"blender_seconds": 0.0, "ai_video_seconds": 0.0, "fusion_seconds": 0.0, "footage_seconds": 0.0, "static_plate_seconds": 0.0, "qc_fail_count": 0, "regen_count": 0, "production_mix": {}},
    "retention": {"views": None, "avd_sec": None, "apv": None, "retention_drop_1": None, "retention_drop_2": None, "comments": None, "likes": None, "shares": None, "subs": None},
    "learnings": [],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_from_manifest(root: Path, episode_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    """Build the initial analytics record from the episode source of truth."""

    record = copy.deepcopy(ANALYTICS_TEMPLATE)
    shots = [shot for shot in manifest.get("shots", []) if isinstance(shot, dict)]
    durations = [float(shot.get("duration_target", 0) or 0) for shot in shots]
    total_duration = sum(durations)
    methods = {"blender": "blender_seconds", "ai_video": "ai_video_seconds", "fusion": "fusion_seconds", "footage": "footage_seconds", "animatic_card": "static_plate_seconds", "ai_image": "static_plate_seconds"}
    method_seconds: dict[str, float] = {}
    for shot, duration in zip(shots, durations):
        key = methods.get(str(shot.get("method")))
        if key:
            method_seconds[key] = round(method_seconds.get(key, 0.0) + duration, 3)
    creative = manifest.get("creative", {}) if isinstance(manifest.get("creative"), dict) else {}
    first_role = str(shots[0].get("role", "")) if shots else ""
    hero_id = creative.get("hero_shot")
    hero_shot = next((shot for shot in shots if shot.get("id") == hero_id), None)
    hero_role = str(hero_shot.get("role", "")) if isinstance(hero_shot, dict) else ""
    peak_roles = ("hook", "hero", "payoff", "restart", "mismatch", "reveal", "speed", "distance")
    visual_peaks = sum(
        1
        for shot in shots
        if bool(shot.get("visual_peak"))
        or any(token in str(shot.get("role", "")).lower() for token in peak_roles)
    )
    audio_events = manifest.get("audio", {}).get("events", []) if isinstance(manifest.get("audio"), dict) else []
    if not audio_events:
        sound_design_path = root / "episodes" / episode_id / "audio" / "sound_design.yaml"
        if sound_design_path.exists():
            try:
                sound_design = load_yaml(sound_design_path)
                audio_events = sound_design.get("events", []) if isinstance(sound_design, dict) else []
            except (OSError, ValueError):
                audio_events = []
    record["video"].update({"episode_id": episode_id, "published_at": manifest.get("publish", {}).get("published_at")})
    record["creative"].update(
        {
            "hook_type": creative.get("hook_type") or first_role or "unknown",
            "hero_shot_type": creative.get("hero_shot_type") or hero_role or "unknown",
            "time_to_anomaly": creative.get("time_to_anomaly_sec", record["creative"].get("time_to_anomaly")),
        }
    )
    record["metadata"].update(
        {
            "title": manifest.get("publish", {}).get("title"),
            "language": manifest.get("language", "en-US"),
            "duration_sec": round(total_duration, 3) if total_duration else None,
        }
    )
    record["timeline_metrics"].update(
        {
            "avg_shot_duration": round(total_duration / len(durations), 3) if durations else None,
            "shot_count": len(shots),
            "visual_peak_count": visual_peaks,
            "audio_peak_count": len(audio_events) if isinstance(audio_events, list) else 0,
        }
    )
    record["production_metrics"].update(method_seconds)
    record["production_metrics"]["production_mix"] = {
        key.removesuffix("_seconds"): round(value / total_duration, 4) if total_duration else 0.0
        for key, value in method_seconds.items()
    }
    qc_report = root / "episodes" / episode_id / "qc" / "report.json"
    if qc_report.exists():
        try:
            report = json.loads(qc_report.read_text(encoding="utf-8"))
            record["production_metrics"]["qc_fail_count"] = sum(1 for item in report.get("shots", []) if item.get("decision") == "FAIL")
        except (OSError, json.JSONDecodeError):
            pass
    return record


def _write_optional_exports(root: Path, episode_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """Write durable local analytics exports without making optional deps core."""

    analytics_root = root / "analytics"
    analytics_root.mkdir(parents=True, exist_ok=True)
    row = {"episode_id": episode_id, "updated_at": _utc_now(), **record}
    jsonl = analytics_root / "records.jsonl"
    existing: list[str] = []
    if jsonl.exists():
        existing = [line for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = []
    for line in existing:
        try:
            parsed = json.loads(line)
            if parsed.get("episode_id") != episode_id:
                rows.append(parsed)
        except json.JSONDecodeError:
            continue
    rows.append(row)
    jsonl.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows), encoding="utf-8")
    result: dict[str, Any] = {"jsonl": str(jsonl), "duckdb": None, "parquet": None, "optional_status": {}}
    try:
        import duckdb  # type: ignore

        database = analytics_root / "analytics.duckdb"
        connection = duckdb.connect(str(database))
        connection.execute(
            """CREATE TABLE IF NOT EXISTS video_records (
                episode_id VARCHAR PRIMARY KEY,
                updated_at VARCHAR,
                title VARCHAR,
                language VARCHAR,
                duration_sec DOUBLE,
                shot_count INTEGER,
                avg_shot_duration DOUBLE,
                hook_type VARCHAR,
                hero_shot_type VARCHAR,
                blender_seconds DOUBLE,
                ai_video_seconds DOUBLE,
                static_plate_seconds DOUBLE,
                fusion_seconds DOUBLE,
                footage_seconds DOUBLE,
                qc_fail_count INTEGER,
                payload_json VARCHAR
            )"""
        )
        existing_columns = {str(item[1]) for item in connection.execute("PRAGMA table_info('video_records')").fetchall()}
        required_columns = {
            "title": "VARCHAR",
            "language": "VARCHAR",
            "duration_sec": "DOUBLE",
            "shot_count": "INTEGER",
            "avg_shot_duration": "DOUBLE",
            "hook_type": "VARCHAR",
            "hero_shot_type": "VARCHAR",
            "blender_seconds": "DOUBLE",
            "ai_video_seconds": "DOUBLE",
            "static_plate_seconds": "DOUBLE",
            "fusion_seconds": "DOUBLE",
            "footage_seconds": "DOUBLE",
            "qc_fail_count": "INTEGER",
            "payload_json": "VARCHAR",
        }
        for column, type_name in required_columns.items():
            if column not in existing_columns:
                connection.execute(f"ALTER TABLE video_records ADD COLUMN {column} {type_name}")
        production = record.get("production_metrics", {})
        timeline = record.get("timeline_metrics", {})
        metadata = record.get("metadata", {})
        creative = record.get("creative", {})
        connection.execute(
            """INSERT OR REPLACE INTO video_records (
                episode_id, updated_at, title, language, duration_sec,
                shot_count, avg_shot_duration, hook_type, hero_shot_type,
                blender_seconds, ai_video_seconds, static_plate_seconds,
                fusion_seconds, footage_seconds, qc_fail_count, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                row["episode_id"],
                row["updated_at"],
                metadata.get("title"),
                metadata.get("language"),
                metadata.get("duration_sec"),
                timeline.get("shot_count"),
                timeline.get("avg_shot_duration"),
                creative.get("hook_type"),
                creative.get("hero_shot_type"),
                production.get("blender_seconds", 0.0),
                production.get("ai_video_seconds", 0.0),
                production.get("static_plate_seconds", 0.0),
                production.get("fusion_seconds", 0.0),
                production.get("footage_seconds", 0.0),
                production.get("qc_fail_count", 0),
                json.dumps(record, ensure_ascii=False),
            ],
        )
        parquet = analytics_root / "video_records.parquet"
        connection.execute("COPY (SELECT * FROM video_records) TO ? (FORMAT PARQUET)", [str(parquet)])
        connection.close()
        result["duckdb"] = str(database)
        result["parquet"] = str(parquet)
        result["optional_status"] = {"duckdb": "PASS", "parquet": "PASS"}
    except ImportError:
        result["optional_status"] = {"duckdb": "BLOCKED_OPTIONAL_DEPENDENCY", "parquet": "BLOCKED_OPTIONAL_DEPENDENCY"}
    except Exception as exc:
        result["optional_status"] = {"duckdb": "FAIL", "parquet": "FAIL", "error": type(exc).__name__}
    write_json(result, analytics_root / "export_status.json")
    return result


def initialize_record(root: str | Path, episode_id: str) -> Path:
    root_path = Path(root).resolve()
    destination = root_path / "episodes" / episode_id / "analytics.json"
    manifest_path = destination.parent / "episode.yaml"
    if manifest_path.exists():
        manifest = load_manifest(manifest_path)
        record = _record_from_manifest(root_path, episode_id, manifest)
    else:
        record = copy.deepcopy(ANALYTICS_TEMPLATE)
        record["video"]["episode_id"] = episode_id
    write_json(record, destination)
    if manifest_path.exists():
        store = StateStore(root_path / "studio" / "studio.sqlite3")
        store.sync_manifest(manifest, manifest_path, manifest_hash(manifest_path))
        store.upsert_analytics(episode_id, record)
    _write_optional_exports(root_path, episode_id, record)
    return destination
