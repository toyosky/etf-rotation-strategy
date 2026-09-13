#!/usr/bin/env python3
"""MUV Stage 17: local relation-structure audit, strict expanding OOS.

Question: conditional on path activity, do a few ex-ante pairwise interactions
between local state gaps and correlation improve signed-MUV identification?

This script intentionally does not search interactions, thresholds, model
classes, or policy rules. It compares Stage-3's fixed pairwise logistic model
with one frozen relation-interaction extension.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

INPUT = Path("muv-retention-labels-v1.parquet")
OUT_JSON = Path("muv-retention-stage17-report.json")
OUT_PRED = Path("muv-retention-stage17-predictions.csv")
START_TEST = "2023-01"
EPS = 1e-10

PAIRWISE_FEATURES = [
    "pair_score_exact_gap_alt",
    "pair_r2_gap_alt",
    "pair_current_resid_gap_alt",
    "pair_ret10_gap_alt",
    "pair_ret20_gap_alt",
    "pair_efficiency10_gap_alt",
    "pair_vol20_gap_alt",
    "pair_ma10_dist_gap_alt",
    "pair_corr120_with_alt",
    "pair_top3_freq20_gap_alt",
]

INTERACTION_SPECS = {
    "score_gap_x_corr": ("pair_score_exact_gap_alt", "pair_corr120_with_alt"),
    "resid_gap_x_corr": ("pair_current_resid_gap_alt", "pair_corr120_with_alt"),
    "ret20_gap_x_corr": ("pair_ret20_gap_alt", "pair_corr120_with_alt"),
    "top3_gap_x_corr": ("pair_top3_freq20_gap_alt", "pair_corr120_with_alt"),
}


def pipe_logit():
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=1.0, max_iter=2000, solver="lbfgs")),
    ])


def auc(y, p):
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        return None
    return float(roc_auc_score(y, np.asarray(p, dtype=float)))


def period(month: str):
    return "2023-24" if int(month[:4]) <= 2024 else "2025-26"


def add_interactions(x: pd.DataFrame) -> pd.DataFrame:
    z = x.copy()
    for new_col, (a, b) in INTERACTION_SPECS.items():
        z[new_col] = pd.to_numeric(z[a], errors="coerce") * pd.to_numeric(z[b], errors="coerce")
    return z


def metrics(g: pd.DataFrame, pcol: str):
    if g.empty:
        return {
            "n": 0,
            "sign_auc": None,
            "brier": None,
            "false_negative_positive_regret_sum": 0.0,
            "correct_negative_value_sum": 0.0,
            "largest_positive_miss": None,
        }
    y = (g.delta_return > EPS).astype(int)
    pred_neg = g[pcol] < 0.5
    fn = g[pred_neg & (g.delta_return > EPS)]
    cn = g[pred_neg & (g.delta_return < -EPS)]
    return {
        "n": int(len(g)),
        "sign_auc": auc(y, g[pcol]),
        "brier": float(brier_score_loss(y, g[pcol])),
        "false_negative_positive_regret_sum": float(fn.delta_return.sum()) if len(fn) else 0.0,
        "correct_negative_value_sum": float((-cn.delta_return).sum()) if len(cn) else 0.0,
        "largest_positive_miss": float(fn.delta_return.max()) if len(fn) else None,
    }


def delta_metrics(base: dict, rel: dict):
    def sub(k):
        if base.get(k) is None or rel.get(k) is None:
            return None
        return float(rel[k] - base[k])
    return {
        "sign_auc_delta": sub("sign_auc"),
        "brier_delta": sub("brier"),
        "false_negative_positive_regret_sum_delta": sub("false_negative_positive_regret_sum"),
        "correct_negative_value_sum_delta": sub("correct_negative_value_sum"),
        "largest_positive_miss_delta": sub("largest_positive_miss"),
    }


def main():
    df = pd.read_parquet(INPUT)
    df["label_month"] = df.label_month.astype(str)
    df["delta_return"] = pd.to_numeric(df.delta_return, errors="coerce")
    df["path_active"] = pd.to_numeric(df.path_direct_selection_days, errors="coerce").fillna(0) > 0

    req = set(PAIRWISE_FEATURES)
    missing = req - set(df.columns)
    if missing:
        raise RuntimeError(f"Stage17 required features missing: {sorted(missing)}")

    df = add_interactions(df)
    relation_features = PAIRWISE_FEATURES + list(INTERACTION_SPECS)

    months = sorted(m for m in df.label_month.unique() if m >= START_TEST)
    outs = []
    for m in months:
        tr = df[(df.label_month < m) & df.path_active].copy()
        te = df[(df.label_month == m) & df.path_active].copy()
        if te.empty or len(tr) < 40:
            continue
        ytr = (tr.delta_return > EPS).astype(int)
        if ytr.nunique() < 2:
            continue

        base = pipe_logit()
        base.fit(tr[PAIRWISE_FEATURES], ytr)
        p_base = base.predict_proba(te[PAIRWISE_FEATURES])[:, 1]

        rel = pipe_logit()
        rel.fit(tr[relation_features], ytr)
        p_rel = rel.predict_proba(te[relation_features])[:, 1]

        out = te[["label_month", "asof_date", "symbol", "delta_return"]].copy()
        out["oos_period"] = period(m)
        out["p_positive_pairwise"] = p_base
        out["p_positive_relation"] = p_rel
        outs.append(out)

    p = pd.concat(outs, ignore_index=True)
    p.to_csv(OUT_PRED, index=False)

    overall_base = metrics(p, "p_positive_pairwise")
    overall_rel = metrics(p, "p_positive_relation")

    by_period = {}
    period_passes = []
    for per, g in p.groupby("oos_period"):
        bm = metrics(g, "p_positive_pairwise")
        rm = metrics(g, "p_positive_relation")
        dm = delta_metrics(bm, rm)
        auc_improves = (
            bm["sign_auc"] is not None and rm["sign_auc"] is not None
            and rm["sign_auc"] > bm["sign_auc"]
        )
        regret_not_worse = (
            rm["false_negative_positive_regret_sum"]
            <= bm["false_negative_positive_regret_sum"] + 1e-12
        )
        period_passes.append(bool(auc_improves and regret_not_worse))
        by_period[per] = {
            "pairwise_baseline": bm,
            "relation_interactions": rm,
            "delta_relation_minus_baseline": dm,
            "auc_improves": bool(auc_improves),
            "false_negative_regret_not_worse": bool(regret_not_worse),
        }

    stable_support = bool(len(period_passes) >= 2 and all(period_passes))

    report = {
        "version": "muv_stage17_local_relation_structure_20260913",
        "design": {
            "source": "existing point-in-time V1.3/V1.4 retention labels",
            "population": "path_active rows only",
            "test_start": START_TEST,
            "split": "monthly expanding; no random split",
            "baseline_features": PAIRWISE_FEATURES,
            "interaction_specs": INTERACTION_SPECS,
            "model": "LogisticRegression L2 C=1 fixed",
            "hyperparameter_search": False,
            "interaction_search": False,
            "threshold_search": False,
            "policy_backtest": False,
            "interpretation_rule": (
                "Support requires sign AUC improvement and non-worsening false-negative positive regret "
                "in both 2023-24 and 2025-26. Full-sample improvement alone is insufficient."
            ),
        },
        "overall": {
            "pairwise_baseline": overall_base,
            "relation_interactions": overall_rel,
            "delta_relation_minus_baseline": delta_metrics(overall_base, overall_rel),
        },
        "by_period": by_period,
        "stable_relation_structure_support": stable_support,
        "next_rule": (
            "If false, do not add more interactions immediately; move to a broader local-neighborhood/path-displacement representation audit."
        ),
    }

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
