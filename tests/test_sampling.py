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

    def test_max_samples_is_applied_per_scene_not_globally(self):
        values = scene_samples(
            [{"start": index * 2.0, "end": index * 2.0 + 1.5} for index in range(10)],
            max_samples_per_scene=3,
        )
        self.assertEqual(len(values), 30)
        self.assertEqual({item[0] for item in values}, set(range(10)))

    def test_long_scene_can_use_configured_long_strategy(self):
        values = sample_positions(
            10.0,
            long_threshold=8.0,
            long_positions=[0.0, 0.25, 0.5, 0.75, 1.0],
            max_samples_per_scene=5,
        )
        self.assertEqual(values, [0.0, 0.25, 0.5, 0.75, 1.0])
