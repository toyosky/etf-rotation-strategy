#!/usr/bin/env python3
"""MUV Stage 2: strict expanding-window two-stage retention model.

No random split and no hyperparameter search.

Stage A
    P(ETF changes next-month OLS/portfolio path | X_t)

Stage B
    E(delta_return | path changes, X_t)

Combined expected marginal value
    P(path change) * conditional expected delta_return

We compare a conservative conditional-value model using only relatively stable
context features with a larger version that also includes own trend-strength
features.  This is an OOS diagnostic, not yet a multi-removal portfolio backtest.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.compose import TransformedTargetRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, roc_auc_score, mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

INPUT = Path("muv-retention-labels-v1.parquet")
OUT_JSON = Path("muv-retention-stage2-report.json")
OUT_PRED = Path("muv-retention-stage2-predictions.csv")
START_TEST = "2023-01"
EPS = 1e-10

STAGE_A_FEATURES = [
    "own_score_ratio_top1",
    "top3_freq20",
    "days_since_top1",
    "x_score",
    "x_r2",
    "x_score_delta",
]

VALUE_CONTEXT_FEATURES = [
    "asof_top1_margin",
    "asof_top1_score",
    "x_r2_delta",
    "x_current_resid",
    "x_efficiency10",
]

VALUE_PLUS_STRENGTH_FEATURES = VALUE_CONTEXT_FEATURES + [
    "x_score",
    "x_ret10",
    "x_ret20",
    "own_score_ratio_top1",
]


def xpipe(model):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
        ("model", model),
    ])


def safe_auc(y, p):
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    if len(np.unique(y)) < 2:
        return None
    return float(roc_auc_score(y, p))


def safe_spearman(y, p):
    z = pd.DataFrame({"y": y, "p": p}).dropna()
    if len(z) < 10 or z.y.nunique() < 3 or z.p.nunique() < 3:
        return None
    r = spearmanr(z.y, z.p).statistic
    return float(r) if np.isfinite(r) else None


def safe_pearson(y, p):
    z = pd.DataFrame({"y": y, "p": p}).dropna()
    if len(z) < 3 or z.y.std() == 0 or z.p.std() == 0:
        return None
    return float(z.y.corr(z.p, method="pearson"))


def metrics(g: pd.DataFrame, pred_col: str) -> dict:
    return {
        "rows": int(len(g)),
        "months": int(g.label_month.nunique()),
        "spearman_delta": safe_spearman(g.delta_return, g[pred_col]),
        "pearson_delta": safe_pearson(g.delta_return, g[pred_col]),
        "mae_delta": float(mean_absolute_error(g.delta_return, g[pred_col])),
        "positive_sign_auc_all": safe_auc((g.delta_return > EPS).astype(int), g[pred_col]),
    }


def conditional_metrics(g: pd.DataFrame, pred_col: str) -> dict:
    z = g[g.path_active].copy()
    return {
        "rows": int(len(z)),
        "months": int(z.label_month.nunique()),
        "spearman_delta": safe_spearman(z.delta_return, z[pred_col]),
        "pearson_delta": safe_pearson(z.delta_return, z[pred_col]),
        "mae_delta": float(mean_absolute_error(z.delta_return, z[pred_col])) if len(z) else None,
        "positive_sign_auc": safe_auc((z.delta_return > EPS).astype(int), z[pred_col]) if len(z) else None,
        "pred_positive_share": float((z[pred_col] > 0).mean()) if len(z) else None,
        "actual_positive_share": float((z.delta_return > EPS).mean()) if len(z) else None,
    }


def bucket_summary(df: pd.DataFrame, pred_col: str) -> list[dict]:
    z = df[[pred_col, "delta_return", "path_active"]].dropna().copy()
    if z[pred_col].nunique() < 5:
        return []
    z["bucket"] = pd.qcut(z[pred_col], 5, labels=False, duplicates="drop") + 1
    out = []
    for b, g in z.groupby("bucket"):
        out.append({
            "bucket": int(b),
            "rows": int(len(g)),
            "pred_mean": float(g[pred_col].mean()),
            "actual_delta_mean": float(g.delta_return.mean()),
            "actual_delta_median": float(g.delta_return.median()),
            "path_effect_rate": float(g.path_active.mean()),
            "positive_rate": float((g.delta_return > EPS).mean()),
            "negative_rate": float((g.delta_return < -EPS).mean()),
        })
    return out


def period_label(month: str) -> str:
    y = int(month[:4])
    return "2023-24" if y <= 2024 else "2025-26"


def main():
    df = pd.read_parquet(INPUT)
    df["label_month"] = df["label_month"].astype(str)
    df["path_active"] = (
        pd.to_numeric(df["path_direct_selection_days"], errors="coerce").fillna(0) > 0
    )
    df["delta_return"] = pd.to_numeric(df["delta_return"], errors="coerce")

    required = set(STAGE_A_FEATURES + VALUE_PLUS_STRENGTH_FEATURES)
    miss = required - set(df.columns)
    if miss:
        raise RuntimeError(f"features missing: {sorted(miss)}")

    months = sorted(m for m in df.label_month.unique() if m >= START_TEST)
    preds = []

    for test_month in months:
        train = df[df.label_month < test_month].copy()
        test = df[df.label_month == test_month].copy()
        if len(test) == 0:
            continue

        # Fixed architecture; no C / alpha selection.
        clf = xpipe(LogisticRegression(C=1.0, max_iter=2000, solver="lbfgs"))
        clf.fit(train[STAGE_A_FEATURES], train.path_active.astype(int))
        p_active = clf.predict_proba(test[STAGE_A_FEATURES])[:, 1]

        active_train = train[train.path_active].copy()
        if len(active_train) < 30:
            continue

        reg_context = xpipe(Ridge(alpha=1.0))
        reg_plus = xpipe(Ridge(alpha=1.0))
        reg_context.fit(active_train[VALUE_CONTEXT_FEATURES], active_train.delta_return)
        reg_plus.fit(active_train[VALUE_PLUS_STRENGTH_FEATURES], active_train.delta_return)

        cond_context = reg_context.predict(test[VALUE_CONTEXT_FEATURES])
        cond_plus = reg_plus.predict(test[VALUE_PLUS_STRENGTH_FEATURES])
        train_cond_mean = float(active_train.delta_return.mean())

        out = test[["label_month", "asof_date", "symbol", "delta_return"]].copy()
        out["path_active"] = test.path_active.to_numpy()
        out["p_active"] = p_active
        out["cond_context"] = cond_context
        out["cond_plus_strength"] = cond_plus
        out["cond_mean_baseline"] = train_cond_mean
        out["muv_relevance_only"] = p_active * train_cond_mean
        out["muv_context"] = p_active * cond_context
        out["muv_plus_strength"] = p_active * cond_plus
        out["oos_period"] = period_label(test_month)
        out["train_months"] = int(train.label_month.nunique())
        out["train_rows"] = int(len(train))
        out["train_active_rows"] = int(len(active_train))
        preds.append(out)

    if not preds:
        raise RuntimeError("no OOS predictions")
    p = pd.concat(preds, ignore_index=True)
    p.to_csv(OUT_PRED, index=False)

    model_cols = ["muv_relevance_only", "muv_context", "muv_plus_strength"]
    report = {
        "design": {
            "test_start": START_TEST,
            "split": "monthly expanding window; test month uses only earlier label months",
            "stage_a_features": STAGE_A_FEATURES,
            "value_context_features": VALUE_CONTEXT_FEATURES,
            "value_plus_strength_features": VALUE_PLUS_STRENGTH_FEATURES,
            "stage_a_model": "LogisticRegression L2 C=1 fixed",
            "stage_b_model": "Ridge alpha=1 fixed, trained only on prior path-active rows",
            "hyperparameter_search": False,
            "portfolio_backtest": False,
        },
        "oos": {
            "rows": int(len(p)),
            "months": int(p.label_month.nunique()),
            "month_min": str(p.label_month.min()),
            "month_max": str(p.label_month.max()),
            "path_prevalence": float(p.path_active.mean()),
            "stage_a_auc": safe_auc(p.path_active.astype(int), p.p_active),
            "stage_a_brier": float(brier_score_loss(p.path_active.astype(int), p.p_active)),
            "stage_a_pred_mean": float(p.p_active.mean()),
        },
        "combined_models": {},
        "conditional_value_models": {
            "context": conditional_metrics(p, "cond_context"),
            "plus_strength": conditional_metrics(p, "cond_plus_strength"),
        },
        "by_period": {},
        "buckets": {},
        "notes": [
            "Predictions are genuinely forward by label month; no random CV is used.",
            "The zero threshold is not used to construct a multi-removal universe backtest because remove-one labels are not additive.",
            "Relevance-only uses the expanding historical mean conditional value, so it isolates the information in P(path change).",
            "Bucket summaries are evaluation diagnostics, not production cutoffs.",
        ],
    }

    for c in model_cols:
        report["combined_models"][c] = metrics(p, c)
        report["buckets"][c] = bucket_summary(p, c)

    for per, g in p.groupby("oos_period"):
        report["by_period"][per] = {
            "rows": int(len(g)),
            "months": int(g.label_month.nunique()),
            "stage_a_auc": safe_auc(g.path_active.astype(int), g.p_active),
            "stage_a_brier": float(brier_score_loss(g.path_active.astype(int), g.p_active)),
            "models": {c: metrics(g, c) for c in model_cols},
            "conditional_context": conditional_metrics(g, "cond_context"),
            "conditional_plus_strength": conditional_metrics(g, "cond_plus_strength"),
        }

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
