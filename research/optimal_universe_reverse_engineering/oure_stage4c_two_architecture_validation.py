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
LATE = pd.Timestamp("2025-01-01")
SEED = 20260914


def parse_members(x: str) -> list[str]:
    return [s for s in str(x).split(",") if s and s != CASH]


def run_lengths(pos: np.ndarray) -> list[int]:
    out: list[int] = []
    cur = -2
    n = 0
    for x in pos.astype(int):
        if x < 0:
            if cur >= 0:
                out.append(n)
            cur, n = -2, 0
        elif x == cur:
            n += 1
        else:
            if cur >= 0:
                out.append(n)
            cur, n = x, 1
    if cur >= 0:
        out.append(n)
    return out


def architecture_metrics(score: pd.DataFrame, gross: pd.DataFrame,
                         signal_dates: pd.DatetimeIndex, exec_dates: pd.DatetimeIndex,
                         members: list[str], era_mask: np.ndarray) -> dict:
    m = [s for s in members if s in score.columns]
    if not m:
        return {}
    sm_all = score.loc[signal_dates, m].to_numpy(float)
    gm_all = gross.loc[signal_dates, m].to_numpy(float)
    gm_all = np.where(np.isfinite(gm_all), gm_all, 0.0)
    sub = np.flatnonzero(era_mask)
    sm = sm_all[sub]
    gm = gm_all[sub]
    dates = pd.DatetimeIndex(exec_dates[sub])
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
        hhi = np.nan
        effective = np.nan

    lens = run_lengths(leader)
    switches = int(np.sum(leader[1:] != leader[:-1])) if t > 1 else 0

    gaps: list[float] = []
    if k >= 2:
        for r in safe:
            rr = r[np.isfinite(r)]
            if len(rr) >= 2:
                p = np.partition(rr, -2)
                gaps.append(float(p[-1] - p[-2]))

    jaccards: list[float] = []
    crossings: list[float] = []
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
                sg = sg[sg != 0]
                if len(sg) >= 2:
                    crossings.append(float(np.mean(sg[1:] != sg[:-1])))

    switch_alpha: list[float] = []
    productive: list[bool] = []
    transitions: list[tuple[int, int]] = []
    noncash_switches = 0
    for tt in range(1, t):
        old, new = int(leader[tt - 1]), int(leader[tt])
        if old == new:
            continue
        new_r = 0.0 if new < 0 else float(gm[tt, new])
        old_r = 0.0 if old < 0 else float(gm[tt, old])
        if not np.isfinite(new_r):
            new_r = 0.0
        if not np.isfinite(old_r):
            old_r = 0.0
        a = new_r - old_r
        switch_alpha.append(a)
        productive.append(a > 0)
        if old >= 0 and new >= 0:
            noncash_switches += 1
            transitions.append((old, new))

    dominant_year_shares: list[float] = []
    leader_spans: list[float] = []
    first_dates: list[pd.Timestamp] = []
    for li in active_vals.astype(int):
        idx = np.flatnonzero(leader == li)
        if len(idx) == 0:
            continue
        ld = pd.DatetimeIndex(dates[idx])
        yc = pd.Series(ld.year).value_counts()
        dominant_year_shares.append(float(yc.iloc[0] / len(ld)))
        leader_spans.append(float((ld.max() - ld.min()).days))
        first_dates.append(pd.Timestamp(ld.min()))

    active_leaders = int(len(active_vals))
    coverage_efficiency = float(active_leaders / counts[covered].mean()) if covered.any() and counts[covered].mean() > 0 else np.nan
    late_share = float(np.mean([d >= LATE for d in first_dates])) if first_dates else np.nan
    transition_diversity = float(len(set(transitions)) / noncash_switches) if noncash_switches else np.nan

    return {
        "k_noncash": k,
        "coverage_share": float(covered.mean()),
        "mean_eligible_count": float(counts.mean()),
        "mean_eligible_when_covered": float(counts[covered].mean()) if covered.any() else 0.0,
        "coverage_efficiency": coverage_efficiency,
        "active_leader_count": active_leaders,
        "active_leader_share": float(active_leaders / k),
        "leader_hhi": hhi,
        "effective_leader_count": effective,
        "switch_events": switches,
        "switch_rate": float(switches / max(1, t - 1)),
        "mean_top1_tenure": float(np.mean(lens)) if lens else np.nan,
        "median_top1_tenure": float(np.median(lens)) if lens else np.nan,
        "short_run_le2_share": float(np.mean(np.asarray(lens) <= 2)) if lens else np.nan,
        "top1_top2_gap_mean": float(np.mean(gaps)) if gaps else np.nan,
        "top1_top2_gap_median": float(np.median(gaps)) if gaps else np.nan,
        "mean_pair_trend_jaccard": float(np.mean(jaccards)) if jaccards else np.nan,
        "max_pair_trend_jaccard": float(np.max(jaccards)) if jaccards else np.nan,
        "mean_pair_score_crossing_rate": float(np.mean(crossings)) if crossings else np.nan,
        "productive_switch_share": float(np.mean(productive)) if productive else np.nan,
        "switch_counterfactual_gain_sum": float(np.sum(switch_alpha)) if switch_alpha else 0.0,
        "switch_counterfactual_gain_mean": float(np.mean(switch_alpha)) if switch_alpha else np.nan,
        "leader_year_specialization": float(np.mean(dominant_year_shares)) if dominant_year_shares else np.nan,
        "median_leader_span_days": float(np.median(leader_spans)) if leader_spans else np.nan,
        "late_arriving_leader_share": late_share,
        "leader_transition_diversity": transition_diversity,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--stage1-dir", required=True)
    ap.add_argument("--stage3b-dir", required=True)
    ap.add_argument("--output-dir", default="oure-stage4c-output")
    ap.add_argument("--elite-n", type=int, default=25)
    ap.add_argument("--random-n", type=int, default=50)
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    s1 = pd.read_csv(Path(args.stage1_dir) / "all_fix15_subsets.csv")
    e3 = pd.read_csv(Path(args.stage3b_dir) / "elite_universes.csv")
    r3 = pd.read_csv(Path(args.stage3b_dir) / "same_k_random_controls.csv")

    k7_all = s1[s1["k_including_cash"] == 7].sort_values("log_growth", ascending=False).copy()
    small_elite = k7_all.head(args.elite_n).copy()
    small_rest = k7_all.iloc[args.elite_n:].copy()
    rng = np.random.default_rng(SEED)
    if len(small_rest) > args.random_n:
        ix = rng.choice(len(small_rest), size=args.random_n, replace=False)
        small_random = small_rest.iloc[np.sort(ix)].copy()
    else:
        small_random = small_rest.copy()

    large_elite = e3.sort_values("log_growth", ascending=False).head(args.elite_n).copy()
    if len(r3) > args.random_n:
        ix = rng.choice(len(r3), size=args.random_n, replace=False)
        large_random = r3.iloc[np.sort(ix)].copy()
    else:
        large_random = r3.copy()

    fix_row = s1[s1["k_including_cash"] == len(FIXED15)].sort_values("log_growth", ascending=False).head(1).copy()

    specs: list[dict] = []
    for group, df in [
        ("small_k_elite", small_elite),
        ("small_k_random", small_random),
        ("large_k_elite", large_elite),
        ("large_k_random", large_random),
        ("fix15", fix_row),
    ]:
        for rank, (_, r) in enumerate(df.iterrows(), 1):
            specs.append({
                "group": group,
                "rank_in_group": rank,
                "members": parse_members(r["members"]),
                "source_log_growth": float(r["log_growth"]),
            })

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng)
    bars["symbol"] = bars["symbol"].astype(str)
    feat = build_features(bars)
    feat["symbol"] = feat["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    start_i = int(cal.searchsorted(START, side="left"))
    spos = np.arange(start_i, len(cal) - 2, dtype=int)
    signal_dates = pd.DatetimeIndex(cal[spos])
    exec_dates = pd.DatetimeIndex(cal[spos + 1])
    eras = {
        "full": np.ones(len(exec_dates), dtype=bool),
        "2021_2024": np.asarray(exec_dates < SPLIT),
        "2025_2026": np.asarray(exec_dates >= SPLIT),
    }

    rows: list[dict] = []
    for spec in specs:
        for era, mask in eras.items():
            met = architecture_metrics(score, gross, signal_dates, exec_dates, spec["members"], mask)
            if not met:
                continue
            rows.append({
                "group": spec["group"],
                "rank_in_group": spec["rank_in_group"],
                "era": era,
                "members": ",".join(spec["members"]),
                "source_log_growth": spec["source_log_growth"],
                **met,
            })

    detail = pd.DataFrame(rows)
    detail.to_csv(out / "stage4c_universe_metrics.csv", index=False)

    numeric = [c for c in detail.select_dtypes(include=[np.number]).columns if c != "rank_in_group"]
    med = detail.groupby(["group", "era"])[numeric].median().reset_index()
    med.to_csv(out / "stage4c_group_medians.csv", index=False)

    effects: list[dict] = []
    pairs = [("small_k_elite", "small_k_random", "persistence"), ("large_k_elite", "large_k_random", "relay")]
    for elite, control, architecture in pairs:
        for era in eras:
            a = med[(med.group == elite) & (med.era == era)]
            b = med[(med.group == control) & (med.era == era)]
            if a.empty or b.empty:
                continue
            for metric in numeric:
                av = float(a.iloc[0][metric])
                bv = float(b.iloc[0][metric])
                effects.append({
                    "architecture": architecture,
                    "elite_group": elite,
                    "control_group": control,
                    "era": era,
                    "metric": metric,
                    "elite_median": av,
                    "control_median": bv,
                    "difference": av - bv,
                })
    eff = pd.DataFrame(effects)
    eff.to_csv(out / "stage4c_group_effects.csv", index=False)

    champs = detail[(detail["rank_in_group"] == 1) & detail["group"].isin(["small_k_elite", "large_k_elite", "fix15"])].copy()
    champs.to_csv(out / "stage4c_champions.csv", index=False)

    payload = {
        "study": "OURE Stage4C two-architecture mechanism validation",
        "status": "completed",
        "frozen_groups": {
            "small_k_elite_n": int(len(small_elite)),
            "small_k_random_n": int(len(small_random)),
            "large_k_elite_n": int(len(large_elite)),
            "large_k_random_n": int(len(large_random)),
            "random_seed": SEED,
        },
        "champions": champs.to_dict(orient="records"),
        "group_medians": med.to_dict(orient="records"),
        "interpretation_gate": "Support two architectures only if small-K elite separates coherently from small-K random on persistence metrics and large-K elite separates coherently from large-K random on relay/productive-replacement metrics. Champion-only separation is insufficient.",
    }
    (out / "oure_stage4c_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
