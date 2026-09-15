#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage8a_opportunity30 as s8a
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

KS = [8, 10, 12, 15, 20, 25, 30]
H = 126
HIST_SESSIONS = 378
START_EXEC = pd.Timestamp("2021-01-01")
FIX15 = tuple(s8a.FIX15)


def greedy_order(mat: np.ndarray, common: list[str], max_k: int = 30) -> list[int]:
    selected: list[int] = []
    remaining = set(range(len(common)))
    mean_r = np.nanmean(mat, axis=1)
    for _ in range(max_k):
        best = None
        best_key = None
        for j in remaining:
            sc = s8a.top2_coverage(mat, selected + [j])
            key = (sc, float(mean_r[j]), -j)
            if best_key is None or key > best_key:
                best_key = key
                best = j
        if best is None:
            raise RuntimeError("greedy order failed")
        selected.append(best)
        remaining.remove(best)
    return selected


def competition_diagnostics(mat: np.ndarray, ids: list[int]) -> dict:
    v = mat[np.asarray(ids, dtype=int), :]
    k, w = v.shape
    if k <= 1:
        mean_pair_spearman = np.nan
    else:
        # Columns are selected ETFs, rows are 21-session historical windows.
        c = pd.DataFrame(v.T).corr(method="spearman").to_numpy(float)
        iu = np.triu_indices(k, 1)
        vals = c[iu]
        mean_pair_spearman = float(np.nanmean(vals)) if np.isfinite(vals).any() else np.nan

    # Which selected ETF is the best single historical opportunity in each window?
    winners = np.nanargmax(v, axis=0)
    counts = np.bincount(winners, minlength=k).astype(float)
    used = counts[counts > 0]
    distinct = int(len(used))
    p = used / used.sum()
    entropy = float(-np.sum(p * np.log(p))) if len(p) else np.nan
    eff = float(np.exp(entropy)) if np.isfinite(entropy) else np.nan
    max_share = float(used.max() / used.sum()) if len(used) else np.nan
    return {
        "mean_pair_spearman": mean_pair_spearman,
        "distinct_window_winners": distinct,
        "effective_winner_count": eff,
        "max_window_winner_share": max_share,
    }


def path_stats(g: pd.DataFrame) -> dict:
    g = g.sort_values("signal_date").reset_index(drop=True)
    r = g["net"].to_numpy(float)
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.r_[1.0, eq])[1:]
    mdd = float(np.min(eq / peak - 1.0)) if len(eq) else np.nan

    # Risk-asset tenure only. Cash runs are excluded.
    tenures = []
    prev = object()
    cur_len = 0
    cur_target = None
    switch_events = 0
    for x in g["target"].tolist():
        x = None if pd.isna(x) else str(x)
        if cur_len == 0:
            cur_target = x
            cur_len = 1
        elif x == cur_target:
            cur_len += 1
        else:
            if cur_target is not None:
                tenures.append(cur_len)
            switch_events += 1
            cur_target = x
            cur_len = 1
    if cur_len and cur_target is not None:
        tenures.append(cur_len)

    return {
        "total_return": float(np.prod(1.0 + r) - 1.0),
        "mdd": mdd,
        "turnover_sides": int(g["sides"].sum()),
        "switch_events": int(switch_events),
        "mean_top1_tenure": float(np.mean(tenures)) if tenures else np.nan,
        "median_top1_tenure": float(np.median(tenures)) if tenures else np.nan,
        "sessions": int(len(g)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage8b-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng)
    bars["symbol"] = bars["symbol"].astype(str)
    feat = build_features(bars)
    feat["symbol"] = feat["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)
    meta = pd.read_sql_query(
        text("select symbol,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"), eng
    )
    meta["symbol"] = meta["symbol"].astype(str)

    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    starts = s8a.extended_starts(cal, start0)
    starts_map = {b: p for b, p in starts}
    first_exec_pos = int(cal.searchsorted(START_EXEC, side="left"))
    first_signal = max(0, first_exec_pos - 1)
    last_signal = len(cal) - 3

    need = []
    for b, p in starts:
        next_p = starts_map.get(b + 1, len(cal))
        if next_p <= first_signal or p > last_signal:
            continue
        if p - HIST_SESSIONS < 0:
            continue
        if all((b - j) in starts_map for j in (1, 2, 3)):
            need.append((b, p))
    if not need:
        raise RuntimeError("no blocks")

    by_k: dict[int, dict[int, tuple[str, ...]]] = {k: {} for k in KS}
    sel_rows = []

    for bno, pos in need:
        common = s8a.common_pool_for_block(bno, pos, starts_map, cal, close, meta)
        hist_start = pos - HIST_SESSIONS
        rank_mat, labels = s8a.window_rank_matrix(score, gross, cal, hist_start, common)
        order = greedy_order(rank_mat, common, max(KS))

        # Hard reproduction guard: Stage8A Opportunity30 must be identical.
        old30 = tuple(s8a.greedy_select(rank_mat, common))
        new30 = tuple(sorted(common[j] for j in order[:30]))
        if old30 != new30:
            raise RuntimeError(f"B{bno}: Stage8A K30 reproduction failed")

        prev_cov = None
        for k in KS:
            ids = order[:k]
            members = tuple(sorted(common[j] for j in ids))
            by_k[k][bno] = members
            cov = float(s8a.top2_coverage(rank_mat, ids))
            comp = competition_diagnostics(rank_mat, ids)
            sel_rows.append({
                "block_no": int(bno),
                "decision_date": str(pd.Timestamp(cal[pos]).date()),
                "k": int(k),
                "common_pool_n": int(len(common)),
                "coverage": cov,
                "marginal_coverage_from_prev_k": np.nan if prev_cov is None else cov - prev_cov,
                **comp,
                "overlap_fix15": int(len(set(members) & set(FIX15))),
                "members": ",".join(members),
            })
            prev_cov = cov

    # Same frozen OLS execution engine as Stage8A.
    daily_parts = []
    for k in KS:
        daily_parts.append(
            s8a.build_variant_daily(
                f"OPPORTUNITY_K{k}", by_k[k], starts_map, cal, score, gross, first_signal, last_signal
            )
        )
    fix_by = {b: FIX15 for b, _ in need}
    daily_parts.append(
        s8a.build_variant_daily("FIX15_BENCHMARK", fix_by, starts_map, cal, score, gross, first_signal, last_signal)
    )
    daily = pd.concat(daily_parts, ignore_index=True)
    daily = daily.loc[daily["execution_date"] >= START_EXEC].copy()

    ann, _ = s8a.summarize(daily)
    full_rows = []
    for variant, g in daily.groupby("variant"):
        rec = {"variant": variant, **path_stats(g)}
        full_rows.append(rec)
    full = pd.DataFrame(full_rows)

    sels = pd.DataFrame(sel_rows)
    frontier_rows = []
    for k in KS:
        sk = sels.loc[sels["k"] == k]
        variant = f"OPPORTUNITY_K{k}"
        pr = full.loc[full["variant"] == variant].iloc[0]
        frontier_rows.append({
            "k": k,
            "mean_historical_coverage": float(sk["coverage"].mean()),
            "median_historical_coverage": float(sk["coverage"].median()),
            "mean_marginal_coverage": float(sk["marginal_coverage_from_prev_k"].mean()) if k != KS[0] else np.nan,
            "mean_pair_spearman": float(sk["mean_pair_spearman"].mean()),
            "mean_distinct_window_winners": float(sk["distinct_window_winners"].mean()),
            "mean_effective_winner_count": float(sk["effective_winner_count"].mean()),
            "mean_overlap_fix15": float(sk["overlap_fix15"].mean()),
            "total_return": float(pr["total_return"]),
            "mdd": float(pr["mdd"]),
            "turnover_sides": int(pr["turnover_sides"]),
            "switch_events": int(pr["switch_events"]),
            "mean_top1_tenure": float(pr["mean_top1_tenure"]),
            "median_top1_tenure": float(pr["median_top1_tenure"]),
        })
    frontier = pd.DataFrame(frontier_rows)

    # Diagnostic elbow: smallest K achieving >=99% of K30 mean historical coverage.
    cov30 = float(frontier.loc[frontier["k"] == 30, "mean_historical_coverage"].iloc[0])
    eligible = frontier.loc[frontier["mean_historical_coverage"] >= 0.99 * cov30, "k"]
    coverage99_k = int(eligible.min()) if len(eligible) else None

    sels.to_csv(out / "stage8b_selections.csv", index=False)
    daily.to_csv(out / "stage8b_daily.csv", index=False)
    ann.to_csv(out / "stage8b_annual.csv", index=False)
    full.to_csv(out / "stage8b_full.csv", index=False)
    frontier.to_csv(out / "stage8b_frontier.csv", index=False)

    summary = {
        "study": "OURE Stage8B Opportunity Coverage K frontier",
        "ks": KS,
        "blocks": int(sels["block_no"].nunique()),
        "coverage99_k": coverage99_k,
        "k30_stage8a_reproduction": True,
        "frontier": frontier.to_dict(orient="records"),
    }
    (out / "stage8b_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(frontier.to_string(index=False))
    print(json.dumps({"coverage99_k": coverage99_k, "blocks": summary["blocks"]}, indent=2))


if __name__ == "__main__":
    main()
