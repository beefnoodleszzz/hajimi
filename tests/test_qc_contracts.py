from __future__ import annotations

from pathlib import Path

from studio.config import dump_yaml, write_json
from studio.media.audio import audio_qc
from studio.qc.engine import _asr_needs_review, _find_master, _media_for_shot, run_episode_qc


def test_find_master_uses_resolve_registered_output(tmp_path: Path) -> None:
    master_root = tmp_path / "master"
    master_root.mkdir()
    old = master_root / "EP001_master_final.mp4"
    current = master_root / "EP001_master_final_v2.mp4"
    old.write_bytes(b"old")
    current.write_bytes(b"current")
    write_json({"output": str(current), "master_type": "resolve_master"}, master_root / "build.json")

    assert _find_master(tmp_path) == current


def test_episode_qc_does_not_pass_when_a_manifest_shot_has_no_media(tmp_path: Path) -> None:
    episode_root = tmp_path / "episodes" / "EP001_empty"
    (episode_root / "shots" / "S001").mkdir(parents=True)
    manifest = {
        "episode_id": "EP001_empty",
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
        "shots": [{"id": "S001", "role": "test", "duration_target": 1, "method": "fusion", "status": "qc_pending"}],
    }
    dump_yaml(manifest, episode_root / "episode.yaml")

    result = run_episode_qc("EP001_empty", root=tmp_path)

    assert result["decision"] == "FAIL"
    assert result["shots"][0]["decision"] == "FAIL"


def test_audio_qc_does_not_attempt_asr_for_video_only_media(monkeypatch) -> None:
    monkeypatch.setattr(
        "studio.media.audio.probe_media",
        lambda _path: {"ok": True, "streams": [{"codec_type": "video"}], "audio": {}},
    )

    result = audio_qc("video-only.mp4")

    assert result == {"status": "NO_AUDIO", "asr": {"status": "not_run"}}


def test_master_asr_gate_reviews_any_nonpassing_transcript_diff() -> None:
    asr = {
        "status": "PASS",
        "language_match": True,
        "diff": {"decision": "REVIEW", "coverage": 0.99, "missing_key_tokens": []},
    }

    assert _asr_needs_review(asr, "The locked narration") is True
    assert _asr_needs_review(
        {"status": "PASS", "language_match": True, "diff": {"decision": "PASS"}},
        "The locked narration",
    ) is False


def test_active_media_resolves_episode_relative_manifest_path(tmp_path: Path) -> None:
    episode_root = tmp_path / "episodes" / "EP001_relative"
    shot_dir = episode_root / "shots" / "S001"
    media = shot_dir / "production" / "shot.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"media")

    resolved = _media_for_shot(
        shot_dir,
        "shots/S001/production/shot.mp4",
        base_dir=episode_root,
    )

    assert resolved == media.resolve()


def test_missing_explicit_active_media_does_not_fallback_to_another_file(tmp_path: Path) -> None:
    episode_root = tmp_path / "episodes" / "EP001_relative"
    shot_dir = episode_root / "shots" / "S001"
    fallback = shot_dir / "production" / "wrong.mp4"
    fallback.parent.mkdir(parents=True)
    fallback.write_bytes(b"wrong")

    assert _media_for_shot(shot_dir, "production/missing.mp4", base_dir=episode_root) is None


def test_resolve_handoff_does_not_fallback_when_explicit_media_is_missing(tmp_path: Path) -> None:
    from studio.resolve.sync import _shot_media

    episode_root = tmp_path / "episodes" / "EP001_relative"
    shot_dir = episode_root / "shots" / "S001"
    production = shot_dir / "production"
    production.mkdir(parents=True)
    (production / "fallback.mp4").write_bytes(b"fallback")

    media = _shot_media(
        tmp_path,
        episode_root,
        "EP001_relative",
        {"id": "S001", "active_media": "production/missing.mp4"},
    )

    assert media["active"] is None
    assert media["videos"] == []
