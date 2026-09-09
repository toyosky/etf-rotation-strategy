#!/usr/bin/env python3
"""Cluster90 + V1-style liquidity / score-gap hysteresis ablation.

Research only. No production changes.

Port of original V1 ideas into the current raw-OLS Cluster90 engine:
- liquidity gate: trailing 20d average amount >= RMB 100m;
- holding buffer: incumbent may be retained while still trend-eligible and rank <= 5;
- score-gap: challenger must exceed incumbent by > 0.30 cross-sectional z-score units.

The 0.30 is applied to a daily standardized current OLS Score because original V1's
0.30 gap was defined on a standardized FinalScore. Raw OLS score units are not
comparable to original V1 FinalScore units, so using raw gap=0.30 would be invalid.
No threshold sweep is performed.
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
from monthly_liquidity_cluster_universe import build_monthly_rep_pools
from walk_forward_candidate_pool import backtest_open_to_open, summarize_variant

BACKTEST_START = pd.Timestamp("2021-01-01")
SIGNAL_WARMUP_START = pd.Timestamp("2020-12-01")
LIQ_AMOUNT20 = 100_000_000.0
RANK_BUFFER = 5
Z_GAP_THRESHOLD = 0.30


def attach_avg_amount20(bars: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    x = bars[["date", "symbol", "amount"]].copy()
    x["symbol"] = x["symbol"].astype(str)
    x = x.sort_values(["symbol", "date"])
    x["avg_amount20"] = (
        x.groupby("symbol", sort=False)["amount"]
        .transform(lambda s: s.rolling(20, min_periods=20).mean())
    )
    return features.merge(
        x[["date", "symbol", "avg_amount20"]],
        on=["date", "symbol"], how="left", validate="one_to_one",
    )


def cluster90_candidate_table(features, c90, liquidity_gate):
    f = features.loc[features["date"] >= SIGNAL_WARMUP_START].copy()
    f["symbol"] = f["symbol"].astype(str)
    all_dates = pd.Index(sorted(pd.to_datetime(f["date"].unique())), name="date")
    out = {}
    counts = {}
    for d in all_dates:
        reps = c90.get(pd.Timestamp(d), set())
        day = f.loc[
            (f["date"] == d)
            & f["symbol"].isin(reps)
            & f["trend_eligible"].fillna(False).astype(bool),
            ["symbol", "score", "avg_amount20"],
        ].copy()
        if liquidity_gate:
            day = day.loc[day["avg_amount20"] >= LIQ_AMOUNT20].copy()
        day = day.dropna(subset=["score"]).sort_values(
            ["score", "symbol"], ascending=[False, True]
        ).reset_index(drop=True)
        if len(day):
            sd = float(day["score"].std(ddof=0))
            if math.isfinite(sd) and sd > 1e-12:
                day["score_z"] = (day["score"] - float(day["score"].mean())) / sd
            else:
                day["score_z"] = 0.0
            day["rank"] = np.arange(1, len(day) + 1)
        else:
            day["score_z"] = pd.Series(dtype=float)
            day["rank"] = pd.Series(dtype=int)
        out[pd.Timestamp(d)] = day
        counts[pd.Timestamp(d)] = int(len(day))
    return out, pd.Series(counts, name="candidate_count").sort_index()


def direct_targets(cands):
    rows = {}
    for d, day in cands.items():
        if len(day):
            rows[d] = str(day.iloc[0]["symbol"])
    return pd.Series(rows, name="target").sort_index()


def hysteresis_targets(cands, variant):
    current = None
    targets = {}
    events = []
    for d in sorted(cands):
        day = cands[d]
        if day.empty:
            if current is not None:
                events.append({"date": d, "variant": variant, "incumbent": current,
                               "challenger": None, "incumbent_rank": np.nan,
                               "score_old": np.nan, "score_new": np.nan, "z_gap": np.nan,
                               "decision": "EXIT_NO_CANDIDATE"})
            current = None
            continue

        challenger = str(day.iloc[0]["symbol"])
        if current is None:
            current = challenger
            events.append({"date": d, "variant": variant, "incumbent": None,
                           "challenger": challenger, "incumbent_rank": np.nan,
                           "score_old": np.nan, "score_new": float(day.iloc[0]["score"]),
                           "z_gap": np.nan, "decision": "ENTER"})
            targets[d] = current
            continue

        row_old = day.loc[day["symbol"] == current]
        if row_old.empty:
            old = current
            current = challenger
            events.append({"date": d, "variant": variant, "incumbent": old,
                           "challenger": challenger, "incumbent_rank": np.nan,
                           "score_old": np.nan, "score_new": float(day.iloc[0]["score"]),
                           "z_gap": np.nan, "decision": "SWITCH_OLD_INVALID"})
            targets[d] = current
            continue

        old = row_old.iloc[0]
        if challenger == current:
            targets[d] = current
            continue

        old_rank = int(old["rank"])
        new = day.iloc[0]
        z_gap = float(new["score_z"] - old["score_z"])
        prior = current
        if old_rank > RANK_BUFFER:
            current = challenger
            decision = "SWITCH_RANK_GT5"
        elif z_gap > Z_GAP_THRESHOLD:
            current = challenger
            decision = "SWITCH_GAP"
        else:
            decision = "VETO_GAP"

        events.append({"date": d, "variant": variant, "incumbent": prior,
                       "challenger": challenger, "incumbent_rank": old_rank,
                       "score_old": float(old["score"]), "score_new": float(new["score"]),
                       "z_gap": z_gap, "decision": decision})
        targets[d] = current

    return pd.Series(targets, name="target").sort_index(), pd.DataFrame(events)


def run_stats_from_pnl(pnl, start, end=None):
    s = pnl.loc[pnl["date"] >= pd.Timestamp(start)].copy()
    if end is not None:
        s = s.loc[s["date"] <= pd.Timestamp(end)].copy()
    if s.empty:
        return {}
    vals = s["target"].where(s["target"].notna(), "__CASH__").astype(str).tolist()
    runs = []
    cur = None
    n = 0
    for v in vals:
        if v == cur:
            n += 1
        else:
            if n:
                runs.append(n)
            cur = v
            n = 1
    if n:
        runs.append(n)
    a = np.asarray(runs, dtype=float)
    return {"runs": int(len(a)), "mean_days": float(a.mean()),
            "median_days": float(np.median(a)), "max_days": int(a.max()),
            "pct_ge5": float((a >= 5).mean()), "pct_ge10": float((a >= 10).mean())}


def event_stats(events, start, end=None):
    if events.empty:
        return {}
    g = events.loc[events["date"] >= pd.Timestamp(start)].copy()
    if end is not None:
        g = g.loc[g["date"] <= pd.Timestamp(end)].copy()
    challenges = g.loc[g["decision"].isin(["VETO_GAP", "SWITCH_GAP", "SWITCH_RANK_GT5"])]
    veto = g.loc[g["decision"] == "VETO_GAP"]
    return {
        "events": int(len(g)),
        "challenge_events": int(len(challenges)),
        "veto_gap": int((g["decision"] == "VETO_GAP").sum()),
        "switch_gap": int((g["decision"] == "SWITCH_GAP").sum()),
        "switch_rank_gt5": int((g["decision"] == "SWITCH_RANK_GT5").sum()),
        "switch_old_invalid": int((g["decision"] == "SWITCH_OLD_INVALID").sum()),
        "veto_share_of_rank1_challenges": float(len(veto) / len(challenges)) if len(challenges) else None,
        "veto_z_gap_mean": float(veto["z_gap"].mean()) if len(veto) else None,
        "veto_old_rank_mean": float(veto["incumbent_rank"].mean()) if len(veto) else None,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="cluster90-v1-hysteresis-summary.json")
    p.add_argument("--daily-path", default="cluster90-v1-hysteresis-daily.csv")
    p.add_argument("--events-path", default="cluster90-v1-hysteresis-events.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = attach_avg_amount20(bars, build_features(bars))
    pools, _ = build_monthly_rep_pools(bars, features)
    c90 = pools["cluster90"]

    c_base, count_base = cluster90_candidate_table(features, c90, False)
    c_liq, count_liq = cluster90_candidate_table(features, c90, True)
    target_a = direct_targets(c_base)
    target_b = direct_targets(c_liq)
    target_c, events_c = hysteresis_targets(c_base, "C_V1_HYST")
    target_d, events_d = hysteresis_targets(c_liq, "D_LIQ20_V1_HYST")

    variants = {
        "A_CLUSTER90_RAW": (target_a, count_base),
        "B_LIQ20_RAW": (target_b, count_liq),
        "C_V1_HYST": (target_c, count_base),
        "D_LIQ20_V1_HYST": (target_d, count_liq),
    }
    summary = {
        "design": {"liquidity_gate": "avg_amount20 >= RMB 100m", "rank_buffer": 5,
                   "score_gap": "daily cross-sectional OLS score z-gap > 0.30",
                   "threshold_sweep": False, "primary": "2021-2024", "posterior": "2025-2026"},
        "variants": {}, "hysteresis_events": {}
    }
    daily_parts = []
    for name, (target, counts) in variants.items():
        pnl = backtest_open_to_open(bars, target)
        sm = summarize_variant(name, pnl, target, counts)
        sm["run_stats_2021_2024"] = run_stats_from_pnl(pnl, "2021-01-01", "2024-12-31")
        sm["run_stats_2025_2026"] = run_stats_from_pnl(pnl, "2025-01-01")
        summary["variants"][name] = sm
        z = pnl.copy(); z["variant"] = name; daily_parts.append(z)

    for name, ev in [("C_V1_HYST", events_c), ("D_LIQ20_V1_HYST", events_d)]:
        summary["hysteresis_events"][name] = {
            "2021_2024": event_stats(ev, "2021-01-01", "2024-12-31"),
            "2025_2026": event_stats(ev, "2025-01-01")}

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.concat(daily_parts, ignore_index=True).to_csv(args.daily_path, index=False)
    pd.concat([events_c, events_d], ignore_index=True).to_csv(args.events_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
