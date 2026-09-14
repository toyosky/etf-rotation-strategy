#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
from validate_fixed15_vs_full_market import FIXED15
from walk_forward_candidate_pool import SIDE_COST

CASH = "511220"
MAX_K = 60
SINGLETON_SHORTLIST = 180
GREEDY_SEEDS = 8
SWAP_SHORTLIST = 80
REFINE_ROUNDS = 5
ROBUST_TOP_N = 20
RANDOM_N = 100
SEED = 20260914
LOOKBACKS = (63, 126, 252)


def member_key(members) -> tuple[str, ...]:
    return tuple(sorted(set(str(x) for x in members if str(x) != CASH)))


@dataclass
class EvalResult:
    members: tuple[str, ...]
    log_growth: float
    total_return: float
    max_drawdown: float
    switch_events: int
    turnover_sides: int
    invested_ratio: float


class WindowEvaluator:
    def __init__(self, score: pd.DataFrame, gross: pd.DataFrame, dates: pd.DatetimeIndex,
                 pool: list[str], start: int, end: int):
        self.dates = pd.DatetimeIndex(dates[start:end])
        self.pool = list(pool)
        self.index = {s: i for i, s in enumerate(self.pool)}
        self.cash_score = score.loc[self.dates, CASH].to_numpy(float)
        self.score = score.loc[self.dates, self.pool].to_numpy(float)
        self.gross = gross.loc[self.dates, self.pool].to_numpy(float)
        self.gross = np.where(np.isfinite(self.gross), self.gross, 0.0)
        self.cache: dict[tuple[str, ...], EvalResult] = {}

    def evaluate(self, members) -> EvalResult:
        key = member_key(members)
        if key in self.cache:
            return self.cache[key]
        if len(key) > MAX_K:
            raise ValueError("K above MAX_K")
        t = len(self.dates)
        best_score = np.where(np.isfinite(self.cash_score), self.cash_score, -np.inf).copy()
        target = np.full(t, -1, dtype=np.int32)
        for sym in key:
            if sym not in self.index:
                continue
            j = self.index[sym]
            v = self.score[:, j]
            choose = np.isfinite(v) & (v > best_score)
            target[choose] = j
            best_score[choose] = v[choose]
        active = target >= 0
        rows = np.arange(t)
        g = np.zeros(t, dtype=float)
        if t:
            g[active] = self.gross[rows[active], target[active]]
        sides = np.zeros(t, dtype=np.int8)
        if t:
            if target[0] >= 0:
                sides[0] = 1
            if t > 1:
                changed = target[1:] != target[:-1]
                one_cash = (target[1:] < 0) | (target[:-1] < 0)
                sides[1:] = np.where(changed, np.where(one_cash, 1, 2), 0)
        net = (1.0 + g) * (1.0 - SIDE_COST * sides) - 1.0
        lg = np.log1p(net)
        eq = np.exp(np.cumsum(lg)) if len(lg) else np.array([1.0])
        dd = eq / np.maximum.accumulate(eq) - 1.0
        out = EvalResult(
            members=key,
            log_growth=float(lg.sum()),
            total_return=float(np.exp(lg.sum()) - 1.0),
            max_drawdown=float(dd.min()) if len(dd) else 0.0,
            switch_events=int(np.count_nonzero(sides)),
            turnover_sides=int(sides.sum()),
            invested_ratio=float(active.mean()) if t else 0.0,
        )
        self.cache[key] = out
        return out

    def mechanism(self, members) -> dict[str, float]:
        key = member_key(members)
        m = [s for s in key if s in self.index]
        if not m:
            return {"coverage_efficiency": np.nan, "productive_switch_share": np.nan,
                    "switch_counterfactual_gain_mean": np.nan}
        idx = [self.index[s] for s in m]
        sm = self.score[:, idx]
        gm = self.gross[:, idx]
        eligible = np.isfinite(sm)
        counts = eligible.sum(axis=1)
        covered = counts > 0
        safe = np.where(eligible, sm, -np.inf)
        leader = np.full(len(sm), -1, dtype=int)
        if len(sm):
            best = safe.max(axis=1)
            has = np.isfinite(best)
            leader[has] = np.argmax(safe[has], axis=1)
        active_leaders = len(np.unique(leader[leader >= 0]))
        mean_elig = float(counts[covered].mean()) if covered.any() else np.nan
        coverage_eff = float(active_leaders / mean_elig) if np.isfinite(mean_elig) and mean_elig > 0 else np.nan
        alpha = []
        productive = []
        for t in range(1, len(leader)):
            old, new = int(leader[t - 1]), int(leader[t])
            if old == new:
                continue
            new_r = 0.0 if new < 0 else float(gm[t, new])
            old_r = 0.0 if old < 0 else float(gm[t, old])
            if not np.isfinite(new_r): new_r = 0.0
            if not np.isfinite(old_r): old_r = 0.0
            a = new_r - old_r
            alpha.append(a)
            productive.append(a > 0)
        return {
            "coverage_efficiency": coverage_eff,
            "productive_switch_share": float(np.mean(productive)) if productive else np.nan,
            "switch_counterfactual_gain_mean": float(np.mean(alpha)) if alpha else np.nan,
        }


def rank_pct(values: dict[tuple[str, ...], float], higher=True) -> dict[tuple[str, ...], float]:
    keys = list(values)
    arr = np.array([values[k] for k in keys], dtype=float)
    bad = ~np.isfinite(arr)
    if higher:
        arr[bad] = -np.inf
    else:
        arr[bad] = np.inf
    order = np.argsort(arr, kind="mergesort")
    ranks = np.empty(len(arr), dtype=float)
    ranks[order] = np.arange(len(arr), dtype=float)
    if len(arr) <= 1:
        pct = np.ones(len(arr))
    else:
        pct = ranks / (len(arr) - 1)
    if not higher:
        pct = 1.0 - pct
    return {k: float(p) for k, p in zip(keys, pct)}


def greedy_path(ev: WindowEvaluator, seed: str, syms: list[str]) -> list[tuple[str, ...]]:
    cur = {seed}
    out = [member_key(cur)]
    while len(cur) < MAX_K:
        base = ev.evaluate(cur).log_growth
        best_sym = None
        best_val = base
        for s in syms:
            if s in cur:
                continue
            v = ev.evaluate(cur | {s}).log_growth
            if v > best_val + 1e-12:
                best_val, best_sym = v, s
        if best_sym is None:
            break
        cur.add(best_sym)
        out.append(member_key(cur))
    return out


def refine(ev: WindowEvaluator, start: tuple[str, ...], swap_syms: list[str]) -> tuple[str, ...]:
    cur = set(start)
    for _ in range(REFINE_ROUNDS):
        base = ev.evaluate(cur).log_growth
        best_val = base
        best = set(cur)
        if len(cur) > 1:
            for x in sorted(cur):
                cand = cur - {x}
                v = ev.evaluate(cand).log_growth
                if v > best_val + 1e-12:
                    best_val, best = v, set(cand)
        for x in sorted(cur):
            for y in swap_syms:
                if y in cur:
                    continue
                cand = (cur - {x}) | {y}
                v = ev.evaluate(cand).log_growth
                if v > best_val + 1e-12:
                    best_val, best = v, set(cand)
        if best == cur:
            break
        cur = best
    return member_key(cur)


def search_library(ev: WindowEvaluator, pool: list[str]) -> tuple[set[tuple[str, ...]], pd.DataFrame]:
    rows = []
    for s in pool:
        r = ev.evaluate({s})
        rows.append((s, r.log_growth))
    single = pd.DataFrame(rows, columns=["symbol", "log_growth"]).sort_values(
        ["log_growth", "symbol"], ascending=[False, True]
    )
    shortlist = single.head(min(SINGLETON_SHORTLIST, len(single)))["symbol"].tolist()
    seeds = shortlist[:min(GREEDY_SEEDS, len(shortlist))]
    lib: set[tuple[str, ...]] = set()
    endpoints = []
    for seed in seeds:
        path = greedy_path(ev, seed, shortlist)
        lib.update(path)
        endpoints.append(path[-1])
    lib.update(member_key([s]) for s in shortlist[:20])
    endpoints = sorted(set(endpoints), key=lambda x: (-ev.evaluate(x).log_growth, x))[:4]
    swap_syms = shortlist[:min(SWAP_SHORTLIST, len(shortlist))]
    for ep in endpoints:
        rr = refine(ev, ep, swap_syms)
        lib.add(rr)
    return lib, single


def decision_indices(cal: pd.DatetimeIndex) -> list[int]:
    out = []
    for y in range(2022, 2027):
        for m in (1, 7):
            d = pd.Timestamp(y, m, 1)
            i = int(cal.searchsorted(d, side="left"))
            if i < len(cal) - 2 and i >= 252:
                out.append(i)
    return sorted(set(out))


def available_pool(close: pd.DataFrame, meta: pd.DataFrame, cal: pd.DatetimeIndex, d: int) -> list[str]:
    guarded = set(meta.loc[
        (meta["has_daily_bars"].fillna(False).astype(bool))
        & (~meta["leveraged_flag"].fillna(False).astype(bool))
        & (~meta["inverse_flag"].fillna(False).astype(bool)), "symbol"
    ].astype(str))
    past_dates = cal[d - 252:d]
    out = []
    for s in close.columns.astype(str):
        if s == CASH or s not in guarded:
            continue
        x = close.loc[past_dates, s].to_numpy(float)
        if np.isfinite(x).sum() >= 240 and np.isfinite(x[-1]):
            out.append(s)
    return sorted(out)


def choose_rules(evals: dict[int, WindowEvaluator], libraries: dict[int, set[tuple[str, ...]]]):
    union = set().union(*libraries.values())
    values = {L: {u: evals[L].evaluate(u).log_growth for u in union} for L in LOOKBACKS}
    # Rule A
    a = max(union, key=lambda u: (values[126][u], -len(u), tuple(reversed(u))))
    # Rule B
    pct = {L: rank_pct(values[L]) for L in LOOKBACKS}
    robust = {}
    for u in union:
        ps = [pct[L][u] for L in LOOKBACKS]
        robust[u] = (min(ps), float(np.mean(ps)))
    robust_order = sorted(union, key=lambda u: (-robust[u][0], -robust[u][1], len(u), u))
    b = robust_order[0]
    # Rule C
    mech_candidates = robust_order[:min(ROBUST_TOP_N, len(robust_order))]
    mech_raw = {u: evals[126].mechanism(u) for u in mech_candidates}
    comps = {}
    for metric in ("coverage_efficiency", "productive_switch_share", "switch_counterfactual_gain_mean"):
        vals = {u: mech_raw[u][metric] for u in mech_candidates}
        comps[metric] = rank_pct(vals)
    mscore = {u: float(np.mean([comps[m][u] for m in comps])) for u in mech_candidates}
    c = sorted(mech_candidates, key=lambda u: (-mscore[u], robust_order.index(u), len(u), u))[0]
    return {
        "past6m_winner": a,
        "robust_3_6_12": b,
        "mechanism_assisted": c,
    }, robust, mech_raw


def random_same_k(pool: list[str], k: int, n: int, seed: int) -> list[tuple[str, ...]]:
    rng = np.random.default_rng(seed)
    if k <= 0 or k > len(pool):
        return []
    seen = set()
    limit = max(1000, n * 20)
    for _ in range(limit):
        z = member_key(rng.choice(pool, size=k, replace=False).tolist())
        seen.add(z)
        if len(seen) >= n:
            break
    return sorted(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage5-output")
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
    if CASH not in score.columns:
        raise RuntimeError("cash proxy missing")
    meta = pd.read_sql_query(text("""
        select symbol,has_daily_bars,leveraged_flag,inverse_flag,
               exposure_level1,risk_bucket
        from public.instrument_metadata_current
    """), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    dec = decision_indices(cal)
    rows = []
    selections = []
    for pi, d in enumerate(dec):
        next_d = dec[pi + 1] if pi + 1 < len(dec) else min(len(cal) - 2, d + 126)
        if next_d <= d:
            continue
        pool = available_pool(close, meta, cal, d)
        if len(pool) < 30:
            raise RuntimeError(f"too few point-in-time candidates at {cal[d].date()}: {len(pool)}")

        evals = {}
        libs = {}
        singles = {}
        for L in LOOKBACKS:
            ev = WindowEvaluator(score, gross, cal, pool, d - L, d)
            lib, single = search_library(ev, pool)
            evals[L], libs[L], singles[L] = ev, lib, single
        chosen, robust_scores, mech_raw = choose_rules(evals, libs)

        future = WindowEvaluator(score, gross, cal, pool, d, next_d)
        fix_members = [s for s in FIXED15 if s != CASH and s in pool]
        fix_res = future.evaluate(fix_members)
        full_res = future.evaluate(pool[:MAX_K]) if len(pool) <= MAX_K else None
        # Full market may exceed MAX_K. Evaluate it with a temporary evaluator limit-safe direct method.
        if full_res is None:
            old = globals()["MAX_K"]
            globals()["MAX_K"] = len(pool)
            try:
                full_res = future.evaluate(pool)
            finally:
                globals()["MAX_K"] = old

        for ri, (rule, members) in enumerate(chosen.items()):
            f = future.evaluate(members)
            fm = future.mechanism(members)
            hm = evals[126].mechanism(members)
            rnd_sets = random_same_k(pool, len(members), RANDOM_N, SEED + pi * 1000 + ri)
            rnd_ret = []
            rnd_log = []
            rnd_mech = []
            for rs in rnd_sets:
                rr = future.evaluate(rs)
                rnd_ret.append(rr.total_return)
                rnd_log.append(rr.log_growth)
                rnd_mech.append(future.mechanism(rs))
            rmd = pd.DataFrame(rnd_mech)
            row = {
                "decision_date": str(cal[d].date()),
                "future_end_date": str(cal[next_d - 1].date()),
                "partial_final_period": bool(pi == len(dec) - 1 and next_d < d + 126),
                "rule": rule,
                "k_noncash": len(members),
                "members": ",".join(members),
                "past63_log": evals[63].evaluate(members).log_growth,
                "past126_log": evals[126].evaluate(members).log_growth,
                "past252_log": evals[252].evaluate(members).log_growth,
                "past_coverage_efficiency": hm["coverage_efficiency"],
                "past_productive_switch_share": hm["productive_switch_share"],
                "past_switch_gain_mean": hm["switch_counterfactual_gain_mean"],
                "future_log_growth": f.log_growth,
                "future_total_return": f.total_return,
                "future_max_drawdown": f.max_drawdown,
                "future_switch_events": f.switch_events,
                "future_coverage_efficiency": fm["coverage_efficiency"],
                "future_productive_switch_share": fm["productive_switch_share"],
                "future_switch_gain_mean": fm["switch_counterfactual_gain_mean"],
                "random_n": len(rnd_sets),
                "random_return_mean": float(np.mean(rnd_ret)) if rnd_ret else np.nan,
                "random_return_median": float(np.median(rnd_ret)) if rnd_ret else np.nan,
                "random_log_median": float(np.median(rnd_log)) if rnd_log else np.nan,
                "random_future_coverage_efficiency_median": float(rmd["coverage_efficiency"].median()) if not rmd.empty else np.nan,
                "random_future_productive_switch_share_median": float(rmd["productive_switch_share"].median()) if not rmd.empty else np.nan,
                "random_future_switch_gain_mean_median": float(rmd["switch_counterfactual_gain_mean"].median()) if not rmd.empty else np.nan,
                "fix15_future_log": fix_res.log_growth,
                "fix15_future_return": fix_res.total_return,
                "full_market_future_log": full_res.log_growth,
                "full_market_future_return": full_res.total_return,
                "point_in_time_pool_n": len(pool),
                "library_n_63": len(libs[63]),
                "library_n_126": len(libs[126]),
                "library_n_252": len(libs[252]),
            }
            rows.append(row)
            selections.append({"decision_date": row["decision_date"], "rule": rule, "members": row["members"], "k_noncash": len(members)})

    res = pd.DataFrame(rows)
    res.to_csv(out / "stage5_period_results.csv", index=False)
    pd.DataFrame(selections).to_csv(out / "stage5_selected_universes.csv", index=False)

    summary = {"study": "OURE Stage5 Historical Universe Transfer", "status": "completed", "rules": {}}
    for rule, g in res.groupby("rule"):
        g = g.sort_values("decision_date")
        linked_log = float(g["future_log_growth"].sum())
        random_linked_log = float(g["random_log_median"].sum())
        completed = g[~g["partial_final_period"]]
        hit = float((completed["future_total_return"] > completed["random_return_median"]).mean()) if len(completed) else np.nan
        summary["rules"][rule] = {
            "periods": int(len(g)),
            "completed_periods": int(len(completed)),
            "linked_log_growth": linked_log,
            "linked_total_return": float(np.exp(linked_log) - 1.0),
            "random_median_linked_log": random_linked_log,
            "random_median_linked_total_return": float(np.exp(random_linked_log) - 1.0),
            "same_k_random_median_hit_rate_completed": hit,
            "median_k_noncash": float(g["k_noncash"].median()),
            "median_future_coverage_delta_vs_random": float((g["future_coverage_efficiency"] - g["random_future_coverage_efficiency_median"]).median()),
            "median_future_productive_switch_delta_vs_random": float((g["future_productive_switch_share"] - g["random_future_productive_switch_share_median"]).median()),
            "median_future_switch_gain_delta_vs_random": float((g["future_switch_gain_mean"] - g["random_future_switch_gain_mean_median"]).median()),
        }
    # Common benchmark linked returns (same for all rules period-by-period).
    one = res[res["rule"] == sorted(res["rule"].unique())[0]].sort_values("decision_date")
    summary["benchmarks"] = {
        "fix15_linked_total_return": float(np.exp(one["fix15_future_log"].sum()) - 1.0),
        "full_market_linked_total_return": float(np.exp(one["full_market_future_log"].sum()) - 1.0),
    }
    (out / "oure_stage5_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
