import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import asset_health_active as mod


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self.rows = list(rows)
        self.status = None

    def select(self, _columns):
        return self

    def eq(self, key, value):
        if key == "universe_status":
            self.status = value
        return self

    def order(self, _column):
        return self

    def execute(self):
        rows = [r for r in self.rows if self.status is None or r["universe_status"] == self.status]
        return _Response(rows)


class _Client:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        if name != "asset_universe":
            raise AssertionError(name)
        return _Query(self.rows)


class ActiveUniverseTests(unittest.TestCase):
    def test_only_active_assets_are_selected(self):
        client = _Client(
            [
                {"symbol": "159509", "name": "A", "universe_status": "ACTIVE"},
                {"symbol": "159825", "name": "B", "universe_status": "RETIRED"},
                {"symbol": "513030", "name": "C", "universe_status": "CANDIDATE"},
                {"symbol": "511220", "name": "D", "universe_status": "CASH_PROXY"},
                {"symbol": "518880", "name": "E", "universe_status": "ACTIVE"},
            ]
        )
        self.assertEqual(mod.get_active_pool(client, "ignored"), ["159509", "518880"])

    def test_empty_active_pool_fails_closed(self):
        client = _Client([{"symbol": "159825", "name": "B", "universe_status": "RETIRED"}])
        with self.assertRaises(RuntimeError):
            mod.get_active_pool(client, "ignored")


if __name__ == "__main__":
    unittest.main()
