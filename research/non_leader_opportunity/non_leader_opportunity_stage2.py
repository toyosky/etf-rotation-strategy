#!/usr/bin/env python3
"""Stage 2: shadow leaders + zero-state decomposition.

Diagnostic research only. Does not modify production trading rules.

Builds on Stage 1's frozen production-style raw OLS panel and evaluates:
1) first-entry episodes into Rank 2-3 and Rank 4-5 shadow zones;
2) three zero-score states:
   - ZERO_DEEP_OVERSOLD: ret10 <= -4% and >=8% below 20d high
   - ZERO_NEAR_EXIT: annual <= 0 and signed_score >= -0.01
   - ZERO_MIDDLE: remaining annual <= 0 cases
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from non_leader_opportunity_stage1 import (
    HORIZON,
    RISK_POOL,
    START,
    SPLIT,
    build_panel,
)
import sys

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "research"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, load_daily_bars


def add_future_returns(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.sort_values(["symbol", "date"]).copy()
    for h in (5, 10, 20):
        p[f"fwd{h}"] = p.groupby("symbol")["close"].shift(-h) / p["close"] - 1.0
    return p


def shadow_entries(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    p["shadow_state"] = "OTHER"
    p.loc[p["raw_rank"].between(2, 3), "shadow_state"] = "RANK2_3"
    p.loc[p["raw_rank"].between(4, 5), "shadow_state"] = "RANK4_5"
    p["prev_shadow_state"] = p.groupby("symbol")["shadow_state"].shift(1).fillna("OTHER")
    entries = p[
        p["shadow_state"].isin(["RANK2_3", "RANK4_5"])
        & (p["shadow_state"] != p["prev_shadow_state"])
        & p["fwd20"].notna()
    ].copy()

    top1 = (
        p[p["raw_rank"] == 1][["date", "symbol", "fwd20"]]
        .rename(columns={"symbol": "top1_symbol", "fwd20": "top1_fwd20"})
    )
    entries = entries.merge(top1, on="date", how="left")

    rows = []
    by_symbol = {
        s: g.sort_values("date").reset_index(drop=True)
        for s, g in p.groupby("symbol", sort=False)
    }
    for _, e in entries.iterrows():
        g = by_symbol[e["symbol"]]
        idx = int(g.index[g["date"].eq(e["date"])][0])
        future = g.iloc[idx + 1 : idx + HORIZON + 1]
        t1 = future[future["raw_rank"] == 1]
        delay = np.nan if t1.empty else int(t1.index[0] - idx)
        rows.append({
            "period": "2025-2026" if e["date"] >= SPLIT else "2021-2024",
            "symbol": e["symbol"],
            "date": e["date"],
            "shadow_state": e["shadow_state"],
            "fwd5": e["fwd5"],
            "fwd10": e["fwd10"],
            "fwd20": e["fwd20"],
            "top1_symbol": e["top1_symbol"],
            "top1_fwd20": e["top1_fwd20"],
            "beat_incumbent20": bool(e["fwd20"] > e["top1_fwd20"])
                if pd.notna(e["top1_fwd20"]) else np.nan,
            "top1_delay": delay,
        })
    return pd.DataFrame(rows)


def shadow_summary(events: pd.DataFrame) -> pd.DataFrame:
    def one(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "episodes": len(g),
            "avg_fwd5": g["fwd5"].mean(),
            "avg_fwd10": g["fwd10"].mean(),
            "avg_fwd20": g["fwd20"].mean(),
            "beat_incumbent20": g["beat_incumbent20"].mean(),
            "hit20_8": (g["fwd20"] >= 0.08).mean(),
            "become_top1_20": g["top1_delay"].notna().mean(),
            "med_top1_delay": g["top1_delay"].median(),
        })
    return (
        events.groupby(["period", "shadow_state"], observed=True)
        .apply(one, include_groups=False)
        .reset_index()
    )


def add_zero_states(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    p["zero_state"] = "POSITIVE"
    deep = (
        (p["annual"] <= 0)
        & (p["ret10"] <= -0.04)
        & (p["dist_high20"] <= -0.08)
    )
    near = (
        (p["annual"] <= 0)
        & (~deep)
        & (p["signed_score"] >= -0.01)
    )
    middle = (p["annual"] <= 0) & (~deep) & (~near)
    p.loc[deep, "zero_state"] = "ZERO_DEEP_OVERSOLD"
    p.loc[near, "zero_state"] = "ZERO_NEAR_EXIT"
    p.loc[middle, "zero_state"] = "ZERO_MIDDLE"
    p["prev_zero_state"] = p.groupby("symbol")["zero_state"].shift(1).fillna("POSITIVE")
    return p


def zero_daily_summary(panel: pd.DataFrame) -> pd.DataFrame:
    z = panel[
        panel["zero_state"].ne("POSITIVE")
        & panel["fwd20"].notna()
    ].copy()
    def one(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "n": len(g),
            "avg_fwd5": g["fwd5"].mean(),
            "avg_fwd10": g["fwd10"].mean(),
            "avg_fwd20": g["fwd20"].mean(),
            "med_fwd20": g["fwd20"].median(),
            "hit20_5": (g["fwd20"] >= 0.05).mean(),
            "hit20_8": (g["fwd20"] >= 0.08).mean(),
        })
    return (
        z.groupby(["period", "zero_state"], observed=True)
        .apply(one, include_groups=False)
        .reset_index()
    )


def zero_entry_events(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    entries = p[
        p["zero_state"].ne("POSITIVE")
        & (p["zero_state"] != p["prev_zero_state"])
        & p["fwd20"].notna()
    ].copy()

    rows = []
    by_symbol = {
        s: g.sort_values("date").reset_index(drop=True)
        for s, g in p.groupby("symbol", sort=False)
    }
    for _, e in entries.iterrows():
        g = by_symbol[e["symbol"]]
        idx = int(g.index[g["date"].eq(e["date"])][0])
        future = g.iloc[idx + 1 : idx + HORIZON + 1]
        pos = future[future["raw_score"] > 0]
        t3 = future[(future["raw_score"] > 0) & (future["raw_rank"] <= 3)]
        t1 = future[(future["raw_score"] > 0) & (future["raw_rank"] == 1)]
        rows.append({
            "period": "2025-2026" if e["date"] >= SPLIT else "2021-2024",
            "symbol": e["symbol"],
            "date": e["date"],
            "zero_state": e["zero_state"],
            "fwd5": e["fwd5"],
            "fwd10": e["fwd10"],
            "fwd20": e["fwd20"],
            "positive_delay": np.nan if pos.empty else int(pos.index[0] - idx),
            "top3_delay": np.nan if t3.empty else int(t3.index[0] - idx),
            "top1_delay": np.nan if t1.empty else int(t1.index[0] - idx),
        })
    return pd.DataFrame(rows)


def zero_event_summary(events: pd.DataFrame) -> pd.DataFrame:
    def one(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "episodes": len(g),
            "avg_fwd5": g["fwd5"].mean(),
            "avg_fwd10": g["fwd10"].mean(),
            "avg_fwd20": g["fwd20"].mean(),
            "hit20_8": (g["fwd20"] >= 0.08).mean(),
            "positive20": g["positive_delay"].notna().mean(),
            "med_positive_delay": g["positive_delay"].median(),
            "top3_20": g["top3_delay"].notna().mean(),
            "top1_20": g["top1_delay"].notna().mean(),
        })
    return (
        events.groupby(["period", "zero_state"], observed=True)
        .apply(one, include_groups=False)
        .reset_index()
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--out-dir", default=str(Path(__file__).resolve().parent / "output_stage2"))
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)

    bars = load_daily_bars(engine)
    panel = add_future_returns(build_panel(bars))
    panel = add_zero_states(panel)
    panel["period"] = np.where(panel["date"] >= SPLIT, "2025-2026", "2021-2024")

    se = shadow_entries(panel)
    ss = shadow_summary(se)
    zd = zero_daily_summary(panel)
    ze = zero_entry_events(panel)
    zs = zero_event_summary(ze)

    se.to_csv(out / "shadow_entry_events.csv", index=False)
    ss.to_csv(out / "shadow_summary.csv", index=False)
    zd.to_csv(out / "zero_daily_summary.csv", index=False)
    ze.to_csv(out / "zero_entry_events.csv", index=False)
    zs.to_csv(out / "zero_event_summary.csv", index=False)

    result = {
        "pool": RISK_POOL,
        "start": str(START.date()),
        "latest_date": str(panel["date"].max().date()),
        "shadow_episodes": int(len(se)),
        "zero_entry_events": int(len(ze)),
        "zero_thresholds": {
            "deep_oversold_ret10": -0.04,
            "deep_oversold_dist_high20": -0.08,
            "near_exit_signed_score": -0.01,
        },
    }
    (out / "run_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\nShadow summary:")
    print(ss.to_string(index=False))
    print("\nZero-state daily summary:")
    print(zd.to_string(index=False))
    print("\nZero-state event summary:")
    print(zs.to_string(index=False))


if __name__ == "__main__":
    main()
