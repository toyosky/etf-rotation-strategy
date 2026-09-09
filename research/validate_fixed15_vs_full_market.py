#!/usr/bin/env python3
"""Sanity check: same daily engine on fixed15 vs full-market baseline."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sqlalchemy import create_engine

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from walk_forward_candidate_pool import backtest_open_to_open, build_daily_targets, summarize_variant

FIXED15 = {
    "518880", "159985", "159825", "161226", "513100",
    "159915", "511220", "159509", "513290", "159529",
    "159981", "501018", "513920", "511380", "164824",
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="fixed15-vs-full-market-summary.json")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    f = build_features(bars)

    out = {"variants": {}}
    for label, ff in [
        ("full_market_baseline", f),
        ("fixed15_baseline", f.loc[f["symbol"].isin(FIXED15)].copy()),
    ]:
        targets, counts = build_daily_targets(ff, "baseline")
        pnl = backtest_open_to_open(bars, targets)
        out["variants"][label] = summarize_variant(label, pnl, targets, counts)

    Path(args.summary_path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
