#!/usr/bin/env python3
"""Stage26 exact-oracle infrastructure wrapper.

Research semantics are unchanged. This wrapper only increases the HiGHS wall-clock
budget used to certify the already-frozen MILP optimum after the exact dormant-candidate
preprocessing. No feature, label, objective, horizon, K, or tolerance is changed.
"""
from __future__ import annotations

import model_stage26_set_value_oracle as base
import run_stage26_set_value_oracle_compressed as compressed

_ORIG_MILP = base.milp


def milp_with_certification_budget(*args, **kwargs):
    options = dict(kwargs.get("options") or {})
    options["time_limit"] = 120.0
    kwargs["options"] = options
    return _ORIG_MILP(*args, **kwargs)


base.milp = milp_with_certification_budget
base.solve_oracle = compressed.solve_oracle_compressed

if __name__ == "__main__":
    base.main()
