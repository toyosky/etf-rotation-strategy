#!/usr/bin/env python3
"""Diagnose cross-sectional independence of healthy Cluster90 leaders.
Research only; no threshold search or trading-rule changes.
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
from monthly_frozen_universe import build_targets_from_mask, frozen_mask
from selected_top1_lifespan_diagnostic import add_life_labels
from cluster90_resistance_score_v1_test import build_needed_profiles
from healthy_trend_universe_attribution import add_extra_state, make_entries, cluster_env

START = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")
LOOKBACK = 120
MIN_OVERLAP = 60


def candidate_symbols_on_date(features: pd.DataFrame, c90: dict, d: pd.Timestamp) -> list[str]:
    reps = set(map(str, c90.get(pd.Timestamp(d), set())))
    day = features.loc[
        (features["date"] == d)
        & features["symbol"].isin(reps)
        & features["trend_eligible"].fillna(False).astype(bool),
        "symbol",
    ]
    return day.astype(str).tolist()


def independence_for_event(ret_wide: pd.DataFrame, leader: str, peers: list[str], d: pd.Timestamp) -> dict:
    peers = [str(s) for s in peers if str(s) != str(leader) and str(s) in ret_wide.columns]
    if str(leader) not in ret_wide.columns or not peers:
        return {}
    hist = ret_wide.loc[ret_wide.index < d, [str(leader)] + peers].tail(LOOKBACK)
    lead = hist[str(leader)]
    corrs = []
    for s in peers:
        x = pd.concat([lead, hist[s]], axis=1).dropna()
        if len(x) >= MIN_OVERLAP:
            c = x.iloc[:,0].corr(x.iloc[:,1])
            if pd.notna(c):
                corrs.append(float(c))
    factor = hist[peers].mean(axis=1, skipna=True)
    xf = pd.concat([lead, factor], axis=1).dropna()
    factor_corr = float(xf.iloc[:,0].corr(xf.iloc[:,1])) if len(xf) >= MIN_OVERLAP else np.nan
    if not corrs:
        return {"peer_n": 0, "mean_peer_corr": np.nan, "median_peer_corr": np.nan,
                "share_peer_corr_ge50": np.nan, "factor_corr": factor_corr}
    a = np.asarray(corrs, dtype=float)
    return {
        "peer_n": int(len(a)),
        "mean_peer_corr": float(a.mean()),
        "median_peer_corr": float(np.median(a)),
        "share_peer_corr_ge50": float((a >= 0.50).mean()),
        "factor_corr": factor_corr,
    }


def summarize(g: pd.DataFrame) -> dict:
    if g.empty:
        return {"n": 0}
    return {
        "n": int(len(g)),
        "symbols": int(g["symbol"].nunique()),
        "fwd10_mean": float(g["fwd10_close"].mean()),
        "fwd10_positive_share": float((g["fwd10_close"] > 0).mean()),
        "mean_peer_corr": float(g["mean_peer_corr"].mean()),
        "median_peer_corr": float(g["median_peer_corr"].mean()),
        "share_peer_corr_ge50": float(g["share_peer_corr_ge50"].mean()),
        "factor_corr": float(g["factor_corr"].mean()),
        "signal_tenure_mean": float(g["signal_tenure"].mean()),
        "remaining_raw20_mean": float(g["remaining_raw20"].mean()),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="healthy-leader-independence-summary.json")
    p.add_argument("--events-path", default="healthy-leader-independence-events.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = add_extra_state(add_life_labels(build_features(bars)))
    features["symbol"] = features["symbol"].astype(str)
    pools, _ = build_monthly_rep_pools(bars, features)
    c90 = pools["cluster90"]
    c90_allowed = frozen_mask(features, c90)
    targets, _ = build_targets_from_mask(features, c90_allowed)
    calendar = pd.Index(sorted(pd.to_datetime(features.loc[features["date"] >= START, "date"].unique())), name="date")
    env = cluster_env(features, c90, calendar)
    needed = set(targets.dropna().astype(str).unique())
    profiles = build_needed_profiles(bars, needed)
    entries = make_entries("cluster90", targets, calendar, features, profiles, env)
    entries = entries.loc[entries["healthy"]].copy()

    close = bars.pivot(index="date", columns="symbol", values="close").sort_index()
    close.columns = close.columns.astype(str)
    ret = close.pct_change(fill_method=None)

    rows = []
    for r in entries.itertuples(index=False):
        d = pd.Timestamp(r.signal_date)
        peers = candidate_symbols_on_date(features, c90, d)
        z = independence_for_event(ret, str(r.symbol), peers, d)
        q = r._asdict()
        q.update(z)
        rows.append(q)
    ev = pd.DataFrame(rows)
    ev = ev.loc[ev["peer_n"].fillna(0) > 0].copy()

    summary = {"identity": {}, "outside_median_split": {}, "correlations": {}}
    for period, gp in ev.groupby("period", sort=True):
        summary["identity"][period] = {
            "fixed15": summarize(gp.loc[gp["is_fixed15"]]),
            "outside": summarize(gp.loc[~gp["is_fixed15"]]),
        }
        out = gp.loc[~gp["is_fixed15"]].copy()
        if len(out):
            med = float(out["factor_corr"].median())
            summary["outside_median_split"][period] = {
                "factor_corr_median": med,
                "more_independent": summarize(out.loc[out["factor_corr"] <= med]),
                "more_common_factor": summarize(out.loc[out["factor_corr"] > med]),
            }
        corr = {}
        for col in ["mean_peer_corr", "median_peer_corr", "share_peer_corr_ge50", "factor_corr"]:
            x = gp[[col, "fwd10_close"]].dropna()
            corr[col] = float(x.corr(method="spearman").iloc[0,1]) if len(x) >= 3 else None
        summary["correlations"][period] = corr

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    ev.to_csv(args.events_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
