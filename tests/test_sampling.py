import unittest

from studio.media.sampling import sample_positions, scene_samples


class SamplingTests(unittest.TestCase):
    def test_long_scene_uses_three_positions(self):
        self.assertEqual(sample_positions(3.0), [0.10, 0.50, 0.90])

    def test_short_scene_uses_two_positions(self):
        self.assertEqual(sample_positions(1.1), [0.25, 0.75])

    def test_scene_samples_are_bounded(self):
        values = scene_samples([{"start": 2.0, "end": 4.0}])
        self.assertEqual(len(values), 3)
        self.assertTrue(all(2.0 <= item[2] <= 4.0 for item in values))
