from pathlib import Path
import tempfile
import unittest

from studio.manifest import load_manifest, load_shot_manifest, validate_manifest, write_manifest


ROOT = Path(__file__).resolve().parents[1]


class ManifestTests(unittest.TestCase):
    def test_ep001_is_valid_and_has_stable_shots(self):
        path = ROOT / "episodes" / "EP001_earth-stop" / "episode.yaml"
        manifest = load_manifest(path)
        self.assertEqual(validate_manifest(manifest, path), [])
        self.assertEqual([shot["id"] for shot in manifest["shots"]], [f"S{index:03d}" for index in range(1, 11)])
        self.assertEqual(manifest["creative"]["hero_shot"], "S007")

    def test_methods_are_explicit(self):
        path = ROOT / "episodes" / "EP001_earth-stop" / "episode.yaml"
        manifest = load_manifest(path)
        methods = {shot["method"] for shot in manifest["shots"]}
        self.assertTrue({"blender", "fusion", "ai_video"}.issubset(methods))

    def test_short_manifest_requires_string_portrait_aspect_ratio(self):
        path = ROOT / "episodes" / "EP001_earth-stop" / "episode.yaml"
        manifest = load_manifest(path)
        self.assertEqual(manifest["aspect_ratio"], "9:16")
        manifest["aspect_ratio"] = "16:9"
        self.assertTrue(any("aspect_ratio" in error for error in validate_manifest(manifest, path)))

    def test_ep001_shot_contracts_are_parseable(self):
        shot = load_shot_manifest(ROOT / "episodes" / "EP001_earth-stop" / "shots" / "S007" / "shot.yaml")
        self.assertEqual(shot["id"], "S007")
        self.assertEqual(shot["method"], "blender")

    def test_blender_shot_requires_explicit_renderer(self):
        shot = {
            "id": "S001",
            "version": 1,
            "role": "hero",
            "method": "blender",
            "intent": "test",
            "camera": {"lens_mm": 35},
            "output": {"render": "render/"},
        }
        from studio.manifest import validate_shot_manifest

        self.assertTrue(any("renderer" in error for error in validate_shot_manifest(shot)))

    def test_internal_manifest_path_is_not_serialized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "episode.yaml"
            write_manifest({"episode_id": "EP001_test", "_path": "/private/runtime/path"}, path)
            self.assertNotIn("_path", path.read_text(encoding="utf-8"))
