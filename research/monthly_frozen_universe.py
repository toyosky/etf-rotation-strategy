#!/usr/bin/env python3
"""Monthly frozen-universe research for full-market ETF OLS.

Research question
-----------------
Can a slow-frequency point-in-time screen choose ETFs that are *suitable for
OLS rotation*, freeze that universe for the next month, and then let the
original daily OLS ranking operate unchanged inside it?

Two slow metrics are tested:
1. persistence126: average observed run length of raw OLS-positive states in
   the prior 126 trading days.  This is intentionally retained as a diagnostic;
   it can over-reward cash-like instruments that drift upward very smoothly.
2. trendability126: persistence126 * median(slope * R2) on raw-positive days.
   This approximates the typical model-implied log-price excursion of a trend:
   it must both last and move enough to be economically tradable.

The trendability metric is additionally tested with monthly point-in-time
correlation deduplication at 0.95 and 0.90, using only the prior 120 daily
returns.  These are robustness points, not optimized thresholds.

No H4 health filter, maturity veto, V1, VP, or volume execution overlay is used
here.  The daily selector remains raw OLS Score among trend-eligible ETFs in the
frozen monthly universe.  This isolates the universe-construction layer.
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
CORR_LOOKBACK = 120
BREADTHS = (20, 40, 80)
DEDUP_THRESHOLDS = (0.95, 0.90)


def _greedy_dedup(
    ranked_symbols: list[str],
    corr: pd.DataFrame,
    k: int,
    threshold: float,
) -> list[str]:
    """Keep highest-ranked symbols while avoiding near-duplicates."""
    kept: list[str] = []
    for sym in ranked_symbols:
        duplicate = False
        for rep in kept:
            c = corr.at[sym, rep] if sym in corr.index and rep in corr.columns else np.nan
            if pd.notna(c) and float(c) >= threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(sym)
            if len(kept) >= k:
                break
    return kept


def monthly_frozen_pools(
    bars: pd.DataFrame,
    features: pd.DataFrame,
) -> tuple[dict[str, dict[pd.Timestamp, set[str]]], pd.DataFrame]:
    """Build next-month frozen universes using only information before month start."""
    calendar = pd.Index(sorted(pd.to_datetime(bars["date"].unique())))
    months = pd.Series(calendar, index=calendar).groupby(calendar.to_period("M"))

    state = features[[
        "date", "symbol", "universe_eligible", "annual", "r2", "score",
        "slope", "avg_amount60",
    ]].copy()
    state["symbol"] = state["symbol"].astype(str)
    state["raw_positive"] = (
        state["universe_eligible"].fillna(False).astype(bool)
        & (state["annual"] > 0)
        & (state["r2"] > 0)
        & (state["score"] > 0)
    )
    state["linear_strength"] = np.where(
        state["raw_positive"],
        state["slope"].astype(float) * state["r2"].astype(float),
        np.nan,
    )

    raw_wide = state.pivot(index="date", columns="symbol", values="raw_positive").reindex(calendar)
    strength_wide = state.pivot(index="date", columns="symbol", values="linear_strength").reindex(calendar)
    close = bars.pivot(index="date", columns="symbol", values="close").reindex(calendar)
    ret = close.pct_change(fill_method=None)

    pool_names = [f"persistence_top{k}" for k in BREADTHS]
    pool_names += [f"trendability_top{k}" for k in BREADTHS]
    pool_names += [f"trendability_top40_dedup{int(t*100)}" for t in DEDUP_THRESHOLDS]
    pools: dict[str, dict[pd.Timestamp, set[str]]] = {name: {} for name in pool_names}
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
        starts = x & (~x.shift(1, fill_value=False))
        runs = starts.sum(axis=0).astype(float)
        avg_run = pos_days / runs.replace(0.0, np.nan)
        pos_ratio = pos_days / float(len(hist_dates))
        median_strength = strength_wide.loc[hist_dates, eligible].median(axis=0, skipna=True)

        rank = pd.DataFrame({
            "symbol": eligible,
            "persistence126": [float(avg_run.get(s, np.nan)) for s in eligible],
            "positive_ratio126": [float(pos_ratio.get(s, 0.0)) for s in eligible],
            "median_linear_strength126": [float(median_strength.get(s, np.nan)) for s in eligible],
        }).merge(prev, on="symbol", how="left")

        rank["persistence126"] = rank["persistence126"].fillna(0.0)
        rank["median_linear_strength126"] = rank["median_linear_strength126"].fillna(0.0)
        rank["trendability126"] = rank["persistence126"] * rank["median_linear_strength126"]

        persistence_rank = rank.sort_values(
            ["persistence126", "positive_ratio126", "avg_amount60", "symbol"],
            ascending=[False, False, False, True],
        ).reset_index(drop=True)
        persistence_rank["persistence_rank"] = np.arange(1, len(persistence_rank) + 1)

        trend_rank = rank.sort_values(
            ["trendability126", "positive_ratio126", "avg_amount60", "symbol"],
            ascending=[False, False, False, True],
        ).reset_index(drop=True)
        trend_rank["trendability_rank"] = np.arange(1, len(trend_rank) + 1)

        for k in BREADTHS:
            pchosen = set(persistence_rank.head(k)["symbol"].astype(str))
            tchosen = set(trend_rank.head(k)["symbol"].astype(str))
            for d in month_dates:
                pools[f"persistence_top{k}"][pd.Timestamp(d)] = pchosen
                pools[f"trendability_top{k}"][pd.Timestamp(d)] = tchosen

        corr_start = max(0, first_pos - CORR_LOOKBACK)
        corr_dates = calendar[corr_start:first_pos]
        corr = ret.loc[corr_dates, eligible].corr(min_periods=60) if len(corr_dates) >= 60 else pd.DataFrame()
        ranked_symbols = trend_rank["symbol"].astype(str).tolist()
        for threshold in DEDUP_THRESHOLDS:
            if corr.empty:
                chosen_list = ranked_symbols[:40]
            else:
                chosen_list = _greedy_dedup(ranked_symbols, corr, 40, threshold)
            chosen = set(chosen_list)
            name = f"trendability_top40_dedup{int(threshold*100)}"
            for d in month_dates:
                pools[name][pd.Timestamp(d)] = chosen

        audit = trend_rank.merge(
            persistence_rank[["symbol", "persistence_rank"]], on="symbol", how="left"
        )
        dedup95 = set(_greedy_dedup(ranked_symbols, corr, 40, 0.95)) if not corr.empty else set(ranked_symbols[:40])
        dedup90 = set(_greedy_dedup(ranked_symbols, corr, 40, 0.90)) if not corr.empty else set(ranked_symbols[:40])
        for row in audit.head(max(BREADTHS)).itertuples(index=False):
            audit_rows.append({
                "month": str(period),
                "prev_date": prev_date,
                "symbol": str(row.symbol),
                "trendability_rank": int(row.trendability_rank),
                "persistence_rank": int(row.persistence_rank),
                "persistence126": float(row.persistence126),
                "median_linear_strength126": float(row.median_linear_strength126),
                "trendability126": float(row.trendability126),
                "positive_ratio126": float(row.positive_ratio126),
                "avg_amount60": float(row.avg_amount60),
                "eligible_count": int(len(rank)),
                "dedup95_top40": str(row.symbol) in dedup95,
                "dedup90_top40": str(row.symbol) in dedup90,
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
    return build_targets_from_mask(features, pd.Series(True, index=features.index, dtype=bool))


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
            "persistence_metric": "average observed run length of raw OLS-positive state",
            "trendability_metric": "persistence126 * median(slope * r2) on raw-positive days",
            "breadths": list(BREADTHS),
            "dedup_thresholds": list(DEDUP_THRESHOLDS),
            "daily_ranking": "unchanged raw OLS score among trend_eligible ETFs in frozen pool",
            "extra_health_or_maturity_filter": False,
            "backtest_start": str(BACKTEST_START.date()),
        },
        "variants": {},
        "pool_audit": {},
    }

    for label, ff in [
        ("full_market_baseline", features),
        ("fixed15_baseline", features.loc[features["symbol"].astype(str).isin(FIXED15)].copy()),
    ]:
        targets, counts = build_baseline_targets(ff)
        pnl = backtest_open_to_open(bars, targets)
        summary["variants"][label] = summarize_variant(label, pnl, targets, counts)

    test_names = [f"persistence_top{k}" for k in BREADTHS]
    test_names += [f"trendability_top{k}" for k in BREADTHS]
    test_names += [f"trendability_top40_dedup{int(t*100)}" for t in DEDUP_THRESHOLDS]

    for name in test_names:
        allowed = frozen_mask(features, pools[name])
        targets, counts = build_targets_from_mask(features, allowed)
        pnl = backtest_open_to_open(bars, targets)
        label = f"monthly_{name}"
        result = summarize_variant(label, pnl, targets, counts)
        result["monthly_pool"] = name
        summary["variants"][label] = result

    # Compact audit focused on the economically meaningful trendability ranks.
    for k in BREADTHS:
        a = audit.loc[audit["trendability_rank"] <= k]
        summary["pool_audit"][f"trendability_top{k}"] = {
            "months": int(a["month"].nunique()) if len(a) else 0,
            "mean_eligible_count": float(a.groupby("month")["eligible_count"].first().mean()) if len(a) else 0.0,
            "mean_selected_count": float(a.groupby("month").size().mean()) if len(a) else 0.0,
            "median_persistence126": float(a["persistence126"].median()) if len(a) else 0.0,
            "median_linear_strength126": float(a["median_linear_strength126"].median()) if len(a) else 0.0,
            "median_trendability126": float(a["trendability126"].median()) if len(a) else 0.0,
        }
    for threshold in DEDUP_THRESHOLDS:
        col = f"dedup{int(threshold*100)}_top40"
        a = audit.loc[audit[col]]
        summary["pool_audit"][col] = {
            "months": int(a["month"].nunique()) if len(a) else 0,
            "mean_selected_count": float(a.groupby("month").size().mean()) if len(a) else 0.0,
        }

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    audit.to_csv(args.audit_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
