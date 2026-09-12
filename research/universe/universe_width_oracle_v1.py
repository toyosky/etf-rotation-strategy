#!/usr/bin/env python3
"""Universe Width Oracle V1.

Hindsight mechanism study only.

Stages
------
A. Greedy deletion path from Fixed15 to width 5 (cash signal always retained).
B. Random/exhaustive subset distributions by width, with frozen RNG seed.
C. At widths 13/11/9, test same-width external swaps and add-one variants
   using the already-frozen structural candidate set from Universe Oracle V1.

The purpose is to separate:
- selecting the right members;
- pool-width / cross-sectional competition effects;
- incremental value of replacements once the pool is already smaller.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe.oracle_replacement_v1 import (
    FIXED15, CASH_SIGNAL, CHANGE_DATE,
    load_metadata, load_first_dates, load_oracle_stats,
)
from universe.oracle_grid_v1 import candidate_sets, prepare_wides, evaluate

MIN_WIDTH = 5
MAX_WIDTH = 15
RANDOM_SAMPLE_N = 300
RANDOM_SEED = 20260912
REPLACEMENT_WIDTHS = (13, 11, 9)


def rank_one_pool(score: pd.DataFrame, pool: set[str]) -> tuple[pd.Series, pd.Series]:
    cols = [c for c in score.columns if c in pool]
    if not cols:
        return pd.Series(None, index=score.index, dtype=object), pd.Series(0, index=score.index, dtype=int)
    sub = score.loc[:, cols]
    counts = sub.notna().sum(axis=1).astype(int)
    ranked = pd.Series(None, index=score.index, dtype=object)
    mask = counts > 0
    if bool(mask.any()):
        ranked.loc[mask] = sub.loc[mask].idxmax(axis=1).astype(str)
    return ranked, counts


def make_runner(score: pd.DataFrame, oo: pd.DataFrame):
    pre_ranked, pre_counts = rank_one_pool(score, set(FIXED15))
    post_mask = score.index >= CHANGE_DATE
    cache: dict[tuple[str, ...], dict] = {}

    def run(pool: set[str]) -> dict:
        key = tuple(sorted(pool))
        if key in cache:
            return cache[key]
        ranked = pre_ranked.copy()
        counts = pre_counts.copy()
        post_ranked, post_counts = rank_one_pool(score.loc[post_mask], pool)
        ranked.loc[post_mask] = post_ranked
        counts.loc[post_mask] = post_counts
        m = evaluate(ranked, counts, oo)
        cache[key] = m
        return m

    return run, cache


def greedy_path(run) -> tuple[pd.DataFrame, dict[int, set[str]]]:
    current = set(FIXED15)
    rows: list[dict] = []
    pools: dict[int, set[str]] = {len(current): set(current)}
    base = run(current)
    rows.append({"width": len(current), "removed": None, "pool": ",".join(sorted(current)), **base})

    while len(current) > MIN_WIDTH:
        candidates = sorted(current - {CASH_SIGNAL})
        trials = []
        for sym in candidates:
            p = current - {sym}
            m = run(p)
            trials.append((float(m["total_return"]), sym, p, m))
        # Frozen criterion: maximize total return only; deterministic symbol tie-break.
        trials.sort(key=lambda x: (-x[0], x[1]))
        _, removed, chosen_pool, metric = trials[0]
        current = set(chosen_pool)
        pools[len(current)] = set(current)
        rows.append({"width": len(current), "removed": removed, "pool": ",".join(sorted(current)), **metric})
    return pd.DataFrame(rows), pools


def width_combinations(noncash: list[str], width: int, rng: random.Random) -> tuple[list[tuple[str, ...]], bool]:
    choose_n = width - 1  # cash is forced in
    combos = list(itertools.combinations(noncash, choose_n))
    exhaustive = len(combos) <= RANDOM_SAMPLE_N
    if exhaustive:
        return combos, True
    return rng.sample(combos, RANDOM_SAMPLE_N), False


def random_width_distribution(run, baseline_return: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    noncash = sorted(set(FIXED15) - {CASH_SIGNAL})
    rng = random.Random(RANDOM_SEED)
    detail_rows = []
    summary_rows = []

    for width in range(MAX_WIDTH, MIN_WIDTH - 1, -1):
        combos, exhaustive = width_combinations(noncash, width, rng)
        vals = []
        for combo in combos:
            pool = set(combo) | {CASH_SIGNAL}
            m = run(pool)
            row = {
                "width": width,
                "pool": ",".join(sorted(pool)),
                "exhaustive_width": exhaustive,
                **m,
            }
            detail_rows.append(row)
            vals.append(row)
        g = pd.DataFrame(vals)
        summary_rows.append({
            "width": width,
            "n": len(g),
            "exhaustive_width": exhaustive,
            "beat_fixed15_share": float((g["total_return"] > baseline_return).mean()),
            "return_p10": float(g["total_return"].quantile(0.10)),
            "return_median": float(g["total_return"].median()),
            "return_p90": float(g["total_return"].quantile(0.90)),
            "return_best": float(g["total_return"].max()),
            "return_worst": float(g["total_return"].min()),
            "mdd_median": float(g["max_drawdown"].median()),
            "tenure_median": float(g["mean_top1_tenure"].median()),
            "switches_median": float(g["switches"].median()),
            "candidate_mean_median": float(g["candidate_mean"].median()),
        })
    return pd.DataFrame(detail_rows), pd.DataFrame(summary_rows)


def replacement_tests(run, greedy_pools: dict[int, set[str]], external: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    summary = []
    for width in REPLACEMENT_WIDTHS:
        base_pool = set(greedy_pools[width])
        base_m = run(base_pool)
        base_ret = float(base_m["total_return"])

        for incumbent in sorted(base_pool - {CASH_SIGNAL}):
            for ext in external:
                if ext in base_pool:
                    continue
                pool = (base_pool - {incumbent}) | {ext}
                m = run(pool)
                rows.append({
                    "width": width,
                    "kind": "swap",
                    "incumbent_out": incumbent,
                    "external_in": ext,
                    "base_return": base_ret,
                    "return_delta_vs_drop_pool": float(m["total_return"] - base_ret),
                    **m,
                })

        for ext in external:
            if ext in base_pool:
                continue
            pool = base_pool | {ext}
            m = run(pool)
            rows.append({
                "width": width,
                "kind": "add_one",
                "incumbent_out": None,
                "external_in": ext,
                "base_return": base_ret,
                "return_delta_vs_drop_pool": float(m["total_return"] - base_ret),
                **m,
            })

    detail = pd.DataFrame(rows)
    for (width, kind), g in detail.groupby(["width", "kind"], sort=True):
        base_ret = float(g["base_return"].iloc[0])
        summary.append({
            "width": int(width),
            "kind": str(kind),
            "n": int(len(g)),
            "base_drop_only_return": base_ret,
            "improve_share": float((g["total_return"] > base_ret).mean()),
            "median_total_return": float(g["total_return"].median()),
            "best_total_return": float(g["total_return"].max()),
            "worst_total_return": float(g["total_return"].min()),
            "median_delta": float(g["return_delta_vs_drop_pool"].median()),
            "best_delta": float(g["return_delta_vs_drop_pool"].max()),
            "median_mdd": float(g["max_drawdown"].median()),
            "median_tenure": float(g["mean_top1_tenure"].median()),
            "median_switches": float(g["switches"].median()),
        })
    return detail, pd.DataFrame(summary)


def pct(x: float) -> str:
    return f"{x:.2%}"


def build_report(baseline: dict, greedy: pd.DataFrame, width_summary: pd.DataFrame,
                 replacement_summary: pd.DataFrame, external: list[str]) -> str:
    lines = [
        "# Universe Width Oracle V1 — Results",
        "",
        "> Hindsight mechanism diagnostic only. Greedy deletion is an Oracle upper bound; random width distributions are the primary evidence for a structural width effect.",
        "",
        f"- Fixed15 2025-26 return: **{pct(float(baseline['total_return']))}**",
        f"- Fixed15 MDD: **{pct(float(baseline['max_drawdown']))}**",
        f"- External replacement candidates frozen from prior grid: `{len(external)}`",
        f"- Random seed: `{RANDOM_SEED}`; max subsets/width: `{RANDOM_SAMPLE_N}`",
        "",
        "## A. Greedy deletion path",
        "",
        "| Width | Removed at step | Return | MDD | Switches | Mean tenure | Candidate mean |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in greedy.sort_values("width", ascending=False).iterrows():
        lines.append(
            f"| {int(r['width'])} | {r['removed'] if pd.notna(r['removed']) else '-'} | {pct(float(r['total_return']))} | "
            f"{pct(float(r['max_drawdown']))} | {int(r['switches'])} | {float(r['mean_top1_tenure']):.2f} | {float(r['candidate_mean']):.2f} |"
        )

    lines += [
        "",
        "## B. Fixed15-subset distribution by width",
        "",
        "| Width | N | Exhaustive | Beat Fixed15 | P10 return | Median return | P90 return | Median MDD | Median tenure | Median switches |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in width_summary.sort_values("width", ascending=False).iterrows():
        lines.append(
            f"| {int(r['width'])} | {int(r['n'])} | {bool(r['exhaustive_width'])} | {pct(float(r['beat_fixed15_share']))} | "
            f"{pct(float(r['return_p10']))} | {pct(float(r['return_median']))} | {pct(float(r['return_p90']))} | "
            f"{pct(float(r['mdd_median']))} | {float(r['tenure_median']):.2f} | {float(r['switches_median']):.1f} |"
        )

    lines += [
        "",
        "## C. Replacement tests on smaller Greedy pools",
        "",
        "| Width | Kind | N | Drop-only return | Improve share | Median return | Best return | Median delta | Median tenure | Median switches |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in replacement_summary.sort_values(["width", "kind"], ascending=[False, True]).iterrows():
        lines.append(
            f"| {int(r['width'])} | {r['kind']} | {int(r['n'])} | {pct(float(r['base_drop_only_return']))} | "
            f"{pct(float(r['improve_share']))} | {pct(float(r['median_total_return']))} | {pct(float(r['best_total_return']))} | "
            f"{pct(float(r['median_delta']))} | {float(r['median_tenure']):.2f} | {float(r['median_switches']):.1f} |"
        )

    lines += [
        "",
        "## Interpretation rules",
        "",
        "1. Do not use Greedy deletion alone to claim a small pool is better; it is maximally hindsight-selected.",
        "2. A structural width effect requires the random/exhaustive subset median to improve as width falls, not merely the best subset.",
        "3. If median subset performance peaks and then falls, the evidence favors an intermediate width rather than minimal width.",
        "4. Replacement is incrementally useful only if a meaningful share of swaps beats the same-width drop-only pool; a single best swap is insufficient.",
        "5. Any operational rule still requires point-in-time monthly walk-forward validation.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--greedy-path", default="universe-width-greedy-v1.csv")
    ap.add_argument("--width-detail-path", default="universe-width-random-detail-v1.csv")
    ap.add_argument("--width-summary-path", default="universe-width-random-summary-v1.csv")
    ap.add_argument("--replacement-detail-path", default="universe-width-replacement-detail-v1.csv")
    ap.add_argument("--replacement-summary-path", default="universe-width-replacement-summary-v1.csv")
    ap.add_argument("--summary-path", default="universe-width-oracle-v1-summary.json")
    ap.add_argument("--report-path", default="universe-width-oracle-v1-report.md")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)
    meta = load_metadata(engine)
    firsts = load_first_dates(engine)
    stats = load_oracle_stats(engine)
    nasdaq, fallback, _ = candidate_sets(meta, firsts, stats)
    external = sorted(set(nasdaq) | set(fallback))

    union = set(FIXED15) | set(external)
    _, score, oo = prepare_wides(bars, features, union)
    run, cache = make_runner(score, oo)

    baseline = run(set(FIXED15))
    greedy, greedy_pools = greedy_path(run)
    random_detail, width_summary = random_width_distribution(run, float(baseline["total_return"]))
    replacement_detail, replacement_summary = replacement_tests(run, greedy_pools, external)

    greedy.to_csv(args.greedy_path, index=False)
    random_detail.to_csv(args.width_detail_path, index=False)
    width_summary.to_csv(args.width_summary_path, index=False)
    replacement_detail.to_csv(args.replacement_detail_path, index=False)
    replacement_summary.to_csv(args.replacement_summary_path, index=False)

    best_greedy = greedy.sort_values("total_return", ascending=False).iloc[0]
    best_median = width_summary.sort_values("return_median", ascending=False).iloc[0]
    summary = {
        "study": "Universe Width Oracle V1",
        "lookahead": True,
        "design_file": "research/universe/UNIVERSE_WIDTH_ORACLE_V1.md",
        "baseline": baseline,
        "external_candidates": external,
        "greedy_best": best_greedy.replace({np.nan: None}).to_dict(),
        "random_width_best_median": best_median.replace({np.nan: None}).to_dict(),
        "greedy_path": greedy.replace({np.nan: None}).to_dict(orient="records"),
        "width_summary": width_summary.replace({np.nan: None}).to_dict(orient="records"),
        "replacement_summary": replacement_summary.replace({np.nan: None}).to_dict(orient="records"),
        "evaluated_unique_pools": int(len(cache)),
        "random_seed": RANDOM_SEED,
        "max_subsets_per_width": RANDOM_SAMPLE_N,
        "replacement_widths": list(REPLACEMENT_WIDTHS),
    }
    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    Path(args.report_path).write_text(
        build_report(baseline, greedy, width_summary, replacement_summary, external),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
