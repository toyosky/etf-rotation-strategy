#!/usr/bin/env python3
"""MUV Stage 17: local-Universe relational identifiability audit.

Frozen question
---------------
Conditional on path activity, do a few point-in-time local-Universe
relationship variables add *stable expanding-window OOS* information about the
sign of retention MUV beyond the existing Stage-3 context + strongest-alt
pairwise representation?

No policy backtest, threshold search, feature search, tree/ensemble model, or
hyperparameter tuning is performed here.
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

import model_retention_stage3_pairwise_sign as s3

INPUT = Path("muv-retention-labels-v1.parquet")
OUT_REPORT = Path("muv-retention-stage17-report.json")
OUT_PRED = Path("muv-retention-stage17-predictions.csv")
START_TEST = "2023-01"
EPS = 1e-10

BASE_FEATURES = s3.CONTEXT_FEATURES + s3.PAIRWISE_FEATURES
LOCAL_FEATURES = [
    "local_own_minus_alt_top3_mean_score",
    "local_alt_top3_score_std",
    "local_alt1_minus_alt3_score",
    "local_corr120_top3_mean",
    "local_corr120_top3_max",
    "local_corr120_top3_std",
    "local_corr120_rest_mean",
    "local_corr120_rest_max",
    "local_corr120_top3_minus_rest_mean",
]
FULL_FEATURES = BASE_FEATURES + LOCAL_FEATURES


def pipe_logit():
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=1.0, max_iter=2000, solver="lbfgs")),
    ])


def auc(y, p):
    y = np.asarray(y, dtype=int)
    if len(y) < 10 or len(np.unique(y)) < 2:
        return None
    return float(roc_auc_score(y, np.asarray(p, dtype=float)))


def summarize(g: pd.DataFrame, pred_col: str) -> dict:
    if len(g) == 0:
        return {"n": 0, "auc": None, "brier": None, "positive_share": None}
    y = (g["delta_return"] > EPS).astype(int)
    return {
        "n": int(len(g)),
        "auc": auc(y, g[pred_col]),
        "brier": float(brier_score_loss(y, g[pred_col])) if y.nunique() >= 2 else None,
        "positive_share": float(y.mean()),
        "pred_positive_mean": float(g[pred_col].mean()),
    }


def period(month: str) -> str:
    return "2023-24" if int(str(month)[:4]) <= 2024 else "2025-26"


def main() -> None:
    df = pd.read_parquet(INPUT)
    df["label_month"] = df["label_month"].astype(str)
    df["delta_return"] = pd.to_numeric(df["delta_return"], errors="coerce")
    df["path_active"] = pd.to_numeric(df["path_direct_selection_days"], errors="coerce").fillna(0) > 0

    missing = set(FULL_FEATURES) - set(df.columns)
    if missing:
        raise RuntimeError(f"Stage17 local relational features missing: {sorted(missing)}")

    months = sorted(m for m in df["label_month"].unique() if m >= START_TEST)
    outs = []

    for m in months:
        tr = df[(df["label_month"] < m) & df["path_active"]].copy()
        te = df[(df["label_month"] == m) & df["path_active"]].copy()
        if te.empty or len(tr) < 40:
            continue

        y = (tr["delta_return"] > EPS).astype(int)
        if y.nunique() < 2:
            continue

        base = pipe_logit()
        full = pipe_logit()
        base.fit(tr[BASE_FEATURES], y)
        full.fit(tr[FULL_FEATURES], y)

        out = te[["label_month", "asof_date", "symbol", "delta_return"]].copy()
        out["oos_period"] = period(m)
        out["p_positive_base"] = base.predict_proba(te[BASE_FEATURES])[:, 1]
        out["p_positive_local"] = full.predict_proba(te[FULL_FEATURES])[:, 1]
        outs.append(out)

    if not outs:
        raise RuntimeError("Stage17 produced no OOS predictions")

    p = pd.concat(outs, ignore_index=True)
    p.to_csv(OUT_PRED, index=False)

    all_base = summarize(p, "p_positive_base")
    all_local = summarize(p, "p_positive_local")

    by_period = {}
    period_direction = []
    for per, g in p.groupby("oos_period"):
        b = summarize(g, "p_positive_base")
        l = summarize(g, "p_positive_local")
        auc_delta = None if b["auc"] is None or l["auc"] is None else float(l["auc"] - b["auc"])
        brier_delta = None if b["brier"] is None or l["brier"] is None else float(l["brier"] - b["brier"])
        by_period[str(per)] = {
            "base": b,
            "local_relational": l,
            "auc_delta_local_minus_base": auc_delta,
            "brier_delta_local_minus_base": brier_delta,
        }
        if auc_delta is not None:
            period_direction.append(auc_delta)

    overall_auc_delta = (
        None if all_base["auc"] is None or all_local["auc"] is None
        else float(all_local["auc"] - all_base["auc"])
    )
    overall_brier_delta = (
        None if all_base["brier"] is None or all_local["brier"] is None
        else float(all_local["brier"] - all_base["brier"])
    )

    # Predeclared qualitative interpretation; this is not a policy threshold.
    # We call the relation structurally supportive only if OOS AUC does not
    # deteriorate overall and the period deltas do not disagree in sign.
    same_nonnegative_direction = bool(period_direction) and all(x >= 0 for x in period_direction)
    same_nonpositive_direction = bool(period_direction) and all(x <= 0 for x in period_direction)

    report = {
        "version": "muv_stage17_local_relational_20260913",
        "frozen_question": (
            "Does local current-Universe relational state add stable OOS sign information "
            "conditional on path activity beyond Stage-3 context + strongest-alt pairwise state?"
        ),
        "design": {
            "dataset_required": "V1.5 local relational",
            "test_start": START_TEST,
            "split": "strict monthly expanding; active rows only; no random split",
            "model": "LogisticRegression L2 C=1 fixed",
            "baseline_features": BASE_FEATURES,
            "added_local_features": LOCAL_FEATURES,
            "feature_search": False,
            "hyperparameter_search": False,
            "threshold_search": False,
            "policy_backtest": False,
            "future_identity_features": False,
        },
        "overall": {
            "base": all_base,
            "local_relational": all_local,
            "auc_delta_local_minus_base": overall_auc_delta,
            "brier_delta_local_minus_base": overall_brier_delta,
        },
        "by_period": by_period,
        "direction_audit": {
            "period_auc_deltas": period_direction,
            "all_periods_nonnegative": same_nonnegative_direction,
            "all_periods_nonpositive": same_nonpositive_direction,
        },
        "interpretation_rule": (
            "Treat local-Universe structure as evidence only if improvement is broad and time-consistent. "
            "A single-period bump or attractive overall average is insufficient. If the added variables fail, "
            "do not tune subsets or thresholds on this sample; the next step should change the causal/relational "
            "representation (e.g. explicit path displacement labels), not search this feature family."
        ),
    }

    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
