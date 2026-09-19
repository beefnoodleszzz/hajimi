from pathlib import Path
import tempfile

from studio.config import dump_yaml, load_yaml
from studio.manifest import load_manifest, load_shot_manifest, validate_manifest, write_manifest


EPISODE_ID = "EP099_manifest-fixture"
METHODS = ["h3_i2v", "hybrid_ai", "h3_fl2v", "h3_ref2v", "fusion", "footage", "animatic_card", "ai_image"]


def _example_manifest() -> dict:
    return {
        "episode_id": EPISODE_ID,
        "status": "research",
        "channel": "Test Channel",
        "format": "youtube_short",
        "language": "en-US",
        "aspect_ratio": "9:16",
        "master": {"width": 1080, "height": 1920, "fps": 30, "sample_rate": 48000},
        "creative": {"promise": "Test promise", "hero_shot": "S001", "target_duration_sec": 8.0},
        "script": {"path": "script/script_v01.md"},
        "audio": {"narrator": "science_female_main", "target_lufs": -14, "true_peak_max_db": -1},
        "shots": [
            {
                "id": f"S{index:03d}",
                "role": "HERO" if index == 1 else "STORY",
                "method": method,
                "status": "storyboard",
                "duration_target": 1.0,
            }
            for index, method in enumerate(METHODS, start=1)
        ],
        "publish": {"visibility": "private"},
    }


def _h3_shot(shot_id: str, episode_id: str = EPISODE_ID) -> dict:
    role = "HERO"
    return {
        "episode": episode_id,
        "id": shot_id,
        "version": 1,
        "role": role,
        "method": "h3_i2v",
        "intent": "Test motion contract.",
        "camera": {"movement": "small push"},
        "shot_contract": {
            "shot_id": shot_id,
            "role": role,
            "narrative_purpose": "test",
            "visual_goal": "Show one clear change.",
            "subject": "test subject",
            "environment": "test stage",
            "composition": "centered portrait frame",
            "first_frame": "test start state",
            "end_frame": "test end state",
            "subject_motion": "moves gently",
            "environmental_motion": "subtle background motion",
            "camera_motion": "small push",
            "lighting": "soft key light",
            "palette": "neutral",
            "continuity": {"identity": "same subject"},
            "forbidden": ["generated text"],
        },
        "reference_pack": {},
        "motion_plan": {"source_keyframe": f"shots/{shot_id}/images/first.png"},
        "video_candidate_plan": {"candidates": 2},
        "output": {
            "provenance": "provenance.json",
            "selected_keyframe": f"shots/{shot_id}/images/first.png",
            "video_dir": f"shots/{shot_id}/video",
            "download_target": f"shots/{shot_id}/video",
        },
    }


def _write_episode_fixture(root: Path) -> Path:
    episode_root = root / "episodes" / EPISODE_ID
    manifest = _example_manifest()
    dump_yaml(manifest, episode_root / "episode.yaml")
    for shot in manifest["shots"]:
        shot_id = shot["id"]
        dump_yaml({"id": shot_id, "version": 1, "role": "STORY", "method": "animatic_card", "intent": "fixture", "camera": {}, "output": {"card": f"{shot_id}.png"}}, episode_root / "shots" / shot_id / "shot.yaml")
    storyboard = {"shots": [{"id": shot["id"], "method": shot["method"]} for shot in manifest["shots"]]}
    dump_yaml(storyboard, episode_root / "storyboard" / "storyboard_v01.yaml")
    return episode_root


def test_example_manifest_is_valid_and_has_stable_shot_ids(tmp_path: Path) -> None:
    episode_root = _write_episode_fixture(tmp_path)
    manifest = load_manifest(episode_root / "episode.yaml")

    assert validate_manifest(manifest, episode_root / "episode.yaml") == []
    assert [shot["id"] for shot in manifest["shots"]] == [f"S{index:03d}" for index in range(1, 9)]
    assert manifest["creative"]["hero_shot"] == "S001"


def test_shot_methods_are_explicit() -> None:
    methods = {shot["method"] for shot in _example_manifest()["shots"]}
    assert {"hybrid_ai", "h3_i2v", "h3_fl2v", "h3_ref2v"}.issubset(methods)
    assert "blender" not in methods


def test_short_manifest_requires_portrait_aspect_ratio() -> None:
    manifest = _example_manifest()
    manifest["aspect_ratio"] = "16:9"
    assert any("aspect_ratio" in error for error in validate_manifest(manifest))


def test_shot_contract_files_are_parseable_without_a_production_episode(tmp_path: Path) -> None:
    episode_root = _write_episode_fixture(tmp_path)
    for index in range(1, 9):
        shot_id = f"S{index:03d}"
        shot = load_shot_manifest(
            episode_root / "shots" / shot_id / "shot.yaml",
            expected_episode_id=EPISODE_ID,
            expected_shot_id=shot_id,
        )
        assert shot["id"] == shot_id


def test_h3_video_shot_requires_contract_and_motion_plan() -> None:
    shot = {
        "id": "S001",
        "version": 1,
        "role": "HERO",
        "method": "h3_i2v",
        "intent": "test",
        "camera": {"movement": "none"},
        "output": {"provenance": "provenance.json"},
    }
    from studio.manifest import validate_shot_manifest

    errors = validate_shot_manifest(shot)
    assert any("shot_contract" in error for error in errors)
    assert any("motion_plan" in error for error in errors)


def test_output_null_returns_validation_error_instead_of_crashing() -> None:
    from studio.manifest import validate_shot_manifest

    shot = {"id": "S001", "version": 1, "role": "HERO", "method": "ai_image", "intent": "test", "camera": {}, "output": None}
    assert any("output" in error for error in validate_shot_manifest(shot))


def test_episode_shot_contract_identity_and_storyboard_method_match(tmp_path: Path) -> None:
    from studio.manifest import validate_shot_manifest

    episode_root = _write_episode_fixture(tmp_path)
    shot_path = episode_root / "shots" / "S001" / "shot.yaml"
    shot = _h3_shot("S001")
    dump_yaml(shot, shot_path)
    shot["shot_contract"]["shot_id"] = "S999"
    shot["shot_contract"]["role"] = "STORY"
    errors = validate_shot_manifest(shot)
    assert any("shot_contract.shot_id" in error for error in errors)
    assert any("shot_contract.role" in error for error in errors)

    manifest = load_manifest(episode_root / "episode.yaml")
    storyboard = load_yaml(episode_root / "storyboard" / "storyboard_v01.yaml")
    board_methods = {item["id"]: item["method"] for item in storyboard["shots"]}
    assert {item["id"]: item["method"] for item in manifest["shots"]} == board_methods


def test_internal_manifest_path_is_not_serialized() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "episode.yaml"
        write_manifest({"episode_id": "EP099_test", "_path": "/private/runtime/path"}, path)
        assert "_path" not in path.read_text(encoding="utf-8")


def test_animatic_card_cannot_be_approved_in_production_phase() -> None:
    manifest = _example_manifest()
    manifest["status"] = "production"
    manifest["shots"][0]["method"] = "animatic_card"
    manifest["shots"][0]["status"] = "approved"

    assert any("animatic_card" in error for error in validate_manifest(manifest))
