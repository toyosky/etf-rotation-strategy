#!/usr/bin/env python3
"""MUV Stage 9: second-removal Oracle headroom after frozen Stage-7 action.

This is NOT a predictive policy. It asks a narrower economic question:

    Once the frozen Stage-7 primary policy has safely removed one ETF,
    is there enough additional counterfactual value in a second removal
    to justify building a true dynamic sequential model?

The second removal is future-aware Oracle and is used only as an upper-bound /
headroom diagnostic. No Stage-7 action is changed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from full_market_ols_storage import _db_url, build_features
from universe.oracle_replacement_v1 import FIXED15, CASH_SIGNAL
from build_retention_labels_v1 import (
    _target,
    load_fixed15_bars,
    monthly_metrics,
    prepare_wides,
    rank_pool,
)

MONTHLY = Path("muv-retention-stage7-monthly-policy.csv")
OUT = Path("muv-retention-stage9-report.json")
OUT_MONTHLY = Path("muv-retention-stage9-second-removal-oracle.csv")
EPS = 1e-12


def wealth(r) -> float:
    a = np.asarray(r, dtype=float)
    return float(np.prod(1.0 + a))


def month_setup(calendar: pd.Index, baseline_ranked: pd.Series, label_period: pd.Period):
    candidates = calendar[
        pd.Index([pd.Timestamp(d).to_period("M") == label_period for d in calendar])
    ]
    if len(candidates) == 0:
        raise RuntimeError(f"No execution dates for {label_period}")
    first_exec = pd.Timestamp(candidates[0])
    first_pos = int(calendar.get_loc(first_exec))
    if first_pos == 0:
        raise RuntimeError(f"No prior signal for {label_period}")
    prev_signal_pos = first_pos - 2
    initial_prev = None
    if prev_signal_pos >= 0:
        initial_prev = _target(baseline_ranked.iloc[prev_signal_pos])
    return initial_prev


def normalize_symbol(v) -> str:
    s = str(v)
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(6)


def main() -> None:
    db = os.getenv("ETF_DAILY_BARS_DATABASE_URL")
    if not db:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    m = pd.read_csv(MONTHLY)
    m["label_month"] = m.label_month.astype(str)
    primary = m[m.act_primary_regime90].copy()
    if primary.empty:
        raise RuntimeError("Stage7 primary has no action months")

    engine = create_engine(_db_url(db), pool_pre_ping=True)
    bars = load_fixed15_bars(engine)
    features = build_features(bars)
    calendar, score, _, _, oo, _, _ = prepare_wides(bars, features)
    baseline_ranked, _ = rank_pool(score, set(FIXED15))

    details = []
    max_sanity_diff = 0.0
    for _, r in primary.iterrows():
        mo = str(r.label_month)
        lp = pd.Period(mo, freq="M")
        first = normalize_symbol(r.symbol_primary_regime90)
        if first not in FIXED15 or first == CASH_SIGNAL:
            raise RuntimeError(f"Invalid Stage7 first removal {first} in {mo}")

        initial_prev = month_setup(calendar, baseline_ranked, lp)
        u1 = set(FIXED15) - {first}
        rank1, count1 = rank_pool(score, u1)
        met1 = monthly_metrics(rank1, count1, oo, calendar, lp, initial_prev)
        stage7_ret = float(r.ret_primary_regime90)
        sanity = abs(float(met1["total_return"]) - stage7_ret)
        max_sanity_diff = max(max_sanity_diff, sanity)

        candidates = []
        for second in sorted(u1 - {CASH_SIGNAL}):
            u2 = u1 - {second}
            rank2, count2 = rank_pool(score, u2)
            met2 = monthly_metrics(rank2, count2, oo, calendar, lp, initial_prev)
            add = float(met2["total_return"] - met1["total_return"])
            candidates.append((add, second, met2))

        candidates.sort(key=lambda z: (z[0], z[1]), reverse=True)
        best_add, best_second, best_met = candidates[0]
        use_second = bool(best_add > EPS)
        ret2 = float(best_met["total_return"] if use_second else met1["total_return"])
        details.append({
            "label_month": mo,
            "first_removed_stage7": first,
            "stage7_return": float(met1["total_return"]),
            "best_second_removed_oracle": best_second if use_second else None,
            "oracle_second_positive": use_second,
            "oracle_second_additional_return": float(max(best_add, 0.0)),
            "oracle_two_removal_return": ret2,
            "best_raw_second_delta": float(best_add),
            "first_stage7_improvement_vs_keep_all": float(r.improvement_primary_regime90),
        })

    if max_sanity_diff > 1e-10:
        raise RuntimeError(f"Stage9 first-removal return does not reproduce Stage7; max diff={max_sanity_diff}")

    d = pd.DataFrame(details).sort_values("label_month").reset_index(drop=True)
    d.to_csv(OUT_MONTHLY, index=False)

    # Chain the Oracle second-removal return only in Stage7 action months.
    two = m[["label_month", "base_return", "ret_primary_regime90"]].copy()
    two = two.merge(
        d[["label_month", "oracle_two_removal_return", "oracle_second_positive"]],
        on="label_month", how="left", validate="one_to_one"
    )
    two["ret_stage7_plus_oracle_second"] = two.ret_primary_regime90
    mask = two.oracle_second_positive.fillna(False)
    two.loc[mask, "ret_stage7_plus_oracle_second"] = two.loc[mask, "oracle_two_removal_return"]

    fw_base = wealth(two.base_return)
    fw_stage7 = wealth(two.ret_primary_regime90)
    fw_two = wealth(two.ret_stage7_plus_oracle_second)

    positive = d[d.oracle_second_positive].copy()
    period = {}
    for name, pmask in {
        "2023-24": two.label_month.str[:4].astype(int).le(2024),
        "2025-26": two.label_month.str[:4].astype(int).ge(2025),
    }.items():
        g = two[pmask]
        p = d[d.label_month.isin(g.label_month)]
        f1 = wealth(g.ret_primary_regime90)
        f2 = wealth(g.ret_stage7_plus_oracle_second)
        period[name] = {
            "stage7_action_months": int(p.shape[0]),
            "months_with_positive_second_oracle": int(p.oracle_second_positive.sum()),
            "stage7_final_wealth": f1,
            "stage7_plus_second_oracle_final_wealth": f2,
            "incremental_terminal_wealth_vs_stage7": float(f2 / f1 - 1.0),
            "sum_oracle_second_additional_monthly_return": float(p.oracle_second_additional_return.sum()),
        }

    report = {
        "design": {
            "first_removal": "frozen Stage7 primary_regime90 action; never changed",
            "second_removal": "future-aware best additional removal after first removal; Oracle headroom only",
            "max_second_removals": 1,
            "model_fitted": False,
            "purpose": "decide whether true dynamic multi-step retention is worth building",
        },
        "sanity": {
            "stage7_action_months": int(len(d)),
            "max_abs_reproduced_stage7_return_diff": float(max_sanity_diff),
        },
        "headroom": {
            "months_with_positive_second_oracle": int(d.oracle_second_positive.sum()),
            "share_action_months_with_positive_second_oracle": float(d.oracle_second_positive.mean()),
            "sum_additional_monthly_return": float(d.oracle_second_additional_return.sum()),
            "mean_additional_return_all_action_months": float(d.oracle_second_additional_return.mean()),
            "mean_additional_return_positive_months": float(positive.oracle_second_additional_return.mean()) if len(positive) else 0.0,
            "median_additional_return_positive_months": float(positive.oracle_second_additional_return.median()) if len(positive) else 0.0,
            "max_additional_return": float(d.oracle_second_additional_return.max()),
        },
        "wealth": {
            "keep_all_final_wealth": fw_base,
            "stage7_final_wealth": fw_stage7,
            "stage7_relative_vs_keep_all": float(fw_stage7 / fw_base - 1.0),
            "stage7_plus_oracle_second_final_wealth": fw_two,
            "incremental_terminal_wealth_vs_stage7": float(fw_two / fw_stage7 - 1.0),
            "relative_terminal_wealth_vs_keep_all": float(fw_two / fw_base - 1.0),
        },
        "by_period": period,
        "positive_second_oracle_months": positive.sort_values(
            "oracle_second_additional_return", ascending=False
        ).to_dict(orient="records"),
        "notes": [
            "The second-removal result is intentionally future-aware and is not a tradable result.",
            "Only months where Stage7 primary actually made a first removal are examined.",
            "A large second-step Oracle headroom would justify engineering a true reduced-universe prediction engine; small headroom would argue for keeping max one removal.",
            "Monthly execution / initial-position convention is kept identical to the existing retention label engine for comparability.",
        ],
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
