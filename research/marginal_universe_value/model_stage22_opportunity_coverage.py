#!/usr/bin/env python3
"""Stage22 opportunity coverage audit.

Mechanism audit only. No model fit, threshold search, asset selection, or policy
backtest. Compares Fixed15 with all point-in-time trend-eligible ETFs and the
frozen monthly Cluster90 representative set at trading month-end.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from monthly_liquidity_cluster_universe import build_monthly_rep_pools
from monthly_frozen_universe import frozen_mask
from validate_fixed15_vs_full_market import FIXED15

START = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")
CASH = "511220"
OUT = Path("muv-stage22-opportunity-coverage-report.json")
OUT_MONTHS = Path("muv-stage22-opportunity-coverage-months.csv")


def add_fwd20(features: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for _, g0 in features.groupby("symbol", sort=False):
        g = g0.sort_values("date").copy()
        close = pd.to_numeric(g["close"], errors="coerce").to_numpy(dtype=float)
        vals = np.full(len(g), np.nan, dtype=float)
        if len(g) > 20:
            vals[:-20] = close[20:] / close[:-20] - 1.0
        g["fwd20_close"] = vals
        parts.append(g)
    return pd.concat(parts, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)


def month_end_dates(features: pd.DataFrame) -> list[pd.Timestamp]:
    d = pd.DataFrame({"date": pd.to_datetime(features.loc[features["date"] >= START, "date"].drop_duplicates())})
    d["month"] = d["date"].dt.to_period("M")
    return [pd.Timestamp(x) for x in d.groupby("month")["date"].max().sort_values().tolist()]


def pool_stats(g: pd.DataFrame, prefix: str) -> dict:
    z = g.dropna(subset=["score", "fwd20_close"]).copy()
    if z.empty:
        return {
            f"{prefix}_candidate_count": 0,
            f"{prefix}_score_top1_symbol": None,
            f"{prefix}_score_top1_fwd20": np.nan,
            f"{prefix}_oracle_best_symbol": None,
            f"{prefix}_oracle_best_fwd20": np.nan,
            f"{prefix}_oracle_top3_mean_fwd20": np.nan,
        }
    by_score = z.sort_values(["score", "symbol"], ascending=[False, True])
    by_future = z.sort_values(["fwd20_close", "symbol"], ascending=[False, True])
    return {
        f"{prefix}_candidate_count": int(len(z)),
        f"{prefix}_score_top1_symbol": str(by_score.iloc[0]["symbol"]),
        f"{prefix}_score_top1_fwd20": float(by_score.iloc[0]["fwd20_close"]),
        f"{prefix}_oracle_best_symbol": str(by_future.iloc[0]["symbol"]),
        f"{prefix}_oracle_best_fwd20": float(by_future.iloc[0]["fwd20_close"]),
        f"{prefix}_oracle_top3_mean_fwd20": float(by_future.head(3)["fwd20_close"].mean()),
    }


def finite_mean(s: pd.Series):
    x = pd.to_numeric(s, errors="coerce").dropna()
    return float(x.mean()) if len(x) else None


def share_positive(s: pd.Series):
    x = pd.to_numeric(s, errors="coerce").dropna()
    return float((x > 0).mean()) if len(x) else None


def summarize(g: pd.DataFrame) -> dict:
    if g.empty:
        return {"n_months": 0}
    return {
        "n_months": int(len(g)),
        "fixed_candidate_count_mean": finite_mean(g["fixed_candidate_count"]),
        "full_candidate_count_mean": finite_mean(g["full_candidate_count"]),
        "cluster90_candidate_count_mean": finite_mean(g["cluster90_candidate_count"]),
        "full_minus_fixed_oracle_best_mean": finite_mean(g["full_minus_fixed_oracle_best"]),
        "full_minus_fixed_oracle_top3_mean": finite_mean(g["full_minus_fixed_oracle_top3_mean"]),
        "cluster90_minus_fixed_oracle_best_mean": finite_mean(g["cluster90_minus_fixed_oracle_best"]),
        "cluster90_minus_fixed_oracle_top3_mean": finite_mean(g["cluster90_minus_fixed_oracle_top3_mean"]),
        "full_minus_fixed_score_top1_mean": finite_mean(g["full_minus_fixed_score_top1"]),
        "cluster90_minus_fixed_score_top1_mean": finite_mean(g["cluster90_minus_fixed_score_top1"]),
        "full_oracle_best_gap_positive_share": share_positive(g["full_minus_fixed_oracle_best"]),
        "full_oracle_top3_gap_positive_share": share_positive(g["full_minus_fixed_oracle_top3_mean"]),
        "cluster90_oracle_best_gap_positive_share": share_positive(g["cluster90_minus_fixed_oracle_best"]),
        "cluster90_oracle_top3_gap_positive_share": share_positive(g["cluster90_minus_fixed_oracle_top3_mean"]),
        "full_oracle_best_outside_fixed15_share": float(g["full_oracle_best_outside_fixed15"].mean()),
    }


def nonnegative(x) -> bool:
    return x is not None and np.isfinite(x) and x >= 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output", default=str(OUT))
    ap.add_argument("--months-output", default=str(OUT_MONTHS))
    args = ap.parse_args()
    if not args.database_url:
        raise RuntimeError("ETF_DAILY_BARS_DATABASE_URL is required")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = add_fwd20(build_features(bars))
    features["symbol"] = features["symbol"].astype(str)

    pools, _ = build_monthly_rep_pools(bars, features)
    c90_allowed = pd.Series(frozen_mask(features, pools["cluster90"]), index=features.index)

    fixed_set = set(map(str, FIXED15)) - {CASH}
    rows = []
    for d in month_end_dates(features):
        base = features.loc[
            (features["date"] == d)
            & features["trend_eligible"].fillna(False).astype(bool)
            & (features["symbol"] != CASH),
            ["symbol", "score", "fwd20_close"],
        ].copy()
        # Last months without a full 20-day outcome horizon are excluded.
        base = base.dropna(subset=["fwd20_close"])
        if base.empty:
            continue

        idx = features.index[(features["date"] == d) & features["trend_eligible"].fillna(False).astype(bool) & (features["symbol"] != CASH)]
        c90_syms = set(features.loc[idx[c90_allowed.loc[idx].to_numpy(dtype=bool)], "symbol"].astype(str))

        fixed = base.loc[base["symbol"].isin(fixed_set)].copy()
        full = base.copy()
        c90 = base.loc[base["symbol"].isin(c90_syms)].copy()

        row = {"date": d, "period": "2021-24" if d < SPLIT else "2025-26"}
        row.update(pool_stats(fixed, "fixed"))
        row.update(pool_stats(full, "full"))
        row.update(pool_stats(c90, "cluster90"))

        row["full_minus_fixed_oracle_best"] = row["full_oracle_best_fwd20"] - row["fixed_oracle_best_fwd20"]
        row["full_minus_fixed_oracle_top3_mean"] = row["full_oracle_top3_mean_fwd20"] - row["fixed_oracle_top3_mean_fwd20"]
        row["cluster90_minus_fixed_oracle_best"] = row["cluster90_oracle_best_fwd20"] - row["fixed_oracle_best_fwd20"]
        row["cluster90_minus_fixed_oracle_top3_mean"] = row["cluster90_oracle_top3_mean_fwd20"] - row["fixed_oracle_top3_mean_fwd20"]
        row["full_minus_fixed_score_top1"] = row["full_score_top1_fwd20"] - row["fixed_score_top1_fwd20"]
        row["cluster90_minus_fixed_score_top1"] = row["cluster90_score_top1_fwd20"] - row["fixed_score_top1_fwd20"]
        row["full_oracle_best_outside_fixed15"] = bool(row["full_oracle_best_symbol"] not in fixed_set) if row["full_oracle_best_symbol"] else False
        rows.append(row)

    monthly = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    if monthly.empty:
        raise RuntimeError("Stage22 produced no month-end rows")
    monthly.to_csv(args.months_output, index=False)

    overall = summarize(monthly)
    by_era = {str(p): summarize(g) for p, g in monthly.groupby("period", sort=True)}

    full_supported = (
        nonnegative(overall.get("full_minus_fixed_oracle_best_mean"))
        and nonnegative(overall.get("full_minus_fixed_oracle_top3_mean"))
        and all(nonnegative(v.get("full_minus_fixed_oracle_best_mean")) and nonnegative(v.get("full_minus_fixed_oracle_top3_mean")) for v in by_era.values())
    )
    c90_no_reversal = all(
        nonnegative(v.get("cluster90_minus_fixed_oracle_best_mean"))
        and nonnegative(v.get("cluster90_minus_fixed_oracle_top3_mean"))
        for v in [overall, *by_era.values()]
    )
    stable = bool(full_supported and c90_no_reversal)

    report = {
        "version": "muv_stage22_opportunity_coverage_audit_20260913",
        "frozen_question": "Does Fixed15 materially under-cover point-in-time qualified ETF trends that subsequently deliver stronger 20-day continuation, consistently across eras?",
        "design": {
            "new_model_fit": False,
            "feature_search": False,
            "threshold_search": False,
            "policy_backtest": False,
            "decision_dates": "trading month-end",
            "candidate_rule": "existing frozen trend_eligible",
            "outcome": "forward 20-trading-day close return; label-side only",
            "comparators": ["fixed15", "full_market", "cluster90"],
            "oracle_metrics_are_nontradable_coverage_ceilings": True,
        },
        "overall": overall,
        "by_era": by_era,
        "predeclared_interpretation": {
            "stable_opportunity_coverage_gap": stable,
            "full_market_gap_supported": bool(full_supported),
            "cluster90_no_qualitative_reversal": bool(c90_no_reversal),
            "rule": "Support a structural coverage gap only if full-market oracle best and top3-mean gaps are non-negative overall and in both eras, and Cluster90 does not reverse the qualitative conclusion. No threshold or ETF-subset tuning on this sample.",
        },
    }
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
