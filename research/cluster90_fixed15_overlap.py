#!/usr/bin/env python3
"""Measure how much of the fixed15 actually participates in Cluster90.

This diagnostic separates:
1) monthly frozen Cluster90 representatives;
2) daily trend_eligible candidates that actually enter OLS ranking;
3) Cluster90 daily Top1/Top2/Top3 composition.

It is descriptive only and does not optimize any strategy rule.
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
from monthly_liquidity_cluster_universe import build_monthly_rep_pools
from validate_fixed15_vs_full_market import FIXED15

START = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")


def period_of(d: pd.Timestamp) -> str:
    return "2021-2024" if d < SPLIT else "2025-2026"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="cluster90-fixed15-overlap-summary.json")
    p.add_argument("--daily-path", default="cluster90-fixed15-overlap-daily.csv")
    p.add_argument("--symbol-path", default="cluster90-fixed15-overlap-symbol.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    f = build_features(bars)
    pools, _ = build_monthly_rep_pools(bars, f)
    c90 = pools["cluster90"]
    fixed = set(map(str, FIXED15))

    f = f.loc[f["date"] >= START].copy()
    f["symbol"] = f["symbol"].astype(str)
    dates = pd.Index(sorted(pd.to_datetime(f["date"].unique())))

    rows = []
    symbol_rows = []
    for d in dates:
        day = f.loc[f["date"] == d, ["symbol", "trend_eligible", "score"]].copy()
        reps = set(map(str, c90.get(pd.Timestamp(d), set())))
        monthly_fixed = fixed & reps

        fixed_day = day.loc[day["symbol"].isin(fixed)]
        fixed_eligible = set(fixed_day.loc[fixed_day["trend_eligible"].fillna(False), "symbol"])

        cand = day.loc[
            day["symbol"].isin(reps) & day["trend_eligible"].fillna(False),
            ["symbol", "score"],
        ].sort_values(["score", "symbol"], ascending=[False, True])
        cand_syms = set(cand["symbol"])
        fixed_cand = fixed & cand_syms
        top = cand.head(3)["symbol"].astype(str).tolist()

        rows.append({
            "date": d,
            "period": period_of(pd.Timestamp(d)),
            "cluster90_rep_count": len(reps),
            "cluster90_fixed15_rep_count": len(monthly_fixed),
            "cluster90_fixed15_rep_share": len(monthly_fixed) / len(reps) if reps else np.nan,
            "fixed15_trend_eligible_count": len(fixed_eligible),
            "cluster90_candidate_count": len(cand),
            "cluster90_fixed15_candidate_count": len(fixed_cand),
            "cluster90_fixed15_candidate_share": len(fixed_cand) / len(cand) if len(cand) else np.nan,
            "fixed15_eligible_retained_share": len(fixed_cand) / len(fixed_eligible) if fixed_eligible else np.nan,
            "top1": top[0] if len(top) >= 1 else None,
            "top2": top[1] if len(top) >= 2 else None,
            "top3": top[2] if len(top) >= 3 else None,
            "top1_is_fixed15": bool(len(top) >= 1 and top[0] in fixed),
            "top2_is_fixed15": bool(len(top) >= 2 and top[1] in fixed),
            "top3_is_fixed15": bool(len(top) >= 3 and top[2] in fixed),
            "top3_fixed15_count": sum(s in fixed for s in top),
        })

        for sym in sorted(fixed):
            symbol_rows.append({
                "date": d,
                "period": period_of(pd.Timestamp(d)),
                "symbol": sym,
                "is_monthly_rep": sym in reps,
                "is_trend_eligible": sym in fixed_eligible,
                "is_cluster90_candidate": sym in fixed_cand,
                "rank": (top.index(sym) + 1) if sym in top else np.nan,
            })

    daily = pd.DataFrame(rows)
    syms = pd.DataFrame(symbol_rows)

    summary = {
        "fixed15": sorted(fixed),
        "periods": {},
        "symbol_detail": {},
    }
    for period, g in daily.groupby("period", sort=True):
        summary["periods"][period] = {
            "days": int(len(g)),
            "cluster90_rep_count_mean": float(g["cluster90_rep_count"].mean()),
            "cluster90_fixed15_rep_count_mean": float(g["cluster90_fixed15_rep_count"].mean()),
            "cluster90_fixed15_rep_share_mean": float(g["cluster90_fixed15_rep_share"].mean()),
            "fixed15_trend_eligible_count_mean": float(g["fixed15_trend_eligible_count"].mean()),
            "cluster90_candidate_count_mean": float(g["cluster90_candidate_count"].mean()),
            "cluster90_fixed15_candidate_count_mean": float(g["cluster90_fixed15_candidate_count"].mean()),
            "cluster90_fixed15_candidate_share_mean": float(g["cluster90_fixed15_candidate_share"].mean()),
            "fixed15_eligible_retained_share_mean": float(g["fixed15_eligible_retained_share"].mean()),
            "top1_fixed15_share": float(g["top1_is_fixed15"].mean()),
            "top2_fixed15_share": float(g["top2_is_fixed15"].mean()),
            "top3_rank_fixed15_share": float(g["top3_is_fixed15"].mean()),
            "top3_slots_fixed15_share": float(g["top3_fixed15_count"].sum() / (3 * len(g))),
            "days_with_any_fixed15_in_top3_share": float((g["top3_fixed15_count"] > 0).mean()),
        }

    for (period, sym), g in syms.groupby(["period", "symbol"], sort=True):
        summary["symbol_detail"].setdefault(period, {})[sym] = {
            "monthly_rep_share": float(g["is_monthly_rep"].mean()),
            "trend_eligible_share": float(g["is_trend_eligible"].mean()),
            "cluster90_candidate_share": float(g["is_cluster90_candidate"].mean()),
            "retained_when_eligible_share": float(
                g.loc[g["is_trend_eligible"], "is_cluster90_candidate"].mean()
            ) if bool(g["is_trend_eligible"].any()) else None,
            "top1_days": int((g["rank"] == 1).sum()),
            "top2_days": int((g["rank"] == 2).sum()),
            "top3_days": int((g["rank"] == 3).sum()),
        }

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    daily.to_csv(args.daily_path, index=False)
    syms.to_csv(args.symbol_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
