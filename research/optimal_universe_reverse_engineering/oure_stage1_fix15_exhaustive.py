#!/usr/bin/env python3
"""OURE Stage1: exhaustive static-subset reverse engineering inside Fix15.

Hindsight/explanatory only. Enumerates every subset of the 14 non-cash Fix15
members while always retaining 511220 as the cash signal, then decomposes
set value, marginal value and interactions under the frozen OLS engine.
"""
from __future__ import annotations

import argparse
import json
import math
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
from validate_fixed15_vs_full_market import FIXED15
from walk_forward_candidate_pool import SIDE_COST
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

CASH = "511220"
START = pd.Timestamp("2021-01-01")


def _total_from_log(x: float) -> float:
    return float(np.exp(x) - 1.0)


def _cagr(total: float, first_date: pd.Timestamp, last_date: pd.Timestamp) -> float:
    days = max(1, int((last_date - first_date).days))
    return float((1.0 + total) ** (365.25 / days) - 1.0) if total > -1 else -1.0


def _runs(pos: np.ndarray) -> list[tuple[int, int]]:
    """Return contiguous invested runs as (symbol_index, length). Cash/none ignored."""
    out: list[tuple[int, int]] = []
    cur = -1
    n = 0
    for x in pos.astype(int):
        if x <= 0:
            if cur > 0:
                out.append((cur, n))
            cur, n = -1, 0
            continue
        if x == cur:
            n += 1
        else:
            if cur > 0:
                out.append((cur, n))
            cur, n = x, 1
    if cur > 0:
        out.append((cur, n))
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--output-dir", default="oure-stage1-output")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    bars["symbol"] = bars["symbol"].astype(str)
    features = build_features(bars)
    features["symbol"] = features["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, features)

    fixed = sorted(str(x) for x in FIXED15)
    if CASH not in fixed:
        raise RuntimeError(f"cash signal {CASH} missing from FIXED15")
    noncash = sorted(s for s in fixed if s != CASH)
    if len(noncash) != 14:
        raise RuntimeError(f"expected 14 non-cash Fix15 symbols, got {len(noncash)}")
    symbols = [CASH] + noncash
    missing = [s for s in symbols if s not in score.columns or s not in gross.columns]
    if missing:
        raise RuntimeError(f"Fix15 symbols missing from wide data: {missing}")

    start_i = int(cal.searchsorted(START, side="left"))
    signal_pos = np.arange(start_i, len(cal) - 2, dtype=int)
    signal_dates = pd.DatetimeIndex(cal[signal_pos])
    exec_dates = pd.DatetimeIndex(cal[signal_pos + 1])
    if len(signal_dates) == 0:
        raise RuntimeError("no evaluation dates")

    score_m = score.loc[signal_dates, symbols].to_numpy(float)
    gross_m = gross.loc[signal_dates, symbols].to_numpy(float)
    gross_m = np.where(np.isfinite(gross_m), gross_m, 0.0)
    t = len(signal_dates)
    n = len(noncash)
    nmasks = 1 << n

    # Dynamic-programming exact target matrix. Row=non-cash inclusion mask.
    # Tie handling reproduces idxmax on [cash] + sorted(non-cash): lower column wins.
    targets = np.full((nmasks, t), -1, dtype=np.int16)
    cash_ok = np.isfinite(score_m[:, 0])
    targets[0, cash_ok] = 0
    row_idx = np.arange(t)
    for mask in range(1, nmasks):
        lsb = mask & -mask
        bit = lsb.bit_length() - 1
        prev = mask ^ lsb
        cand_idx = bit + 1
        prev_t = targets[prev]
        prev_score = np.full(t, -np.inf, dtype=float)
        ok_prev = prev_t >= 0
        prev_score[ok_prev] = score_m[row_idx[ok_prev], prev_t[ok_prev]]
        cand_score = score_m[:, cand_idx]
        choose = np.isfinite(cand_score) & (
            (cand_score > prev_score)
            | ((cand_score == prev_score) & ((prev_t < 0) | (cand_idx < prev_t)))
        )
        targets[mask] = prev_t
        targets[mask, choose] = cand_idx

    full_log = np.zeros(nmasks, dtype=float)
    era1_log = np.zeros(nmasks, dtype=float)
    era2_log = np.zeros(nmasks, dtype=float)
    mdd = np.zeros(nmasks, dtype=float)
    switches = np.zeros(nmasks, dtype=np.int32)
    turnover = np.zeros(nmasks, dtype=np.int32)
    invested = np.zeros(nmasks, dtype=float)

    era1 = exec_dates <= pd.Timestamp("2024-12-31")
    era2 = exec_dates >= pd.Timestamp("2025-01-01")

    for mask in range(nmasks):
        raw_t = targets[mask]
        pos = np.where(raw_t > 0, raw_t, -1).astype(np.int16)
        g = np.zeros(t, dtype=float)
        active = pos > 0
        g[active] = gross_m[row_idx[active], pos[active]]
        sides = np.zeros(t, dtype=np.int8)
        if pos[0] > 0:
            sides[0] = 1
        if t > 1:
            changed = pos[1:] != pos[:-1]
            one_cash = (pos[1:] < 0) | (pos[:-1] < 0)
            sides[1:] = np.where(changed, np.where(one_cash, 1, 2), 0)
        net = (1.0 + g) * (1.0 - SIDE_COST * sides) - 1.0
        lg = np.log1p(net)
        full_log[mask] = float(lg.sum())
        era1_log[mask] = float(lg[era1].sum())
        era2_log[mask] = float(lg[era2].sum())
        eq = np.exp(np.cumsum(lg))
        dd = eq / np.maximum.accumulate(eq) - 1.0
        mdd[mask] = float(dd.min()) if len(dd) else 0.0
        switches[mask] = int(np.count_nonzero(sides))
        turnover[mask] = int(sides.sum())
        invested[mask] = float(active.mean())

    members_cache: list[str] = []
    rows: list[dict] = []
    for mask in range(nmasks):
        members = [noncash[b] for b in range(n) if mask & (1 << b)]
        members_cache.append(",".join([CASH, *members]))
        total = _total_from_log(full_log[mask])
        rows.append({
            "mask": mask,
            "k_including_cash": 1 + mask.bit_count(),
            "members": members_cache[-1],
            "log_growth": full_log[mask],
            "total_return": total,
            "cagr": _cagr(total, exec_dates[0], exec_dates[-1]),
            "log_growth_2021_2024": era1_log[mask],
            "return_2021_2024": _total_from_log(era1_log[mask]),
            "log_growth_2025_2026": era2_log[mask],
            "return_2025_2026": _total_from_log(era2_log[mask]),
            "max_drawdown": mdd[mask],
            "switch_events": int(switches[mask]),
            "turnover_sides": int(turnover[mask]),
            "invested_ratio": invested[mask],
        })
    subset = pd.DataFrame(rows).sort_values("mask").reset_index(drop=True)
    subset.to_csv(out / "all_fix15_subsets.csv", index=False)

    full_mask = nmasks - 1
    best_mask = int(np.argmax(full_log))
    ag_bit = noncash.index("159825") if "159825" in noncash else None
    ag_removed_mask = full_mask ^ (1 << ag_bit) if ag_bit is not None else None

    # Best and distribution by K.
    by_k_rows = []
    for k, g in subset.groupby("k_including_cash", sort=True):
        gg = g.sort_values("log_growth", ascending=False)
        best = gg.iloc[0]
        by_k_rows.append({
            "k_including_cash": int(k),
            "n_subsets": int(len(gg)),
            "best_mask": int(best["mask"]),
            "best_members": str(best["members"]),
            "best_total_return": float(best["total_return"]),
            "best_log_growth": float(best["log_growth"]),
            "median_total_return": float(gg["total_return"].median()),
            "p90_total_return": float(gg["total_return"].quantile(.90)),
            "p99_total_return": float(gg["total_return"].quantile(.99)),
        })
    pd.DataFrame(by_k_rows).to_csv(out / "best_and_distribution_by_k.csv", index=False)

    # Exact Banzhaf-style marginal value and context-size profile.
    sym_rows = []
    marginal_size_rows = []
    order = np.argsort(full_log)
    top1_cut = full_log[order[max(0, int(math.floor(.99 * nmasks)))]]
    top5_cut = full_log[order[max(0, int(math.floor(.95 * nmasks)))]]
    top1_masks = np.flatnonzero(full_log >= top1_cut)
    top5_masks = np.flatnonzero(full_log >= top5_cut)

    full_pos = np.where(targets[full_mask] > 0, targets[full_mask], -1)
    full_runs = _runs(full_pos)

    for bit, sym in enumerate(noncash):
        b = 1 << bit
        without = np.array([m for m in range(nmasks) if not (m & b)], dtype=int)
        delta = full_log[without | b] - full_log[without]
        for ctx_size in range(0, n):
            sel = np.array([m.bit_count() == ctx_size for m in without])
            if sel.any():
                d = delta[sel]
                marginal_size_rows.append({
                    "symbol": sym,
                    "context_noncash_size": ctx_size,
                    "n_contexts": int(len(d)),
                    "mean_marginal_log_value": float(d.mean()),
                    "median_marginal_log_value": float(np.median(d)),
                    "positive_share": float((d > 0).mean()),
                })

        idx = bit + 1
        runs = [ln for si, ln in full_runs if si == idx]
        base_mask = full_mask ^ b
        base_pos = np.where(targets[base_mask] > 0, targets[base_mask], -1)
        changed_to_i = full_pos == idx
        coverage_days = int(np.sum(changed_to_i & (base_pos < 0)))
        competition_days = int(np.sum(changed_to_i & (base_pos > 0) & (base_pos != idx)))

        sym_rows.append({
            "symbol": sym,
            "in_global_best": bool(best_mask & b),
            "singleton_total_return": _total_from_log(full_log[b]),
            "singleton_log_growth": float(full_log[b]),
            "fix15_removal_delta_log": float(full_log[full_mask] - full_log[base_mask]),
            "fix15_removal_delta_total_return_pp": float(100.0 * (_total_from_log(full_log[full_mask]) - _total_from_log(full_log[base_mask]))),
            "banzhaf_mean_log_delta": float(delta.mean()),
            "banzhaf_median_log_delta": float(np.median(delta)),
            "banzhaf_positive_share": float((delta > 0).mean()),
            "top1pct_inclusion_rate": float(np.mean((top1_masks & b) != 0)),
            "top5pct_inclusion_rate": float(np.mean((top5_masks & b) != 0)),
            "trend_eligible_share": float(np.isfinite(score_m[:, idx]).mean()),
            "mean_score_when_eligible": float(np.nanmean(score_m[:, idx])) if np.isfinite(score_m[:, idx]).any() else np.nan,
            "median_score_when_eligible": float(np.nanmedian(score_m[:, idx])) if np.isfinite(score_m[:, idx]).any() else np.nan,
            "fix15_selected_days": int(np.sum(full_pos == idx)),
            "fix15_run_count": int(len(runs)),
            "fix15_mean_top1_tenure": float(np.mean(runs)) if runs else np.nan,
            "fix15_short_run_le2_share": float(np.mean(np.asarray(runs) <= 2)) if runs else np.nan,
            "fix15_coverage_days_if_present": coverage_days,
            "fix15_competition_days_if_present": competition_days,
            "fix15_coverage_share_of_changed_days": float(coverage_days / (coverage_days + competition_days)) if (coverage_days + competition_days) else np.nan,
            "best_local_delta_log": float(full_log[best_mask] - full_log[best_mask ^ b]) if (best_mask & b) else float(full_log[best_mask | b] - full_log[best_mask]),
        })

    sym_df = pd.DataFrame(sym_rows).sort_values("banzhaf_mean_log_delta", ascending=False)
    sym_df.to_csv(out / "symbol_structural_traits.csv", index=False)
    pd.DataFrame(marginal_size_rows).to_csv(out / "marginal_value_by_context_size.csv", index=False)

    # Pairwise interaction and trend-opportunity overlap.
    pair_rows = []
    eligible = np.isfinite(score_m[:, 1:])
    for i in range(n):
        bi = 1 << i
        for j in range(i + 1, n):
            bj = 1 << j
            base = np.array([m for m in range(nmasks) if not (m & bi) and not (m & bj)], dtype=int)
            inter = full_log[base | bi | bj] - full_log[base | bi] - full_log[base | bj] + full_log[base]
            a = eligible[:, i]
            b2 = eligible[:, j]
            union = int(np.sum(a | b2))
            overlap = float(np.sum(a & b2) / union) if union else np.nan
            pair_rows.append({
                "symbol_i": noncash[i],
                "symbol_j": noncash[j],
                "mean_pair_interaction_log": float(inter.mean()),
                "median_pair_interaction_log": float(np.median(inter)),
                "positive_interaction_share": float((inter > 0).mean()),
                "trend_eligible_jaccard": overlap,
                "trend_eligible_overlap_days": int(np.sum(a & b2)),
            })
    pd.DataFrame(pair_rows).sort_values("mean_pair_interaction_log", ascending=False).to_csv(
        out / "pairwise_interactions.csv", index=False
    )

    # Compact path diagnostics for Fix15, global best and agriculture removal.
    def path_diag(mask: int) -> dict:
        pos = np.where(targets[mask] > 0, targets[mask], -1)
        rs = _runs(pos)
        lens = [x[1] for x in rs]
        return {
            "mask": int(mask),
            "k_including_cash": 1 + int(mask.bit_count()),
            "members": members_cache[mask],
            "total_return": _total_from_log(full_log[mask]),
            "log_growth": float(full_log[mask]),
            "return_2021_2024": _total_from_log(era1_log[mask]),
            "return_2025_2026": _total_from_log(era2_log[mask]),
            "max_drawdown": float(mdd[mask]),
            "switch_events": int(switches[mask]),
            "turnover_sides": int(turnover[mask]),
            "invested_ratio": float(invested[mask]),
            "mean_top1_tenure": float(np.mean(lens)) if lens else np.nan,
            "median_top1_tenure": float(np.median(lens)) if lens else np.nan,
            "short_run_le2_share": float(np.mean(np.asarray(lens) <= 2)) if lens else np.nan,
        }

    diagnostics = {
        "fix15": path_diag(full_mask),
        "global_best_static_subset": path_diag(best_mask),
        "cash_only": path_diag(0),
    }
    if ag_removed_mask is not None:
        diagnostics["fix15_minus_159825"] = path_diag(ag_removed_mask)

    # Top subset membership list for inspection.
    top = subset.sort_values("log_growth", ascending=False).head(100).copy()
    top.to_csv(out / "top100_subsets.csv", index=False)

    summary = {
        "study": "OURE Stage1 Fix15 exhaustive static-subset reverse engineering",
        "status": "completed",
        "hindsight": True,
        "objective": "full-sample terminal net log growth",
        "evaluation": {
            "signal_start": str(signal_dates[0].date()),
            "signal_end": str(signal_dates[-1].date()),
            "exec_start": str(exec_dates[0].date()),
            "exec_end": str(exec_dates[-1].date()),
            "trading_signals": int(t),
            "side_cost": SIDE_COST,
            "noncash_symbols": noncash,
            "subsets_enumerated": nmasks,
        },
        "diagnostics": diagnostics,
        "best_by_k_file": "best_and_distribution_by_k.csv",
        "symbol_traits_file": "symbol_structural_traits.csv",
        "pairwise_file": "pairwise_interactions.csv",
        "marginal_by_size_file": "marginal_value_by_context_size.csv",
        "next_gate": [
            "Identify identity-free characteristics that separate high-value and low-value subsets.",
            "Freeze a small structural signature before searching outside Fix15.",
            "Test Symbol-disjoint replication excluding every Fix15 code.",
            "Then test Exposure-disjoint replication excluding obvious near-substitutes.",
        ],
    }
    (out / "oure_stage1_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
