import unittest
from datetime import date
from pathlib import Path

from tencent_daily_sync import load_universe, normalize


class TencentDailySyncTests(unittest.TestCase):
    def test_repository_universe_is_valid(self):
        rows = load_universe(Path(__file__).with_name("tencent_daily_universe.csv"))
        self.assertEqual(len(rows), 1090)
        self.assertEqual(len({row["symbol"] for row in rows}), 1090)

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
