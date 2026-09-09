#!/usr/bin/env python3
"""Point-in-time ETF dedup robustness test for walk-forward OLS selection.

Each calendar month uses only information available before that month:
- universe eligibility and 60d average amount from the previous trading day;
- pairwise correlation of daily close returns over the prior 120 trading days;
- greedy representatives sorted by liquidity, keeping a new ETF only if its
  correlation with every already-kept representative is below the threshold.

Tests 0.95 (near-duplicate) and 0.90 as robustness points; neither is optimized.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
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


def monthly_representatives(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    corr_threshold: float,
) -> tuple[dict[pd.Timestamp, set[str]], dict]:
    calendar = pd.Index(sorted(pd.to_datetime(bars["date"].unique())))
    close = bars.pivot(index="date", columns="symbol", values="close").reindex(calendar)
    ret = close.pct_change(fill_method=None)

    # Previous-day point-in-time eligibility/liquidity lookup.
    state = features[["date", "symbol", "universe_eligible", "avg_amount60"]].copy()
    state["symbol"] = state["symbol"].astype(str)

    months = pd.Series(calendar, index=calendar).groupby(calendar.to_period("M"))
    allowed_by_date: dict[pd.Timestamp, set[str]] = {}
    rep_counts = []

    for _, dates_series in months:
        month_dates = pd.Index(dates_series.values)
        first_date = pd.Timestamp(month_dates[0])
        first_pos = calendar.get_loc(first_date)
        if first_pos == 0:
            reps: set[str] = set()
        else:
            prev_date = pd.Timestamp(calendar[first_pos - 1])
            prev_state = state.loc[
                (state["date"] == prev_date) & state["universe_eligible"],
                ["symbol", "avg_amount60"],
            ].dropna().sort_values("avg_amount60", ascending=False)
            eligible = prev_state["symbol"].tolist()

            hist_start = max(0, first_pos - 120)
            hist_dates = calendar[hist_start:first_pos]
            if len(hist_dates) < 60 or not eligible:
                reps = set(eligible)
            else:
                cols = [s for s in eligible if s in ret.columns]
                corr = ret.loc[hist_dates, cols].corr(min_periods=60)
                kept: list[str] = []
                for sym in cols:
                    duplicate = False
                    for rep in kept:
                        c = corr.at[sym, rep] if sym in corr.index and rep in corr.columns else np.nan
                        if pd.notna(c) and float(c) >= corr_threshold:
                            duplicate = True
                            break
                    if not duplicate:
                        kept.append(sym)
                reps = set(kept)

        rep_counts.append(len(reps))
        for d in month_dates:
            allowed_by_date[pd.Timestamp(d)] = reps

    stats = {
        "threshold": corr_threshold,
        "mean_monthly_representatives": float(np.mean(rep_counts)),
        "median_monthly_representatives": float(np.median(rep_counts)),
        "min_monthly_representatives": int(np.min(rep_counts)),
        "max_monthly_representatives": int(np.max(rep_counts)),
    }
    return allowed_by_date, stats


def allowed_mask(f: pd.DataFrame, allowed_by_date: dict[pd.Timestamp, set[str]]) -> pd.Series:
    dates = pd.to_datetime(f["date"]).to_numpy()
    syms = f["symbol"].astype(str).to_numpy()
    return pd.Series(
        [s in allowed_by_date.get(pd.Timestamp(d), set()) for d, s in zip(dates, syms)],
        index=f.index,
        dtype=bool,
    )


def build_entry_targets_with_allowed(
    f: pd.DataFrame,
    entrant_variant: str,
    allowed: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    all_dates = pd.Index(
        sorted(pd.to_datetime(f.loc[f["date"] >= SIGNAL_WARMUP_START, "date"].unique())),
        name="date",
    )
    entrant = candidate_mask(f, entrant_variant) & allowed & (f["date"] >= SIGNAL_WARMUP_START)
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

    current = None
    selected = {}
    for date in all_dates:
        date = pd.Timestamp(date)
        current_valid = False
        current_score = None
        if current is not None and (date, current) in state.index:
            row = state.loc[(date, current)]
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
        elif entrant_symbol is not None and entrant_symbol != current and entrant_score > float(current_score):
            current = entrant_symbol

        if current is not None:
            selected[date] = current

    return pd.Series(selected, name="symbol", dtype=object), counts


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="walk-forward-dedup-summary.json")
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
        "design": "monthly point-in-time correlation dedup + entry-only H4 health + dynamic maturity buy-veto",
        "variants": {},
        "dedup_stats": {},
    }

    for threshold in (0.95, 0.90):
        by_date, stats = monthly_representatives(bars, features, threshold)
        allowed = allowed_mask(features, by_date)
        summary["dedup_stats"][str(threshold)] = stats

        tests = {
            f"dedup{int(threshold*100)}_baseline": "baseline",
            f"dedup{int(threshold*100)}_h4_dynamic_score80": "h4_dynamic_score80",
            f"dedup{int(threshold*100)}_h4_dynamic_score_slope80": "h4_dynamic_score_slope80",
        }
        for label, entrant_variant in tests.items():
            targets, counts = build_entry_targets_with_allowed(features, entrant_variant, allowed)
            pnl = backtest_open_to_open(bars, targets)
            result = summarize_variant(label, pnl, targets, counts)
            result["entrant_variant"] = entrant_variant
            result["corr_threshold"] = threshold
            summary["variants"][label] = result

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
