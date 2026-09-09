#!/usr/bin/env python3
"""Corrected walk-forward health filters, alone and with monthly cluster reps.

This experiment uses the frozen RAW-OLS episode contract:
- an episode starts only when raw OLS turns positive on a point-in-time
  universe-eligible day;
- previous-state detection ignores universe eligibility and D2;
- D2 remains only a daily tradability condition through trend_eligible.

At each valid raw episode start, health admission uses only strictly prior valid
raw episode starts and an expanding historical 20th percentile floor:
  H1: slope_delta >= prior q20
  H2: H1 + current_resid >= prior q20
  H3: H2 + ret5 >= prior q20
  H4: H3 + dist_high20 >= prior q20
Admission is frozen for the raw OLS episode.  No upper/maturity veto is used;
the corrected episode study did not support a robust extreme-Score rejection.

The same health variants are tested on:
- full point-in-time universe;
- monthly liquidity-first correlation representatives at 0.90;
- monthly liquidity-first correlation representatives at 0.95.
Daily ranking remains raw OLS Score Top1.  This is research, not production.
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
from monthly_frozen_universe import build_baseline_targets, build_targets_from_mask, frozen_mask
from validate_fixed15_vs_full_market import FIXED15
from walk_forward_candidate_pool import backtest_open_to_open, summarize_variant

MIN_PRIOR_EPISODES = 200
HEALTH_FEATURES = ["slope_delta", "current_resid", "ret5", "dist_high20"]
HEALTH_VARIANTS = ["h1", "h2", "h3", "h4"]


def attach_correct_raw_episode_ids(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach valid raw episode start only if raw turn-positive day was universe eligible."""
    parts: list[pd.DataFrame] = []
    starts_parts: list[pd.DataFrame] = []
    start_cols = [
        "symbol", "date", "slope_delta", "current_resid", "ret5", "dist_high20",
        "score", "slope", "r2", "annual",
    ]

    for _, g in features.groupby("symbol", sort=False):
        g = g.sort_values("date").copy()
        raw = (
            (g["annual"] > 0) & (g["r2"] > 0) & (g["score"] > 0)
        ).fillna(False)
        raw_start = raw & (~raw.shift(1, fill_value=False))
        valid_start = raw_start & g["universe_eligible"].fillna(False).astype(bool)

        raw_start_date = g["date"].where(raw_start).ffill().where(raw)
        valid_dates = set(pd.to_datetime(g.loc[valid_start, "date"]).tolist())
        g["episode_start_date"] = raw_start_date.where(raw_start_date.isin(valid_dates))
        parts.append(g)

        st = g.loc[valid_start, start_cols].copy().rename(columns={"date": "start_date"})
        starts_parts.append(st)

    f = pd.concat(parts, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
    starts = pd.concat(starts_parts, ignore_index=True).sort_values(["start_date", "symbol"]).reset_index(drop=True)
    return f, starts


def _strict_prior_date_quantile(starts: pd.DataFrame, feature: str, q: float) -> pd.Series:
    """Expanding quantile using only episodes whose start_date is strictly earlier."""
    raw = starts[feature].astype(float).expanding(min_periods=MIN_PRIOR_EPISODES).quantile(q).shift(1)
    first_mask = ~starts["start_date"].duplicated()
    date_map = dict(zip(starts.loc[first_mask, "start_date"], raw.loc[first_mask]))
    return starts["start_date"].map(date_map).astype(float)


def add_admission(starts: pd.DataFrame) -> pd.DataFrame:
    s = starts.copy().sort_values(["start_date", "symbol"]).reset_index(drop=True)
    date_counts = s.groupby("start_date", sort=True).size()
    prior_counts = date_counts.cumsum().shift(1, fill_value=0)
    s["prior_episode_count"] = s["start_date"].map(prior_counts).astype(int)
    calibrated = s["prior_episode_count"] >= MIN_PRIOR_EPISODES

    for feature in HEALTH_FEATURES:
        s[f"{feature}_q20"] = _strict_prior_date_quantile(s, feature, 0.20)

    s["pass_h1"] = calibrated & (s["slope_delta"] >= s["slope_delta_q20"])
    s["pass_h2"] = s["pass_h1"] & (s["current_resid"] >= s["current_resid_q20"])
    s["pass_h3"] = s["pass_h2"] & (s["ret5"] >= s["ret5_q20"])
    s["pass_h4"] = s["pass_h3"] & (s["dist_high20"] >= s["dist_high20_q20"])
    return s


def merge_admission(features: pd.DataFrame, starts: pd.DataFrame) -> pd.DataFrame:
    cols = ["symbol", "start_date", "prior_episode_count"] + [f"pass_{h}" for h in HEALTH_VARIANTS]
    q = starts[cols].rename(columns={"start_date": "episode_start_date"})
    f = features.merge(q, on=["symbol", "episode_start_date"], how="left", validate="many_to_one")
    for h in HEALTH_VARIANTS:
        f[f"pass_{h}"] = f[f"pass_{h}"].fillna(False).astype(bool)
    return f


def health_allowed(features: pd.DataFrame, h: str | None) -> pd.Series:
    if h is None:
        return pd.Series(True, index=features.index, dtype=bool)
    return features[f"pass_{h}"].fillna(False).astype(bool)


def run_variant(label: str, bars: pd.DataFrame, features: pd.DataFrame, allowed: pd.Series) -> dict:
    targets, counts = build_targets_from_mask(features, allowed)
    pnl = backtest_open_to_open(bars, targets)
    return summarize_variant(label, pnl, targets, counts)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="corrected-health-cluster-summary.json")
    p.add_argument("--admission-path", default="corrected-health-admission.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)
    features, starts = attach_correct_raw_episode_ids(features)
    starts = add_admission(starts)
    features = merge_admission(features, starts)
    pools, _ = build_monthly_rep_pools(bars, features)

    summary = {
        "design": {
            "episode_contract": "raw OLS turn-positive; current start day universe eligible; prior state ignores universe/D2",
            "health_floor": "strictly-prior expanding 20th percentile",
            "health_variants": {
                "h1": ["slope_delta"],
                "h2": ["slope_delta", "current_resid"],
                "h3": ["slope_delta", "current_resid", "ret5"],
                "h4": ["slope_delta", "current_resid", "ret5", "dist_high20"],
            },
            "admission_frozen_for_raw_episode": True,
            "maturity_upper_veto": False,
            "monthly_cluster_thresholds": [0.90, 0.95],
            "daily_ranking": "raw OLS Score Top1 among allowed trend_eligible ETFs",
        },
        "episode_admission": {},
        "variants": {},
    }

    eval_starts = starts.loc[starts["start_date"] >= pd.Timestamp("2021-01-01")]
    summary["episode_admission"]["episodes_2021plus"] = int(len(eval_starts))
    for h in HEALTH_VARIANTS:
        summary["episode_admission"][h] = {
            "admitted": int(eval_starts[f"pass_{h}"].sum()),
            "rate": float(eval_starts[f"pass_{h}"].mean()),
        }

    # Same-engine fixed15 reference.
    fixed_f = features.loc[features["symbol"].astype(str).isin(FIXED15)].copy()
    ft, fc = build_baseline_targets(fixed_f)
    fp = backtest_open_to_open(bars, ft)
    summary["variants"]["fixed15_baseline"] = summarize_variant("fixed15_baseline", fp, ft, fc)

    # Full market corrected health variants, including no-health baseline.
    summary["variants"]["full_baseline"] = run_variant(
        "full_baseline", bars, features, pd.Series(True, index=features.index, dtype=bool)
    )
    for h in HEALTH_VARIANTS:
        label = f"full_{h}"
        summary["variants"][label] = run_variant(label, bars, features, health_allowed(features, h))

    # Monthly neutral correlation representatives x health admission.
    for threshold in (0.90, 0.95):
        cluster_name = f"cluster{int(threshold*100)}"
        cluster_mask = frozen_mask(features, pools[cluster_name])
        label = f"{cluster_name}_baseline"
        summary["variants"][label] = run_variant(label, bars, features, cluster_mask)
        for h in HEALTH_VARIANTS:
            label = f"{cluster_name}_{h}"
            summary["variants"][label] = run_variant(
                label, bars, features, cluster_mask & health_allowed(features, h)
            )

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    cols = [
        "symbol", "start_date", "prior_episode_count", "slope_delta", "current_resid", "ret5", "dist_high20",
        "slope_delta_q20", "current_resid_q20", "ret5_q20", "dist_high20_q20",
        "pass_h1", "pass_h2", "pass_h3", "pass_h4",
    ]
    starts.loc[starts["start_date"] >= pd.Timestamp("2021-01-01"), cols].to_csv(args.admission_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
