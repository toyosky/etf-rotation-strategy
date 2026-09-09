#!/usr/bin/env python3
"""Test frozen Daily Resistance + ScoreDelta V1 on Cluster90.

V1 rule (no tuning):
    ResistancePct252 >= 75% AND ScoreDelta_new <= 0 -> veto new Top1

Cluster90 adaptation: V1 applies only to pure ranking changes. If the incumbent is
no longer an eligible candidate in the current frozen Cluster90 universe, the
baseline switch/exit is not vetoed.

Research only; no production strategy changes.
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

START = pd.Timestamp("2020-12-01")
RES_LOOKBACK = 120
PCT_LOOKBACK = 252
MIN_PROFILE_HISTORY = 60
RES_PCT_THRESHOLD = 75.0


def build_cluster90_candidates(features: pd.DataFrame, c90: dict) -> tuple[dict, pd.Series]:
    f = features.loc[features["date"] >= START, ["date", "symbol", "score", "trend_eligible"]].copy()
    f["symbol"] = f["symbol"].astype(str)
    # ScoreDelta must be computed on the full chronological score series before filtering.
    allf = features[["date", "symbol", "score"]].copy().sort_values(["symbol", "date"])
    allf["symbol"] = allf["symbol"].astype(str)
    allf["score_delta"] = allf.groupby("symbol", sort=False)["score"].diff()
    f = f.merge(allf[["date", "symbol", "score_delta"]], on=["date", "symbol"], how="left", validate="one_to_one")

    dates = pd.Index(sorted(pd.to_datetime(f["date"].unique())), name="date")
    cands: dict[pd.Timestamp, pd.DataFrame] = {}
    counts = {}
    for d in dates:
        reps = set(map(str, c90.get(pd.Timestamp(d), set())))
        day = f.loc[
            (f["date"] == d)
            & f["symbol"].isin(reps)
            & f["trend_eligible"].fillna(False).astype(bool),
            ["symbol", "score", "score_delta"],
        ].dropna(subset=["score"]).copy()
        day = day.sort_values(["score", "symbol"], ascending=[False, True]).reset_index(drop=True)
        day["rank"] = np.arange(1, len(day) + 1)
        cands[pd.Timestamp(d)] = day
        counts[pd.Timestamp(d)] = int(len(day))
    return cands, pd.Series(counts, name="candidate_count").sort_index()


def _overlap_amount(low: np.ndarray, high: np.ndarray, amount: np.ndarray, a: float, b: float) -> float:
    valid = np.isfinite(low) & np.isfinite(high) & np.isfinite(amount) & (amount >= 0)
    if not valid.any():
        return float("nan")
    lo = low[valid]
    hi = high[valid]
    amt = amount[valid]
    left = np.minimum(lo, hi)
    right = np.maximum(lo, hi)
    width = right - left
    ov = np.maximum(0.0, np.minimum(right, b) - np.maximum(left, a))
    frac = np.zeros_like(ov, dtype=float)
    nonzero = width > 1e-12
    frac[nonzero] = ov[nonzero] / width[nonzero]
    # Zero-range days are treated as point masses at the observed price.
    zero = ~nonzero
    if zero.any():
        p = left[zero]
        frac[zero] = ((p >= a) & (p <= b)).astype(float)
    return float(np.sum(amt * frac))


def profile_series_for_symbol(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("date").reset_index(drop=True).copy()
    low = g["low"].astype(float).to_numpy()
    high = g["high"].astype(float).to_numpy()
    close = g["close"].astype(float).to_numpy()
    amount = g["amount"].astype(float).to_numpy()
    n = len(g)
    upper_share = np.full(n, np.nan, dtype=float)
    resistance_pct = np.full(n, np.nan, dtype=float)

    for i in range(n):
        p = close[i]
        if not (math.isfinite(p) and p > 0):
            continue
        j0 = max(0, i - RES_LOOKBACK)
        if i <= j0:
            continue
        lo = low[j0:i]
        hi = high[j0:i]
        amt = amount[j0:i]
        upper = _overlap_amount(lo, hi, amt, p, p * 1.05)
        total = _overlap_amount(lo, hi, amt, p * 0.95, p * 1.05)
        if math.isfinite(total) and total > 0 and math.isfinite(upper):
            upper_share[i] = upper / total

        if math.isfinite(upper_share[i]):
            k0 = max(0, i - PCT_LOOKBACK)
            hist = upper_share[k0:i]
            hist = hist[np.isfinite(hist)]
            if len(hist) >= MIN_PROFILE_HISTORY:
                # Point-in-time empirical percentile versus strictly prior observations.
                resistance_pct[i] = 100.0 * float(np.mean(hist <= upper_share[i]))

    return pd.DataFrame({
        "date": pd.to_datetime(g["date"]),
        "symbol": g["symbol"].astype(str),
        "upper_share": upper_share,
        "resistance_pct252": resistance_pct,
    })


def build_needed_profiles(bars: pd.DataFrame, symbols: set[str]) -> pd.DataFrame:
    parts = []
    b = bars.loc[bars["symbol"].astype(str).isin(symbols), ["date", "symbol", "low", "high", "close", "amount"]].copy()
    b["symbol"] = b["symbol"].astype(str)
    for _, g in b.groupby("symbol", sort=False):
        parts.append(profile_series_for_symbol(g))
    if not parts:
        return pd.DataFrame(columns=["date", "symbol", "upper_share", "resistance_pct252"])
    return pd.concat(parts, ignore_index=True)


def raw_targets(cands: dict) -> pd.Series:
    out = {}
    for d, day in cands.items():
        if len(day):
            out[d] = str(day.iloc[0]["symbol"])
    return pd.Series(out, name="target").sort_index()


def v1_targets(cands: dict, profiles: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    prof = profiles.set_index(["date", "symbol"])["resistance_pct252"].to_dict()
    current = None
    targets = {}
    events = []

    for d in sorted(cands):
        day = cands[d]
        if day.empty:
            if current is not None:
                events.append({"date": d, "incumbent": current, "challenger": None,
                               "resistance_pct252": np.nan, "score_delta_new": np.nan,
                               "decision": "EXIT_NO_CANDIDATE"})
            current = None
            continue

        challenger_row = day.iloc[0]
        challenger = str(challenger_row["symbol"])
        if current is None:
            current = challenger
            events.append({"date": d, "incumbent": None, "challenger": challenger,
                           "resistance_pct252": prof.get((d, challenger), np.nan),
                           "score_delta_new": challenger_row["score_delta"], "decision": "ENTER"})
            targets[d] = current
            continue

        if challenger == current:
            targets[d] = current
            continue

        incumbent_valid = bool((day["symbol"] == current).any())
        rp = prof.get((d, challenger), np.nan)
        sd = float(challenger_row["score_delta"]) if pd.notna(challenger_row["score_delta"]) else np.nan

        if not incumbent_valid:
            old = current
            current = challenger
            decision = "SWITCH_OLD_INVALID"
        elif math.isfinite(rp) and rp >= RES_PCT_THRESHOLD and math.isfinite(sd) and sd <= 0.0:
            old = current
            decision = "VETO_V1"
        else:
            old = current
            current = challenger
            decision = "SWITCH_NORMAL"

        events.append({"date": d, "incumbent": old, "challenger": challenger,
                       "resistance_pct252": rp, "score_delta_new": sd,
                       "decision": decision})
        targets[d] = current

    return pd.Series(targets, name="target").sort_index(), pd.DataFrame(events)


def run_stats(pnl: pd.DataFrame, start: str, end: str | None = None) -> dict:
    s = pnl.loc[pnl["date"] >= pd.Timestamp(start)].copy()
    if end is not None:
        s = s.loc[s["date"] <= pd.Timestamp(end)].copy()
    if s.empty:
        return {}
    vals = s["target"].where(s["target"].notna(), "__CASH__").astype(str).tolist()
    runs = []
    cur, n = None, 0
    for v in vals:
        if v == cur:
            n += 1
        else:
            if n:
                runs.append(n)
            cur, n = v, 1
    if n:
        runs.append(n)
    a = np.asarray(runs, dtype=float)
    return {"runs": int(len(a)), "mean_days": float(a.mean()), "median_days": float(np.median(a)),
            "pct_ge5": float((a >= 5).mean()), "pct_ge10": float((a >= 10).mean())}


def divergence_stats(raw_pnl: pd.DataFrame, v1_pnl: pd.DataFrame, start: str, end: str | None = None) -> dict:
    a = raw_pnl[["date", "target", "gross_ret"]].rename(columns={"target": "raw_target", "gross_ret": "raw_ret"})
    b = v1_pnl[["date", "target", "gross_ret"]].rename(columns={"target": "v1_target", "gross_ret": "v1_ret"})
    x = a.merge(b, on="date", how="inner")
    x = x.loc[x["date"] >= pd.Timestamp(start)].copy()
    if end is not None:
        x = x.loc[x["date"] <= pd.Timestamp(end)].copy()
    x["diff"] = x["raw_target"].fillna("__CASH__").astype(str) != x["v1_target"].fillna("__CASH__").astype(str)
    if not x["diff"].any():
        return {"segments": 0}
    x["seg"] = (x["diff"] != x["diff"].shift(1, fill_value=False)).cumsum()
    rows = []
    for _, g in x.loc[x["diff"]].groupby("seg"):
        raw = float(np.prod(1.0 + g["raw_ret"].to_numpy()) - 1.0)
        v1 = float(np.prod(1.0 + g["v1_ret"].to_numpy()) - 1.0)
        rows.append((v1 - raw) * 100.0)
    arr = np.asarray(rows, dtype=float)
    return {"segments": int(len(arr)), "v1_win_share": float(np.mean(arr > 0)),
            "alpha_pp_mean": float(arr.mean()), "alpha_pp_median": float(np.median(arr)),
            "alpha_pp_sum": float(arr.sum())}


def event_stats(events: pd.DataFrame, start: str, end: str | None = None) -> dict:
    g = events.loc[events["date"] >= pd.Timestamp(start)].copy()
    if end is not None:
        g = g.loc[g["date"] <= pd.Timestamp(end)].copy()
    v = g.loc[g["decision"] == "VETO_V1"]
    return {
        "events": int(len(g)), "veto_days": int(len(v)),
        "normal_switches": int((g["decision"] == "SWITCH_NORMAL").sum()),
        "old_invalid_switches": int((g["decision"] == "SWITCH_OLD_INVALID").sum()),
        "veto_resistance_mean": float(v["resistance_pct252"].mean()) if len(v) else None,
        "veto_score_delta_mean": float(v["score_delta_new"].mean()) if len(v) else None,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="cluster90-resistance-score-v1-summary.json")
    p.add_argument("--daily-path", default="cluster90-resistance-score-v1-daily.csv")
    p.add_argument("--events-path", default="cluster90-resistance-score-v1-events.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)
    pools, _ = build_monthly_rep_pools(bars, features)
    cands, counts = build_cluster90_candidates(features, pools["cluster90"])
    raw = raw_targets(cands)
    needed = set(raw.dropna().astype(str).unique())
    profiles = build_needed_profiles(bars, needed)
    v1, events = v1_targets(cands, profiles)

    raw_pnl = backtest_open_to_open(bars, raw)
    v1_pnl = backtest_open_to_open(bars, v1)
    summary = {
        "design": {
            "v1": "ResistancePct252>=75 AND ScoreDelta_new<=0 veto",
            "profile": "120 prior days amount uniformly spread in daily low-high; empirical percentile vs prior 252, min 60",
            "cluster90_adaptation": "pure-rank switches only; hard invalidation not vetoed",
            "threshold_sweep": False,
        },
        "variants": {
            "A_CLUSTER90_RAW": summarize_variant("A_CLUSTER90_RAW", raw_pnl, raw, counts),
            "B_CLUSTER90_V1": summarize_variant("B_CLUSTER90_V1", v1_pnl, v1, counts),
        },
        "run_stats": {
            "A_2021_2024": run_stats(raw_pnl, "2021-01-01", "2024-12-31"),
            "B_2021_2024": run_stats(v1_pnl, "2021-01-01", "2024-12-31"),
            "A_2025_2026": run_stats(raw_pnl, "2025-01-01"),
            "B_2025_2026": run_stats(v1_pnl, "2025-01-01"),
        },
        "v1_events": {
            "2021_2024": event_stats(events, "2021-01-01", "2024-12-31"),
            "2025_2026": event_stats(events, "2025-01-01"),
        },
        "divergence": {
            "2021_2024": divergence_stats(raw_pnl, v1_pnl, "2021-01-01", "2024-12-31"),
            "2025_2026": divergence_stats(raw_pnl, v1_pnl, "2025-01-01"),
        },
        "profile_symbols": int(len(needed)),
    }

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.concat([raw_pnl.assign(variant="A_CLUSTER90_RAW"), v1_pnl.assign(variant="B_CLUSTER90_V1")], ignore_index=True).to_csv(args.daily_path, index=False)
    events.to_csv(args.events_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
