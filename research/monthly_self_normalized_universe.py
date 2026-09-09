#!/usr/bin/env python3
"""Self-normalized monthly universe research.

Motivation
----------
A global cross-sectional Top-K trendability screen compares structurally
heterogeneous assets (gold, commodities, broad equity, tech, bond/cash-like
ETFs) on the same absolute slope scale.  The attribution diagnostic showed that
this excludes many useful fixed-pool opportunities in 2021-2024, while the
within-pool raw OLS ranking itself was not the main problem.

This experiment therefore normalizes the slow monthly regime signal *within
ETF through time*:
- before each month, compute prior-126-day trendability exactly as in
  monthly_frozen_universe.py;
- compare the current trendability only with that ETF's strictly earlier
  monthly trendability observations;
- freeze ETFs whose self-percentile is >= 50%, 60%, or 70% for the next month;
- inside the frozen universe, keep the daily OLS selector unchanged.

The three natural percentile levels are robustness points, not fitted cutoffs.
No H4, maturity veto, V1, VP, or volume execution overlay is included.
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
from walk_forward_candidate_pool import BACKTEST_START, backtest_open_to_open, summarize_variant
from monthly_frozen_universe import (
    LOOKBACK,
    build_baseline_targets,
    build_targets_from_mask,
    frozen_mask,
)

MIN_PRIOR_MONTHS = 12
SELF_PERCENTILES = (0.50, 0.60, 0.70)


def build_monthly_metrics(bars: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
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

    rows: list[dict] = []
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
        persistence = pos_days / runs.replace(0.0, np.nan)
        pos_ratio = pos_days / float(len(hist_dates))
        median_strength = strength_wide.loc[hist_dates, eligible].median(axis=0, skipna=True)

        for sym in eligible:
            p = float(persistence.get(sym, np.nan))
            if not np.isfinite(p):
                p = 0.0
            s = float(median_strength.get(sym, np.nan))
            if not np.isfinite(s):
                s = 0.0
            rows.append({
                "month": str(period),
                "month_start": first_date,
                "prev_date": prev_date,
                "symbol": sym,
                "persistence126": p,
                "median_linear_strength126": s,
                "trendability126": p * s,
                "positive_ratio126": float(pos_ratio.get(sym, 0.0)),
                "avg_amount60": float(prev.loc[prev["symbol"] == sym, "avg_amount60"].iloc[0]),
            })

    m = pd.DataFrame(rows).sort_values(["symbol", "month_start"]).reset_index(drop=True)
    if m.empty:
        raise RuntimeError("No monthly metrics generated")

    # Strictly prior monthly observations only.  Empirical percentile is the
    # share of prior values <= current value; no future or same-month peers enter.
    pct = np.full(len(m), np.nan, dtype=float)
    prior_n = np.zeros(len(m), dtype=int)
    for _, idx in m.groupby("symbol", sort=False).groups.items():
        idx = list(idx)
        vals: list[float] = []
        for j in idx:
            v = float(m.at[j, "trendability126"])
            prior_n[j] = len(vals)
            if len(vals) >= MIN_PRIOR_MONTHS:
                a = np.asarray(vals, dtype=float)
                pct[j] = float(np.mean(a <= v))
            vals.append(v)
    m["prior_months"] = prior_n
    m["self_trendability_pct"] = pct
    return m


def monthly_pools_from_metrics(metrics: pd.DataFrame, bars: pd.DataFrame) -> dict[str, dict[pd.Timestamp, set[str]]]:
    calendar = pd.Index(sorted(pd.to_datetime(bars["date"].unique())))
    month_dates = {str(p): pd.Index(v.values) for p, v in pd.Series(calendar, index=calendar).groupby(calendar.to_period("M"))}
    pools: dict[str, dict[pd.Timestamp, set[str]]] = {
        f"self_p{int(q*100)}": {} for q in SELF_PERCENTILES
    }
    for month, g in metrics.groupby("month", sort=True):
        dates = month_dates.get(str(month), pd.Index([]))
        if len(dates) == 0:
            continue
        for q in SELF_PERCENTILES:
            chosen = set(g.loc[
                (g["prior_months"] >= MIN_PRIOR_MONTHS)
                & (g["self_trendability_pct"] >= q),
                "symbol",
            ].astype(str))
            for d in dates:
                pools[f"self_p{int(q*100)}"][pd.Timestamp(d)] = chosen
    return pools


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="monthly-self-normalized-summary.json")
    p.add_argument("--audit-path", default="monthly-self-normalized-audit.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)
    metrics = build_monthly_metrics(bars, features)
    pools = monthly_pools_from_metrics(metrics, bars)

    summary = {
        "design": {
            "monthly_freeze": True,
            "lookback_trading_days": LOOKBACK,
            "trendability_metric": "persistence126 * median(slope * r2) on raw-positive days",
            "normalization": "within ETF, empirical percentile versus strictly prior monthly observations",
            "min_prior_months": MIN_PRIOR_MONTHS,
            "self_percentiles": list(SELF_PERCENTILES),
            "daily_ranking": "unchanged raw OLS score among trend_eligible ETFs in frozen pool",
            "extra_health_or_maturity_filter": False,
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

    for q in SELF_PERCENTILES:
        name = f"self_p{int(q*100)}"
        allowed = frozen_mask(features, pools[name])
        targets, counts = build_targets_from_mask(features, allowed)
        pnl = backtest_open_to_open(bars, targets)
        summary["variants"][name] = summarize_variant(name, pnl, targets, counts)

        g = metrics.loc[(metrics["prior_months"] >= MIN_PRIOR_MONTHS) & (metrics["self_trendability_pct"] >= q)]
        summary["pool_audit"][name] = {
            "months": int(g["month"].nunique()),
            "mean_selected_count": float(g.groupby("month").size().mean()) if len(g) else 0.0,
            "median_selected_count": float(g.groupby("month").size().median()) if len(g) else 0.0,
            "median_self_percentile": float(g["self_trendability_pct"].median()) if len(g) else None,
        }

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics.to_csv(args.audit_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
