from pathlib import Path
import tempfile
import unittest

from PIL import Image

from studio.db import StateStore
from studio.qc.engine import run_media_qc


class QCCacheTests(unittest.TestCase):
    def test_unchanged_hash_and_profile_reuse_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_path = root / "frame.png"
            Image.new("RGB", (64, 64), "#223344").save(image_path)
            store = StateStore(root / "state.sqlite3")
            first = run_media_qc(image_path, scope="shot/EP001/S001", store=store, work_dir=root / "qc")
            second = run_media_qc(image_path, scope="shot/EP001/S001", store=store, work_dir=root / "qc")
            self.assertFalse(first["cache_hit"])
            self.assertTrue(second["cache_hit"])
            self.assertEqual(first["asset_hash"], second["asset_hash"])
