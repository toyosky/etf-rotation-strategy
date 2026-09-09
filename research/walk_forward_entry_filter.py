#!/usr/bin/env python3
"""Entry-only walk-forward candidate filter.

New entries must pass the episode-start health gate and the current dynamic
maturity gate. An already-held ETF is grandfathered while its raw OLS trend
remains eligible; maturity is therefore a buy-veto, not an automatic sell rule.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from walk_forward_candidate_pool import (
    BACKTEST_START,
    SIGNAL_WARMUP_START,
    add_walk_forward_admission,
    attach_daily_maturity_thresholds,
    attach_raw_episode_ids,
    backtest_open_to_open,
    candidate_mask,
    merge_episode_admission,
    summarize_variant,
)

ENTRY_VARIANTS = {
    "entry_baseline": "baseline",
    "entry_h1_dynamic_score80": "h1_dynamic_score80",
    "entry_h2_dynamic_score80": "h2_dynamic_score80",
    "entry_h4_dynamic_score80": "h4_dynamic_score80",
    "entry_h4_dynamic_score_slope80": "h4_dynamic_score_slope80",
}


def build_entry_only_targets(
    f: pd.DataFrame,
    entrant_variant: str,
) -> tuple[pd.Series, pd.Series]:
    all_dates = pd.Index(
        sorted(pd.to_datetime(f.loc[f["date"] >= SIGNAL_WARMUP_START, "date"].unique())),
        name="date",
    )

    entrant = candidate_mask(f, entrant_variant) & (f["date"] >= SIGNAL_WARMUP_START)
    d = f.loc[entrant, ["date", "symbol", "score"]].copy()
    counts = d.groupby("date").size().reindex(all_dates, fill_value=0).astype(int)

    if d.empty:
        return pd.Series(dtype=object), counts

    idx = d.groupby("date", sort=True)["score"].idxmax()
    top = d.loc[idx, ["date", "symbol", "score"]].sort_values("date").set_index("date")

    state = f.loc[
        f["date"] >= SIGNAL_WARMUP_START,
        ["date", "symbol", "score", "trend_eligible"],
    ].copy().set_index(["date", "symbol"])

    current: str | None = None
    selected: dict[pd.Timestamp, str] = {}

    for date in all_dates:
        date = pd.Timestamp(date)
        current_valid = False
        current_score = None
        if current is not None and (date, current) in state.index:
            row = state.loc[(date, current)]
            # symbol/date is unique, but protect against accidental DataFrame shape.
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            current_valid = bool(row["trend_eligible"])
            if current_valid:
                current_score = float(row["score"])

        entrant_symbol = None
        entrant_score = None
        if date in top.index:
            row = top.loc[date]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            entrant_symbol = str(row["symbol"])
            entrant_score = float(row["score"])

        if not current_valid:
            current = entrant_symbol
        elif entrant_symbol is not None and entrant_score is not None:
            # Current holding is grandfathered, but a stronger admissible entrant
            # can still replace it under the original OLS ranking principle.
            if entrant_symbol != current and entrant_score > float(current_score):
                current = entrant_symbol

        if current is not None:
            selected[date] = current

    return pd.Series(selected, name="symbol", dtype=object), counts


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="walk-forward-entry-filter-summary.json")
    p.add_argument("--daily-path", default="walk-forward-entry-filter-daily.csv")
    args = p.parse_args()

    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)
    features, starts = attach_raw_episode_ids(features)
    starts = add_walk_forward_admission(starts)
    features = merge_episode_admission(features, starts)
    features = attach_daily_maturity_thresholds(features, starts)

    summary = {
        "design": {
            "architecture": "episode health admission + dynamic maturity buy-veto + grandfather current holding",
            "backtest_start": str(BACKTEST_START.date()),
            "ranking": "raw OLS score among admissible entrants; current holding can be replaced only by stronger admissible entrant",
        },
        "variants": {},
    }
    daily_frames = []

    for label, entrant_variant in ENTRY_VARIANTS.items():
        targets, counts = build_entry_only_targets(features, entrant_variant)
        pnl = backtest_open_to_open(bars, targets)
        result = summarize_variant(label, pnl, targets, counts)
        result["entrant_variant"] = entrant_variant
        summary["variants"][label] = result
        tmp = pnl.copy()
        tmp["variant"] = label
        daily_frames.append(tmp)

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.concat(daily_frames, ignore_index=True).to_csv(args.daily_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
