#!/usr/bin/env python3
"""Stage26D: semantics-aligned exact/bound audit for set_value_next20_fixed_ols_v2."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import model_stage26_set_value_oracle as base
import run_stage26_set_value_oracle_compressed as compressed

WINDOW = 20
_ORIG_MILP = base.milp


def aligned_interval_data(f, bars, t, _t_next):
    decision = f.loc[(f["date"] == t) & f["universe_eligible"].fillna(False).astype(bool) & (f["symbol"] != base.CASH)].copy()
    decision = decision.sort_values("symbol").drop_duplicates("symbol", keep="last")
    symbols = decision["symbol"].astype(str).tolist()
    sym_to_i = {s: i for i, s in enumerate(symbols)}
    calendar = pd.DatetimeIndex(sorted(pd.to_datetime(bars["date"].unique())))
    pos = {pd.Timestamp(d): i for i, d in enumerate(calendar)}
    if t not in pos:
        return [], [], [], np.zeros((0, 0)), decision
    p0 = pos[t]
    signal_dates = [pd.Timestamp(d) for d in calendar[p0 + 1:p0 + 1 + WINDOW] if pos[pd.Timestamp(d)] + 2 < len(calendar)]
    if len(signal_dates) != WINDOW:
        return [], [], [], np.zeros((0, 0)), decision
    open_wide = bars.pivot(index="date", columns="symbol", values="open").reindex(calendar)
    f_interval = f.loc[(f["date"].isin(signal_dates)) & (f["symbol"].isin(symbols)) & f["trend_eligible"].fillna(False).astype(bool), ["date", "symbol", "score"]].copy()
    active_ranked = []
    logret = np.zeros((len(signal_dates), len(symbols)), dtype=float)
    by_date = {pd.Timestamp(d): g for d, g in f_interval.groupby("date", sort=False)}
    for d_idx, d in enumerate(signal_dates):
        g = by_date.get(d)
        ranked = []
        if g is not None and len(g):
            g = g.sort_values(["score", "symbol"], ascending=[False, True])
            ranked = [sym_to_i[str(s)] for s in g["symbol"] if str(s) in sym_to_i]
        active_ranked.append(ranked)
        exec_date, exit_date = calendar[pos[d] + 1], calendar[pos[d] + 2]
        for i in ranked:
            s = symbols[i]
            try:
                p_in, p_out = float(open_wide.at[exec_date, s]), float(open_wide.at[exit_date, s])
                if math.isfinite(p_in) and math.isfinite(p_out) and p_in > 0 and p_out > 0:
                    logret[d_idx, i] = math.log(p_out / p_in)
            except (KeyError, TypeError, ValueError):
                pass
    return symbols, signal_dates, active_ranked, logret, decision


def milp_budget(*args, **kwargs):
    options = dict(kwargs.get("options") or {})
    options["time_limit"] = 120.0
    kwargs["options"] = options
    return _ORIG_MILP(*args, **kwargs)


base.build_interval_data = aligned_interval_data
base.solve_oracle = compressed.solve_oracle_compressed
base.milp = milp_budget

if __name__ == "__main__":
    report = "muv-stage26d-aligned-exact-bound-report.json"
    months = "muv-stage26d-aligned-exact-bound-months.csv"
    labels = "muv-stage26d-aligned-exact-bound-labels.csv"
    sys.argv = [sys.argv[0], "--report-path", report, "--months-path", months, "--labels-path", labels]
    base.main()
    p = Path(report)
    r = json.loads(p.read_text(encoding="utf-8"))
    r["stage"] = "26D"
    r["name"] = "aligned_exact_bound_audit"
    r["label_version"] = "set_value_next20_fixed_ols_v2"
    r["semantic_repair"] = "exactly next 20 trading signal days after decision date; aligns MILP with frozen greedy/local Stage26"
    m = pd.read_csv(months)
    certified = (m["solver_primary_status"] == 0)
    mincard = certified & (m["solver_secondary_status"] == 0)
    violation = certified & (m["oracle_log"] + 1e-9 < m["best_singleton_log"])
    r["certification"] = {
        "months": int(len(m)),
        "primary_exact_months": int(certified.sum()),
        "min_cardinality_exact_months": int(mincard.sum()),
        "certified_singleton_violations": int(violation.sum()),
        "primary_exact_2025_26": int((certified & (pd.to_datetime(m["decision_date"]).dt.year >= 2025)).sum()),
    }
    p.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
