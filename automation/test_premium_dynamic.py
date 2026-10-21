import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import premium_history_sync as sync


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, *args, **kwargs):
        return self

    def mappings(self):
        return self

    def all(self):
        return self.rows


class FakeEngine:
    def __init__(self, rows=()):
        self.rows = rows

    def connect(self):
        return FakeConnection(self.rows)


class DynamicPremiumTest(unittest.TestCase):
    def test_candidates_not_bound_to_a_single_symbol(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signal.json"
            path.write_text(json.dumps({
                "next_strategy_target": {
                    "model_target": "159100",
                    "symbol": "512800",
                    "holding_target": "520870"
                },
                "current_holding": {"symbol": "159529"}
            }), encoding="utf-8")
            selected = sync.read_signal_symbols(str(path))
            self.assertEqual(selected, {"159100", "512800", "520870", "159529"})
            universe = sync.load_universe(FakeEngine(), selected, only_selected=True)
            self.assertEqual({row["symbol"] for row in universe}, selected)

    def test_new_etf_lookup_uses_exchange_metadata(self):
        selected = {"588000"}
        engine = FakeEngine([{"symbol": "588000", "name": "Sample ETF", "product_type": "ETF"}])
        universe = sync.load_universe(engine, selected, only_selected=True)
        self.assertEqual(universe[0]["symbol"], "588000")

    def test_unsupported_code_fails_closed(self):
        self.assertRaises(ValueError, sync.normalize_symbols, ["OIL"])
        self.assertRaises(RuntimeError, sync.load_universe, FakeEngine(), {"000001"}, True)

    def test_fixed_ols_pool_is_not_full_market(self):
        symbols = sync.fixed_ols_symbols()
        self.assertEqual(len(symbols), 15)  # 14 risk ETFs/LOFs plus US carrier
        self.assertIn("501018", symbols)
        self.assertIn("512800", symbols)
        self.assertIn("513500", symbols)
        self.assertNotIn("520870", symbols)
        self.assertNotIn("159100", symbols)

    def test_full_market_qualified_kept_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "full.json"
            path.write_text(json.dumps({
                "as_of":"2026-10-20", "data_quality_gate":"PASS",
                "qualified_candidates":[
                    {"symbol":"520870","stage":"REBUILDING_QUALIFIED",
                     "first_qualified_date":"2026-10-20"},
                    {"symbol":"159100","stage":"REBUILDING_QUALIFIED",
                     "first_qualified_date":"2026-10-19"},
                    {"symbol":"512800","stage":"REBUILD_WATCH",
                     "first_qualified_date":"2026-10-20"}
                ]
            }), encoding="utf-8")
            self.assertEqual(sync.rebuild_qualified_symbols(str(path)), {"520870","159100"})
            self.assertEqual(sync.rebuild_qualified_symbols(str(path), True), {"520870"})

    def test_default_universe_includes_banks_and_brazil(self):
        universe = sync.load_universe(FakeEngine())
        names = {row["symbol"] for row in universe}
        self.assertIn("512800", names)
        self.assertIn("159100", names)
        self.assertIn("520870", names)
        self.assertNotIn("511220", names)


if __name__ == "__main__":
    unittest.main()
