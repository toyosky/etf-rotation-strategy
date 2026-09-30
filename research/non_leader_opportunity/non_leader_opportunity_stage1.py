#!/usr/bin/env python3
"""Stage 1: Non-Leader Opportunity Study.

Purpose
-------
Measure how often meaningful 20-session rallies exist outside OLS Top1, how
long OLS takes to promote them, and how much of the move is already realized
before promotion.

This is diagnostic research only. It does not change the production strategy.

Data
----
Supabase public.daily_bars, current frozen FixV2 risk pool.
OLS definition matches production raw State Map:
26 prices, nominal half-life 10 with q^2 fit weights, annualization 250,
raw_score = annual * R2 only when annual > 0 and R2 > 0.
D2 is recorded but does not affect raw rank.
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

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "research"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, load_daily_bars, feature_one_symbol

RISK_POOL = [
    "159934", "159985", "161226", "513100", "159957", "159509", "513290",
    "159529", "159981", "501018", "513530", "511380", "164824",
]
START = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")
THRESHOLDS = (0.05, 0.08, 0.12)
HORIZON = 20


def build_panel(bars: pd.DataFrame) -> pd.DataFrame:
    bars = bars[bars["symbol"].astype(str).isin(RISK_POOL)].copy()
    parts = []
    for symbol, g in bars.groupby("symbol", sort=False):
        f = feature_one_symbol(g).copy()
        f["symbol"] = str(symbol)
        # Production raw score is deliberately independent of D2 and liquidity.
        f["raw_score"] = np.where(
            (f["annual"] > 0) & (f["r2"] > 0),
            f["annual"] * f["r2"],
            0.0,
        )
        f["signed_score"] = f["annual"] * f["r2"].clip(lower=0.0)
        c = f["close"].astype(float)
        f["fwd5"] = c.shift(-5) / c - 1.0
        f["fwd10"] = c.shift(-10) / c - 1.0
        f["fwd20"] = c.shift(-20) / c - 1.0
        f["signed_lag3"] = f["signed_score"].shift(3)
        parts.append(f)

    p = pd.concat(parts, ignore_index=True)
    p = p[p["date"] >= START].copy()
    p["raw_rank"] = (
        p.groupby("date")["raw_score"]
        .rank(method="first", ascending=False)
        .astype("Int64")
    )

    p["state_bucket"] = "ZERO_OTHER"
    p.loc[(p["raw_score"] > 0) & (p["raw_rank"] == 1), "state_bucket"] = "TOP1"
    p.loc[
        (p["raw_score"] > 0) & p["raw_rank"].between(2, 3),
        "state_bucket",
    ] = "TOP2_3"
    p.loc[
        (p["raw_score"] > 0) & (p["raw_rank"] >= 4),
        "state_bucket",
    ] = "POS_RANK4PLUS"

    repair = (
        (p["raw_score"] == 0)
        & (p["annual"] < 0)
        & p["signed_lag3"].notna()
        & (p["signed_score"] > p["signed_lag3"])
        & (p["ret5"] > 0)
    )
    p.loc[repair, "state_bucket"] = "ZERO_REPAIR"
    p["period"] = np.where(p["date"] >= SPLIT, "2025-2026", "2021-2024")
    return p.sort_values(["symbol", "date"]).reset_index(drop=True)


def daily_state_summary(panel: pd.DataFrame) -> pd.DataFrame:
    valid = panel[panel["fwd20"].notna()].copy()

    def one(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "n": len(g),
            "avg_fwd5": g["fwd5"].mean(),
            "avg_fwd10": g["fwd10"].mean(),
            "avg_fwd20": g["fwd20"].mean(),
            "med_fwd20": g["fwd20"].median(),
            "hit_fwd20_5": (g["fwd20"] >= 0.05).mean(),
            "hit_fwd20_8": (g["fwd20"] >= 0.08).mean(),
            "d2_block_rate": g["recent_drop3"].fillna(False).mean(),
        })

    return (
        valid.groupby(["period", "state_bucket"], observed=True)
        .apply(one, include_groups=False)
        .reset_index()
    )


def build_events(panel: pd.DataFrame, threshold: float) -> pd.DataFrame:
    rows = []
    lookup = {
        s: g.sort_values("date").reset_index(drop=True)
        for s, g in panel.groupby("symbol", sort=False)
    }

    for symbol, g in lookup.items():
        opp = g["fwd20"].ge(threshold) & g["fwd20"].notna()
        starts = opp & ~opp.shift(1, fill_value=False)
        for i in np.flatnonzero(starts.to_numpy()):
            start = g.iloc[i]
            future = g.iloc[i : min(i + HORIZON + 1, len(g))]
            t1 = future[(future["raw_score"] > 0) & (future["raw_rank"] == 1)]
            t3 = future[(future["raw_score"] > 0) & (future["raw_rank"] <= 3)]

            def capture_info(x: pd.DataFrame):
                if x.empty:
                    return (np.nan, np.nan)
                j = int(x.index[0])
                delay = j - i
                move = float(g.loc[j, "close"] / start["close"] - 1.0)
                return delay, move

            top1_delay, move_before_top1 = capture_info(t1)
            top3_delay, move_before_top3 = capture_info(t3)
            rows.append({
                "threshold": threshold,
                "symbol": symbol,
                "date": start["date"],
                "period": start["period"],
                "state_bucket": start["state_bucket"],
                "raw_rank": start["raw_rank"],
                "raw_score": start["raw_score"],
                "signed_score": start["signed_score"],
                "annual": start["annual"],
                "r2": start["r2"],
                "fwd20": start["fwd20"],
                "top1_delay": top1_delay,
                "top3_delay": top3_delay,
                "move_before_top1": move_before_top1,
                "move_before_top3": move_before_top3,
            })
    return pd.DataFrame(rows)


def event_summary(events: pd.DataFrame) -> pd.DataFrame:
    def one(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "events": len(g),
            "start_top1_rate": ((g["raw_score"] > 0) & (g["raw_rank"] == 1)).mean(),
            "start_top3_rate": ((g["raw_score"] > 0) & (g["raw_rank"] <= 3)).mean(),
            "top1_capture20": g["top1_delay"].notna().mean(),
            "top3_capture20": g["top3_delay"].notna().mean(),
            "med_top1_delay": g["top1_delay"].median(),
            "med_move_before_top1": g["move_before_top1"].median(),
        })
    return (
        events.groupby(["period", "threshold"], observed=True)
        .apply(one, include_groups=False)
        .reset_index()
    )


def bucket_event_summary(events: pd.DataFrame, threshold: float = 0.08) -> pd.DataFrame:
    e = events[np.isclose(events["threshold"], threshold)].copy()

    def one(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "events": len(g),
            "top1_capture20": g["top1_delay"].notna().mean(),
            "med_top1_delay": g["top1_delay"].median(),
            "med_move_before_top1": g["move_before_top1"].median(),
            "top3_capture20": g["top3_delay"].notna().mean(),
            "med_top3_delay": g["top3_delay"].median(),
            "avg_event_fwd20": g["fwd20"].mean(),
        })

    return (
        e.groupby(["period", "state_bucket"], observed=True)
        .apply(one, include_groups=False)
        .reset_index()
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent / "output"),
    )
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    panel = build_panel(bars)
    state = daily_state_summary(panel)
    events = pd.concat(
        [build_events(panel, t) for t in THRESHOLDS],
        ignore_index=True,
    )
    summary = event_summary(events)
    bucket = bucket_event_summary(events, 0.08)

    panel_cols = [
        "date", "symbol", "close", "annual", "r2", "raw_score", "signed_score",
        "raw_rank", "ret3", "ret5", "ret10", "ret20", "recent_drop3",
        "state_bucket", "fwd5", "fwd10", "fwd20",
    ]
    panel[panel_cols].to_csv(out / "daily_state_panel.csv.gz", index=False)
    events.to_csv(out / "rally_events.csv", index=False)
    state.to_csv(out / "daily_state_summary.csv", index=False)
    summary.to_csv(out / "capture_sensitivity.csv", index=False)
    bucket.to_csv(out / "event_bucket_summary_8pct.csv", index=False)

    result = {
        "source": "public.daily_bars",
        "pool": RISK_POOL,
        "start": str(START.date()),
        "latest_date": str(panel["date"].max().date()),
        "panel_rows": int(len(panel)),
        "thresholds": list(THRESHOLDS),
        "events": int(len(events)),
    }
    (out / "run_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\nCapture sensitivity:")
    print(summary.to_string(index=False))
    print("\n8% event buckets:")
    print(bucket.to_string(index=False))


if __name__ == "__main__":
    main()
