from __future__ import annotations

from pathlib import Path

from studio.config import dump_yaml
from studio.creative import discover_ideas, generate_creative_package, run_tournament, validate_creative_package
from studio.voice.manifest import VOICE_PROVIDER, production_voice_check, script_hash, write_voice_manifest


def test_idea_discovery_and_tournament_produce_structured_shortlist() -> None:
    analysis = discover_ideas("EP001_earth-stop", {"episode_id": "EP001_earth-stop"})
    tournament = run_tournament(analysis)

    assert len(analysis["ideas"]) >= 7
    assert all(
        {"id", "viewer_question", "hook_potential", "visual_potential", "story_potential", "production_fit", "risk", "evidence"}
        <= idea.keys()
        for idea in analysis["ideas"]
    )
    assert len(tournament["comparisons"]) >= 3
    assert len(tournament["angle_variants"]) == 10
    assert tournament["selected_candidate"]["hook"] == "human_inertia"


def test_creative_package_writes_both_generation_plan_contracts(tmp_path: Path) -> None:
    episode_root = tmp_path / "episodes" / "EP001_earth-stop"
    dump_yaml({"episode_id": "EP001_earth-stop", "creative": {}, "audio": {}}, episode_root / "episode.yaml")

    result = generate_creative_package(tmp_path, "EP001_earth-stop", force=True)

    assert result["status"] == "PASS"
    package_dir = episode_root / "creative"
    assert not validate_creative_package(package_dir)
    assert (package_dir / "visual_concept.yaml").is_file()
    assert (package_dir / "generation_plan.yaml").is_file()
    assert (episode_root / "production" / "generation_plan.yaml").is_file()


def test_production_voice_check_rejects_temporary_and_stale_voice(tmp_path: Path) -> None:
    episode_root = tmp_path / "episodes" / "EP001_earth-stop"
    beat_script = episode_root / "creative" / "beat_script.yaml"
    dump_yaml({"schema_version": "beat-script-v1", "beats": [{"beat_id": "B01"}]}, beat_script)
    output = episode_root / "audio" / "voxcpm2" / "run_0001"
    output.mkdir(parents=True)

    write_voice_manifest(
        episode_root,
        {
            "provider": VOICE_PROVIDER,
            "script_hash": script_hash(episode_root),
            "production_voice": {"provider": VOICE_PROVIDER, "status": "READY", "temporary": True, "path": str(output)},
        },
    )
    blocked = production_voice_check(episode_root)
    assert blocked["pass"] is False
    assert "temporary_voice_is_not_allowed" in blocked["reason"]

    write_voice_manifest(
        episode_root,
        {
            "provider": VOICE_PROVIDER,
            "script_hash": "stale",
            "production_voice": {"provider": VOICE_PROVIDER, "status": "READY", "temporary": False, "path": str(output)},
        },
    )
    stale = production_voice_check(episode_root)
    assert stale["pass"] is False
    assert "voice_script_hash_stale" in stale["reason"]


def test_production_voice_check_rejects_other_provider(tmp_path: Path) -> None:
    episode_root = tmp_path / "episodes" / "EP001_earth-stop"
    output = episode_root / "audio" / "other" / "run_0001"
    output.mkdir(parents=True)
    write_voice_manifest(
        episode_root,
        {
            "provider": "qwen_tts",
            "script_hash": None,
            "production_voice": {"provider": "qwen_tts", "status": "READY", "temporary": False, "path": str(output)},
        },
    )

    blocked = production_voice_check(episode_root)

    assert blocked["pass"] is False
    assert "provider_must_be_voxcpm2_local" in blocked["reason"]
    assert "production_voice_provider_must_be_voxcpm2_local" in blocked["reason"]


def test_voxcpm2_unavailable_is_blocked_without_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VOXCPM_PROJECT", str(tmp_path / "missing-voxcpm2"))
    from studio.voice.voxcpm2 import doctor

    result = doctor(tmp_path, "EP001_earth-stop")

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "BLOCKED_VOXCPM2"
    assert result["fallback"] is None
