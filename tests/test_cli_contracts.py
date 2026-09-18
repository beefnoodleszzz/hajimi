from __future__ import annotations

from pathlib import Path

from studio.cli import main
from studio.config import dump_yaml


def test_master_cli_requires_a_real_resolve_export(tmp_path: Path) -> None:
    episode_root = tmp_path / "episodes" / "EP001_contract"
    episode_root.mkdir(parents=True)
    manifest = {
        "episode_id": "EP001_contract",
        "status": "qc_pending",
        "channel": "test",
        "format": "youtube_short",
        "language": "en-US",
        "aspect_ratio": "9:16",
        "master": {"width": 1080, "height": 1920, "fps": 30, "sample_rate": 48000},
        "creative": {"promise": "test", "hero_shot": "S001", "target_duration_sec": 1},
        "script": {"path": "script.md"},
        "audio": {"narrator": "test", "target_lufs": -14, "true_peak_max_db": -1},
        "publish": {"title": "test", "description": "test", "ai_disclosure": True, "visibility": "private"},
        "shots": [{"id": "S001", "role": "hook", "duration_target": 1, "method": "blender", "status": "qc_pending"}],
    }
    dump_yaml(manifest, episode_root / "episode.yaml")

    assert main(["--root", str(tmp_path), "master", "EP001_contract"]) == 2
