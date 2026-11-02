"""Regression checks for public.daily_bars without a source column."""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import asset_health_repo as mod


class FakeCursor:
    def __init__(self):
        self.query = None

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params):
        self.query = sql
        assert "source" not in sql.lower(), "daily_bars does not have source column"
    def fetchall(self):
        return [("518880", date(2026, 10, 30), 8.5)]


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self.fake_cursor


class DailyBarsSchemaTests(unittest.TestCase):
    def test_load_bars_without_source_column(self):
        cursor = FakeCursor()
        with patch.object(mod.psycopg2, "connect", return_value=FakeConnection(cursor)):
            result = mod.load_bars("fake", ["518880"], date(2026, 10, 30))
        self.assertEqual(result["518880"], [{"date": date(2026, 10, 30), "close": 8.5}])

    def test_replay_accepts_rows_without_source(self):
        start = date(2026, 1, 1)
        rows = [{"date": start + timedelta(days=i), "close": 10 + i * 0.1} for i in range(60)]
        events = mod.replay_events({"518880": rows}, ["518880"])
        self.assertGreater(len(events["518880"]), 0)


if __name__ == "__main__":
    unittest.main()
