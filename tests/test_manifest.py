from pathlib import Path
import tempfile
import unittest

from studio.manifest import load_manifest, load_shot_manifest, validate_manifest, write_manifest


ROOT = Path(__file__).resolve().parents[1]


class ManifestTests(unittest.TestCase):
    def test_ep001_is_valid_and_has_stable_shots(self):
        path = ROOT / "episodes" / "EP001_cloud-weight" / "episode.yaml"
        manifest = load_manifest(path)
        self.assertEqual(validate_manifest(manifest, path), [])
        self.assertEqual([shot["id"] for shot in manifest["shots"]], [f"S{index:03d}" for index in range(1, 9)])
        self.assertEqual(manifest["creative"]["hero_shot"], "S006")

    def test_methods_are_explicit(self):
        path = ROOT / "episodes" / "EP001_cloud-weight" / "episode.yaml"
        manifest = load_manifest(path)
        methods = {shot["method"] for shot in manifest["shots"]}
        self.assertTrue({"hybrid_ai", "ai_i2v", "ai_multiframe"}.issubset(methods))
        self.assertNotIn("blender", methods)

    def test_short_manifest_requires_string_portrait_aspect_ratio(self):
        path = ROOT / "episodes" / "EP001_cloud-weight" / "episode.yaml"
        manifest = load_manifest(path)
        self.assertEqual(manifest["aspect_ratio"], "9:16")
        manifest["aspect_ratio"] = "16:9"
        self.assertTrue(any("aspect_ratio" in error for error in validate_manifest(manifest, path)))

    def test_ep001_shot_contracts_are_parseable(self):
        episode = "EP001_cloud-weight"
        for index in range(1, 9):
            shot_id = f"S{index:03d}"
            shot = load_shot_manifest(
                ROOT / "episodes" / episode / "shots" / shot_id / "shot.yaml",
                expected_episode_id=episode,
                expected_shot_id=shot_id,
            )
            self.assertEqual(shot["id"], shot_id)
        self.assertEqual(
            load_shot_manifest(ROOT / "episodes" / episode / "shots" / "S007" / "shot.yaml")["method"],
            "ai_multiframe",
        )

    def test_ai_video_shot_requires_contract_and_download_target(self):
        shot = {
            "id": "S001",
            "version": 1,
            "role": "hero",
            "method": "ai_i2v",
            "intent": "test",
            "camera": {"lens_mm": 35},
            "output": {"provenance": "provenance.json"},
        }
        from studio.manifest import validate_shot_manifest

        errors = validate_shot_manifest(shot)
        self.assertTrue(any("shot_contract" in error for error in errors))
        self.assertTrue(any("motion_plan" in error for error in errors))

    def test_output_null_returns_validation_error_instead_of_crashing(self):
        from studio.manifest import validate_shot_manifest

        shot = {"id": "S001", "version": 1, "role": "hero", "method": "ai_image", "intent": "test", "camera": {}, "output": None}
        self.assertTrue(any("output" in error for error in validate_shot_manifest(shot)))

    def test_episode_shot_contract_identity_and_storyboard_method_match(self):
        from studio.config import load_yaml
        from studio.manifest import validate_shot_manifest

        episode_root = ROOT / "episodes" / "EP001_cloud-weight"
        shot = load_shot_manifest(episode_root / "shots" / "S001" / "shot.yaml")
        shot["shot_contract"]["shot_id"] = "S999"
        shot["shot_contract"]["role"] = "STORY"
        errors = validate_shot_manifest(shot)
        self.assertTrue(any("shot_contract.shot_id" in error for error in errors))
        self.assertTrue(any("shot_contract.role" in error for error in errors))

        episode = load_manifest(episode_root / "episode.yaml")
        storyboard = load_yaml(episode_root / "storyboard" / "storyboard_v01.yaml")
        board_methods = {shot["id"]: shot["method"] for shot in storyboard["shots"]}
        self.assertEqual({shot["id"]: shot["method"] for shot in episode["shots"]}, board_methods)
        self.assertIsInstance(episode["shots"][5]["long_hold_justification"]["reason"], str)

    def test_internal_manifest_path_is_not_serialized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "episode.yaml"
            write_manifest({"episode_id": "EP001_test", "_path": "/private/runtime/path"}, path)
            self.assertNotIn("_path", path.read_text(encoding="utf-8"))

    def test_animatic_card_cannot_be_approved_in_production_phase(self):
        manifest = {
            "episode_id": "EP001_test",
            "status": "production",
            "channel": "test",
            "format": "youtube_short",
            "language": "en-US",
            "aspect_ratio": "9:16",
            "master": {"width": 1080, "height": 1920, "fps": 30, "sample_rate": 48000},
            "creative": {"promise": "test", "hero_shot": "S001", "target_duration_sec": 1},
            "script": {"path": "script.md"},
            "audio": {"narrator": "test", "target_lufs": -14, "true_peak_max_db": -1},
            "publish": {"title": "test", "description": "test", "ai_disclosure": True, "visibility": "private"},
            "shots": [{"id": "S001", "role": "hook", "duration_target": 1, "method": "animatic_card", "status": "approved"}],
        }

        assert any("animatic_card" in error for error in validate_manifest(manifest))
