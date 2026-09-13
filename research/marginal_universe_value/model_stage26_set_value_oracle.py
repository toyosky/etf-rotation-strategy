#!/usr/bin/env python3
"""Stage26: exact monthly set-value oracle structure audit.

Future-aware oracle for label/upper-bound construction only. Not executable.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from validate_fixed15_vs_full_market import FIXED15
from walk_forward_candidate_pool import SIDE_COST

CASH = "511220"
START_DECISION = pd.Timestamp("2020-12-31")
RANDOM_DRAWS = 100
SEED = 260913
OPT_TOL = 1e-9
FEATURE_COLS = [
    "score", "annual", "r2", "slope", "score_delta", "r2_delta", "slope_delta",
    "current_resid", "ret3", "ret5", "ret10", "ret20", "ret60",
    "dist_high20", "dist_high60", "dist_high120", "vol20", "vol60",
    "efficiency10", "efficiency20", "ma10_dist", "avg_amount60",
    "median_amount60", "nonzero_volume_ratio60", "trend_eligible",
]


def month_ends(calendar: pd.DatetimeIndex) -> list[pd.Timestamp]:
    s = pd.Series(calendar, index=calendar)
    return [pd.Timestamp(x) for x in s.groupby(calendar.to_period("M")).max().tolist()]


def build_interval_data(
    f: pd.DataFrame,
    bars: pd.DataFrame,
    t: pd.Timestamp,
    t_next: pd.Timestamp,
) -> tuple[list[str], list[pd.Timestamp], list[list[int]], np.ndarray, pd.DataFrame]:
    decision = f.loc[
        (f["date"] == t)
        & f["universe_eligible"].fillna(False).astype(bool)
        & (f["symbol"] != CASH)
    ].copy()
    decision = decision.sort_values("symbol").drop_duplicates("symbol", keep="last")
    symbols = decision["symbol"].astype(str).tolist()
    n = len(symbols)
    sym_to_i = {s: i for i, s in enumerate(symbols)}

    calendar = pd.DatetimeIndex(sorted(pd.to_datetime(bars["date"].unique())))
    pos = {pd.Timestamp(d): i for i, d in enumerate(calendar)}
    if t not in pos or t_next not in pos:
        return [], [], [], np.zeros((0, 0)), decision
    p0, p1 = pos[t], pos[t_next]
    signal_dates = [pd.Timestamp(d) for d in calendar[p0:p1] if pos[pd.Timestamp(d)] + 2 < len(calendar)]

    open_wide = bars.pivot(index="date", columns="symbol", values="open").reindex(calendar)
    f_interval = f.loc[
        (f["date"].isin(signal_dates))
        & (f["symbol"].isin(symbols))
        & f["trend_eligible"].fillna(False).astype(bool),
        ["date", "symbol", "score"],
    ].copy()

    active_ranked: list[list[int]] = []
    logret = np.zeros((len(signal_dates), n), dtype=float)
    by_date = {pd.Timestamp(d): g for d, g in f_interval.groupby("date", sort=False)}

    for d_idx, d in enumerate(signal_dates):
        g = by_date.get(d)
        ranked: list[int] = []
        if g is not None and len(g):
            g = g.sort_values(["score", "symbol"], ascending=[False, True])
            ranked = [sym_to_i[str(s)] for s in g["symbol"] if str(s) in sym_to_i]
        active_ranked.append(ranked)

        exec_date = calendar[pos[d] + 1]
        exit_date = calendar[pos[d] + 2]
        for i in ranked:
            s = symbols[i]
            try:
                p_in = float(open_wide.at[exec_date, s])
                p_out = float(open_wide.at[exit_date, s])
                if math.isfinite(p_in) and math.isfinite(p_out) and p_in > 0 and p_out > 0:
                    logret[d_idx, i] = math.log(p_out / p_in)
            except (KeyError, TypeError, ValueError):
                logret[d_idx, i] = 0.0
    return symbols, signal_dates, active_ranked, logret, decision


def evaluate_subset(
    subset: set[int],
    active_ranked: list[list[int]],
    logret: np.ndarray,
) -> dict:
    targets: list[int | None] = []
    gross_log = 0.0
    for d, ranked in enumerate(active_ranked):
        target = next((i for i in ranked if i in subset), None)
        targets.append(target)
        if target is not None:
            gross_log += float(logret[d, target])

    sides = 0
    prev: int | None = None
    for target in targets:
        if target == prev:
            continue
        if target is None or prev is None:
            sides += 1
        else:
            sides += 2
        prev = target
    if prev is not None:
        sides += 1

    cost_log = -math.log(1.0 - SIDE_COST)
    net_log = gross_log - cost_log * sides
    switches = 0
    prev = None
    for target in targets:
        if target != prev:
            switches += 1
        prev = target
    return {
        "log_value": float(net_log),
        "return": float(math.exp(net_log) - 1.0),
        "gross_log": float(gross_log),
        "turnover_sides": int(sides),
        "switch_events": int(switches),
        "targets": targets,
    }


def build_milp(
    n: int,
    active_ranked: list[list[int]],
    logret: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, Bounds, LinearConstraint]:
    d_count = len(active_ranked)
    y0 = n
    s0 = n + d_count * n
    n_s = max(0, d_count - 1) * n
    n_var = n + d_count * n + n_s

    def xid(i: int) -> int:
        return i

    def yid(d: int, i: int) -> int:
        return y0 + d * n + i

    def sid(d: int, i: int) -> int:
        return s0 + (d - 1) * n + i

    c = np.zeros(n_var, dtype=float)
    cost_log = -math.log(1.0 - SIDE_COST)
    for d in range(d_count):
        for i in range(n):
            c[yid(d, i)] = -float(logret[d, i])
            if d == 0 or d == d_count - 1:
                c[yid(d, i)] += cost_log
    for d in range(1, d_count):
        for i in range(n):
            c[sid(d, i)] = cost_log

    integrality = np.zeros(n_var, dtype=np.int8)
    integrality[: n + d_count * n] = 1
    bounds = Bounds(np.zeros(n_var), np.ones(n_var))

    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    lbs: list[float] = []
    ubs: list[float] = []
    r = 0

    def add(coeffs: dict[int, float], lb: float = -np.inf, ub: float = np.inf) -> None:
        nonlocal r
        for col, val in coeffs.items():
            if val:
                rows.append(r)
                cols.append(col)
                data.append(float(val))
        lbs.append(float(lb))
        ubs.append(float(ub))
        r += 1

    active_sets = [set(x) for x in active_ranked]
    for d, ranked in enumerate(active_ranked):
        rank_pos = {i: p for p, i in enumerate(ranked)}
        for i in range(n):
            y = yid(d, i)
            if i not in active_sets[d]:
                add({y: 1.0}, lb=0.0, ub=0.0)
                continue
            p = rank_pos[i]
            above = ranked[:p]
            add({y: 1.0, xid(i): -1.0}, ub=0.0)
            lower = {y: 1.0, xid(i): -1.0}
            for j in above:
                lower[xid(j)] = lower.get(xid(j), 0.0) + 1.0
            add(lower, lb=0.0)
            if above:
                upper = {y: float(len(above))}
                for j in above:
                    upper[xid(j)] = upper.get(xid(j), 0.0) + 1.0
                add(upper, ub=float(len(above)))

    for d in range(1, d_count):
        for i in range(n):
            s = sid(d, i)
            yd = yid(d, i)
            yp = yid(d - 1, i)
            add({yd: 1.0, yp: -1.0, s: -1.0}, ub=0.0)
            add({yp: 1.0, yd: -1.0, s: -1.0}, ub=0.0)

    A = coo_matrix((data, (rows, cols)), shape=(r, n_var)).tocsr()
    return c, integrality, bounds, LinearConstraint(A, np.array(lbs), np.array(ubs))


def solve_oracle(
    symbols: list[str],
    active_ranked: list[list[int]],
    logret: np.ndarray,
) -> tuple[set[int], dict]:
    n = len(symbols)
    if n == 0 or not active_ranked:
        return set(), {"status": "empty", "primary_fun": 0.0, "secondary_status": "empty"}

    c, integrality, bounds, base_constraint = build_milp(n, active_ranked, logret)
    options = {"time_limit": 20.0, "mip_rel_gap": 1e-8, "presolve": True}
    primary = milp(c=c, integrality=integrality, bounds=bounds, constraints=base_constraint, options=options)
    if primary.x is None:
        raise RuntimeError(f"Primary MILP failed: status={primary.status}, message={primary.message}")

    opt_fun = float(primary.fun)
    n_var = len(c)
    x_obj = np.zeros(n_var, dtype=float)
    x_obj[:n] = 1.0
    value_constraint = LinearConstraint(
        coo_matrix(c.reshape(1, -1)).tocsr(),
        np.array([-np.inf]),
        np.array([opt_fun + OPT_TOL]),
    )
    secondary = milp(
        c=x_obj,
        integrality=integrality,
        bounds=bounds,
        constraints=(base_constraint, value_constraint),
        options=options,
    )
    sol = secondary.x if secondary.x is not None else primary.x
    subset = {i for i in range(n) if sol[i] >= 0.5}
    meta = {
        "status": int(primary.status),
        "message": str(primary.message),
        "primary_fun": opt_fun,
        "secondary_status": int(secondary.status),
        "secondary_message": str(secondary.message),
        "mip_gap": None if getattr(primary, "mip_gap", None) is None else float(primary.mip_gap),
    }
    return subset, meta


def random_same_k(
    n: int,
    k: int,
    active_ranked: list[list[int]],
    logret: np.ndarray,
    rng: np.random.Generator,
) -> dict:
    if k <= 0:
        vals = np.zeros(RANDOM_DRAWS, dtype=float)
    elif k >= n:
        v = evaluate_subset(set(range(n)), active_ranked, logret)["log_value"]
        vals = np.full(RANDOM_DRAWS, v, dtype=float)
    else:
        vals = np.array([
            evaluate_subset(set(rng.choice(n, size=k, replace=False).tolist()), active_ranked, logret)["log_value"]
            for _ in range(RANDOM_DRAWS)
        ])
    return {
        "mean_log": float(vals.mean()),
        "p90_log": float(np.quantile(vals, 0.90)),
        "max_log": float(vals.max()),
        "mean_return": float(np.exp(vals.mean()) - 1.0),
    }


def summarize_months(m: pd.DataFrame, start: str, end: str | None = None) -> dict:
    s = m.loc[m["decision_date"] >= pd.Timestamp(start)].copy()
    if end:
        s = s.loc[s["decision_date"] <= pd.Timestamp(end)].copy()
    if s.empty:
        return {}
    j = s["oracle_jaccard_prev"].dropna()
    return {
        "months": int(len(s)),
        "candidate_count_mean": float(s["candidate_count"].mean()),
        "oracle_k_mean": float(s["oracle_k"].mean()),
        "oracle_k_median": float(s["oracle_k"].median()),
        "oracle_k_p90": float(s["oracle_k"].quantile(0.90)),
        "k0_share": float((s["oracle_k"] == 0).mean()),
        "k1_share": float((s["oracle_k"] == 1).mean()),
        "k_le_5_share": float((s["oracle_k"] <= 5).mean()),
        "oracle_log_sum": float(s["oracle_log"].sum()),
        "full_market_log_sum": float(s["full_market_log"].sum()),
        "fixed15_log_sum": float(s["fixed15_log"].sum()),
        "random_same_k_log_sum": float(s["random_mean_log"].sum()),
        "oracle_return_compounded": float(math.exp(s["oracle_log"].sum()) - 1.0),
        "full_market_return_compounded": float(math.exp(s["full_market_log"].sum()) - 1.0),
        "fixed15_return_compounded": float(math.exp(s["fixed15_log"].sum()) - 1.0),
        "oracle_minus_full_market_log_mean": float((s["oracle_log"] - s["full_market_log"]).mean()),
        "oracle_minus_fixed15_log_mean": float((s["oracle_log"] - s["fixed15_log"]).mean()),
        "oracle_minus_random_log_mean": float((s["oracle_log"] - s["random_mean_log"]).mean()),
        "jaccard_mean": float(j.mean()) if len(j) else None,
        "dormant_member_share_mean": float(s["oracle_dormant_member_share"].fillna(0).mean()),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--report-path", default="muv-stage26-set-value-oracle-report.json")
    p.add_argument("--months-path", default="muv-stage26-set-value-oracle-months.csv")
    p.add_argument("--labels-path", default="muv-stage26-set-value-oracle-labels.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    f = build_features(bars)
    f["date"] = pd.to_datetime(f["date"])
    bars["date"] = pd.to_datetime(bars["date"])
    cal = pd.DatetimeIndex(sorted(bars["date"].unique()))
    decisions = [d for d in month_ends(cal) if d >= START_DECISION]

    rng = np.random.default_rng(SEED)
    month_rows: list[dict] = []
    label_rows: list[dict] = []
    prev_oracle_symbols: set[str] | None = None

    for idx in range(len(decisions) - 1):
        t, t_next = decisions[idx], decisions[idx + 1]
        symbols, signal_dates, active_ranked, logret, decision = build_interval_data(f, bars, t, t_next)
        if not signal_dates:
            continue
        n = len(symbols)
        subset, solver = solve_oracle(symbols, active_ranked, logret)
        oracle = evaluate_subset(subset, active_ranked, logret)
        full = evaluate_subset(set(range(n)), active_ranked, logret)
        fixed_idx = {i for i, s in enumerate(symbols) if s in FIXED15 and s != CASH}
        fixed = evaluate_subset(fixed_idx, active_ranked, logret)

        best_single = {"log_value": 0.0, "return": 0.0}
        best_single_symbol = None
        for i in range(n):
            v = evaluate_subset({i}, active_ranked, logret)
            if best_single_symbol is None or v["log_value"] > best_single["log_value"]:
                best_single = v
                best_single_symbol = symbols[i]

        rnd = random_same_k(n, len(subset), active_ranked, logret, rng)
        oracle_symbols = {symbols[i] for i in subset}
        jaccard = None
        if prev_oracle_symbols is not None:
            union = oracle_symbols | prev_oracle_symbols
            jaccard = 1.0 if not union else len(oracle_symbols & prev_oracle_symbols) / len(union)
        prev_oracle_symbols = oracle_symbols

        decision_idx = decision.set_index("symbol", drop=False)
        dormant_count = 0
        for s in oracle_symbols:
            if s in decision_idx.index and not bool(decision_idx.loc[s, "trend_eligible"]):
                dormant_count += 1
        dormant_share = dormant_count / len(oracle_symbols) if oracle_symbols else 0.0

        month_rows.append({
            "decision_date": t,
            "next_decision_date": t_next,
            "candidate_count": n,
            "signal_days": len(signal_dates),
            "oracle_k": len(subset),
            "oracle_log": oracle["log_value"],
            "oracle_return": oracle["return"],
            "oracle_turnover_sides": oracle["turnover_sides"],
            "oracle_switch_events": oracle["switch_events"],
            "full_market_log": full["log_value"],
            "full_market_return": full["return"],
            "fixed15_k": len(fixed_idx),
            "fixed15_log": fixed["log_value"],
            "fixed15_return": fixed["return"],
            "best_singleton_symbol": best_single_symbol,
            "best_singleton_log": best_single["log_value"],
            "best_singleton_return": best_single["return"],
            "random_mean_log": rnd["mean_log"],
            "random_p90_log": rnd["p90_log"],
            "random_max_log": rnd["max_log"],
            "oracle_jaccard_prev": jaccard,
            "oracle_dormant_member_share": dormant_share,
            "solver_primary_status": solver["status"],
            "solver_secondary_status": solver["secondary_status"],
            "oracle_symbols": ",".join(sorted(oracle_symbols)),
        })

        for i, s in enumerate(symbols):
            base = {
                "decision_date": t,
                "next_decision_date": t_next,
                "symbol": s,
                "oracle_member": int(i in subset),
                "oracle_k": len(subset),
                "candidate_count": n,
                "oracle_log": oracle["log_value"],
            }
            if i in subset:
                alt = evaluate_subset(subset - {i}, active_ranked, logret)
                base["local_set_delta_log"] = oracle["log_value"] - alt["log_value"]
                base["local_label_type"] = "remove_loss"
            else:
                alt = evaluate_subset(subset | {i}, active_ranked, logret)
                base["local_set_delta_log"] = alt["log_value"] - oracle["log_value"]
                base["local_label_type"] = "add_delta"
            if s in decision_idx.index:
                row = decision_idx.loc[s]
                for col in FEATURE_COLS:
                    if col in row.index:
                        val = row[col]
                        if isinstance(val, (np.bool_, bool)):
                            base[col] = int(bool(val))
                        elif pd.isna(val):
                            base[col] = np.nan
                        else:
                            try:
                                base[col] = float(val)
                            except (TypeError, ValueError):
                                base[col] = val
            label_rows.append(base)

        print(json.dumps({
            "decision_date": str(t.date()),
            "candidate_count": n,
            "oracle_k": len(subset),
            "oracle_return": oracle["return"],
            "full_market_return": full["return"],
        }, ensure_ascii=False))

    months = pd.DataFrame(month_rows).sort_values("decision_date").reset_index(drop=True)
    labels = pd.DataFrame(label_rows).sort_values(["decision_date", "symbol"]).reset_index(drop=True)
    if months.empty:
        raise RuntimeError("Stage26 produced no decision months")

    months.to_csv(args.months_path, index=False)
    labels.to_csv(args.labels_path, index=False)

    report = {
        "stage": 26,
        "name": "set_value_oracle_structure_audit",
        "label_version": "downstream_ols_set_value_month_v1",
        "oracle_is_executable": False,
        "downstream_rule": {
            "rank": "highest score among trend_eligible ETFs in month-frozen U_t",
            "signal_execution": "close(d) -> open(d+1), mark open(d+1)->open(d+2)",
            "side_cost": SIDE_COST,
            "month_boundary": "cash before first signal and after final signal",
        },
        "sample": {
            "first_decision": str(months["decision_date"].min().date()),
            "last_decision": str(months["decision_date"].max().date()),
            "months": int(len(months)),
        },
        "summary": {
            "full_2021_2026": summarize_months(months, "2021-01-01"),
            "period_2021_2024": summarize_months(months, "2021-01-01", "2024-12-31"),
            "period_2025_2026": summarize_months(months, "2025-01-01"),
        },
        "interpretation_guardrails": {
            "oracle_future_aware": True,
            "do_not_promote_as_strategy": True,
            "next_step": "test whether point-in-time state can learn conditional set value with strict expanding OOS",
        },
    }
    Path(args.report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
