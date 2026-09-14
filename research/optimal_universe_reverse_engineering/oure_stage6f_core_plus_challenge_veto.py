#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
from optimal_universe_reverse_engineering.oure_stage5_history_transfer import (
    CASH, LOOKBACKS, ROBUST_TOP_N, RANDOM_N, SEED,
    WindowEvaluator, available_pool, decision_indices, member_key,
    random_same_k, rank_pct, search_library,
)

CORE_K = 29
FINAL_K = 30
CHALLENGE_LOOKBACK = 126
BOOT_N = 20000


def current_rank(score: pd.DataFrame, cal: pd.DatetimeIndex, d: int, pool: list[str]) -> list[str]:
    row = score.loc[cal[d - 1], pool]
    vals = []
    for s in pool:
        v = float(row[s]) if pd.notna(row[s]) else -np.inf
        vals.append((s, v))
    return [s for s, _ in sorted(vals, key=lambda z: (-z[1], z[0]))]


def robust_consensus_core(evals, libs, current_order: list[str]) -> tuple[str, ...]:
    union = set().union(*libs.values())
    values = {L: {u: evals[L].evaluate(u).log_growth for u in union} for L in LOOKBACKS}
    pct = {L: rank_pct(values[L]) for L in LOOKBACKS}
    robust = {}
    for u in union:
        ps = [pct[L][u] for L in LOOKBACKS]
        robust[u] = (min(ps), float(np.mean(ps)))
    order = sorted(union, key=lambda u: (-robust[u][0], -robust[u][1], len(u), u))
    cohort = order[:min(ROBUST_TOP_N, len(order))]
    votes: dict[str, int] = {}
    for u in cohort:
        for s in u:
            votes[s] = votes.get(s, 0) + 1
    current_pos = {s: i for i, s in enumerate(current_order)}
    ranked = sorted(votes, key=lambda s: (-votes[s], current_pos.get(s, 10**9), s))
    chosen = []
    for s in ranked + current_order:
        if s not in chosen:
            chosen.append(s)
        if len(chosen) == CORE_K:
            break
    if len(chosen) != CORE_K:
        raise RuntimeError(f"robust core has only {len(chosen)} members")
    return member_key(chosen)


def state_metrics(score: pd.DataFrame, cal: pd.DatetimeIndex, d: int, pool: list[str]) -> dict[str, float]:
    dates = cal[d - CHALLENGE_LOOKBACK:d]
    sm = score.loc[dates, pool].to_numpy(float)
    finite = np.isfinite(sm)
    eligible_share = float(finite.mean()) if sm.size else np.nan
    gaps = []
    for r in sm:
        x = r[np.isfinite(r)]
        if len(x) >= 2:
            z = np.partition(x, -2)[-2:]
            gaps.append(float(z.max() - z.min()))
    return {
        "eligible_share": eligible_share,
        "top1_top2_gap_median": float(np.median(gaps)) if gaps else np.nan,
    }


def neutral_member(core: tuple[str, ...], current_order: list[str]) -> str:
    core_set = set(core)
    for s in current_order:
        if s not in core_set:
            return s
    raise RuntimeError("no neutral outsider")


def challenge_shares(score: pd.DataFrame, cal: pd.DatetimeIndex, d: int,
                     core: tuple[str, ...], outsiders: list[str]) -> dict[str, float]:
    dates = cal[d - CHALLENGE_LOOKBACK:d]
    core_sm = score.loc[dates, list(core)].to_numpy(float)
    safe = np.where(np.isfinite(core_sm), core_sm, -np.inf)
    leader = safe.max(axis=1)
    active = np.isfinite(leader)
    out = {}
    for s in outsiders:
        x = score.loc[dates, s].to_numpy(float)
        challenge = active & np.isfinite(x) & (x > leader)
        out[s] = float(challenge.mean()) if len(challenge) else np.nan
    return out


def veto_member(score: pd.DataFrame, cal: pd.DatetimeIndex, d: int,
                core: tuple[str, ...], current_order: list[str]) -> tuple[str, float, float, bool]:
    outsiders = [s for s in current_order if s not in set(core)]
    shares = challenge_shares(score, cal, d, core, outsiders)
    vals = np.array([shares[s] for s in outsiders if np.isfinite(shares[s])], dtype=float)
    threshold = float(np.median(vals)) if len(vals) else np.nan
    proposed = outsiders[0]
    pv = shares.get(proposed, np.nan)
    if not np.isfinite(threshold) or not np.isfinite(pv) or pv <= threshold:
        return proposed, pv, threshold, False
    for s in outsiders:
        v = shares.get(s, np.nan)
        if np.isfinite(v) and v <= threshold:
            return s, v, threshold, s != proposed
    return proposed, pv, threshold, False


def bootstrap_ci(x: np.ndarray, seed: int) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if not len(x):
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(BOOT_N, len(x)))
    means = x[idx].mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def era(date: str) -> str:
    return "2022-24" if str(date)[:4] <= "2024" else "2025-26"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage6f-output")
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
    meta = pd.read_sql_query(text("""
        select symbol,has_daily_bars,leveraged_flag,inverse_flag
        from public.instrument_metadata_current
    """), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    dec = decision_indices(cal)
    past_states: list[dict[str, float]] = []
    rows = []

    for pi, d in enumerate(dec):
        next_d = dec[pi + 1] if pi + 1 < len(dec) else min(len(cal) - 2, d + 126)
        if next_d <= d:
            continue
        pool = available_pool(close, meta, cal, d)
        if len(pool) < FINAL_K:
            raise RuntimeError(f"too few point-in-time candidates: {len(pool)}")
        cur_order = current_rank(score, cal, d, pool)
        core_a = member_key(cur_order[:CORE_K])

        evals, libs = {}, {}
        for L in LOOKBACKS:
            ev = WindowEvaluator(score, gross, cal, pool, d - L, d)
            lib, _ = search_library(ev, pool)
            evals[L], libs[L] = ev, lib
        core_b = robust_consensus_core(evals, libs, cur_order)

        st = state_metrics(score, cal, d, pool)
        if len(past_states) >= 2:
            med_elig = float(np.median([x["eligible_share"] for x in past_states]))
            med_gap = float(np.median([x["top1_top2_gap_median"] for x in past_states]))
            transfer_on = bool(st["eligible_share"] >= med_elig and st["top1_top2_gap_median"] >= med_gap)
        else:
            med_elig = np.nan
            med_gap = np.nan
            transfer_on = False
        core_c = core_b if transfer_on else core_a
        past_states.append(st)

        future = WindowEvaluator(score, gross, cal, pool, d, next_d)
        rule_sets = {}
        for name, core in [("core_a_current", core_a), ("core_b_robust", core_b), ("core_c_state_gated_neutral", core_c)]:
            adm = neutral_member(core, cur_order)
            rule_sets[name] = member_key(list(core) + [adm])
        proposed = neutral_member(core_c, cur_order)
        admitted, admitted_share, veto_thr, veto_triggered = veto_member(score, cal, d, core_c, cur_order)
        rule_sets["core_c_state_gated_veto"] = member_key(list(core_c) + [admitted])

        rnd_sets = random_same_k(pool, FINAL_K, RANDOM_N, SEED + pi * 1000 + 77)
        rnd_logs = np.array([future.evaluate(u).log_growth for u in rnd_sets], dtype=float)
        rnd_med = float(np.median(rnd_logs)) if len(rnd_logs) else np.nan

        for name, members in rule_sets.items():
            rr = future.evaluate(members)
            rows.append({
                "decision_date": str(cal[d].date()),
                "future_end_date": str(cal[next_d - 1].date()),
                "partial_final_period": bool(pi == len(dec) - 1 and next_d < d + 126),
                "era": era(str(cal[d].date())),
                "rule": name,
                "future_log_growth": rr.log_growth,
                "future_total_return": rr.total_return,
                "future_max_drawdown": rr.max_drawdown,
                "future_switch_events": rr.switch_events,
                "random_k30_log_median": rnd_med,
                "beats_random_median": bool(rr.log_growth > rnd_med),
                "transfer_on": transfer_on,
                "eligible_share": st["eligible_share"],
                "eligible_share_hist_median": med_elig,
                "top1_top2_gap_median": st["top1_top2_gap_median"],
                "top1_top2_gap_hist_median": med_gap,
                "veto_triggered": veto_triggered if name.startswith("core_c") else False,
                "neutral_admission": proposed if name.startswith("core_c") else neutral_member(core_a if name.startswith("core_a") else core_b, cur_order),
                "final_admission": admitted if name == "core_c_state_gated_veto" else (proposed if name.startswith("core_c") else neutral_member(core_a if name.startswith("core_a") else core_b, cur_order)),
                "admitted_challenge_share": admitted_share if name == "core_c_state_gated_veto" else np.nan,
                "challenge_median_threshold": veto_thr if name.startswith("core_c") else np.nan,
                "members": ",".join(members),
            })

    res = pd.DataFrame(rows)
    res.to_csv(out / "stage6f_period_results.csv", index=False)
    complete = res[~res["partial_final_period"]].copy()
    piv = complete.pivot(index="decision_date", columns="rule", values="future_log_growth")

    a = piv["core_a_current"]
    b = piv["core_b_robust"]
    c = piv["core_c_state_gated_neutral"]
    v = piv["core_c_state_gated_veto"]
    d_ca = (c - a).to_numpy(float)
    d_cb = (c - b).to_numpy(float)
    d_v = (v - c).to_numpy(float)

    crows = complete[complete["rule"] == "core_c_state_gated_neutral"]
    veto_rows = complete[complete["rule"] == "core_c_state_gated_veto"]
    era_veto = {}
    for e in ("2022-24", "2025-26"):
        p = complete[complete["era"] == e].pivot(index="decision_date", columns="rule", values="future_log_growth")
        era_veto[e] = float((p["core_c_state_gated_veto"] - p["core_c_state_gated_neutral"]).median()) if len(p) else np.nan

    core_gate = bool(
        c.sum() > a.sum() and c.sum() > b.sum()
        and ((c > a) & (c > b)).mean() > 0.5
        and crows["beats_random_median"].mean() > 0.5
    )
    veto_gate = bool(
        v.sum() > c.sum()
        and (v > c).mean() > 0.5
        and all(np.isfinite(era_veto[e]) and era_veto[e] >= 0 for e in era_veto)
    )

    summary = {
        "study": "OURE Stage6F fixed-K30 core formation plus challenge veto",
        "status": "completed",
        "completed_periods": int(len(piv)),
        "core_gate_pass": core_gate,
        "veto_gate_pass": veto_gate,
        "linked_total_return_completed": {col: float(np.exp(piv[col].sum()) - 1.0) for col in piv.columns},
        "core_c_win_both_rate": float(((c > a) & (c > b)).mean()),
        "core_c_random_median_hit_rate": float(crows["beats_random_median"].mean()),
        "veto_improvement_rate": float((v > c).mean()),
        "veto_trigger_rate": float(veto_rows["veto_triggered"].mean()),
        "median_veto_delta_by_era": era_veto,
        "paired_mean_delta_log": {
            "core_c_minus_a": float(np.mean(d_ca)),
            "core_c_minus_b": float(np.mean(d_cb)),
            "veto_minus_neutral": float(np.mean(d_v)),
        },
        "bootstrap95_mean_delta_log": {
            "core_c_minus_a": bootstrap_ci(d_ca, SEED + 1),
            "core_c_minus_b": bootstrap_ci(d_cb, SEED + 2),
            "veto_minus_neutral": bootstrap_ci(d_v, SEED + 3),
        },
    }
    (out / "oure_stage6f_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
