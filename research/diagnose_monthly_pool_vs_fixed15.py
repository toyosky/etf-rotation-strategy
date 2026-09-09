#!/usr/bin/env python3
"""Diagnose why monthly trendability Top40 differs from fixed15 baseline.

For each signal day, classify the relationship between the fixed15 OLS Top1 and
monthly trendability Top40 OLS Top1:
- same_pick: both choose the same ETF;
- fixed_excluded: fixed15 Top1 is not in that month's frozen Top40;
- fixed_included_but_overridden: fixed15 Top1 is in Top40, but a different ETF
  has the higher daily raw OLS Score and wins;
- fixed_no_signal / dynamic_no_signal for completeness.

The return attribution uses gross open(t+1)->open(t+2) returns to isolate
selection quality from turnover costs.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from monthly_frozen_universe import (
    BACKTEST_START,
    build_baseline_targets,
    build_targets_from_mask,
    frozen_mask,
    monthly_frozen_pools,
)
from validate_fixed15_vs_full_market import FIXED15


def target_return(open_wide: pd.DataFrame, calendar: pd.Index, signal_date: pd.Timestamp, symbol: str | None) -> float:
    if symbol is None or pd.isna(symbol):
        return 0.0
    try:
        i = int(calendar.get_loc(signal_date))
    except KeyError:
        return np.nan
    if i + 2 >= len(calendar):
        return np.nan
    d1 = pd.Timestamp(calendar[i + 1])
    d2 = pd.Timestamp(calendar[i + 2])
    try:
        p1 = float(open_wide.at[d1, str(symbol)])
        p2 = float(open_wide.at[d2, str(symbol)])
    except (KeyError, TypeError, ValueError):
        return np.nan
    if not (math.isfinite(p1) and math.isfinite(p2) and p1 > 0):
        return np.nan
    return p2 / p1 - 1.0


def period_label(date: pd.Timestamp) -> str:
    return "2021-2024" if date.year <= 2024 else "2025-2026"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="monthly-pool-vs-fixed15-diagnostic.json")
    p.add_argument("--daily-path", default="monthly-pool-vs-fixed15-daily.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)
    pools, _ = monthly_frozen_pools(bars, features)

    fixed_f = features.loc[features["symbol"].astype(str).isin(FIXED15)].copy()
    fixed_targets, _ = build_baseline_targets(fixed_f)
    allowed = frozen_mask(features, pools["trendability_top40"])
    dynamic_targets, _ = build_targets_from_mask(features, allowed)

    calendar = pd.Index(sorted(pd.to_datetime(bars["date"].unique())))
    open_wide = bars.pivot(index="date", columns="symbol", values="open").reindex(calendar)
    signal_dates = calendar[(calendar >= BACKTEST_START) & (calendar <= calendar[-3])]

    rows = []
    for d in signal_dates:
        d = pd.Timestamp(d)
        f = fixed_targets.get(d, None)
        x = dynamic_targets.get(d, None)
        f = str(f) if f is not None and not pd.isna(f) else None
        x = str(x) if x is not None and not pd.isna(x) else None
        month_pool = pools["trendability_top40"].get(d, set())
        fixed_in_pool = f in month_pool if f is not None else False

        if f is None:
            cat = "fixed_no_signal"
        elif x is None:
            cat = "dynamic_no_signal"
        elif f == x:
            cat = "same_pick"
        elif not fixed_in_pool:
            cat = "fixed_excluded"
        else:
            cat = "fixed_included_but_overridden"

        fr = target_return(open_wide, calendar, d, f)
        xr = target_return(open_wide, calendar, d, x)
        rows.append({
            "signal_date": d,
            "period": period_label(d),
            "category": cat,
            "fixed_target": f,
            "dynamic_target": x,
            "fixed_in_monthly_top40": fixed_in_pool,
            "fixed_gross_ret": fr,
            "dynamic_gross_ret": xr,
            "dynamic_minus_fixed": xr - fr if pd.notna(fr) and pd.notna(xr) else np.nan,
        })

    daily = pd.DataFrame(rows)

    def summarize_group(g: pd.DataFrame) -> dict:
        valid = g.dropna(subset=["fixed_gross_ret", "dynamic_gross_ret", "dynamic_minus_fixed"])
        return {
            "days": int(len(g)),
            "valid_return_days": int(len(valid)),
            "fixed_mean_daily_gross": float(valid["fixed_gross_ret"].mean()) if len(valid) else None,
            "dynamic_mean_daily_gross": float(valid["dynamic_gross_ret"].mean()) if len(valid) else None,
            "mean_daily_diff": float(valid["dynamic_minus_fixed"].mean()) if len(valid) else None,
            "dynamic_win_rate": float((valid["dynamic_minus_fixed"] > 0).mean()) if len(valid) else None,
            "sum_log_relative": float(np.log1p(valid["dynamic_gross_ret"]).sum() - np.log1p(valid["fixed_gross_ret"]).sum()) if len(valid) else None,
        }

    summary = {
        "design": "gross selection attribution: fixed15 Top1 vs monthly trendability Top40 Top1",
        "overall": summarize_group(daily),
        "fixed_target_in_pool_rate": float(daily.loc[daily["fixed_target"].notna(), "fixed_in_monthly_top40"].mean()),
        "same_pick_rate_when_fixed_signal": float((daily.loc[daily["fixed_target"].notna(), "category"] == "same_pick").mean()),
        "by_period": {},
        "by_category": {},
        "by_period_category": {},
    }
    for period, g in daily.groupby("period"):
        summary["by_period"][period] = summarize_group(g)
    for cat, g in daily.groupby("category"):
        summary["by_category"][cat] = summarize_group(g)
    for (period, cat), g in daily.groupby(["period", "category"]):
        summary["by_period_category"][f"{period}|{cat}"] = summarize_group(g)

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    daily.to_csv(args.daily_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
