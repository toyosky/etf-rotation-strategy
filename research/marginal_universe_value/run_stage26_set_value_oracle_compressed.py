#!/usr/bin/env python3
"""Mechanical Stage26 runner: remove provably irrelevant never-active candidates before exact MILP.

This does not change the Stage26 set-value objective, label semantics, downstream OLS rule,
or minimum-cardinality tie-break. Any ETF that is never trend-eligible on any signal day
cannot become the selected OLS target for any subset, so excluding it from the MILP is exact.
"""
from __future__ import annotations

import numpy as np

import model_stage26_set_value_oracle as base

_ORIG_SOLVE = base.solve_oracle


def solve_oracle_compressed(symbols, active_ranked, logret):
    n = len(symbols)
    relevant = sorted({i for ranked in active_ranked for i in ranked})
    if not relevant:
        return set(), {
            "status": "empty_active_union",
            "primary_fun": 0.0,
            "secondary_status": "empty_active_union",
            "original_candidate_count": n,
            "milp_candidate_count": 0,
        }
    if len(relevant) == n:
        subset, meta = _ORIG_SOLVE(symbols, active_ranked, logret)
        meta["original_candidate_count"] = n
        meta["milp_candidate_count"] = n
        return subset, meta

    old_to_new = {old: new for new, old in enumerate(relevant)}
    reduced_symbols = [symbols[i] for i in relevant]
    reduced_ranked = [[old_to_new[i] for i in ranked if i in old_to_new] for ranked in active_ranked]
    reduced_logret = np.asarray(logret)[:, relevant]

    reduced_subset, meta = _ORIG_SOLVE(reduced_symbols, reduced_ranked, reduced_logret)
    subset = {relevant[i] for i in reduced_subset}
    meta["original_candidate_count"] = n
    meta["milp_candidate_count"] = len(relevant)
    meta["exact_preprocessing"] = "drop_never_active_candidates"
    return subset, meta


base.solve_oracle = solve_oracle_compressed

if __name__ == "__main__":
    base.main()
