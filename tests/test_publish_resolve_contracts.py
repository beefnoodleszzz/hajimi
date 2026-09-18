from __future__ import annotations

import json
from pathlib import Path

import pytest

from studio.config import dump_yaml, write_json
from studio.media.hashing import sha256_file
from studio.publish.youtube import build_publish_plan, record_upload_readback
from studio.resolve.sync import record_resolve_readback, validate_resolve_readback


def _manifest() -> dict:
    return {
        "episode_id": "EP999_contract",
        "status": "qc_pending",
        "channel": "The World You Never Knew",
        "format": "youtube_short",
        "language": "en-US",
        "aspect_ratio": "9:16",
        "master": {"width": 1080, "height": 1920, "fps": 30, "sample_rate": 48000},
        "creative": {"promise": "Contract test", "hero_shot": "S001", "target_duration_sec": 2},
        "script": {"version": 1, "path": "script/script.md", "locked": False},
        "audio": {"narrator": "test", "target_lufs": -14, "true_peak_max_db": -1},
        "publish": {
            "title": "Contract title",
            "description": "Contract description",
            "ai_disclosure": True,
            "visibility": "private",
            "audience": {"made_for_kids": False},
        },
        "shots": [
            {
                "id": "S001",
                "role": "hook",
                "duration_target": 2,
                "time_start": 0,
                "time_end": 2,
                "method": "blender",
                "status": "approved",
            }
        ],
    }


def _ready_root(tmp_path: Path) -> tuple[Path, Path, Path]:
    episode_root = tmp_path / "episodes" / "EP999_contract"
    (episode_root / "publish").mkdir(parents=True)
    (episode_root / "qc").mkdir()
    (episode_root / "master").mkdir()
    (episode_root / "animatic").mkdir()
    (episode_root / "script").mkdir()
    shot_media = episode_root / "shots" / "S001" / "production" / "shot.mp4"
    shot_media.parent.mkdir(parents=True)
    shot_media.write_bytes(b"shot-contract-media")
    dump_yaml(
        {
            "id": "S001",
            "version": 1,
            "role": "hook",
            "method": "blender",
            "status": "qc_pending",
            "intent": "Contract shot",
            "renderer": "eevee",
            "camera": {"lens_mm": 24},
            "output": {"production": "production/shot.mp4", "provenance": "provenance.json"},
        },
        shot_media.parent.parent / "shot.yaml",
    )
    write_json(
        {
            "schema_version": "shot-production-provenance-v1",
            "episode_id": "EP999_contract",
            "shot_id": "S001",
            "candidate_id": "S001-contract-001",
            "media_type": "video",
            "output_asset": "episodes/EP999_contract/shots/S001/production/shot.mp4",
            "output_sha256": sha256_file(shot_media),
            "qc": {"fast_qc": "PASS"},
            "license": {"source": "test"},
        },
        shot_media.parent.parent / "provenance.json",
    )
    dump_yaml(_manifest(), episode_root / "episode.yaml")
    master = episode_root / "master" / "EP999_contract_master_final.mp4"
    master.write_bytes(b"master-contract-media")
    write_json(
        {
            "decision": "PASS",
            "master_sha256": sha256_file(master),
            "human_review": {"status": "PASS", "reviewer": "human", "confirmed_at": "2026-09-18T00:00:00Z"},
            "human_review_recorded": True,
        },
        episode_root / "qc" / "master_report.json",
    )
    write_json({"decision": "PASS"}, episode_root / "animatic" / "gate.json")
    write_json(
        {
            "episode_id": "EP999_contract",
            "shots": [
                {
                    "shot_id": "S001",
                    "decision": "PASS",
                    "source": str(shot_media),
                    "asset_hash": sha256_file(shot_media),
                }
            ],
        },
        episode_root / "qc" / "report.json",
    )
    write_json(
        {"output": str(master), "master_type": "resolve_master", "master_sha256": sha256_file(master)},
        episode_root / "master" / "build.json",
    )
    write_json(
        {
            "timeline_name": "EP999_Master",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "sample_rate": 48000,
            "shot_ids": ["S001"],
            "master_path": str(master),
        },
        episode_root / "edit" / "resolve_production_readback.json",
    )
    return tmp_path, episode_root, master


def test_publish_plan_has_ego_upload_contract_and_human_gate(tmp_path: Path) -> None:
    root, _, master = _ready_root(tmp_path)

    plan = build_publish_plan(root, "EP999_contract")

    assert plan["status"] == "READY"
    assert plan["upload"]["method"] == "ego-browser"
    assert plan["upload"]["operation"] == "uploadFile"
    assert plan["master"]["sha256"] == sha256_file(master)
    assert plan["readback_contract"]["required"] == ["video_url", "visibility", "metadata", "checks", "processing", "schedule"]


def test_upload_readback_is_validated_and_persisted(tmp_path: Path) -> None:
    root, _, master = _ready_root(tmp_path)
    plan = build_publish_plan(root, "EP999_contract")
    readback = {
        "video_url": "https://studio.youtube.com/video/abc123",
        "visibility": "private",
        "master_sha256": sha256_file(master),
        "metadata": {
            "title": plan["metadata"]["title"],
            "description": plan["metadata"]["description"],
            "audience": plan["metadata"]["audience"],
            "ai_disclosure": plan["metadata"]["ai_use"],
        },
        "checks": {"copyright": "running", "likeness": "running", "upload": "complete"},
        "processing": {"status": "processed"},
        "schedule": plan["metadata"]["schedule"],
    }

    result = record_upload_readback(root, "EP999_contract", readback)

    assert result["status"] == "UPLOADED_PRIVATE"
    assert result["video_url"] == readback["video_url"]
    saved = json.loads((root / "episodes/EP999_contract/publish/youtube.json").read_text())
    assert saved["metadata_readback"]["title"] == plan["metadata"]["title"]
    assert saved["youtube_checks"]["upload"] == "complete"


def test_resolve_readback_rejects_legacy_timeline_and_accepts_current_contract() -> None:
    expected = {
        "episode_id": "EP999_contract",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "sample_rate": 48000,
        "shot_ids": ["S001"],
    }
    accepted = {
        "timeline_name": "EP999_Master",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "sample_rate": 48000,
        "shot_ids": ["S001"],
        "master_path": "/tmp/master.mp4",
    }
    assert validate_resolve_readback(expected, accepted)["decision"] == "PASS"
    rejected = {**accepted, "timeline_name": "V03_Final"}
    result = validate_resolve_readback(expected, rejected)
    assert result["decision"] == "FAIL"
    assert "legacy_timeline" in result["errors"]


def test_resolve_readback_normalizes_string_numeric_fields() -> None:
    expected = {
        "episode_id": "EP999_contract",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "sample_rate": 48000,
        "shot_ids": ["S001"],
    }
    readback = {
        "timeline_name": "EP999_Master",
        "width": "1080",
        "height": "1920",
        "fps": "30/1",
        "sample_rate": "48000",
        "shot_ids": ["S001"],
        "master_path": "/tmp/master.mp4",
    }
    assert validate_resolve_readback(expected, readback)["decision"] == "PASS"


def test_resolve_readback_rejects_export_for_a_different_master(tmp_path: Path) -> None:
    expected_master = tmp_path / "episodes" / "EP999_contract" / "master" / "current.mp4"
    result = validate_resolve_readback(
        {
            "episode_id": "EP999_contract",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "sample_rate": 48000,
            "shot_ids": ["S001"],
            "master_path": str(expected_master),
        },
        {
            "timeline_name": "EP999_Master",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "sample_rate": 48000,
            "shot_ids": ["S001"],
            "master_path": "episodes/EP999_contract/master/old.mp4",
        },
        root=tmp_path,
    )

    assert result["decision"] == "FAIL"
    assert "master_path_mismatch" in result["errors"]


def test_resolve_readback_persists_raw_export_and_separate_validation(tmp_path: Path) -> None:
    root, episode_root, master = _ready_root(tmp_path)
    readback = {
        "timeline_name": "EP999_Master",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "sample_rate": 48000,
        "shot_ids": ["S001"],
        "master_path": str(master),
    }

    result = record_resolve_readback(root, "EP999_contract", readback)

    assert result["decision"] == "PASS"
    raw = json.loads((episode_root / "edit" / "resolve_production_readback.json").read_text())
    validation = json.loads((episode_root / "edit" / "resolve_readback_validation.json").read_text())
    assert raw["timeline_name"] == "EP999_Master"
    assert validation["decision"] == "PASS"
