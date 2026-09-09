#!/usr/bin/env python3
"""Diagnose why expanded-universe OLS behaves oppositely across 2021-24 vs 2025-26.

This is a mechanism diagnostic, not a strategy optimization.

Compare actual signal-entry choices from:
- frozen fixed15 baseline
- monthly liquidity-first correlation cluster90

At each new non-cash Top1 signal, measure only contemporaneously-defined state plus
future labels for diagnosis:
- age of the current raw OLS-positive episode at signal time;
- remaining raw OLS-positive life (capped at 20 trading days);
- remaining MA10 and mom5 life (capped at 20);
- forward 5/10 close returns;
- signal holding tenure until the target changes.

Also compare cluster90 vs fixed15 on the same cluster90 entry dates when the two
selectors disagree. This directly tests whether cluster90 selected shorter-lived
trends in 2021-24 but longer-lived trends in 2025-26.
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
from monthly_liquidity_cluster_universe import build_monthly_rep_pools
from monthly_frozen_universe import build_baseline_targets, build_targets_from_mask, frozen_mask

START = pd.Timestamp("2021-01-01")
CAP = 20


def add_life_labels(features: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for _, g0 in features.groupby("symbol", sort=False):
        g = g0.sort_values("date").copy().reset_index(drop=True)
        raw = (
            (g["annual"].astype(float) > 0)
            & (g["r2"].astype(float) > 0)
            & (g["score"].astype(float) > 0)
        ).fillna(False).to_numpy(dtype=bool)
        ma10 = (g["close"].astype(float) >= g["ma10"].astype(float)).fillna(False).to_numpy(dtype=bool)
        mom5 = g["mom5_pass"].fillna(False).to_numpy(dtype=bool)
        close = g["close"].astype(float).to_numpy()
        n = len(g)

        age = np.full(n, np.nan)
        run_age = -1
        for i in range(n):
            if raw[i]:
                run_age = run_age + 1 if i > 0 and raw[i - 1] else 0
                age[i] = run_age
            else:
                run_age = -1

        def remaining(arr: np.ndarray) -> np.ndarray:
            out = np.zeros(n, dtype=np.int16)
            for i in range(n):
                if not arr[i]:
                    out[i] = 0
                    continue
                maxoff = min(CAP, n - 1 - i)
                val = maxoff
                for d in range(1, maxoff + 1):
                    if not arr[i + d]:
                        val = d
                        break
                out[i] = val
            return out

        g["raw_episode_age"] = age
        g["remaining_raw20"] = remaining(raw)
        g["remaining_ma10_20"] = remaining(ma10)
        g["remaining_mom5_20"] = remaining(mom5)
        for h in (5, 10):
            vals = np.full(n, np.nan)
            if n > h:
                vals[:-h] = close[h:] / close[:-h] - 1.0
            g[f"fwd{h}_close"] = vals
        parts.append(g)
    return pd.concat(parts, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)


def aligned_targets(targets: pd.Series, calendar: pd.Index) -> pd.Series:
    x = targets.copy()
    x.index = pd.to_datetime(x.index)
    return x.reindex(calendar)


def entry_rows(name: str, targets: pd.Series, features: pd.DataFrame, calendar: pd.Index) -> pd.DataFrame:
    aligned = aligned_targets(targets, calendar)
    prev = aligned.shift(1)
    # NaN-safe change. A non-null target is an entry whenever yesterday was cash or another symbol.
    is_entry = aligned.notna() & (prev.isna() | (aligned.astype(object) != prev.astype(object)))

    # Signal tenure: number of consecutive signal dates carrying the same target from entry onward.
    vals = aligned.astype(object).to_numpy()
    tenures: dict[pd.Timestamp, int] = {}
    for i in np.flatnonzero(is_entry.to_numpy()):
        sym = vals[i]
        j = i
        while j + 1 < len(vals) and pd.notna(vals[j + 1]) and vals[j + 1] == sym:
            j += 1
        tenures[pd.Timestamp(calendar[i])] = int(j - i + 1)

    base = pd.DataFrame({"signal_date": calendar[is_entry.to_numpy()], "symbol": aligned.loc[is_entry].astype(str).values})
    base["variant"] = name
    base["signal_tenure"] = base["signal_date"].map(tenures).astype(int)

    cols = [
        "date", "symbol", "score", "raw_episode_age", "remaining_raw20",
        "remaining_ma10_20", "remaining_mom5_20", "fwd5_close", "fwd10_close",
    ]
    state = features[cols].copy()
    state["symbol"] = state["symbol"].astype(str)
    base = base.merge(state, left_on=["signal_date", "symbol"], right_on=["date", "symbol"], how="left")
    base = base.drop(columns=["date"])
    base["outside_fixed15"] = ~base["symbol"].isin(set(FIXED15))
    base["period"] = np.where(base["signal_date"] < pd.Timestamp("2025-01-01"), "2021-2024", "2025-2026")
    return base.loc[base["signal_date"] >= START].reset_index(drop=True)


def summarize_entries(x: pd.DataFrame) -> dict:
    out: dict[str, dict] = {}
    for period, g in x.groupby("period", sort=True):
        out[str(period)] = {
            "entries": int(len(g)),
            "outside_fixed15_share": float(g["outside_fixed15"].mean()),
            "episode_age_mean": float(g["raw_episode_age"].mean()),
            "episode_age_median": float(g["raw_episode_age"].median()),
            "remaining_raw20_mean": float(g["remaining_raw20"].mean()),
            "remaining_raw20_median": float(g["remaining_raw20"].median()),
            "remaining_raw20_le3_share": float((g["remaining_raw20"] <= 3).mean()),
            "remaining_ma10_20_mean": float(g["remaining_ma10_20"].mean()),
            "remaining_mom5_20_mean": float(g["remaining_mom5_20"].mean()),
            "signal_tenure_mean": float(g["signal_tenure"].mean()),
            "signal_tenure_median": float(g["signal_tenure"].median()),
            "fwd5_close_mean": float(g["fwd5_close"].mean()),
            "fwd10_close_mean": float(g["fwd10_close"].mean()),
        }
    return out


def paired_disagreement(cluster_entries: pd.DataFrame, fixed_targets: pd.Series, features: pd.DataFrame, calendar: pd.Index) -> tuple[pd.DataFrame, dict]:
    fixed_aligned = aligned_targets(fixed_targets, calendar)
    cols = ["date", "symbol", "raw_episode_age", "remaining_raw20", "remaining_ma10_20", "remaining_mom5_20", "fwd5_close", "fwd10_close", "score"]
    st = features[cols].copy()
    st["symbol"] = st["symbol"].astype(str)
    st = st.set_index(["date", "symbol"])

    rows = []
    for r in cluster_entries.itertuples(index=False):
        d = pd.Timestamp(r.signal_date)
        fixed = fixed_aligned.get(d, np.nan)
        if pd.isna(fixed) or str(fixed) == str(r.symbol):
            continue
        fsym = str(fixed)
        key = (d, fsym)
        if key not in st.index:
            continue
        f = st.loc[key]
        # should be one row; guard in case of accidental duplicates
        if isinstance(f, pd.DataFrame):
            f = f.iloc[0]
        rows.append({
            "signal_date": d,
            "period": "2021-2024" if d < pd.Timestamp("2025-01-01") else "2025-2026",
            "cluster_symbol": str(r.symbol),
            "fixed_symbol": fsym,
            "cluster_outside_fixed15": bool(r.outside_fixed15),
            "cluster_age": float(r.raw_episode_age),
            "fixed_age": float(f["raw_episode_age"]),
            "cluster_remaining_raw20": float(r.remaining_raw20),
            "fixed_remaining_raw20": float(f["remaining_raw20"]),
            "cluster_remaining_ma10_20": float(r.remaining_ma10_20),
            "fixed_remaining_ma10_20": float(f["remaining_ma10_20"]),
            "cluster_remaining_mom5_20": float(r.remaining_mom5_20),
            "fixed_remaining_mom5_20": float(f["remaining_mom5_20"]),
            "cluster_fwd5": float(r.fwd5_close) if pd.notna(r.fwd5_close) else np.nan,
            "fixed_fwd5": float(f["fwd5_close"]) if pd.notna(f["fwd5_close"]) else np.nan,
            "cluster_fwd10": float(r.fwd10_close) if pd.notna(r.fwd10_close) else np.nan,
            "fixed_fwd10": float(f["fwd10_close"]) if pd.notna(f["fwd10_close"]) else np.nan,
            "cluster_score": float(r.score),
            "fixed_score": float(f["score"]),
        })
    p = pd.DataFrame(rows)
    summary: dict[str, dict] = {}
    if p.empty:
        return p, summary
    for period, g in p.groupby("period", sort=True):
        raw_diff = g["cluster_remaining_raw20"] - g["fixed_remaining_raw20"]
        ma_diff = g["cluster_remaining_ma10_20"] - g["fixed_remaining_ma10_20"]
        f5diff = g["cluster_fwd5"] - g["fixed_fwd5"]
        f10diff = g["cluster_fwd10"] - g["fixed_fwd10"]
        summary[str(period)] = {
            "disagreement_cluster_entries": int(len(g)),
            "cluster_outside_fixed15_share": float(g["cluster_outside_fixed15"].mean()),
            "cluster_age_minus_fixed_mean": float((g["cluster_age"] - g["fixed_age"]).mean()),
            "cluster_remaining_raw20_minus_fixed_mean": float(raw_diff.mean()),
            "cluster_remaining_raw20_gt_fixed_share": float((raw_diff > 0).mean()),
            "cluster_remaining_ma10_minus_fixed_mean": float(ma_diff.mean()),
            "cluster_fwd5_minus_fixed_mean": float(f5diff.mean()),
            "cluster_fwd10_minus_fixed_mean": float(f10diff.mean()),
            "cluster_score_div_fixed_median": float((g["cluster_score"] / g["fixed_score"].replace(0, np.nan)).median()),
        }
    return p, summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="selected-top1-lifespan-summary.json")
    p.add_argument("--entries-path", default="selected-top1-lifespan-entries.csv")
    p.add_argument("--paired-path", default="selected-top1-lifespan-paired.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = add_life_labels(build_features(bars))
    pools, _ = build_monthly_rep_pools(bars, features)

    fixed_f = features.loc[features["symbol"].astype(str).isin(FIXED15)].copy()
    fixed_targets, _ = build_baseline_targets(fixed_f)
    c90_allowed = frozen_mask(features, pools["cluster90"])
    c90_targets, _ = build_targets_from_mask(features, c90_allowed)

    calendar = pd.Index(sorted(pd.to_datetime(features.loc[features["date"] >= START, "date"].unique())), name="date")
    fixed_entries = entry_rows("fixed15", fixed_targets, features, calendar)
    c90_entries = entry_rows("cluster90", c90_targets, features, calendar)
    paired, paired_summary = paired_disagreement(c90_entries, fixed_targets, features, calendar)

    entries = pd.concat([fixed_entries, c90_entries], ignore_index=True)
    summary = {
        "question": "Does cluster90 pick shorter-lived trends in 2021-24 but longer-lived trends in 2025-26?",
        "definitions": {
            "entry": "new non-cash daily Top1 signal; signal close(t), backtest executes open(t+1)",
            "raw_episode_age": "trading days elapsed since raw OLS first became positive, 0 on first-positive day",
            "remaining_life": "trading-day offset to first failure, capped at 20",
            "fixed15": "same simplified daily OLS selector used in prior sanity checks",
            "cluster90": "monthly liquidity-first 120d-correlation dedup at rho>=0.90, then unchanged daily OLS Top1",
        },
        "entry_stats": {
            "fixed15": summarize_entries(fixed_entries),
            "cluster90": summarize_entries(c90_entries),
        },
        "paired_on_cluster90_entry_disagreements": paired_summary,
    }

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    entries.to_csv(args.entries_path, index=False)
    paired.to_csv(args.paired_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
