#!/usr/bin/env python3
"""Stage20 replacement emergence mechanism audit.

No model fit. Reuses Stage19 pair rows and OOS event IDs to determine whether
realized dominant replacements were already qualified/visible at the decision
as-of or emerged from outside the currently qualified set.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

PAIRS = Path("muv-retention-stage19-pairs.parquet")
EVENTS = Path("muv-retention-stage19-event-ranks.csv")
OUT = Path("muv-retention-stage20-report.json")
OUT_ROWS = Path("muv-retention-stage20-targets.csv")


def period(month: str) -> str:
    return "2023-24" if int(str(month)[:4]) <= 2024 else "2025-26"


def rank_metrics(g: pd.DataFrame) -> dict:
    z = pd.to_numeric(g["static_score_rank"], errors="coerce")
    return {
        "n_events": int(len(g)),
        "hit_at_1": float((z == 1).mean()) if len(g) else None,
        "hit_at_3": float((z <= 3).fillna(False).mean()) if len(g) else None,
        "mrr": float((1.0 / z).replace([np.inf, -np.inf], np.nan).fillna(0).mean()) if len(g) else None,
        "median_rank": float(z.dropna().median()) if z.notna().any() else None,
    }


def summarize(g: pd.DataFrame) -> dict:
    if g.empty:
        return {"n_events": 0}
    qnow = g["qualified_now"]
    return {
        "n_events": int(len(g)),
        "qualified_now_share": float(qnow.mean()),
        "emergent_recent_share": float(g["emergent_recent"].mean()),
        "dormant_20_share": float(g["dormant_20"].mean()),
        "top3_visible_recent_share": float(g["top3_visible_recent"].mean()),
        "top1_visible_recent_share": float(g["top1_visible_recent"].mean()),
        "qualified_frac20_mean": float(g["x_pair_j_qualified_frac20"].mean()),
        "qualified_frac20_median": float(g["x_pair_j_qualified_frac20"].median()),
        "top3_frac20_mean": float(g["x_pair_j_top3_frac20"].mean()),
        "top3_frac20_median": float(g["x_pair_j_top3_frac20"].median()),
        "static_rank_metrics_all": rank_metrics(g),
        "static_rank_metrics_qualified_now": rank_metrics(g[qnow]),
    }


def main() -> None:
    pairs = pd.read_parquet(PAIRS)
    events = pd.read_csv(EVENTS)
    event_ids = set(pd.to_numeric(events["event_id"], errors="coerce").dropna().astype(int))

    target = pairs[(pairs["event_id"].isin(event_ids)) & (pairs["y_is_dominant_replacement"] == 1)].copy()
    if target.empty:
        raise RuntimeError("Stage20 found no realized replacement rows from Stage19 OOS events")

    target["label_month"] = target["label_month"].astype(str)
    target["oos_period"] = target["label_month"].map(period)
    target["qualified_now"] = pd.to_numeric(target["x_pair_j_qualified_now"], errors="coerce").fillna(0) > 0
    qfrac = pd.to_numeric(target["x_pair_j_qualified_frac20"], errors="coerce").fillna(0)
    t3 = pd.to_numeric(target["x_pair_j_top3_frac20"], errors="coerce").fillna(0)
    t1 = pd.to_numeric(target["x_pair_j_top1_frac20"], errors="coerce").fillna(0)
    target["emergent_recent"] = (~target["qualified_now"]) & (qfrac > 0)
    target["dormant_20"] = (~target["qualified_now"]) & (qfrac == 0)
    target["top3_visible_recent"] = t3 > 0
    target["top1_visible_recent"] = t1 > 0

    keep = [
        "event_id", "label_month", "oos_period", "incumbent", "candidate",
        "static_score_rank", "qualified_now", "emergent_recent", "dormant_20",
        "top3_visible_recent", "top1_visible_recent",
        "x_pair_j_qualified_frac20", "x_pair_j_top3_frac20", "x_pair_j_top1_frac20",
        "disp_direct_dominant_share", "delta_return",
    ]
    target[keep].to_csv(OUT_ROWS, index=False)

    report = {
        "version": "muv_stage20_replacement_emergence_audit_20260913",
        "frozen_question": "How often does the next-month realized dominant replacement emerge from outside the currently qualified set, and was it already intermittently visible in the prior 20 trading days?",
        "design": {
            "new_model_fit": False,
            "feature_search": False,
            "threshold_search": False,
            "horizon_tuning": False,
            "policy_backtest": False,
            "oos_event_set": "exact Stage19 OOS non-cash replacement events",
            "category_thresholds": "literal occurrence only: >0 means observed at least once; no fitted cutoff",
        },
        "overall": summarize(target),
        "by_period": {str(p): summarize(g) for p, g in target.groupby("oos_period")},
        "interpretation_rule": (
            "If most failures are qualified-now, retain focus on ranking among known competitors. "
            "If a material persistent share is unqualified-now but recently visible, prioritize qualification/admission transition modeling. "
            "If many realized replacements are dormant for the full prior 20 days, recent score/rank state is structurally insufficient and a broader state representation is required."
        ),
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
