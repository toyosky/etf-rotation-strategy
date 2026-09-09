#!/usr/bin/env python3
"""Monthly frozen-universe research for full-market ETF OLS.

Purpose
-------
Test the slow-frequency universe idea *in isolation*:
- before each calendar month, use only the prior 126 trading days;
- among point-in-time universe-eligible ETFs, estimate recent OLS-trend
  persistence as average observed run length of raw OLS-positive states;
- freeze the top K ETFs for the whole next month;
- inside that frozen universe, keep the original daily OLS ranking unchanged.

No H4 health filter, maturity veto, V1, VP, or volume execution overlay is used
here.  This isolates whether monthly universe construction itself adds value.

The top-K breadths 20/40/80 are robustness points, not optimized parameters.
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
from validate_fixed15_vs_full_market import FIXED15
from walk_forward_candidate_pool import (
    BACKTEST_START,
    SIGNAL_WARMUP_START,
    backtest_open_to_open,
    summarize_variant,
)

LOOKBACK = 126
BREADTHS = (20, 40, 80)


def monthly_frozen_pools(
    bars: pd.DataFrame,
    features: pd.DataFrame,
) -> tuple[dict[int, dict[pd.Timestamp, set[str]]], pd.DataFrame]:
    """Build next-month frozen universes using only information before month start."""
    calendar = pd.Index(sorted(pd.to_datetime(bars["date"].unique())))
    months = pd.Series(calendar, index=calendar).groupby(calendar.to_period("M"))

    state = features[[
        "date", "symbol", "universe_eligible", "annual", "r2", "score",
        "avg_amount60",
    ]].copy()
    state["symbol"] = state["symbol"].astype(str)
    state["raw_positive"] = (
        state["universe_eligible"].fillna(False).astype(bool)
        & (state["annual"] > 0)
        & (state["r2"] > 0)
        & (state["score"] > 0)
    )

    raw_wide = state.pivot(index="date", columns="symbol", values="raw_positive").reindex(calendar)
    pools: dict[int, dict[pd.Timestamp, set[str]]] = {k: {} for k in BREADTHS}
    audit_rows: list[dict] = []

    for period, dates_series in months:
        month_dates = pd.Index(dates_series.values)
        first_date = pd.Timestamp(month_dates[0])
        first_pos = int(calendar.get_loc(first_date))
        if first_pos == 0:
            continue
        prev_date = pd.Timestamp(calendar[first_pos - 1])
        hist_start = max(0, first_pos - LOOKBACK)
        hist_dates = calendar[hist_start:first_pos]
        if len(hist_dates) < 60:
            continue

        prev = state.loc[
            (state["date"] == prev_date) & state["universe_eligible"],
            ["symbol", "avg_amount60"],
        ].dropna(subset=["avg_amount60"]).copy()
        eligible = [s for s in prev["symbol"].astype(str).tolist() if s in raw_wide.columns]
        if not eligible:
            continue

        x = raw_wide.loc[hist_dates, eligible].fillna(False).astype(bool)
        pos_days = x.sum(axis=0).astype(float)
        # Count positive-state runs observed inside the trailing window.  If the
        # first window day is already positive, that visible run counts as one.
        starts = x & (~x.shift(1, fill_value=False))
        runs = starts.sum(axis=0).astype(float)
        avg_run = pos_days / runs.replace(0.0, np.nan)
        pos_ratio = pos_days / float(len(hist_dates))

        rank = pd.DataFrame({
            "symbol": eligible,
            "persistence126": [float(avg_run.get(s, np.nan)) for s in eligible],
            "positive_ratio126": [float(pos_ratio.get(s, 0.0)) for s in eligible],
        }).merge(prev, on="symbol", how="left")

        # ETFs with no observed positive OLS state get persistence 0 and sort last.
        rank["persistence126"] = rank["persistence126"].fillna(0.0)
        rank = rank.sort_values(
            ["persistence126", "positive_ratio126", "avg_amount60", "symbol"],
            ascending=[False, False, False, True],
        ).reset_index(drop=True)
        rank["rank"] = np.arange(1, len(rank) + 1)

        for k in BREADTHS:
            chosen = set(rank.head(k)["symbol"].astype(str))
            for d in month_dates:
                pools[k][pd.Timestamp(d)] = chosen

        for row in rank.head(max(BREADTHS)).itertuples(index=False):
            audit_rows.append({
                "month": str(period),
                "prev_date": prev_date,
                "symbol": str(row.symbol),
                "rank": int(row.rank),
                "persistence126": float(row.persistence126),
                "positive_ratio126": float(row.positive_ratio126),
                "avg_amount60": float(row.avg_amount60),
                "eligible_count": int(len(rank)),
            })

    return pools, pd.DataFrame(audit_rows)


def frozen_mask(features: pd.DataFrame, by_date: dict[pd.Timestamp, set[str]]) -> pd.Series:
    dates = pd.to_datetime(features["date"]).to_numpy()
    syms = features["symbol"].astype(str).to_numpy()
    return pd.Series(
        [s in by_date.get(pd.Timestamp(d), set()) for d, s in zip(dates, syms)],
        index=features.index,
        dtype=bool,
    )


def build_targets_from_mask(
    features: pd.DataFrame,
    allowed: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    mask = (
        allowed
        & features["trend_eligible"].fillna(False).astype(bool)
        & (features["date"] >= SIGNAL_WARMUP_START)
    )
    d = features.loc[mask, ["date", "symbol", "score"]].copy()
    all_dates = pd.Index(
        sorted(pd.to_datetime(features.loc[features["date"] >= SIGNAL_WARMUP_START, "date"].unique())),
        name="date",
    )
    counts = d.groupby("date").size().reindex(all_dates, fill_value=0).astype(int)
    if d.empty:
        return pd.Series(dtype=object), counts
    idx = d.groupby("date", sort=True)["score"].idxmax()
    picks = d.loc[idx, ["date", "symbol"]].sort_values("date")
    return picks.set_index("date")["symbol"], counts


def build_baseline_targets(features: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    allowed = pd.Series(True, index=features.index, dtype=bool)
    return build_targets_from_mask(features, allowed)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="monthly-frozen-universe-summary.json")
    p.add_argument("--audit-path", default="monthly-frozen-universe-audit.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)

    pools, audit = monthly_frozen_pools(bars, features)
    summary = {
        "design": {
            "monthly_freeze": True,
            "lookback_trading_days": LOOKBACK,
            "selection_metric": "average observed run length of raw OLS-positive state",
            "breadths": list(BREADTHS),
            "ranking_tiebreakers": ["positive_ratio126", "avg_amount60"],
            "daily_ranking": "unchanged raw OLS score among trend_eligible ETFs in frozen pool",
            "extra_health_or_maturity_filter": False,
            "backtest_start": str(BACKTEST_START.date()),
        },
        "variants": {},
        "pool_audit": {},
    }

    # Same-engine references.
    for label, ff in [
        ("full_market_baseline", features),
        ("fixed15_baseline", features.loc[features["symbol"].astype(str).isin(FIXED15)].copy()),
    ]:
        targets, counts = build_baseline_targets(ff)
        pnl = backtest_open_to_open(bars, targets)
        summary["variants"][label] = summarize_variant(label, pnl, targets, counts)

    for k in BREADTHS:
        allowed = frozen_mask(features, pools[k])
        targets, counts = build_targets_from_mask(features, allowed)
        pnl = backtest_open_to_open(bars, targets)
        label = f"monthly_persistence_top{k}"
        result = summarize_variant(label, pnl, targets, counts)
        result["monthly_breadth"] = k
        summary["variants"][label] = result

        a = audit.loc[audit["rank"] <= k]
        summary["pool_audit"][str(k)] = {
            "months": int(a["month"].nunique()) if len(a) else 0,
            "mean_eligible_count": float(a.groupby("month")["eligible_count"].first().mean()) if len(a) else 0.0,
            "mean_selected_count": float(a.groupby("month").size().mean()) if len(a) else 0.0,
            "median_selected_persistence": float(a["persistence126"].median()) if len(a) else 0.0,
        }

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    audit.to_csv(args.audit_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
