#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
import sys
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from validate_fixed15_vs_full_market import FIXED15
from walk_forward_candidate_pool import SIDE_COST

CASH = "511220"
WINDOW = 20
TOL = 1e-12
OUT = Path("muv-stage26-set-value-oracle-report.json")
OUT_MONTHS = Path("muv-stage26-set-value-oracle-months.csv")
OUT_STEPS = Path("muv-stage26-set-value-oracle-steps.csv")


def target_tenure(targets: list[str | None]) -> tuple[float, int]:
    runs: list[int] = []
    prev = None
    n = 0
    for x in targets:
        if x is None:
            if prev is not None and n:
                runs.append(n)
            prev, n = None, 0
            continue
        if x == prev:
            n += 1
        else:
            if prev is not None and n:
                runs.append(n)
            prev, n = x, 1
    if prev is not None and n:
        runs.append(n)
    return (float(np.mean(runs)) if runs else 0.0, len(runs))


def evaluate_indices(
    idxs: tuple[int, ...],
    symbols: list[str],
    score: np.ndarray,
    gross: np.ndarray,
) -> dict:
    d = score.shape[0]
    if not idxs:
        return {
            "value": 0.0,
            "net_return": 0.0,
            "gross_return": 0.0,
            "max_drawdown": 0.0,
            "switch_events": 0,
            "turnover_sides": 0,
            "mean_tenure": 0.0,
            "distinct_targets": 0,
            "targets": [None] * d,
        }

    a = score[:, list(idxs)]
    valid = np.isfinite(a)
    safe = np.where(valid, a, -np.inf)
    arg = np.argmax(safe, axis=1)
    has = valid.any(axis=1)
    chosen = np.asarray(idxs, dtype=int)[arg]

    targets: list[str | None] = [symbols[int(chosen[k])] if has[k] else None for k in range(d)]
    daily_net: list[float] = []
    daily_gross: list[float] = []
    prev: str | None = None
    switches = 0
    sides_total = 0

    for k, target in enumerate(targets):
        if target == prev:
            sides = 0
        elif prev is None or target is None:
            sides = 1
        else:
            sides = 2
        if target != prev:
            switches += 1
        sides_total += sides

        g = 0.0
        if target is not None:
            j = symbols.index(target)
            x = gross[k, j]
            g = float(x) if np.isfinite(x) else 0.0
        nret = (1.0 + g) * (1.0 - SIDE_COST * sides) - 1.0
        daily_gross.append(g)
        daily_net.append(nret)
        prev = target

    # Frozen-window liquidation so each candidate set is valued on the same self-contained horizon.
    if prev is not None:
        sides_total += 1
        daily_net[-1] = (1.0 + daily_net[-1]) * (1.0 - SIDE_COST) - 1.0

    net_arr = np.asarray(daily_net, dtype=float)
    gross_arr = np.asarray(daily_gross, dtype=float)
    value = float(np.log1p(net_arr).sum())
    gross_value = float(np.log1p(gross_arr).sum())
    eq = np.exp(np.cumsum(np.log1p(net_arr)))
    peak = np.maximum.accumulate(np.r_[1.0, eq])[:-1]
    dd = eq / peak - 1.0
    tenure, _ = target_tenure(targets)
    return {
        "value": value,
        "net_return": float(math.exp(value) - 1.0),
        "gross_return": float(math.exp(gross_value) - 1.0),
        "max_drawdown": float(np.min(dd)) if len(dd) else 0.0,
        "switch_events": int(switches),
        "turnover_sides": int(sides_total),
        "mean_tenure": tenure,
        "distinct_targets": int(len({x for x in targets if x is not None})),
        "targets": targets,
    }


def aggregate(g: pd.DataFrame) -> dict:
    if g.empty:
        return {}
    return {
        "months": int(len(g)),
        "candidate_count_median": float(g.candidate_count.median()),
        "oracle_size_mean": float(g.oracle_size.mean()),
        "oracle_size_median": float(g.oracle_size.median()),
        "oracle_size_min": int(g.oracle_size.min()),
        "oracle_size_max": int(g.oracle_size.max()),
        "oracle_distinct_sizes": int(g.oracle_size.nunique()),
        "oracle_net_return_mean": float(g.oracle_net_return.mean()),
        "full_market_net_return_mean": float(g.full_market_net_return.mean()),
        "fixed15_net_return_mean": float(g.fixed15_net_return.mean()),
        "oracle_minus_full_value_mean": float(g.oracle_minus_full_value.mean()),
        "oracle_minus_fixed15_value_mean": float(g.oracle_minus_fixed15_value.mean()),
        "full_switches_mean": float(g.full_switches.mean()),
        "oracle_switches_mean": float(g.oracle_switches.mean()),
        "full_tenure_mean": float(g.full_tenure.mean()),
        "oracle_tenure_mean": float(g.oracle_tenure.mean()),
        "full_path_coverage_mean": float(g.full_path_coverage.mean()),
        "oracle_set_jaccard_mean": float(g.oracle_set_jaccard.dropna().mean()) if g.oracle_set_jaccard.notna().any() else None,
        "best_remaining_add_delta_median": float(g.best_remaining_add_delta.median()),
        "best_swap_delta_median": float(g.best_swap_delta.median()),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    args = p.parse_args()
    if not args.database_url:
        raise RuntimeError("ETF_DAILY_BARS_DATABASE_URL is required")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    bars["symbol"] = bars["symbol"].astype(str)
    f = build_features(bars)
    f["symbol"] = f["symbol"].astype(str)
    f["date"] = pd.to_datetime(f["date"])
    bars["date"] = pd.to_datetime(bars["date"])

    calendar = pd.Index(sorted(pd.to_datetime(bars.date.unique())))
    month_end = pd.Series(calendar, index=calendar).groupby(calendar.to_period("M")).max()
    open_wide = bars.pivot(index="date", columns="symbol", values="open").reindex(calendar)
    gross_wide = open_wide.shift(-2) / open_wide.shift(-1) - 1.0

    months: list[dict] = []
    steps: list[dict] = []
    prev_oracle: set[str] | None = None

    fixed = set(map(str, FIXED15)) - {CASH}

    for period, decision_date0 in month_end.items():
        decision_date = pd.Timestamp(decision_date0)
        pos = int(calendar.get_loc(decision_date))
        signal_dates = calendar[pos + 1: pos + 1 + WINDOW]
        if len(signal_dates) < WINDOW or pos + WINDOW + 2 >= len(calendar):
            continue
        if decision_date < pd.Timestamp("2022-12-01"):
            continue

        dec = f.loc[(f.date == decision_date) & f.universe_eligible.fillna(False), ["symbol"]]
        symbols = sorted(set(dec.symbol.astype(str)) - {CASH})
        if not symbols:
            continue

        fm = f.loc[f.date.isin(signal_dates) & f.symbol.isin(symbols), ["date", "symbol", "score", "trend_eligible"]].copy()
        fm["eligible_score"] = np.where(fm.trend_eligible.fillna(False), fm.score.astype(float), np.nan)
        score_df = fm.pivot(index="date", columns="symbol", values="eligible_score").reindex(index=signal_dates, columns=symbols)
        score = score_df.to_numpy(dtype=float)
        gross = gross_wide.reindex(index=signal_dates, columns=symbols).to_numpy(dtype=float)
        sym_to_i = {s: i for i, s in enumerate(symbols)}

        full_idxs = tuple(range(len(symbols)))
        fixed_idxs = tuple(sym_to_i[s] for s in sorted(fixed & set(symbols)))
        full_eval = evaluate_indices(full_idxs, symbols, score, gross)
        fixed_eval = evaluate_indices(fixed_idxs, symbols, score, gross)

        selected: list[int] = []
        current = evaluate_indices(tuple(), symbols, score, gross)
        remaining = set(range(len(symbols)))

        while remaining:
            best_j = None
            best_eval = None
            best_delta = -np.inf
            for j in remaining:
                ev = evaluate_indices(tuple(selected + [j]), symbols, score, gross)
                delta = ev["value"] - current["value"]
                if delta > best_delta:
                    best_j, best_eval, best_delta = j, ev, delta
            if best_j is None or best_delta <= TOL:
                break
            steps.append({
                "month": str(period), "decision_date": decision_date, "operation": "add",
                "symbol": symbols[best_j], "size_before": len(selected), "size_after": len(selected) + 1,
                "value_before": current["value"], "value_after": best_eval["value"], "marginal_value": best_delta,
            })
            selected.append(best_j)
            remaining.remove(best_j)
            current = best_eval

        forward_size = len(selected)

        # Best-improvement removal cleanup. This is still future oracle structure, never executable selection.
        while selected:
            best_i = None
            best_eval = None
            best_delta = -np.inf
            for i in selected:
                trial = tuple(x for x in selected if x != i)
                ev = evaluate_indices(trial, symbols, score, gross)
                delta = ev["value"] - current["value"]
                if delta > best_delta:
                    best_i, best_eval, best_delta = i, ev, delta
            if best_i is None or best_delta <= TOL:
                break
            steps.append({
                "month": str(period), "decision_date": decision_date, "operation": "remove",
                "symbol": symbols[best_i], "size_before": len(selected), "size_after": len(selected) - 1,
                "value_before": current["value"], "value_after": best_eval["value"], "marginal_value": best_delta,
            })
            selected.remove(best_i)
            remaining.add(best_i)
            current = best_eval

        oracle_set = {symbols[i] for i in selected}

        # Residual one-add and one-swap audits; they are reported but not used to tune or extend the search.
        best_add = -np.inf
        for j in set(range(len(symbols))) - set(selected):
            ev = evaluate_indices(tuple(selected + [j]), symbols, score, gross)
            best_add = max(best_add, ev["value"] - current["value"])
        if not np.isfinite(best_add):
            best_add = 0.0

        best_remove = -np.inf
        for i in selected:
            ev = evaluate_indices(tuple(x for x in selected if x != i), symbols, score, gross)
            best_remove = max(best_remove, ev["value"] - current["value"])
        if not np.isfinite(best_remove):
            best_remove = 0.0

        best_swap = -np.inf
        outsiders = set(range(len(symbols))) - set(selected)
        for i in selected:
            base = [x for x in selected if x != i]
            for j in outsiders:
                ev = evaluate_indices(tuple(base + [j]), symbols, score, gross)
                best_swap = max(best_swap, ev["value"] - current["value"])
        if not np.isfinite(best_swap):
            best_swap = 0.0

        full_targets = full_eval["targets"]
        invested_full = [x for x in full_targets if x is not None]
        path_cov = float(np.mean([x in oracle_set for x in invested_full])) if invested_full else 1.0
        jac = np.nan
        if prev_oracle is not None:
            union = oracle_set | prev_oracle
            jac = float(len(oracle_set & prev_oracle) / len(union)) if union else 1.0
        prev_oracle = oracle_set

        months.append({
            "month": str(period),
            "decision_date": decision_date,
            "era": "2023-24" if decision_date.year < 2025 else "2025-26",
            "candidate_count": len(symbols),
            "forward_size": forward_size,
            "oracle_size": len(selected),
            "oracle_symbols": ";".join(sorted(oracle_set)),
            "oracle_value": current["value"],
            "oracle_net_return": current["net_return"],
            "oracle_max_drawdown": current["max_drawdown"],
            "oracle_switches": current["switch_events"],
            "oracle_tenure": current["mean_tenure"],
            "oracle_distinct_targets": current["distinct_targets"],
            "full_market_value": full_eval["value"],
            "full_market_net_return": full_eval["net_return"],
            "full_switches": full_eval["switch_events"],
            "full_tenure": full_eval["mean_tenure"],
            "fixed15_value": fixed_eval["value"],
            "fixed15_net_return": fixed_eval["net_return"],
            "oracle_minus_full_value": current["value"] - full_eval["value"],
            "oracle_minus_fixed15_value": current["value"] - fixed_eval["value"],
            "full_path_coverage": path_cov,
            "best_remaining_add_delta": best_add,
            "best_remaining_remove_delta": best_remove,
            "best_swap_delta": best_swap,
            "oracle_set_jaccard": jac,
        })

    M = pd.DataFrame(months)
    S = pd.DataFrame(steps)
    M.to_csv(OUT_MONTHS, index=False)
    S.to_csv(OUT_STEPS, index=False)

    report = {
        "version": "muv_stage26_variable_size_set_value_oracle_20260913",
        "label_version": "set_value_next20_fixed_ols_v2",
        "design": {
            "role": "future-informed local oracle structural audit only; not executable OOS policy",
            "decision_frequency": "month-end",
            "candidate_market": "point-in-time non-cash universe_eligible ETFs at decision date",
            "evaluation_window_signal_days": WINDOW,
            "downstream_selector": "unchanged daily max OLS score among trend_eligible members",
            "execution": "close signal -> next open entry -> following open mark",
            "side_cost": SIDE_COST,
            "primary_value": "sum(log1p(net_ret)) with terminal liquidation side",
            "global_subset_enumeration": False,
            "fixed_k": False,
            "oracle_search": "forward best positive single-add until natural stop, then best positive single-remove cleanup; one-swap is audit only",
            "numeric_tolerance": TOL,
        },
        "overall": aggregate(M),
        "by_era": {e: aggregate(g) for e, g in M.groupby("era")},
        "structure": {
            "months": int(len(M)),
            "distinct_oracle_sizes": int(M.oracle_size.nunique()) if len(M) else 0,
            "months_oracle_empty": int((M.oracle_size == 0).sum()) if len(M) else 0,
            "months_positive_residual_add": int((M.best_remaining_add_delta > TOL).sum()) if len(M) else 0,
            "months_positive_residual_remove": int((M.best_remaining_remove_delta > TOL).sum()) if len(M) else 0,
            "months_positive_swap": int((M.best_swap_delta > TOL).sum()) if len(M) else 0,
        },
        "interpretation": "Stage26 diagnoses whether endogenous set size and local set-value structure are real enough to justify a later point-in-time generator. No oracle set is an executable result.",
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
