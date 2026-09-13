#!/usr/bin/env python3
"""Stage19 dynamic replacement reachability audit.

Strict monthly expanding OOS candidate ranking. No policy backtest or threshold
search. Compares a frozen static current-score baseline with a fixed logistic
ranker using only pairwise score/rank trajectory state available at the as-of.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

INPUT = Path("muv-retention-stage19-pairs.parquet")
OUT = Path("muv-retention-stage19-report.json")
OUT_RANKS = Path("muv-retention-stage19-event-ranks.csv")
START_TEST = "2023-01"

FEATURES = [
    "x_pair_current_gap_j_minus_i",
    "x_pair_i_qualified_now",
    "x_pair_j_qualified_now",
    "x_pair_i_qualified_frac20",
    "x_pair_j_qualified_frac20",
    "x_pair_both_qualified_frac20",
    "x_pair_gap_mean20",
    "x_pair_gap_std20",
    "x_pair_gap_slope20",
    "x_pair_gap_crossings20",
    "x_pair_j_beats_i_frac20",
    "x_pair_both_top3_frac20",
    "x_pair_j_top1_frac20",
    "x_pair_j_top3_frac20",
]


def pipe():
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, solver="lbfgs")),
    ])


def period(month: str) -> str:
    return "2023-24" if int(str(month)[:4]) <= 2024 else "2025-26"


def metrics(g: pd.DataFrame, rank_col: str) -> dict:
    z = pd.to_numeric(g[rank_col], errors="coerce")
    return {
        "n_events": int(len(g)),
        "hit_at_1": float((z == 1).mean()) if len(g) else None,
        "hit_at_3": float((z <= 3).fillna(False).mean()) if len(g) else None,
        "mrr": float((1.0 / z).replace([np.inf, -np.inf], np.nan).fillna(0).mean()) if len(g) else None,
        "median_rank": float(z.dropna().median()) if z.notna().any() else None,
    }


def main() -> None:
    df = pd.read_parquet(INPUT)
    df["label_month"] = df["label_month"].astype(str)
    missing = set(FEATURES) - set(df.columns)
    if missing:
        raise RuntimeError(f"Stage19 features missing: {sorted(missing)}")

    all_events = df[["event_id", "label_month", "is_cash_event"]].drop_duplicates()
    cash_share = float(all_events["is_cash_event"].mean()) if len(all_events) else None
    noncash = df[~df["is_cash_event"]].copy()
    months = sorted(m for m in noncash["label_month"].unique() if m >= START_TEST)
    event_rows = []

    for m in months:
        tr = noncash[noncash["label_month"] < m].copy()
        te = noncash[noncash["label_month"] == m].copy()
        if te.empty or tr["event_id"].nunique() < 20 or tr["y_is_dominant_replacement"].nunique() < 2:
            continue
        model = pipe()
        model.fit(tr[FEATURES], tr["y_is_dominant_replacement"].astype(int))
        te["p_replacement"] = model.predict_proba(te[FEATURES])[:, 1]

        for event_id, g in te.groupby("event_id"):
            g = g.copy()
            pos = g[g["y_is_dominant_replacement"] == 1]
            if len(pos) != 1:
                continue
            target = str(pos.iloc[0]["candidate"])
            g["dynamic_rank"] = g["p_replacement"].rank(method="min", ascending=False)
            target_row = g[g["candidate"] == target].iloc[0]
            static_rank = pd.to_numeric(pd.Series([target_row["static_score_rank"]]), errors="coerce").iloc[0]
            event_rows.append({
                "event_id": int(event_id),
                "label_month": m,
                "oos_period": period(m),
                "incumbent": str(target_row["incumbent"]),
                "dominant_replacement": target,
                "static_rank": float(static_rank) if pd.notna(static_rank) else np.nan,
                "dynamic_rank": float(target_row["dynamic_rank"]),
                "dynamic_probability": float(target_row["p_replacement"]),
                "dominant_share": float(target_row["disp_direct_dominant_share"]) if pd.notna(target_row["disp_direct_dominant_share"]) else np.nan,
            })

    ev = pd.DataFrame(event_rows)
    if ev.empty:
        raise RuntimeError("Stage19 produced no OOS event ranks")
    ev.to_csv(OUT_RANKS, index=False)

    overall_static = metrics(ev, "static_rank")
    overall_dynamic = metrics(ev, "dynamic_rank")
    by_period = {}
    period_improvements = []
    for p, g in ev.groupby("oos_period"):
        s = metrics(g, "static_rank")
        d = metrics(g, "dynamic_rank")
        delta = {"hit_at_3": d["hit_at_3"] - s["hit_at_3"], "mrr": d["mrr"] - s["mrr"]}
        by_period[str(p)] = {"static": s, "dynamic": d, "delta_dynamic_minus_static": delta}
        period_improvements.append(delta)

    stable = (
        overall_dynamic["hit_at_3"] >= overall_static["hit_at_3"]
        and overall_dynamic["mrr"] >= overall_static["mrr"]
        and all(x["hit_at_3"] >= 0 and x["mrr"] >= 0 for x in period_improvements)
    )

    report = {
        "version": "muv_stage19_dynamic_replacement_reachability_20260913",
        "frozen_question": "Can point-in-time i-j score/rank trajectory state rank the next-month realized dominant non-cash replacement better than static month-end score rank?",
        "design": {
            "label_semantics": "reuse V1.6 realized dominant replacement; no label change",
            "test_start": START_TEST,
            "split": "strict monthly expanding OOS",
            "model": "LogisticRegression L2 C=1 class_weight=balanced fixed",
            "feature_search": False,
            "hyperparameter_search": False,
            "threshold_search": False,
            "policy_backtest": False,
            "cash_events_excluded_from_candidate_ranking": True
        },
        "coverage": {"all_active_events": int(all_events.event_id.nunique()), "dominant_cash_event_share": cash_share, "oos_noncash_events": int(len(ev))},
        "overall": {"static_score_baseline": overall_static, "dynamic_pairwise": overall_dynamic},
        "by_period": by_period,
        "predeclared_interpretation": {
            "stable_incremental_reachability": bool(stable),
            "rule": "Treat dynamic reachability as supported only if hit@3 and MRR do not deteriorate overall and improve/non-deteriorate in both 2023-24 and 2025-26. Do not tune feature subsets or cutoffs on this sample."
        }
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
