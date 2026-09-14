#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
from optimal_universe_reverse_engineering.oure_stage6c_fullmarket_2022_2024_k_frontier import Eval, keyify

CASH = "511220"
K = 30
ELITE_N = 25
CONTEXT_N = 16
GREEDY_SEEDS = 8
SWAP_SHORTLIST = 100
REFINE_ROUNDS = 2
STOCH_STARTS = 6
STOCH_STEPS = 2500
PRE_WINDOW = 126
MIN_CHALLENGE_DAYS = 3
SEED = 20260914
TOL = 1e-12

ERAS = {
    "2022_2024": (pd.Timestamp("2022-01-01"), pd.Timestamp("2024-12-31")),
    "2025_2026": (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-09-09")),
}

CORE_PROXIES = [
    "prior_new_coverage_share",
    "prior_replacement_gain_mean",
    "prior_productive_challenge_share",
]
ALL_PROXIES = CORE_PROXIES + ["prior_challenge_share", "mechanism_score"]


def point_in_time_pool(close: pd.DataFrame, score: pd.DataFrame, meta: pd.DataFrame,
                       cal: pd.DatetimeIndex, start_i: int) -> list[str]:
    guarded = set(meta.loc[
        meta["has_daily_bars"].fillna(False).astype(bool)
        & (~meta["leveraged_flag"].fillna(False).astype(bool))
        & (~meta["inverse_flag"].fillna(False).astype(bool)),
        "symbol"
    ].astype(str))
    pre = cal[max(0, start_i - 252):start_i]
    out = []
    for s in sorted(set(score.columns.astype(str)) & guarded):
        if s == CASH or s not in close.columns:
            continue
        x = close.loc[pre, s].to_numpy(float)
        if len(x) >= 240 and np.isfinite(x).sum() >= 240 and np.isfinite(x[-1]):
            out.append(s)
    return out


def greedy_to_k(ev: Eval, seed: str, candidates: list[str], found: set[tuple[str, ...]]) -> tuple[str, ...]:
    cur = {seed}
    while len(cur) < K:
        bestv = -np.inf
        besty = None
        for y in candidates:
            if y in cur:
                continue
            v = ev.quick_add_log(cur, y)
            if v > bestv + TOL or (abs(v - bestv) <= TOL and (besty is None or y < besty)):
                bestv, besty = v, y
        if besty is None:
            break
        cur.add(besty)
    k = keyify(cur)
    if len(k) == K:
        found.add(k)
    return k


def refine_fixed_k(ev: Eval, start: tuple[str, ...], swap_pool: list[str], found: set[tuple[str, ...]]) -> tuple[str, ...]:
    cur = set(start)
    for _ in range(REFINE_ROUNDS):
        base = ev.evaluate(cur)["log_growth"]
        bestv = base
        best = None
        for x in sorted(cur):
            minus = cur - {x}
            for y in swap_pool:
                if y in cur:
                    continue
                cand = keyify(minus | {y})
                v = ev.evaluate(cand)["log_growth"]
                if v > bestv + TOL:
                    bestv = v
                    best = set(cand)
        if best is None:
            break
        cur = best
        found.add(keyify(cur))
    return keyify(cur)


def stochastic_fixed_k(ev: Eval, start: tuple[str, ...], candidates: list[str], rng: np.random.Generator,
                       found: set[tuple[str, ...]]) -> tuple[str, ...]:
    cur = set(start)
    curv = ev.evaluate(cur)["log_growth"]
    best = set(cur)
    bestv = curv
    for st in range(STOCH_STEPS):
        x = str(rng.choice(sorted(cur)))
        outside = [z for z in candidates if z not in cur]
        y = str(rng.choice(outside))
        cand = keyify((cur - {x}) | {y})
        v = ev.evaluate(cand)["log_growth"]
        temp = 0.06 * max(0.02, 1.0 - st / max(1, STOCH_STEPS))
        if v >= curv or rng.random() < math.exp(min(0.0, (v - curv) / temp)):
            cur = set(cand)
            curv = v
            found.add(cand)
        if v > bestv + TOL:
            best = set(cand)
            bestv = v
    found.add(keyify(best))
    return keyify(best)


def search_elites(ev: Eval, candidates: list[str], seed: int) -> tuple[list[tuple[str, ...]], pd.DataFrame]:
    singles = []
    for s in candidates:
        r = ev.evaluate({s})
        singles.append((s, r["log_growth"]))
    singles = sorted(singles, key=lambda z: (-z[1], z[0]))
    single_df = pd.DataFrame(singles, columns=["symbol", "forward_singleton_log_growth"])
    ordered = [s for s, _ in singles]
    found: set[tuple[str, ...]] = set()
    starts = []
    for s in ordered[:min(GREEDY_SEEDS, len(ordered))]:
        z = greedy_to_k(ev, s, candidates, found)
        if len(z) == K:
            z = refine_fixed_k(ev, z, ordered[:min(SWAP_SHORTLIST, len(ordered))], found)
            starts.append(z)
    if not starts:
        raise RuntimeError("no K30 greedy start")
    incumbent = max(starts, key=lambda z: ev.evaluate(z)["log_growth"])
    rng = np.random.default_rng(seed)
    stoch_starts = [incumbent]
    for _ in range(STOCH_STARTS - 1):
        stoch_starts.append(keyify(rng.choice(candidates, size=K, replace=False).tolist()))
    for z in stoch_starts:
        found.add(z)
        zz = stochastic_fixed_k(ev, z, candidates, rng, found)
        refine_fixed_k(ev, zz, ordered[:min(SWAP_SHORTLIST, len(ordered))], found)
    ranked = sorted(found, key=lambda z: (-ev.evaluate(z)["log_growth"], z))
    return ranked[:min(ELITE_N, len(ranked))], single_df


def add_decomp(ev: Eval, context: tuple[str, ...], y: str) -> dict[str, float]:
    best, target = ev.target_state(context)
    j = ev.idx[y]
    v = ev.score[:, j]
    choose = np.isfinite(v) & (v > best)
    cov = choose & (target < 0)
    chall = choose & (target >= 0)
    n_ch = int(chall.sum())
    if n_ch:
        rows = np.flatnonzero(chall)
        old = target[chall]
        delta = ev.gross[rows, j] - ev.gross[rows, old]
        repl = float(np.mean(delta)) if n_ch >= MIN_CHALLENGE_DAYS else 0.0
        prod = float(np.mean(delta > 0)) if n_ch >= MIN_CHALLENGE_DAYS else 0.0
    else:
        repl = 0.0
        prod = 0.0
    return {
        "new_coverage_share": float(cov.mean()) if len(cov) else 0.0,
        "challenge_share": float(chall.mean()) if len(chall) else 0.0,
        "challenge_days": n_ch,
        "replacement_gain_mean": repl,
        "productive_challenge_share": prod,
        "selected_share_if_added": float(choose.mean()) if len(choose) else 0.0,
    }


def deterministic_contexts(elites: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    contexts = []
    seen = set()
    for i, u in enumerate(elites[:min(CONTEXT_N, len(elites))]):
        ss = sorted(u)
        drop = ss[(7 * i + 3) % len(ss)]
        c = keyify(set(u) - {drop})
        if c not in seen:
            contexts.append(c)
            seen.add(c)
    return contexts


def percentile_score(g: pd.DataFrame) -> pd.Series:
    def pct(s: pd.Series, higher=True) -> pd.Series:
        r = s.rank(pct=True, method="average", ascending=True)
        return r if higher else 1.0 - r + 1.0 / max(1, len(s))
    return pd.concat([
        pct(g["prior_new_coverage_share"], True),
        pct(g["prior_replacement_gain_mean"], True),
        pct(g["prior_productive_challenge_share"], True),
        pct(g["prior_challenge_share"], False),
    ], axis=1).mean(axis=1)


def context_associations(pair_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = pair_df.copy()
    d["mechanism_score"] = np.nan
    for (_, cid), idx in d.groupby(["era", "context_id"]).groups.items():
        d.loc[idx, "mechanism_score"] = percentile_score(d.loc[idx])
    rows = []
    for (era, cid), g in d.groupby(["era", "context_id"]):
        for f in ALL_PROXIES:
            q = g[[f, "future_delta_log"]].dropna()
            corr = float(q[f].corr(q["future_delta_log"], method="spearman")) if len(q) >= 20 and q[f].nunique() > 1 else np.nan
            rows.append({"era": era, "context_id": int(cid), "feature": f, "n": int(len(q)), "spearman": corr})
    corr_df = pd.DataFrame(rows)
    summ = corr_df.groupby(["era", "feature"], as_index=False).agg(
        contexts=("spearman", "count"),
        median_context_spearman=("spearman", "median"),
        mean_context_spearman=("spearman", "mean"),
        positive_context_share=("spearman", lambda x: float(np.mean(np.asarray(x.dropna()) > 0)) if len(x.dropna()) else np.nan),
    )
    return d, summ


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage6d-output")
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
    meta = pd.read_sql_query(text("select symbol,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    elite_rows = []
    member_rows = []
    pair_rows = []
    era_summary = {}
    champions = {}

    for ei, (era, (start, end)) in enumerate(ERAS.items()):
        start_i = int(cal.searchsorted(start, side="left"))
        end_i = int(cal.searchsorted(end, side="right"))
        candidates = point_in_time_pool(close, score, meta, cal, start_i)
        if len(candidates) < K + 10:
            raise RuntimeError(f"too few candidates for {era}: {len(candidates)}")

        fpos = np.arange(start_i, min(end_i, len(cal) - 2), dtype=int)
        fdates = cal[fpos]
        if len(fdates) < 100:
            raise RuntimeError(f"too few forward dates for {era}")
        # Use only past signals whose realized gross return is fully before the forward boundary.
        p_end = start_i - 2
        p_start = p_end - PRE_WINDOW
        if p_start < 0:
            raise RuntimeError(f"insufficient prehistory for {era}")
        pdates = cal[p_start:p_end]
        if len(pdates) != PRE_WINDOW:
            raise RuntimeError(f"bad prewindow for {era}: {len(pdates)}")

        fwd = Eval(score, gross, fdates, candidates)
        pre = Eval(score, gross, pdates, candidates)
        elites, single_df = search_elites(fwd, candidates, SEED + ei * 1000)
        single_df.insert(0, "era", era)
        single_df.to_csv(out / f"singleton_{era}.csv", index=False)
        if not elites:
            raise RuntimeError(f"no elites for {era}")
        champions[era] = elites[0]
        for rank, u in enumerate(elites, 1):
            rr = fwd.diagnostics(u)
            elite_rows.append({
                "era": era, "rank": rank, "members": ",".join(u),
                "log_growth": rr["log_growth"], "total_return": rr["total_return"],
                "switch_rate": rr.get("switch_rate"), "mean_top1_tenure": rr.get("mean_top1_tenure"),
                "productive_switch_share": rr.get("productive_switch_share"),
                "switch_counterfactual_gain_mean": rr.get("switch_counterfactual_gain_mean"),
            })
        freq = {}
        for u in elites:
            for s in u:
                freq[s] = freq.get(s, 0) + 1
        for s in candidates:
            containing = [u for u in elites if s in u]
            drops = []
            for u in containing:
                drops.append(fwd.evaluate(u)["log_growth"] - fwd.evaluate(set(u) - {s})["log_growth"])
            member_rows.append({
                "era": era, "symbol": s,
                "elite_inclusion_rate": freq.get(s, 0) / len(elites),
                "elite_count": freq.get(s, 0),
                "mean_elite_drop_delta_log": float(np.mean(drops)) if drops else np.nan,
                "median_elite_drop_delta_log": float(np.median(drops)) if drops else np.nan,
            })

        contexts = deterministic_contexts(elites)
        for cid, context in enumerate(contexts):
            base_log = fwd.evaluate(context)["log_growth"]
            for y in candidates:
                if y in context:
                    continue
                prior = add_decomp(pre, context, y)
                fut = add_decomp(fwd, context, y)
                delta_log = fwd.quick_add_log(context, y) - base_log
                pair_rows.append({
                    "era": era, "context_id": cid, "context_members": ",".join(context), "candidate": y,
                    "future_delta_log": float(delta_log),
                    "prior_new_coverage_share": prior["new_coverage_share"],
                    "prior_challenge_share": prior["challenge_share"],
                    "prior_challenge_days": prior["challenge_days"],
                    "prior_replacement_gain_mean": prior["replacement_gain_mean"],
                    "prior_productive_challenge_share": prior["productive_challenge_share"],
                    "future_new_coverage_share": fut["new_coverage_share"],
                    "future_challenge_share": fut["challenge_share"],
                    "future_replacement_gain_mean": fut["replacement_gain_mean"],
                    "future_productive_challenge_share": fut["productive_challenge_share"],
                })

        era_summary[era] = {
            "candidate_count": len(candidates),
            "forward_start": str(fdates.min().date()),
            "forward_end": str(fdates.max().date()),
            "pre_start": str(pdates.min().date()),
            "pre_end": str(pdates.max().date()),
            "elite_count": len(elites),
            "context_count": len(contexts),
            "champion_total_return": float(fwd.evaluate(elites[0])["total_return"]),
            "champion_members": list(elites[0]),
        }

    elite_df = pd.DataFrame(elite_rows)
    member_df = pd.DataFrame(member_rows)
    pair_df = pd.DataFrame(pair_rows)
    pair_scored, assoc = context_associations(pair_df)

    # Context-averaged candidate view.
    cand = pair_scored.groupby(["era", "candidate"], as_index=False).agg(
        future_delta_log_mean=("future_delta_log", "mean"),
        future_delta_log_median=("future_delta_log", "median"),
        prior_new_coverage_share=("prior_new_coverage_share", "mean"),
        prior_challenge_share=("prior_challenge_share", "mean"),
        prior_replacement_gain_mean=("prior_replacement_gain_mean", "mean"),
        prior_productive_challenge_share=("prior_productive_challenge_share", "mean"),
        mechanism_score=("mechanism_score", "mean"),
    ).rename(columns={"candidate": "symbol"})
    cand = cand.merge(member_df, on=["era", "symbol"], how="left", validate="one_to_one")

    cand_assoc_rows = []
    for era, g in cand.groupby("era"):
        for f in ALL_PROXIES:
            q = g[[f, "future_delta_log_mean"]].dropna()
            c = float(q[f].corr(q["future_delta_log_mean"], method="spearman")) if len(q) >= 20 and q[f].nunique() > 1 else np.nan
            cand_assoc_rows.append({"era": era, "feature": f, "candidate_level_spearman": c, "n": len(q)})
    cand_assoc = pd.DataFrame(cand_assoc_rows)
    assoc = assoc.merge(cand_assoc, on=["era", "feature"], how="left")

    # Frozen gate.
    gate_core = {}
    gate_score = {}
    for era in ERAS:
        a = assoc[assoc["era"] == era].set_index("feature")
        pos = sum(float(a.loc[f, "median_context_spearman"]) > 0 for f in CORE_PROXIES if f in a.index)
        gate_core[era] = int(pos)
        gate_score[era] = bool("mechanism_score" in a.index and float(a.loc["mechanism_score", "median_context_spearman"]) > 0)
    gate_pass = all(gate_core.get(e, 0) >= 2 and gate_score.get(e, False) for e in ERAS)

    # Raw challenge penalty comparison.
    ac = assoc[assoc["feature"] == "prior_challenge_share"].set_index("era")
    challenge_penalty_stronger_early = bool(
        all(e in ac.index for e in ERAS)
        and float(ac.loc["2022_2024", "median_context_spearman"]) < float(ac.loc["2025_2026", "median_context_spearman"])
    )

    champ_a = set(champions["2022_2024"])
    champ_b = set(champions["2025_2026"])
    overlap = len(champ_a & champ_b) / len(champ_a | champ_b)

    elite_df.to_csv(out / "elite_k30_by_era.csv", index=False)
    member_df.to_csv(out / "elite_member_frequency_and_drop_value.csv", index=False)
    pair_scored.to_csv(out / "candidate_context_pairs.csv", index=False)
    cand.to_csv(out / "candidate_context_aggregate.csv", index=False)
    assoc.to_csv(out / "proxy_association_by_era.csv", index=False)

    summary = {
        "study": "OURE Stage6D fixed-K30 member marginal-value identification",
        "status": "completed",
        "eras": era_summary,
        "champion_member_jaccard_between_eras": float(overlap),
        "core_positive_proxy_count_by_era": gate_core,
        "mechanism_score_positive_by_era": gate_score,
        "challenge_penalty_stronger_2022_2024_than_2025_2026": challenge_penalty_stronger_early,
        "preregistered_gate_pass": bool(gate_pass),
        "decision": "lowdim_member_marginal_identifiable" if gate_pass else "member_marginal_value_not_lowdim_identifiable",
        "warning": "K30 elites are heuristic hindsight searched sets, not exact/global optima; this stage is explanatory and does not authorize a production selector.",
    }
    (out / "stage6d_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
