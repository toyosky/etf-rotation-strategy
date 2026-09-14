#!/usr/bin/env python3
"""OURE Stage3: heuristic static-Universe search after broad exposure exclusion.

Hindsight/mechanism study only. The downstream OLS engine is frozen. Stage2
architecture features are NOT used by the search objective.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from walk_forward_candidate_pool import SIDE_COST
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

CASH = "511220"
START = pd.Timestamp("2021-01-01")
ERA_SPLIT = pd.Timestamp("2025-01-01")
MAX_NONCASH = 15
TOL = 1e-12
SEED = 20260914
BANNED_SYMBOLS = {"159915", "159985", "161226", "501018", "513100", "513920"}


def s(x) -> str:
    return "" if pd.isna(x) else str(x).upper()


def exclusion_reason(r: pd.Series) -> str | None:
    sym = str(r["symbol"])
    if sym in BANNED_SYMBOLS:
        return "EXPLICIT_STAGE1_K7_RISK_SYMBOL"
    ex1, ex2, rb, sty, ac, reg = [s(r.get(k)) for k in (
        "exposure_level1", "exposure_level2", "risk_bucket", "style_sector", "asset_class", "region_primary"
    )]
    blob = "|".join([ex1, ex2, rb, sty])
    if ex2.startswith("CHINA_GROWTH") or rb.startswith("CHINA_GROWTH"):
        return "CHINA_GROWTH_BOARD"
    if "AGRICULTURE" in blob:
        return "AGRICULTURE"
    if "PRECIOUS_METALS" in blob:
        return "PRECIOUS_METALS"
    if ac == "COMMODITY" and "ENERGY" in blob:
        return "ENERGY_COMMODITY"
    if reg == "US" and (
        ex2 in {"US_LARGE_GROWTH", "US_TECH"}
        or rb.startswith("US_NASDAQ")
        or rb.startswith("US_TECH")
        or "GROWTH_TECH" in sty
        or sty == "TECHNOLOGY"
    ):
        return "US_NASDAQ_GROWTH_TECH"
    if "SOE" in blob:
        return "SOE"
    return None


def run_lengths(pos: np.ndarray) -> list[int]:
    out: list[int] = []
    cur = -1
    n = 0
    for v in pos.astype(int):
        if v < 0:
            if cur >= 0:
                out.append(n)
            cur, n = -1, 0
        elif v == cur:
            n += 1
        else:
            if cur >= 0:
                out.append(n)
            cur, n = v, 1
    if cur >= 0:
        out.append(n)
    return out


class Evaluator:
    def __init__(self, score: pd.DataFrame, gross: pd.DataFrame, cal: pd.Index, candidates: list[str]):
        start_i = int(cal.searchsorted(START, side="left"))
        spos = np.arange(start_i, len(cal) - 2, dtype=int)
        self.signal_dates = pd.DatetimeIndex(cal[spos])
        self.exec_dates = pd.DatetimeIndex(cal[spos + 1])
        self.candidates = list(candidates)
        self.index = {x: i for i, x in enumerate(self.candidates)}
        self.cash_score = score.loc[self.signal_dates, CASH].to_numpy(float)
        self.score = score.loc[self.signal_dates, self.candidates].to_numpy(float)
        self.gross = gross.loc[self.signal_dates, self.candidates].to_numpy(float)
        self.gross = np.where(np.isfinite(self.gross), self.gross, 0.0)
        self.era1 = np.asarray(self.exec_dates < ERA_SPLIT)
        self.era2 = np.asarray(self.exec_dates >= ERA_SPLIT)
        self.cache: dict[tuple[str, ...], dict] = {}

    def evaluate(self, members) -> dict:
        key = tuple(sorted(set(map(str, members))))
        if key in self.cache:
            return self.cache[key]
        if len(key) > MAX_NONCASH:
            raise ValueError("subset above MAX_NONCASH")
        t = len(self.signal_dates)
        best_score = np.where(np.isfinite(self.cash_score), self.cash_score, -np.inf).copy()
        target = np.full(t, -1, dtype=np.int32)
        # Cash has precedence on exact ties, then lexicographically sorted risk symbols.
        for sym in key:
            j = self.index[sym]
            v = self.score[:, j]
            choose = np.isfinite(v) & (v > best_score)
            target[choose] = j
            best_score[choose] = v[choose]
        active = target >= 0
        rows = np.arange(t)
        g = np.zeros(t, dtype=float)
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
        eq = np.exp(np.cumsum(lg))
        dd = eq / np.maximum.accumulate(eq) - 1.0 if len(eq) else np.array([0.0])
        lens = run_lengths(target)
        log_full = float(lg.sum())
        rec = {
            "members": key,
            "k_noncash": len(key),
            "k_including_cash": len(key) + 1,
            "log_growth": log_full,
            "total_return": float(np.exp(log_full) - 1.0),
            "log_growth_2021_2024": float(lg[self.era1].sum()),
            "return_2021_2024": float(np.exp(lg[self.era1].sum()) - 1.0),
            "log_growth_2025_2026": float(lg[self.era2].sum()),
            "return_2025_2026": float(np.exp(lg[self.era2].sum()) - 1.0),
            "max_drawdown": float(dd.min()),
            "switch_events": int(np.count_nonzero(sides)),
            "turnover_sides": int(sides.sum()),
            "invested_ratio": float(active.mean()),
            "mean_top1_tenure": float(np.mean(lens)) if lens else np.nan,
            "median_top1_tenure": float(np.median(lens)) if lens else np.nan,
        }
        self.cache[key] = rec
        return rec


def best_of(e: Evaluator, sets: list[tuple[str, ...]]) -> dict:
    return max((e.evaluate(x) for x in sets), key=lambda r: r["log_growth"])


def greedy_from_seed(e: Evaluator, seed: str, all_syms: list[str]) -> tuple[str, ...]:
    cur = {seed}
    while len(cur) < MAX_NONCASH:
        base = e.evaluate(cur)["log_growth"]
        best_sym = None
        best_val = base
        for x in all_syms:
            if x in cur:
                continue
            v = e.evaluate(cur | {x})["log_growth"]
            if v > best_val + TOL:
                best_val, best_sym = v, x
        if best_sym is None:
            break
        cur.add(best_sym)
    return tuple(sorted(cur))


def local_refine(e: Evaluator, start: tuple[str, ...], all_syms: list[str], swap_pool: list[str]) -> tuple[str, ...]:
    cur = set(start)
    for _ in range(12):
        base = e.evaluate(cur)["log_growth"]
        best_set = set(cur)
        best_val = base
        if len(cur) > 1:
            for x in list(cur):
                c = cur - {x}
                v = e.evaluate(c)["log_growth"]
                if v > best_val + TOL:
                    best_val, best_set = v, set(c)
        if len(cur) < MAX_NONCASH:
            for x in all_syms:
                if x in cur:
                    continue
                c = cur | {x}
                v = e.evaluate(c)["log_growth"]
                if v > best_val + TOL:
                    best_val, best_set = v, set(c)
        for x in list(cur):
            for y in swap_pool:
                if y in cur:
                    continue
                c = (cur - {x}) | {y}
                v = e.evaluate(c)["log_growth"]
                if v > best_val + TOL:
                    best_val, best_set = v, set(c)
        if best_set == cur:
            break
        cur = best_set
    return tuple(sorted(cur))


def stochastic_search(e: Evaluator, elites: list[tuple[str, ...]], all_syms: list[str], n_steps: int, seed: int) -> list[tuple[str, ...]]:
    rng = random.Random(seed)
    pool = [set(x) for x in elites[:30]]
    if not pool:
        return []
    found: list[tuple[str, ...]] = []
    temp0 = 0.08
    for step in range(n_steps):
        parent = set(rng.choice(pool))
        cand = set(parent)
        u = rng.random()
        if (u < .30 and len(cand) < MAX_NONCASH) or len(cand) == 1:
            cand.add(rng.choice(all_syms))
        elif u < .55 and len(cand) > 1:
            cand.remove(rng.choice(sorted(cand)))
        else:
            if cand:
                cand.remove(rng.choice(sorted(cand)))
            cand.add(rng.choice(all_syms))
        if not cand or len(cand) > MAX_NONCASH:
            continue
        pv = e.evaluate(parent)["log_growth"]
        cv = e.evaluate(cand)["log_growth"]
        temp = temp0 * max(0.02, 1.0 - step / max(1, n_steps))
        if cv >= pv or rng.random() < math.exp(min(0.0, (cv - pv) / temp)):
            pool.append(set(cand))
            pool = sorted(pool, key=lambda z: e.evaluate(z)["log_growth"], reverse=True)[:60]
            found.append(tuple(sorted(cand)))
    return found


def exact_local_residual(e: Evaluator, champ: tuple[str, ...], all_syms: list[str]) -> dict:
    cur = set(champ)
    base = e.evaluate(cur)["log_growth"]
    best_add = (-np.inf, None)
    if len(cur) < MAX_NONCASH:
        for y in all_syms:
            if y in cur:
                continue
            d = e.evaluate(cur | {y})["log_growth"] - base
            if d > best_add[0]: best_add = (d, y)
    best_drop = (-np.inf, None)
    if len(cur) > 1:
        for x in cur:
            d = e.evaluate(cur - {x})["log_growth"] - base
            if d > best_drop[0]: best_drop = (d, x)
    best_swap = (-np.inf, None, None)
    for x in cur:
        for y in all_syms:
            if y in cur:
                continue
            d = e.evaluate((cur - {x}) | {y})["log_growth"] - base
            if d > best_swap[0]: best_swap = (d, x, y)
    return {
        "best_add_delta_log": None if best_add[1] is None else float(best_add[0]),
        "best_add_symbol": best_add[1],
        "best_drop_delta_log": None if best_drop[1] is None else float(best_drop[0]),
        "best_drop_symbol": best_drop[1],
        "best_swap_delta_log": None if best_swap[1] is None else float(best_swap[0]),
        "best_swap_out": best_swap[1],
        "best_swap_in": best_swap[2],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage3-output")
    ap.add_argument("--greedy-seeds", type=int, default=14)
    ap.add_argument("--swap-shortlist", type=int, default=120)
    ap.add_argument("--stochastic-steps", type=int, default=12000)
    ap.add_argument("--random-per-k", type=int, default=500)
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng); bars["symbol"] = bars["symbol"].astype(str)
    features = build_features(bars); features["symbol"] = features["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, features)
    if CASH not in score.columns:
        raise RuntimeError("cash signal missing")

    q = text("""
        select symbol,name,asset_class,region_primary,exposure_level1,exposure_level2,
               underlying_key,risk_bucket,style_sector,needs_review,has_daily_bars,
               leveraged_flag,inverse_flag
          from public.instrument_metadata_current
    """)
    meta = pd.read_sql_query(q, eng)
    meta["symbol"] = meta["symbol"].astype(str)
    score_syms = set(map(str, score.columns))
    rows = []
    allowed = []
    for _, r in meta.iterrows():
        sym = str(r["symbol"])
        reason = exclusion_reason(r)
        if sym == CASH:
            status = "cash_proxy"
        elif sym not in score_syms or not bool(r.get("has_daily_bars", False)):
            status = "no_score_data"
        elif bool(r.get("needs_review", True)) or pd.isna(r.get("risk_bucket")):
            status = "unclassified_guard"
        elif bool(r.get("leveraged_flag", False)) or bool(r.get("inverse_flag", False)):
            status = "leveraged_inverse_guard"
        elif reason is not None:
            status = reason
        else:
            status = "allowed"
            allowed.append(sym)
        d = r.to_dict(); d["search_status"] = status; rows.append(d)
    audit = pd.DataFrame(rows).sort_values(["search_status","symbol"])
    audit.to_csv(out / "candidate_exclusion_audit.csv", index=False)
    allowed = sorted(set(allowed))
    if len(allowed) < 20:
        raise RuntimeError(f"too few allowed candidates: {len(allowed)}")

    ev = Evaluator(score, gross, cal, allowed)
    singleton_rows = []
    for sym in allowed:
        rec = dict(ev.evaluate({sym}))
        rec["symbol"] = sym
        singleton_rows.append(rec)
    single = pd.DataFrame(singleton_rows).sort_values("log_growth", ascending=False)
    single.to_csv(out / "singleton_values.csv", index=False)

    # Strong seeds plus category-diverse seeds, all selected before multi-member search.
    seeds = list(single.head(args.greedy_seeds)["symbol"].astype(str))
    meta_allowed = meta[meta["symbol"].isin(allowed)][["symbol","risk_bucket"]].copy()
    mm = meta_allowed.merge(single[["symbol","log_growth"]], on="symbol", how="left")
    diverse = (mm.sort_values("log_growth", ascending=False).groupby("risk_bucket", dropna=False).head(1)
               .sort_values("log_growth", ascending=False)["symbol"].astype(str).tolist())
    for x in diverse:
        if x not in seeds:
            seeds.append(x)
        if len(seeds) >= args.greedy_seeds * 2:
            break

    endpoints = []
    hit_counter = Counter()
    for seed in seeds:
        g = greedy_from_seed(ev, seed, allowed)
        endpoints.append(g); hit_counter[g] += 1

    # Shortlist only affects swap proposals; add tests still inspect the full allowed market.
    swap_pool = list(single.head(args.swap_shortlist)["symbol"].astype(str))
    for x in diverse:
        if x not in swap_pool:
            swap_pool.append(x)
    refined = []
    for x in sorted(set(endpoints), key=lambda z: ev.evaluate(z)["log_growth"], reverse=True)[:20]:
        y = local_refine(ev, x, allowed, swap_pool)
        refined.append(y); hit_counter[y] += 1

    elite0 = sorted(set(endpoints + refined), key=lambda z: ev.evaluate(z)["log_growth"], reverse=True)
    stoch = stochastic_search(ev, elite0, allowed, args.stochastic_steps, SEED)
    # Refine the best stochastic discoveries.
    stoch_top = sorted(set(stoch), key=lambda z: ev.evaluate(z)["log_growth"], reverse=True)[:20]
    for x in stoch_top:
        y = local_refine(ev, x, allowed, swap_pool)
        refined.append(y); hit_counter[y] += 1

    searched_sets = set(endpoints + refined + stoch)
    elites = sorted(searched_sets, key=lambda z: ev.evaluate(z)["log_growth"], reverse=True)[:1000]
    elite_rows = []
    risk_map = dict(zip(meta_allowed["symbol"], meta_allowed["risk_bucket"]))
    for rank, key in enumerate(elites, 1):
        r = dict(ev.evaluate(key))
        r["rank"] = rank
        r["members"] = ",".join([CASH, *key])
        r["risk_buckets"] = ",".join(str(risk_map.get(x,"")) for x in key)
        r["rediscovery_count"] = int(hit_counter.get(key, 0))
        elite_rows.append(r)
    elite_df = pd.DataFrame(elite_rows)
    elite_df.to_csv(out / "elite_universes.csv", index=False)
    champion = elites[0]
    champ = dict(ev.evaluate(champion))
    champ["members"] = [CASH, *champion]
    champ["risk_buckets"] = [risk_map.get(x) for x in champion]
    champ["rediscovery_count"] = int(hit_counter.get(champion, 0))
    residual = exact_local_residual(ev, champion, allowed)

    # Same-K random controls from the allowed market.
    rng = random.Random(SEED + 17)
    ks = sorted(set(int(x) for x in elite_df.head(100)["k_noncash"].unique()))
    random_rows = []
    for k in ks:
        seen = set()
        while len(seen) < args.random_per_k:
            key = tuple(sorted(rng.sample(allowed, k)))
            if key in seen: continue
            seen.add(key)
            rr = dict(ev.evaluate(key))
            rr["members"] = ",".join([CASH, *key])
            random_rows.append(rr)
    random_df = pd.DataFrame(random_rows)
    random_df.to_csv(out / "same_k_random_controls.csv", index=False)

    rand_champ_k = random_df[random_df["k_noncash"] == champ["k_noncash"]]["log_growth"]
    summary = {
        "study": "OURE Stage3 exposure-disjoint static Universe search",
        "status": "completed",
        "hindsight": True,
        "allowed_candidates": len(allowed),
        "candidate_status_counts": audit["search_status"].value_counts().to_dict(),
        "evaluated_unique_sets": len(ev.cache),
        "search_endpoints": len(searched_sets),
        "champion": champ,
        "champion_exact_1move_residual": residual,
        "champion_same_k_random": {
            "n": int(len(rand_champ_k)),
            "mean_log_growth": float(rand_champ_k.mean()) if len(rand_champ_k) else None,
            "p90_log_growth": float(rand_champ_k.quantile(.90)) if len(rand_champ_k) else None,
            "p99_log_growth": float(rand_champ_k.quantile(.99)) if len(rand_champ_k) else None,
            "champion_percentile": float((rand_champ_k <= champ["log_growth"]).mean()) if len(rand_champ_k) else None,
        },
        "search_config": {
            "max_noncash": MAX_NONCASH,
            "greedy_seed_count": len(seeds),
            "swap_shortlist": len(swap_pool),
            "stochastic_steps": args.stochastic_steps,
            "random_per_k": args.random_per_k,
            "seed": SEED,
        },
        "next_stage": "Three-group architecture comparison: Fix15-internal high-value vs exposure-disjoint elite vs same-K controls.",
    }
    (out / "oure_stage3_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
