#!/usr/bin/env python3
"""Attribute why healthy OLS leaders differ between fixed15 and Cluster90.

Preregistered in research/healthy_trend_universe_attribution_20260909.md.
Research only; no strategy changes or threshold search.
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
from selected_top1_lifespan_diagnostic import add_life_labels
from cluster90_resistance_score_v1_test import build_needed_profiles

START = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")
RES_THRESHOLD = 75.0
CASH = "511220"


def add_extra_state(features: pd.DataFrame) -> pd.DataFrame:
    f = features.sort_values(["symbol", "date"]).copy()
    f["symbol"] = f["symbol"].astype(str)
    f["score_delta"] = f.groupby("symbol", sort=False)["score"].diff()
    parts = []
    for _, g0 in f.groupby("symbol", sort=False):
        g = g0.sort_values("date").copy()
        close = g["close"].astype(float).to_numpy()
        n = len(g)
        vals = np.full(n, np.nan)
        if n > 20:
            vals[:-20] = close[20:] / close[:-20] - 1.0
        g["fwd20_close"] = vals
        parts.append(g)
    return pd.concat(parts, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)


def align_targets(targets: pd.Series, calendar: pd.Index) -> pd.Series:
    x = targets.copy()
    x.index = pd.to_datetime(x.index)
    return x.reindex(calendar)


def signal_tenure_map(aligned: pd.Series) -> dict[pd.Timestamp, int]:
    vals = aligned.astype(object).to_numpy()
    out = {}
    for i in range(len(vals)):
        if pd.isna(vals[i]):
            continue
        if i > 0 and pd.notna(vals[i-1]) and vals[i-1] == vals[i]:
            continue
        j = i
        while j + 1 < len(vals) and pd.notna(vals[j+1]) and vals[j+1] == vals[i]:
            j += 1
        out[pd.Timestamp(aligned.index[i])] = int(j - i + 1)
    return out


def cluster_env(features: pd.DataFrame, c90: dict, calendar: pd.Index) -> pd.DataFrame:
    rows = []
    for d in calendar:
        reps = set(map(str, c90.get(pd.Timestamp(d), set())))
        day = features.loc[
            (features["date"] == d)
            & features["symbol"].isin(reps)
            & features["trend_eligible"].fillna(False).astype(bool),
            ["symbol", "score"],
        ].dropna(subset=["score"]).sort_values(["score", "symbol"], ascending=[False, True])
        if day.empty:
            rows.append({"date": d, "candidate_count": 0, "top1": None, "score1": np.nan,
                         "score2": np.nan, "score_ratio12": np.nan, "score_div_median": np.nan})
            continue
        s1 = float(day.iloc[0]["score"])
        s2 = float(day.iloc[1]["score"]) if len(day) >= 2 else np.nan
        med = float(day["score"].median())
        rows.append({
            "date": d,
            "candidate_count": int(len(day)),
            "top1": str(day.iloc[0]["symbol"]),
            "score1": s1,
            "score2": s2,
            "score_ratio12": s1 / s2 if np.isfinite(s2) and abs(s2) > 1e-12 else np.nan,
            "score_div_median": s1 / med if np.isfinite(med) and abs(med) > 1e-12 else np.nan,
        })
    return pd.DataFrame(rows)


def make_entries(name: str, targets: pd.Series, calendar: pd.Index, state: pd.DataFrame,
                 profiles: pd.DataFrame, env: pd.DataFrame | None = None) -> pd.DataFrame:
    aligned = align_targets(targets, calendar)
    prev = aligned.shift(1)
    is_entry = aligned.notna() & (prev.isna() | (aligned.astype(object) != prev.astype(object)))
    base = pd.DataFrame({"signal_date": calendar[is_entry.to_numpy()], "symbol": aligned.loc[is_entry].astype(str).values})
    base["selector"] = name
    tenures = signal_tenure_map(aligned)
    base["signal_tenure"] = base["signal_date"].map(tenures)

    cols = ["date", "symbol", "score", "score_delta", "raw_episode_age", "remaining_raw20",
            "remaining_ma10_20", "remaining_mom5_20", "fwd5_close", "fwd10_close", "fwd20_close"]
    st = state[cols].copy()
    base = base.merge(st, left_on=["signal_date", "symbol"], right_on=["date", "symbol"], how="left").drop(columns=["date"])
    pr = profiles[["date", "symbol", "resistance_pct252"]].copy()
    base = base.merge(pr, left_on=["signal_date", "symbol"], right_on=["date", "symbol"], how="left").drop(columns=["date"])
    if env is not None:
        base = base.merge(env.drop(columns=["top1"]), left_on="signal_date", right_on="date", how="left").drop(columns=["date"])
    base["period"] = np.where(base["signal_date"] < SPLIT, "2021-2024", "2025-2026")
    base["is_fixed15"] = base["symbol"].isin(set(map(str, FIXED15)))
    base["healthy"] = (
        base["score_delta"].notna() & (base["score_delta"] > 0)
        & base["resistance_pct252"].notna() & (base["resistance_pct252"] < RES_THRESHOLD)
    )
    return base.loc[base["signal_date"] >= START].reset_index(drop=True)


def summarize_group(g: pd.DataFrame) -> dict:
    if g.empty:
        return {"n": 0}
    sym_means = g.groupby("symbol")[["fwd5_close", "fwd10_close", "fwd20_close"]].mean()
    return {
        "n": int(len(g)),
        "symbols": int(g["symbol"].nunique()),
        "fwd5_mean": float(g["fwd5_close"].mean()),
        "fwd10_mean": float(g["fwd10_close"].mean()),
        "fwd20_mean": float(g["fwd20_close"].mean()),
        "fwd5_symbol_equal": float(sym_means["fwd5_close"].mean()),
        "fwd10_symbol_equal": float(sym_means["fwd10_close"].mean()),
        "fwd20_symbol_equal": float(sym_means["fwd20_close"].mean()),
        "fwd10_positive_share": float((g["fwd10_close"] > 0).mean()),
        "remaining_raw20_mean": float(g["remaining_raw20"].mean()),
        "remaining_ma10_mean": float(g["remaining_ma10_20"].mean()),
        "remaining_mom5_mean": float(g["remaining_mom5_20"].mean()),
        "episode_age_mean": float(g["raw_episode_age"].mean()),
        "signal_tenure_mean": float(g["signal_tenure"].mean()),
        "signal_tenure_median": float(g["signal_tenure"].median()),
        "score_delta_mean": float(g["score_delta"].mean()),
        "resistance_pct_mean": float(g["resistance_pct252"].mean()),
        "candidate_count_mean": float(g["candidate_count"].mean()) if "candidate_count" in g else None,
        "score_ratio12_mean": float(g["score_ratio12"].mean()) if "score_ratio12" in g else None,
        "score_div_median_mean": float(g["score_div_median"].mean()) if "score_div_median" in g else None,
    }


def grouped_summary(entries: pd.DataFrame, group_cols: list[str]) -> dict:
    out = {}
    h = entries.loc[entries["healthy"]].copy()
    if h.empty:
        return out
    for keys, g in h.groupby(group_cols, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        label = "|".join(map(str, keys))
        out[label] = summarize_group(g)
    return out


def paired_disagreement(c90_entries: pd.DataFrame, fixed_targets: pd.Series, calendar: pd.Index,
                        state: pd.DataFrame) -> pd.DataFrame:
    fixed = align_targets(fixed_targets, calendar)
    st = state.set_index(["date", "symbol"])
    rows = []
    for r in c90_entries.loc[c90_entries["healthy"] & (~c90_entries["is_fixed15"])].itertuples(index=False):
        d = pd.Timestamp(r.signal_date)
        fs = fixed.get(d, np.nan)
        if pd.isna(fs):
            continue
        fs = str(fs)
        if fs == CASH or fs == str(r.symbol):
            continue
        key = (d, fs)
        if key not in st.index:
            continue
        q = st.loc[key]
        if isinstance(q, pd.DataFrame):
            q = q.iloc[0]
        if not bool(q["trend_eligible"]):
            continue
        rows.append({
            "signal_date": d,
            "period": "2021-2024" if d < SPLIT else "2025-2026",
            "cluster_symbol": str(r.symbol), "fixed_symbol": fs,
            "cluster_fwd5": r.fwd5_close, "fixed_fwd5": q["fwd5_close"],
            "cluster_fwd10": r.fwd10_close, "fixed_fwd10": q["fwd10_close"],
            "cluster_fwd20": r.fwd20_close, "fixed_fwd20": q["fwd20_close"],
            "cluster_remaining_raw20": r.remaining_raw20, "fixed_remaining_raw20": q["remaining_raw20"],
            "candidate_count": getattr(r, "candidate_count", np.nan),
        })
    return pd.DataFrame(rows)


def summarize_pairs(p: pd.DataFrame) -> dict:
    out = {}
    if p.empty:
        return out
    for period, g in p.groupby("period", sort=True):
        d5 = g["cluster_fwd5"] - g["fixed_fwd5"]
        d10 = g["cluster_fwd10"] - g["fixed_fwd10"]
        d20 = g["cluster_fwd20"] - g["fixed_fwd20"]
        life = g["cluster_remaining_raw20"] - g["fixed_remaining_raw20"]
        out[period] = {
            "n": int(len(g)),
            "cluster_minus_fixed_fwd5_mean": float(d5.mean()),
            "cluster_minus_fixed_fwd10_mean": float(d10.mean()),
            "cluster_minus_fixed_fwd20_mean": float(d20.mean()),
            "cluster_beats_fixed_fwd10_share": float((d10 > 0).mean()),
            "cluster_minus_fixed_remaining_raw20_mean": float(life.mean()),
        }
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="healthy-trend-universe-attribution-summary.json")
    p.add_argument("--entries-path", default="healthy-trend-universe-attribution-entries.csv")
    p.add_argument("--pairs-path", default="healthy-trend-universe-attribution-pairs.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    base_features = build_features(bars)
    features = add_extra_state(add_life_labels(base_features))
    features["symbol"] = features["symbol"].astype(str)

    pools, _ = build_monthly_rep_pools(bars, features)
    c90_allowed = frozen_mask(features, pools["cluster90"])
    c90_targets, _ = build_targets_from_mask(features, c90_allowed)
    fixed_f = features.loc[features["symbol"].isin(set(map(str, FIXED15)))].copy()
    fixed_targets, _ = build_baseline_targets(fixed_f)

    calendar = pd.Index(sorted(pd.to_datetime(features.loc[features["date"] >= START, "date"].unique())), name="date")
    env = cluster_env(features, pools["cluster90"], calendar)

    needed = set(c90_targets.dropna().astype(str).unique()) | set(fixed_targets.dropna().astype(str).unique())
    profiles = build_needed_profiles(bars, needed)

    c90_entries = make_entries("cluster90", c90_targets, calendar, features, profiles, env)
    fixed_entries = make_entries("fixed15", fixed_targets, calendar, features, profiles, None)

    # Attach Cluster90 environment to fixed entries for same-date context diagnostics.
    fixed_entries = fixed_entries.merge(env.drop(columns=["top1"]), left_on="signal_date", right_on="date", how="left").drop(columns=["date"])

    # Product-history control: at least 252 observations strictly before 2021-01-01.
    pre_counts = bars.loc[pd.to_datetime(bars["date"]) < START].groupby(bars["symbol"].astype(str)).size().to_dict()
    for e in (c90_entries, fixed_entries):
        e["pre2021_252bars"] = e["symbol"].map(lambda s: int(pre_counts.get(str(s), 0)) >= 252)

    pairs = paired_disagreement(c90_entries, fixed_targets, calendar, features)
    all_entries = pd.concat([fixed_entries, c90_entries], ignore_index=True)

    summary = {
        "definition": "healthy = new Top1 entry, ScoreDelta>0, valid ResistancePct252<75",
        "primary": "2021-2024",
        "posterior": "2025-2026",
        "A_cluster90_identity": grouped_summary(c90_entries, ["period", "is_fixed15"]),
        "B_selector_comparison": grouped_summary(all_entries, ["period", "selector"]),
        "C_same_asset_context_fixed15_only": grouped_summary(all_entries.loc[all_entries["is_fixed15"]], ["period", "selector"]),
        "D_paired_disagreement": summarize_pairs(pairs),
        "E_historical_product_control_cluster90_outside": grouped_summary(
            c90_entries.loc[~c90_entries["is_fixed15"]], ["period", "pre2021_252bars"]
        ),
        "F_environment": {},
        "counts": {
            "cluster90_entries": int(len(c90_entries)),
            "cluster90_healthy": int(c90_entries["healthy"].sum()),
            "fixed15_entries": int(len(fixed_entries)),
            "fixed15_healthy": int(fixed_entries["healthy"].sum()),
        },
    }

    h = c90_entries.loc[c90_entries["healthy"]].copy()
    for period, g in h.groupby("period", sort=True):
        med = float(g["candidate_count"].median()) if len(g) else np.nan
        lo = g.loc[g["candidate_count"] <= med]
        hi = g.loc[g["candidate_count"] > med]
        summary["F_environment"][period] = {
            "candidate_count_median": med,
            "low_breadth": summarize_group(lo),
            "high_breadth": summarize_group(hi),
            "corr_candidate_count_fwd10": float(g[["candidate_count", "fwd10_close"]].corr(method="spearman").iloc[0,1]) if len(g) >= 3 else None,
            "corr_score_ratio12_fwd10": float(g[["score_ratio12", "fwd10_close"]].corr(method="spearman").iloc[0,1]) if len(g) >= 3 else None,
        }

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    all_entries.to_csv(args.entries_path, index=False)
    pairs.to_csv(args.pairs_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
