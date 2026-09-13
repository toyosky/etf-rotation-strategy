#!/usr/bin/env python3
"""MUV Stage 18: explicit path-displacement audit.

No model is trained. The audit asks whether the point-in-time local competing
set contains the realized counterfactual replacement, and whether monthly MUV
is economically concentrated on direct displacement days rather than spillover.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

INPUT = Path("muv-retention-labels-v1.parquet")
OUT = Path("muv-retention-stage18-report.json")
OUT_ROWS = Path("muv-retention-stage18-active.csv")
EPS = 1e-10


def _rho(a, b):
    z = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(z) < 3 or z.a.nunique() < 2 or z.b.nunique() < 2:
        return None
    r = spearmanr(z.a, z.b).statistic
    return float(r) if np.isfinite(r) else None


def summarize(g: pd.DataFrame) -> dict:
    if g.empty:
        return {"n": 0}
    abs_total = g["delta_return"].abs()
    residual = g["delta_return"] - g["disp_direct_net_delta_sum"]
    dom = g["disp_direct_dominant_replacement"].notna()
    return {
        "n": int(len(g)),
        "dominant_label_available_n": int(dom.sum()),
        "asof_alt1_match_rate": float(g.loc[dom, "disp_dominant_matches_asof_alt1"].mean()) if dom.any() else None,
        "asof_top3_coverage_rate": float(g.loc[dom, "disp_dominant_in_asof_top3"].mean()) if dom.any() else None,
        "dominant_cash_rate": float((g.loc[dom, "disp_direct_dominant_replacement"] == "__CASH__").mean()) if dom.any() else None,
        "dominant_share_mean": float(g.loc[dom, "disp_direct_dominant_share"].mean()) if dom.any() else None,
        "dominant_share_median": float(g.loc[dom, "disp_direct_dominant_share"].median()) if dom.any() else None,
        "replacement_unique_count_mean": float(g["disp_direct_replacement_unique_count"].mean()),
        "direct_days_mean": float(g["disp_direct_days"].mean()),
        "spillover_changed_days_mean": float(g["disp_spillover_changed_days"].mean()),
        "direct_delta_vs_monthly_delta_spearman": _rho(g["disp_direct_net_delta_sum"], g["delta_return"]),
        "direct_delta_sign_agreement": float((np.sign(g["disp_direct_net_delta_sum"]) == np.sign(g["delta_return"])).mean()),
        "mean_abs_monthly_delta": float(abs_total.mean()),
        "mean_abs_direct_delta": float(g["disp_direct_net_delta_sum"].abs().mean()),
        "mean_abs_residual_monthly_minus_direct": float(residual.abs().mean()),
        "sum_abs_spillover_delta": float(g["disp_spillover_net_delta_sum"].abs().sum()),
    }


def period(month: str) -> str:
    return "2023-24" if int(str(month)[:4]) <= 2024 else "2025-26"


def main() -> None:
    df = pd.read_parquet(INPUT)
    required = {
        "label_month", "symbol", "delta_return", "path_direct_selection_days",
        "disp_direct_days", "disp_direct_replacement_unique_count",
        "disp_direct_dominant_replacement", "disp_direct_dominant_share",
        "disp_direct_net_delta_sum", "disp_spillover_net_delta_sum",
        "disp_spillover_changed_days", "disp_dominant_matches_asof_alt1",
        "disp_dominant_in_asof_top3",
    }
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Stage18 displacement labels missing: {sorted(missing)}")

    df["label_month"] = df["label_month"].astype(str)
    df["delta_return"] = pd.to_numeric(df["delta_return"], errors="coerce")
    active = df[pd.to_numeric(df["path_direct_selection_days"], errors="coerce").fillna(0) > 0].copy()
    active["oos_period"] = active["label_month"].map(period)
    active.to_csv(OUT_ROWS, index=False)

    report = {
        "version": "muv_stage18_explicit_displacement_audit_20260913",
        "frozen_question": (
            "Does the point-in-time local competing set identify the realized remove-one replacement, "
            "and is monthly retention MUV mainly generated on direct displacement days?"
        ),
        "design": {
            "new_model_fit": False,
            "feature_search": False,
            "threshold_search": False,
            "policy_backtest": False,
            "future_replacement_identity_is_label_only": True,
            "local_set": "as-of exact-score top3 alternatives frozen in V1.5",
        },
        "overall": summarize(active),
        "by_period": {str(p): summarize(g) for p, g in active.groupby("oos_period")},
        "interpretation_rule": (
            "If realized replacements are usually contained in the frozen as-of local set and direct-day deltas "
            "explain most monthly MUV with little spillover, proceed to a pairwise transition-value model. "
            "If coverage is weak or spillover is material, do not add more sign features; expand the state representation first."
        ),
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
