#!/usr/bin/env python3
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
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
from validate_fixed15_vs_full_market import FIXED15

CASH = "511220"
START = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")


def parse_members(x: str) -> list[str]:
    return [s for s in str(x).split(",") if s and s != CASH]


def run_lengths(pos: np.ndarray) -> list[int]:
    out, cur, n = [], -2, 0
    for x in pos.astype(int):
        if x < 0:
            if cur >= 0: out.append(n)
            cur, n = -2, 0
        elif x == cur:
            n += 1
        else:
            if cur >= 0: out.append(n)
            cur, n = x, 1
    if cur >= 0: out.append(n)
    return out


def universe_metrics(score: pd.DataFrame, gross: pd.DataFrame, signal_dates: pd.DatetimeIndex,
                     exec_dates: pd.DatetimeIndex, members: list[str], era_mask: np.ndarray) -> dict:
    m = [s for s in members if s in score.columns]
    if not m:
        return {}
    sm = score.loc[signal_dates, m].to_numpy(float)
    gm = gross.loc[signal_dates, m].to_numpy(float)
    gm = np.where(np.isfinite(gm), gm, 0.0)
    sub = np.flatnonzero(era_mask)
    sm = sm[sub]; gm = gm[sub]
    dates = exec_dates[sub]
    t, k = sm.shape
    eligible = np.isfinite(sm)
    counts = eligible.sum(axis=1)
    covered = counts > 0

    safe = np.where(eligible, sm, -np.inf)
    leader = np.full(t, -1, dtype=int)
    best = safe.max(axis=1)
    has = np.isfinite(best)
    leader[has] = np.argmax(safe[has], axis=1)

    active_vals, active_counts = np.unique(leader[leader >= 0], return_counts=True)
    if active_counts.size:
        shares = active_counts / active_counts.sum()
        hhi = float(np.square(shares).sum())
        effective = float(1.0 / hhi)
    else:
        hhi = np.nan; effective = np.nan

    switches = int(np.sum(leader[1:] != leader[:-1])) if t > 1 else 0
    lens = run_lengths(leader)

    # Top1-vs-Top2 raw score gap.
    gaps = []
    if k >= 2:
        for r in safe:
            rr = r[np.isfinite(r)]
            if len(rr) >= 2:
                p = np.partition(rr, -2)
                gaps.append(float(p[-1] - p[-2]))
    gap_mean = float(np.mean(gaps)) if gaps else np.nan
    gap_median = float(np.median(gaps)) if gaps else np.nan

    # Pairwise overlap and score crossing while both remain eligible.
    jaccards, crossings = [], []
    for i in range(k):
        for j in range(i + 1, k):
            both = eligible[:, i] & eligible[:, j]
            union = eligible[:, i] | eligible[:, j]
            if union.any():
                jaccards.append(float(both.sum() / union.sum()))
            idx = np.flatnonzero(both)
            if len(idx) >= 2:
                d = sm[idx, i] - sm[idx, j]
                sg = np.sign(d)
                # Ignore exact ties; count sign changes across consecutive co-eligible observations.
                nz = sg != 0
                sg = sg[nz]
                if len(sg) >= 2:
                    crossings.append(float(np.mean(sg[1:] != sg[:-1])))

    # Switch productivity: compare new leader vs previous leader on same one-day gross interval.
    switch_alpha = []
    productive = []
    for tt in range(1, t):
        old, new = int(leader[tt - 1]), int(leader[tt])
        if old == new:
            continue
        new_r = 0.0 if new < 0 else float(gm[tt, new])
        old_r = 0.0 if old < 0 else float(gm[tt, old])
        if not np.isfinite(new_r): new_r = 0.0
        if not np.isfinite(old_r): old_r = 0.0
        a = new_r - old_r
        switch_alpha.append(a)
        productive.append(a > 0)

    return {
        "k_noncash": k,
        "coverage_share": float(covered.mean()),
        "mean_eligible_count": float(counts.mean()),
        "mean_eligible_when_covered": float(counts[covered].mean()) if covered.any() else 0.0,
        "active_leader_count": int(len(active_vals)),
        "active_leader_share": float(len(active_vals) / k),
        "leader_hhi": hhi,
        "effective_leader_count": effective,
        "switch_events": switches,
        "switch_rate": float(switches / max(1, t - 1)),
        "mean_top1_tenure": float(np.mean(lens)) if lens else np.nan,
        "median_top1_tenure": float(np.median(lens)) if lens else np.nan,
        "short_run_le2_share": float(np.mean(np.asarray(lens) <= 2)) if lens else np.nan,
        "mean_pair_trend_jaccard": float(np.mean(jaccards)) if jaccards else np.nan,
        "max_pair_trend_jaccard": float(np.max(jaccards)) if jaccards else np.nan,
        "mean_pair_score_crossing_rate": float(np.mean(crossings)) if crossings else np.nan,
        "top1_top2_gap_mean": gap_mean,
        "top1_top2_gap_median": gap_median,
        "productive_switch_share": float(np.mean(productive)) if productive else np.nan,
        "switch_counterfactual_gain_sum": float(np.sum(switch_alpha)) if switch_alpha else 0.0,
        "switch_counterfactual_gain_mean": float(np.mean(switch_alpha)) if switch_alpha else np.nan,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--stage1-dir", required=True)
    ap.add_argument("--stage3b-dir", required=True)
    ap.add_argument("--output-dir", default="oure-stage4-output")
    ap.add_argument("--top-n", type=int, default=25)
    ap.add_argument("--random-n", type=int, default=50)
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    s1 = pd.read_csv(Path(args.stage1_dir) / "all_fix15_subsets.csv")
    e3 = pd.read_csv(Path(args.stage3b_dir) / "elite_universes.csv")
    r3 = pd.read_csv(Path(args.stage3b_dir) / "same_k_random_controls.csv")

    k7 = s1[s1["k_including_cash"] == 7].sort_values("log_growth", ascending=False).head(args.top_n).copy()
    large = e3.sort_values("log_growth", ascending=False).head(args.top_n).copy()
    rng = np.random.default_rng(20260914)
    if len(r3) > args.random_n:
        ridx = rng.choice(len(r3), size=args.random_n, replace=False)
        randoms = r3.iloc[np.sort(ridx)].copy()
    else:
        randoms = r3.copy()

    full_fix = s1[s1["k_including_cash"] == len(FIXED15)].sort_values("log_growth", ascending=False).head(1).copy()

    specs = []
    for group, df in [("small_k_elite", k7), ("large_k_elite", large), ("large_k_random", randoms), ("fix15", full_fix)]:
        for rank, (_, r) in enumerate(df.iterrows(), 1):
            specs.append({"group": group, "rank_in_group": rank, "members": parse_members(r["members"]), "source_log_growth": float(r["log_growth"])})

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng); bars["symbol"] = bars["symbol"].astype(str)
    feat = build_features(bars); feat["symbol"] = feat["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    start_i = int(cal.searchsorted(START, side="left"))
    spos = np.arange(start_i, len(cal) - 2, dtype=int)
    signal_dates = pd.DatetimeIndex(cal[spos]); exec_dates = pd.DatetimeIndex(cal[spos + 1])
    eras = {
        "full": np.ones(len(exec_dates), dtype=bool),
        "2021_2024": np.asarray(exec_dates < SPLIT),
        "2025_2026": np.asarray(exec_dates >= SPLIT),
    }

    rows = []
    for spec in specs:
        for era, mask in eras.items():
            m = universe_metrics(score, gross, signal_dates, exec_dates, spec["members"], mask)
            if not m: continue
            rows.append({"group": spec["group"], "rank_in_group": spec["rank_in_group"], "era": era,
                         "members": ",".join(spec["members"]), "source_log_growth": spec["source_log_growth"], **m})
    detail = pd.DataFrame(rows)
    detail.to_csv(out / "effective_competition_detail.csv", index=False)

    numeric = [c for c in detail.columns if c not in {"group","rank_in_group","era","members"}]
    summary = detail.groupby(["group","era"])[numeric].median(numeric_only=True).reset_index()
    summary.to_csv(out / "effective_competition_group_medians.csv", index=False)

    champions = detail[(detail["rank_in_group"] == 1) & (detail["group"].isin(["small_k_elite","large_k_elite","fix15"]))]
    payload = {
        "study": "OURE Stage4 effective competition decomposition",
        "status": "completed",
        "champion_metrics": champions.to_dict(orient="records"),
        "group_medians": summary.to_dict(orient="records"),
        "interpretation_gate": "Promote metrics only if both elite groups separate from large-k random in a coherent direction; nominal K alone is not promoted.",
    }
    (out / "oure_stage4_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
