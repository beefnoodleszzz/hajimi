from __future__ import annotations

import json
from pathlib import Path

from studio.config import dump_yaml
from studio.media.hashing import sha256_file
from studio.provenance import validate_shot_provenance


def test_shot_provenance_validates_output_hash_and_ai_fields(tmp_path: Path) -> None:
    episode_root = tmp_path / "episodes" / "EP001_contract" / "shots" / "S001"
    episode_root.mkdir(parents=True)
    output = episode_root / "production.mp4"
    output.write_bytes(b"production")
    sidecar = episode_root / "provenance.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": "ai-visual-provenance-v1",
                "episode_id": "EP001_contract",
                "shot_id": "S001",
                "candidate_id": "S001-candidate-001",
                "media_type": "video",
                "model_provider": "Google Flow",
                "model_version": "Omni",
                "generation_mode": "image_to_video",
                "seed": None,
                "prompt": "controlled motion",
                "references": [],
                "output_asset": "episodes/EP001_contract/shots/S001/production.mp4",
                "output_sha256": sha256_file(output),
                "qc": {"fast_qc": "PASS"},
                "license": {"provider_terms": "test"},
            }
        ),
        encoding="utf-8",
    )
    shot = {"id": "S001", "method": "ai_video", "output": {"provenance": "provenance.json"}}

    result = validate_shot_provenance(tmp_path, "EP001_contract", shot)

    assert result["valid"] is True


def test_shot_provenance_rejects_changed_output(tmp_path: Path) -> None:
    episode_root = tmp_path / "episodes" / "EP001_contract" / "shots" / "S001"
    episode_root.mkdir(parents=True)
    output = episode_root / "production.mp4"
    output.write_bytes(b"changed")
    sidecar = episode_root / "provenance.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": "shot-production-provenance-v1",
                "candidate_id": "S001-candidate-001",
                "media_type": "video",
                "output_asset": "episodes/EP001_contract/shots/S001/production.mp4",
                "output_sha256": "stale",
                "qc": {},
                "license": {},
            }
        ),
        encoding="utf-8",
    )
    shot = {"id": "S001", "method": "blender", "output": {"provenance": "provenance.json"}}

    result = validate_shot_provenance(tmp_path, "EP001_contract", shot)

    assert result["valid"] is False
    assert "output_sha256" in result["errors"]
