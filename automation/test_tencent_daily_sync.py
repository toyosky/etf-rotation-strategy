import unittest
from datetime import date
from pathlib import Path

from tencent_daily_sync import load_universe, normalize


CORE15 = {
    "159934", "159985", "161226", "513100", "159957",
    "159509", "513290", "159529", "159981", "501018",
    "513530", "511380", "164824", "511220", "513500",
}
BENCHMARKS = {"510300"}
RESEARCH_ONLY = {"520870", "159100"}
# Research-only carriers must never expand the frozen production core.


class TencentDailySyncTests(unittest.TestCase):
    def test_repository_universe_keeps_frozen_core15_plus_non_competing_extras(self):
        rows = load_universe(Path(__file__).with_name("tencent_daily_universe.csv"))
        symbols = {row["symbol"] for row in rows}
        self.assertEqual(CORE15, symbols - BENCHMARKS - RESEARCH_ONLY)
        self.assertEqual(BENCHMARKS, symbols & BENCHMARKS)
        self.assertEqual(RESEARCH_ONLY, symbols & RESEARCH_ONLY)
        self.assertEqual(len(rows), len(CORE15) + len(BENCHMARKS) + len(RESEARCH_ONLY))

    def test_single_symbol_response_gets_symbol_volume_type_and_ingest_date(self):
        payload = [{"date": "2026-09-10", "open": 1, "high": 1.2, "low": 0.9, "last": 1.1, "volume": 12, "amount": 1300}]
        rows = normalize(payload, ["sh513100"], {"513100": "ETF"}, date(2026, 9, 10))
        self.assertEqual(rows[0][0], "513100")
        self.assertEqual(rows[0][6], 1200.0)
        self.assertEqual(rows[0][8], "ETF")
        self.assertEqual(rows[0][9], date(2026, 9, 10))

    def test_invalid_ohlc_is_rejected(self):
        payload = [{"symbol": "sh513100", "date": "2026-09-10", "open": 1, "high": 1, "low": 0.9, "last": 1.1, "volume": 1, "amount": 100}]
        with self.assertRaises(ValueError):
            normalize(payload, ["sh513100"], {"513100": "ETF"}, date(2026, 9, 10))


if __name__ == "__main__":
    unittest.main()
