#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import optimal_universe_reverse_engineering.oure_stage5_history_transfer as s5
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
from validate_fixed15_vs_full_market import FIXED15

CASH = "511220"
SPLIT = pd.Timestamp("2025-01-01")


def spearman_no_scipy(x, y) -> float:
    a = pd.Series(np.asarray(x, dtype=float))
    b = pd.Series(np.asarray(y, dtype=float))
    m = a.notna() & b.notna() & np.isfinite(a) & np.isfinite(b)
    if int(m.sum()) < 3:
        return np.nan
    ar = a[m].rank(method="average")
    br = b[m].rank(method="average")
    return float(ar.corr(br, method="pearson"))


def pct_rank(vals: dict) -> dict:
    return s5.rank_pct(vals, higher=True)


def run_lengths(x: np.ndarray) -> list[int]:
    out = []
    if len(x) == 0:
        return out
    cur = int(x[0]); n = 1
    for v in x[1:]:
        v = int(v)
        if v == cur:
            n += 1
        else:
            out.append(n); cur = v; n = 1
    out.append(n)
    return out


def risk_leader_stats(score: pd.DataFrame, dates: pd.DatetimeIndex, members: list[str]) -> dict:
    m = [s for s in members if s in score.columns and s != CASH]
    if not m or len(dates) == 0:
        return {}
    sm = score.loc[dates, m].to_numpy(float)
    elig = np.isfinite(sm)
    cnt = elig.sum(axis=1)
    safe = np.where(elig, sm, -np.inf)
    leader = np.full(len(sm), -1, dtype=int)
    has = cnt > 0
    leader[has] = np.argmax(safe[has], axis=1)
    gaps = []
    for row in safe:
        rr = row[np.isfinite(row)]
        if len(rr) >= 2:
            p = np.partition(rr, -2)
            gaps.append(float(p[-1] - p[-2]))
    lens = run_lengths(leader)
    switches = int(np.sum(leader[1:] != leader[:-1])) if len(leader) > 1 else 0
    active = np.unique(leader[leader >= 0])
    return {
        "eligible_fraction": float(cnt.mean() / max(1, len(m))),
        "mean_eligible_count": float(cnt.mean()),
        "covered_share": float((cnt > 0).mean()),
        "top1_top2_gap_median": float(np.median(gaps)) if gaps else np.nan,
        "leader_switch_rate": float(switches / max(1, len(leader) - 1)),
        "mean_leader_tenure": float(np.mean(lens)) if lens else np.nan,
        "active_leader_share": float(len(active) / len(m)),
    }


def relay_rank(ev: s5.WindowEvaluator, universes: list[tuple[str, ...]]) -> dict:
    raw = {u: ev.mechanism(u) for u in universes}
    metrics = ["coverage_efficiency", "productive_switch_share", "switch_counterfactual_gain_mean"]
    ranks = {}
    for metric in metrics:
        vals = {u: raw[u].get(metric, np.nan) for u in universes}
        ranks[metric] = pct_rank(vals)
    return {u: float(np.mean([ranks[m][u] for m in metrics])) for u in universes}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage6-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng); bars["symbol"] = bars["symbol"].astype(str)
    feat = build_features(bars); feat["symbol"] = feat["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)
    meta = pd.read_sql_query(text("""
        select symbol,has_daily_bars,leveraged_flag,inverse_flag
        from public.instrument_metadata_current
    """), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    dec = s5.decision_indices(cal)
    period_rows = []
    library_rows = []
    for pi, d in enumerate(dec):
        next_d = dec[pi + 1] if pi + 1 < len(dec) else min(len(cal) - 2, d + 126)
        if next_d <= d:
            continue
        decision_date = pd.Timestamp(cal[d])
        future_end = pd.Timestamp(cal[next_d - 1])
        partial = bool(pi + 1 >= len(dec) and (next_d - d) < 110)
        pool = s5.available_pool(close, meta, cal, d)
        if len(pool) < 30:
            raise RuntimeError(f"too few candidates {decision_date.date()}: {len(pool)}")

        evals = {}; libs = {}
        for L in s5.LOOKBACKS:
            ev = s5.WindowEvaluator(score, gross, cal, pool, d - L, d)
            lib, _ = s5.search_library(ev, pool)
            evals[L] = ev; libs[L] = lib
        union = sorted(set().union(*libs.values()))
        chosen, robust_scores, _ = s5.choose_rules(evals, libs)
        future = s5.WindowEvaluator(score, gross, cal, pool, d, next_d)

        past6 = {u: evals[126].evaluate(u).log_growth for u in union}
        fut = {u: future.evaluate(u).log_growth for u in union}
        robust_min = {u: float(robust_scores[u][0]) for u in union}
        past_relay = relay_rank(evals[126], union)
        future_relay = relay_rank(future, union)

        c1 = spearman_no_scipy(list(past6.values()), [fut[u] for u in past6])
        c2 = spearman_no_scipy([robust_min[u] for u in union], [fut[u] for u in union])
        c3 = spearman_no_scipy([past_relay[u] for u in union], [future_relay[u] for u in union])

        winner = chosen["past6m_winner"]
        fut_pct = pct_rank(fut)
        best_future = max(fut.values())
        winner_future = fut[winner]

        fdates = pd.DatetimeIndex(cal[d:next_d])
        market = risk_leader_stats(score, fdates, pool)
        fix_members = [s for s in FIXED15 if s != CASH and s in pool]
        fix_res = future.evaluate(fix_members)
        fix_mech = future.mechanism(fix_members)
        fix_lead = risk_leader_stats(score, fdates, fix_members)

        era = "2022_2024" if decision_date < SPLIT else "2025_2026"
        row = {
            "decision_date": str(decision_date.date()),
            "future_end_date": str(future_end.date()),
            "partial_final_period": partial,
            "era": era,
            "pool_n": len(pool),
            "library_n": len(union),
            "past6_future_spearman": c1,
            "robust_future_spearman": c2,
            "relay_rank_persistence": c3,
            "past6_winner_future_percentile": fut_pct[winner],
            "past6_winner_future_log": winner_future,
            "future_best_library_log": best_future,
            "past6_winner_regret_log": winner_future - best_future,
            "fix15_future_return": fix_res.total_return,
            "fix15_switch_events": fix_res.switch_events,
            "fix15_switch_rate": fix_lead.get("leader_switch_rate", np.nan),
            "fix15_mean_leader_tenure": fix_lead.get("mean_leader_tenure", np.nan),
            "fix15_coverage_efficiency": fix_mech.get("coverage_efficiency", np.nan),
            "fix15_productive_switch_share": fix_mech.get("productive_switch_share", np.nan),
            "fix15_switch_gain_mean": fix_mech.get("switch_counterfactual_gain_mean", np.nan),
            **{f"market_{k}": v for k, v in market.items()},
        }
        period_rows.append(row)

        for u in union:
            library_rows.append({
                "decision_date": str(decision_date.date()), "era": era,
                "members": ",".join(u), "k_noncash": len(u),
                "past126_log": past6[u], "robust_min_rank": robust_min[u],
                "past_relay_rank": past_relay[u], "future_log": fut[u],
                "future_relay_rank": future_relay[u],
            })

    periods = pd.DataFrame(period_rows)
    periods.to_csv(out / "stage6_period_diagnostics.csv", index=False)
    pd.DataFrame(library_rows).to_csv(out / "stage6_library_transfer.csv", index=False)

    complete = periods[~periods["partial_final_period"]].copy()
    metrics = [
        "past6_future_spearman", "robust_future_spearman", "relay_rank_persistence",
        "past6_winner_future_percentile", "past6_winner_regret_log",
        "fix15_future_return", "fix15_switch_rate", "fix15_mean_leader_tenure",
        "fix15_coverage_efficiency", "fix15_productive_switch_share", "fix15_switch_gain_mean",
        "market_eligible_fraction", "market_mean_eligible_count", "market_covered_share",
        "market_top1_top2_gap_median", "market_leader_switch_rate", "market_mean_leader_tenure",
        "market_active_leader_share",
    ]
    summary_rows = []
    for era, g in complete.groupby("era"):
        r = {"era": era, "n_periods": len(g)}
        for m in metrics:
            r[f"median_{m}"] = float(g[m].median())
            r[f"mean_{m}"] = float(g[m].mean())
        r["linked_fix15_return"] = float(np.exp(np.log1p(g["fix15_future_return"]).sum()) - 1.0)
        summary_rows.append(r)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(out / "stage6_regime_summary.csv", index=False)

    old = summary[summary["era"] == "2022_2024"].iloc[0]
    new = summary[summary["era"] == "2025_2026"].iloc[0]
    gate1 = bool(old["median_past6_future_spearman"] <= 0 and new["median_past6_future_spearman"] > 0
                 and new["median_past6_future_spearman"] - old["median_past6_future_spearman"] >= 0.20)
    gate2 = bool(new["median_robust_future_spearman"] - old["median_robust_future_spearman"] >= 0.20)
    gate3 = bool(old["median_past6_winner_future_percentile"] < 0.50
                 and new["median_past6_winner_future_percentile"] > 0.50)
    payload = {
        "study": "OURE Stage6 historical-Universe transfer regime audit",
        "status": "completed",
        "gates": {"past6_rank_flip": gate1, "robust_rank_improvement": gate2, "winner_percentile_flip": gate3},
        "gate_count": int(gate1) + int(gate2) + int(gate3),
        "regime_shift_gate_pass": bool((int(gate1) + int(gate2) + int(gate3)) >= 2),
        "note": "descriptive mechanism evidence only; six old and three new complete half-years",
    }
    (out / "oure_stage6_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
