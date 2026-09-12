#!/usr/bin/env python3
"""Constrained Oracle grid for Universe V1.

Enumerate ALL eligible replacements inside predeclared structural candidate sets.
Do not choose candidates by portfolio return before the grid is evaluated.
This is still hindsight research because the two incumbents to replace were
identified from 2025-2026 diagnostics; it is an upper-bound/mechanism test only.
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
from walk_forward_candidate_pool import SIDE_COST
from universe.oracle_replacement_v1 import (
    FIXED15, CASH_SIGNAL, CHANGE_DATE, MIN_FIRST_DATE, MIN_ORACLE_EPISODES,
    BAD_NASDAQ, BAD_CONSUMER, load_metadata, load_first_dates, load_oracle_stats,
)

START = pd.Timestamp("2020-12-01")
EVAL_START = pd.Timestamp("2025-01-01")


def candidate_sets(meta: pd.DataFrame, firsts: pd.DataFrame, stats: pd.DataFrame) -> tuple[list[str], list[str], pd.DataFrame]:
    x = meta.merge(firsts, on="symbol", how="inner").merge(stats, on="symbol", how="left")
    x["n_2526"] = pd.to_numeric(x["n_2526"], errors="coerce").fillna(0).astype(int)
    base = x.loc[
        (~x["symbol"].isin(FIXED15))
        & (~x["needs_review"].fillna(False).astype(bool))
        & (x["first_date"] <= MIN_FIRST_DATE)
        & (x["n_2526"] >= MIN_ORACLE_EPISODES)
    ].copy()
    mm = meta.set_index("symbol")
    bad1 = mm.loc[BAD_NASDAQ]
    nasdaq = sorted(base.loc[
        (base["region_primary"] == bad1["region_primary"])
        & (base["exposure_level1"] == bad1["exposure_level1"])
        & (base["risk_bucket"] == bad1["risk_bucket"]), "symbol"
    ].astype(str).unique())

    # For 159529 fallback, use structural diversification only. No fwd-return rank.
    remaining = FIXED15 - {BAD_CONSUMER}
    represented = set(meta.loc[meta["symbol"].isin(remaining), "risk_bucket"].dropna().astype(str))
    bad2 = mm.loc[BAD_CONSUMER]
    fallback = sorted(base.loc[
        (base["region_primary"] == bad2["region_primary"])
        & (base["exposure_level1"] == bad2["exposure_level1"])
        & (~base["risk_bucket"].astype(str).isin(represented)), "symbol"
    ].astype(str).unique())
    if not nasdaq or not fallback:
        raise RuntimeError(f"Empty candidate set: nasdaq={len(nasdaq)} fallback={len(fallback)}")
    audit = x.loc[x["symbol"].isin(set(nasdaq) | set(fallback) | {BAD_NASDAQ, BAD_CONSUMER})].copy()
    return nasdaq, fallback, audit


def prepare_wides(bars: pd.DataFrame, features: pd.DataFrame, symbols: set[str]):
    f = features.loc[features["symbol"].astype(str).isin(symbols) & (features["date"] >= START)].copy()
    trend = (
        (f["annual"] > 0) & (f["r2"] > 0) & (f["score"] > 0)
        & (~f["recent_drop3"].fillna(False))
    )
    s = f["score"].where(trend)
    score = f.assign(pool_score=s).pivot(index="date", columns="symbol", values="pool_score").sort_index()
    score = score.reindex(columns=sorted(score.columns, reverse=True))

    calendar = pd.Index(sorted(pd.to_datetime(bars.loc[bars["date"] >= START, "date"].unique())), name="date")
    score = score.reindex(calendar)
    op = bars.loc[bars["symbol"].astype(str).isin(symbols), ["date", "symbol", "open"]].pivot(index="date", columns="symbol", values="open").reindex(calendar)
    oo = op.shift(-2) / op.shift(-1) - 1.0  # aligned to close(t) signal date
    return calendar, score, oo


def target_for_pool(score: pd.DataFrame, pre_pool: set[str], post_pool: set[str]) -> tuple[pd.Series, pd.Series]:
    vals = []
    counts = []
    for d, row in score.iterrows():
        pool = pre_pool if pd.Timestamp(d) < CHANGE_DATE else post_pool
        cols = [c for c in score.columns if c in pool]
        r = row[cols].dropna() if cols else pd.Series(dtype=float)
        counts.append(len(r))
        vals.append(str(r.idxmax()) if len(r) else None)
    ranked = pd.Series(vals, index=score.index, dtype=object)
    count = pd.Series(counts, index=score.index, dtype=int)
    return ranked, count


def evaluate(ranked: pd.Series, counts: pd.Series, oo: pd.DataFrame) -> dict:
    targets = ranked.where(ranked != CASH_SIGNAL, None)
    dates = ranked.index
    prev = None
    rows = []
    for i in range(len(dates) - 2):
        signal = pd.Timestamp(dates[i]); exec_date = pd.Timestamp(dates[i+1])
        if signal < START:
            continue
        t = targets.iloc[i]
        t = str(t) if t is not None and pd.notna(t) else None
        if t == prev:
            sides = 0
        elif prev is None or t is None:
            sides = 1
        else:
            sides = 2
        gross = 0.0; missing = False
        if t is not None:
            try:
                gross = float(oo.at[signal, t])
                if not math.isfinite(gross):
                    gross = 0.0; missing = True
            except Exception:
                gross = 0.0; missing = True
        net = (1.0 + gross) * (1.0 - SIDE_COST * sides) - 1.0
        rows.append((exec_date, signal, t, gross, net, int(t != prev), sides, missing))
        prev = t
    p = pd.DataFrame(rows, columns=["date","signal_date","target","gross","net","switch","sides","missing"])
    e = p.loc[p["date"] >= EVAL_START].copy()
    eq = (1.0 + e["net"]).cumprod(); dd = eq/eq.cummax()-1.0

    r = ranked.loc[ranked.index >= EVAL_START].dropna().astype(str)
    groups = (r != r.shift()).cumsum(); runs = r.groupby(groups).size() if len(r) else pd.Series(dtype=float)
    c = counts.loc[counts.index >= EVAL_START]

    return {
        "total_return": float(eq.iloc[-1]-1.0) if len(eq) else np.nan,
        "max_drawdown": float(dd.min()) if len(dd) else np.nan,
        "switches": int(e["switch"].sum()),
        "turnover_sides": int(e["sides"].sum()),
        "missing_quote_days": int(e["missing"].sum()),
        "candidate_mean": float(c.mean()),
        "top1_runs": int(len(runs)),
        "mean_top1_tenure": float(runs.mean()) if len(runs) else np.nan,
        "median_top1_tenure": float(runs.median()) if len(runs) else np.nan,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--grid-path", default="universe-oracle-grid-v1.csv")
    ap.add_argument("--summary-path", default="universe-oracle-grid-v1-summary.json")
    ap.add_argument("--report-path", default="universe-oracle-grid-v1-report.md")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)
    meta = load_metadata(engine); firsts = load_first_dates(engine); stats = load_oracle_stats(engine)
    nasdaq, fallback, audit = candidate_sets(meta, firsts, stats)
    union = set(FIXED15) | set(nasdaq) | set(fallback)
    calendar, score, oo = prepare_wides(bars, features, union)

    cache = {}
    def run(pool: set[str]):
        key = tuple(sorted(pool))
        if key not in cache:
            ranked, counts = target_for_pool(score, FIXED15, pool)
            cache[key] = evaluate(ranked, counts, oo)
        return cache[key]

    baseline = run(set(FIXED15))
    drop_both_pool = set(FIXED15) - {BAD_NASDAQ, BAD_CONSUMER}
    drop_both = run(drop_both_pool)
    rows = []

    for n in nasdaq:
        pool = (set(FIXED15) - {BAD_NASDAQ}) | {n}
        m = run(pool)
        rows.append({"kind":"replace_nasdaq","nasdaq":n,"fallback":None,**m})
    for c in fallback:
        pool = (set(FIXED15) - {BAD_CONSUMER}) | {c}
        m = run(pool)
        rows.append({"kind":"replace_consumer","nasdaq":None,"fallback":c,**m})
    for n in nasdaq:
        for c in fallback:
            pool = drop_both_pool | {n,c}
            m = run(pool)
            rows.append({"kind":"replace_pair","nasdaq":n,"fallback":c,**m})
            add = set(FIXED15) | {n,c}
            ma = run(add)
            rows.append({"kind":"add_pair","nasdaq":n,"fallback":c,**ma})

    grid = pd.DataFrame(rows)
    grid["return_delta_vs_fixed15"] = grid["total_return"] - baseline["total_return"]
    grid["mdd_delta_vs_fixed15"] = grid["max_drawdown"] - baseline["max_drawdown"]
    grid.to_csv(args.grid_path, index=False)

    group_summary = {}
    for kind,g in grid.groupby("kind"):
        group_summary[kind] = {
            "n": int(len(g)),
            "outperform_return_share": float((g["total_return"] > baseline["total_return"]).mean()),
            "median_total_return": float(g["total_return"].median()),
            "best_total_return": float(g["total_return"].max()),
            "worst_total_return": float(g["total_return"].min()),
            "median_max_drawdown": float(g["max_drawdown"].median()),
            "median_top1_tenure": float(g["mean_top1_tenure"].median()),
            "median_switches": float(g["switches"].median()),
        }
    pair = grid.loc[grid["kind"]=="replace_pair"].sort_values("total_return", ascending=False)
    add = grid.loc[grid["kind"]=="add_pair"].sort_values("total_return", ascending=False)
    summary = {
        "study":"Universe Oracle V1 constrained grid",
        "lookahead":True,
        "baseline":baseline,
        "drop_both":drop_both,
        "candidate_sets":{"nasdaq":nasdaq,"consumer_fallback":fallback},
        "group_summary":group_summary,
        "top_replace_pairs":pair.head(10).replace({np.nan:None}).to_dict(orient="records"),
        "bottom_replace_pairs":pair.tail(5).replace({np.nan:None}).to_dict(orient="records"),
        "top_add_pairs":add.head(5).replace({np.nan:None}).to_dict(orient="records"),
    }
    Path(args.summary_path).write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")

    lines=[
        "# Universe Oracle V1 — Constrained Grid",
        "",
        "> Hindsight mechanism test only. Candidate sets are structural; every eligible combination is reported.",
        "",
        f"- Fixed15 2025-26 return: **{baseline['total_return']:.2%}**; MDD **{baseline['max_drawdown']:.2%}**",
        f"- Drop both return: **{drop_both['total_return']:.2%}**; MDD **{drop_both['max_drawdown']:.2%}**",
        f"- Nasdaq candidate count: `{len(nasdaq)}`",
        f"- Consumer-fallback candidate count: `{len(fallback)}`",
        f"- Pair combinations: `{len(pair)}`",
        "",
        "## Distribution",
        "",
        "| Kind | N | Beat Fixed15 | Median return | Best | Worst | Median MDD | Median tenure |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for kind,s in group_summary.items():
        lines.append(f"| {kind} | {s['n']} | {s['outperform_return_share']:.1%} | {s['median_total_return']:.2%} | {s['best_total_return']:.2%} | {s['worst_total_return']:.2%} | {s['median_max_drawdown']:.2%} | {s['median_top1_tenure']:.2f} |")
    lines += ["", "## Top replacement pairs", "", "| Nasdaq | Other US | Return | MDD | Switches | Tenure |", "|---|---|---:|---:|---:|---:|"]
    for _,r in pair.head(10).iterrows():
        lines.append(f"| {r['nasdaq']} | {r['fallback']} | {r['total_return']:.2%} | {r['max_drawdown']:.2%} | {int(r['switches'])} | {r['mean_top1_tenure']:.2f} |")
    Path(args.report_path).write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))

if __name__ == "__main__":
    main()
