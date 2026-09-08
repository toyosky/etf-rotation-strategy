import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pushplus_notify as mod


class PushPlusTransitionTests(unittest.TestCase):
    def test_same_status_is_silent(self):
        self.assertFalse(mod.should_notify_transition("WARNING", "WARNING"))

    def test_healthy_to_watch_notifies(self):
        self.assertTrue(mod.should_notify_transition("HEALTHY", "WATCH"))

    def test_warning_to_healthy_notifies(self):
        self.assertTrue(mod.should_notify_transition("WARNING", "HEALTHY"))

    def test_insufficient_to_healthy_is_silent(self):
        self.assertFalse(mod.should_notify_transition("INSUFFICIENT_DATA", "HEALTHY"))

    def test_detect_changes_only_keeps_meaningful_transitions(self):
        previous = [
            {"symbol": "159825", "status": "WATCH"},
            {"symbol": "159985", "status": "HEALTHY"},
            {"symbol": "511380", "status": "INSUFFICIENT_DATA"},
        ]
        current = [
            {"symbol": "159825", "status": "WARNING"},
            {"symbol": "159985", "status": "HEALTHY"},
            {"symbol": "511380", "status": "HEALTHY"},
        ]
        changes = mod.detect_changes(previous, current)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["symbol"], "159825")
        self.assertEqual(changes[0]["label"], "升级")


if __name__ == "__main__":
    unittest.main()
