from pathlib import Path

from studio.config import dump_yaml
from studio.pipeline.animatic import _animatic_target, _cadence_check, _static_hold_check, _load_storyboard_cards


def _manifest_with_shots() -> dict:
    return {
        "shots": [
            {"id": f"S{index:03d}", "time_start": index * 1.0, "time_end": (index + 1) * 1.0, "duration_target": 1.0}
            for index in range(8)
        ]
    }


def test_shot_count_does_not_prove_visual_cadence() -> None:
    result = _cadence_check(_manifest_with_shots(), {"visual_cadence": {"target_max_sec": 3.0}})

    assert result["status"] == "FAIL"
    assert any("visual_events are required" in error for error in result["errors"])


def test_visual_event_gap_over_configured_max_fails() -> None:
    manifest = {
        "shots": [{"time_start": 0, "time_end": 8, "duration_target": 8}],
        "visual_events": [
            {"time": 0, "type": "state_change", "description": "start"},
            {"time": 4, "type": "information_reveal", "description": "late reveal"},
            {"time": 8, "type": "impact", "description": "end"},
        ],
    }

    result = _cadence_check(manifest, {"visual_cadence": {"target_max_sec": 3.0}})

    assert result["status"] == "FAIL"
    assert result["value"]["long_gaps_sec"] == [4.0, 4.0]


def test_unjustified_and_justified_static_hold_are_distinguished() -> None:
    manifest = {
        "shots": [{"id": "S001", "time_start": 0, "time_end": 7, "duration_target": 7}],
    }
    probe = {"filters": {"video_events": [
        "freeze_start: 0",
        "freeze_duration: 6",
        "freeze_end: 6",
    ]}}
    settings = {"static_hold": {"max_sec": 5}}

    assert _static_hold_check(manifest, probe, settings)["status"] == "FAIL"
    manifest["shots"][0]["long_hold_justification"] = {"intentional": True, "reason": "readable title card"}
    assert _static_hold_check(manifest, probe, settings)["status"] == "PASS"


def test_animatic_target_changes_when_media_changes(tmp_path: Path) -> None:
    root = tmp_path
    episode_root = root / "episodes" / "EP001_test"
    (episode_root / "animatic" / "cards").mkdir(parents=True)
    (episode_root / "audio").mkdir()
    manifest_path = episode_root / "episode.yaml"
    dump_yaml({"episode_id": "EP001_test", "shots": []}, manifest_path)
    output = episode_root / "animatic" / "EP001_test_animatic.mp4"
    output.write_bytes(b"first")
    first = _animatic_target(root, episode_root, manifest_path, {"profile_version": "test"}, output)
    output.write_bytes(b"changed")
    second = _animatic_target(root, episode_root, manifest_path, {"profile_version": "test"}, output)

    assert first["asset_sha256"] != second["asset_sha256"]


def test_animatic_cards_are_loaded_from_current_episode_storyboard(tmp_path: Path) -> None:
    episode_root = tmp_path / "episodes" / "EP001_cloud-weight"
    storyboard_root = episode_root / "storyboard"
    storyboard_root.mkdir(parents=True)
    dump_yaml(
        {
            "shots": [
                {
                    "id": "S001",
                    "time_start": 0.0,
                    "time_end": 1.4,
                    "animatic_card": {
                        "kicker": "0.0 — 1.4 / HOOK",
                        "title": "A CLOUD ON A SCALE",
                        "sub": "THE SKY IS NOT EMPTY",
                        "kind": "cloud_scale",
                        "accent": "#ffb35c",
                    },
                }
            ]
        },
        storyboard_root / "storyboard_v01.yaml",
    )

    cards = _load_storyboard_cards(episode_root, {"shots": [{"id": "S001", "duration_target": 1.4}]})

    assert cards[0]["title"] == "A CLOUD ON A SCALE"
    assert cards[0]["kind"] == "cloud_scale"
