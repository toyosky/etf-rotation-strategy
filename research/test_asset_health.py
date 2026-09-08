import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import asset_health as mod


def summary(n, mean, win):
    return {
        "count": n,
        "fwd5_mean": mean,
        "fwd5_median": mean,
        "fwd5_win_rate": win,
        "fwd10_mean": mean,
        "fwd10_median": mean,
        "fwd10_win_rate": win,
    }


class ClassifyHealthTests(unittest.TestCase):
    def test_warning_requires_long_and_recent_weakness(self):
        status, _ = mod.classify_health(
            all_near_high=summary(11, -0.04, 0.09),
            recent_2y_near_high=summary(6, -0.017, 0.17),
        )
        self.assertEqual(status, "WARNING")

    def test_watch_for_recent_deterioration(self):
        status, _ = mod.classify_health(
            all_near_high=summary(67, -0.001, 0.48),
            recent_2y_near_high=summary(11, -0.012, 0.27),
        )
        self.assertEqual(status, "WATCH")

    def test_insufficient_data(self):
        status, _ = mod.classify_health(
            all_near_high=summary(8, 0.01, 0.60),
            recent_2y_near_high=summary(3, 0.02, 0.60),
        )
        self.assertEqual(status, "INSUFFICIENT_DATA")

    def test_healthy(self):
        status, _ = mod.classify_health(
            all_near_high=summary(50, 0.02, 0.60),
            recent_2y_near_high=summary(20, 0.01, 0.55),
        )
        self.assertEqual(status, "HEALTHY")


if __name__ == "__main__":
    unittest.main()
