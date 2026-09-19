from pathlib import Path
import tempfile
import unittest

from studio.analytics.schema import initialize_record
from studio.analytics.schema import _record_from_manifest


class AnalyticsTests(unittest.TestCase):
    def test_schema_initializes_episode_record(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = initialize_record(directory, "EP001_earth-stop")
            self.assertTrue(Path(destination).exists())
            self.assertIn('"episode_id": "EP001_earth-stop"', Path(destination).read_text(encoding="utf-8"))

    def test_record_derives_creative_and_audio_peak_metrics(self):
        manifest = {
            "episode_id": "EP001_contract",
            "language": "en-US",
            "publish": {"title": "Contract"},
            "creative": {"hero_shot": "S002", "hook_type": "immediate_consequence"},
            "audio": {"events": [{"time": 0.4}, {"time": 8.0}]},
            "shots": [
                {"id": "S001", "role": "hook_ground_locks", "method": "fusion", "duration_target": 1.0},
                {"id": "S002", "role": "hero_restart_mismatch", "method": "ai_i2v", "duration_target": 2.0},
            ],
        }

        record = _record_from_manifest(Path("/tmp"), "EP001_contract", manifest)

        self.assertEqual(record["creative"]["hook_type"], "immediate_consequence")
        self.assertEqual(record["creative"]["hero_shot_type"], "hero_restart_mismatch")
        self.assertEqual(record["timeline_metrics"]["visual_peak_count"], 2)
        self.assertEqual(record["timeline_metrics"]["audio_peak_count"], 2)
