#!/usr/bin/env python3
"""MUV Stage 3: pairwise alternative sign model, strict expanding OOS.

Stage A is retained from Stage 2 because it validated OOS.
Stage B is reformulated from unstable continuous regression into:

    P(delta_return > 0 | path_active, X_t)

where X_t explicitly describes ETF i relative to the strongest currently
qualified alternative if i were excluded at the decision date.

Magnitude is intentionally not regressed.  We use expanding historical means
of positive and negative active deltas separately, so the experiment isolates
whether pairwise features improve sign discrimination without introducing
fragile tail extrapolation.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

INPUT = Path("muv-retention-labels-v1.parquet")
OUT_JSON = Path("muv-retention-stage3-report.json")
OUT_PRED = Path("muv-retention-stage3-predictions.csv")
START_TEST = "2023-01"
EPS = 1e-10

STAGE_A_FEATURES = [
    "own_score_ratio_top1", "top3_freq20", "days_since_top1",
    "x_score", "x_r2", "x_score_delta",
]

CONTEXT_FEATURES = [
    "asof_top1_margin", "asof_top1_score", "x_r2_delta",
    "x_current_resid", "x_efficiency10",
]

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


def rho(y, p):
    z = pd.DataFrame({"y": y, "p": p}).dropna()
    if len(z) < 10 or z.y.nunique() < 3 or z.p.nunique() < 3:
        return None
    r = spearmanr(z.y, z.p).statistic
    return float(r) if np.isfinite(r) else None


def period(month: str):
    return "2023-24" if int(month[:4]) <= 2024 else "2025-26"


def summarize(g: pd.DataFrame, muv_col: str, sign_col: str):
    active = g[g.path_active]
    return {
        "rows": int(len(g)),
        "months": int(g.label_month.nunique()),
        "muv_spearman": rho(g.delta_return, g[muv_col]),
        "muv_mae": float(mean_absolute_error(g.delta_return, g[muv_col])),
        "positive_auc_all": auc((g.delta_return > EPS).astype(int), g[muv_col]),
        "active_rows": int(len(active)),
        "active_sign_auc": auc((active.delta_return > EPS).astype(int), active[sign_col]) if len(active) else None,
        "active_sign_brier": float(brier_score_loss((active.delta_return > EPS).astype(int), active[sign_col])) if len(active) else None,
        "active_actual_positive_share": float((active.delta_return > EPS).mean()) if len(active) else None,
        "active_pred_positive_mean": float(active[sign_col].mean()) if len(active) else None,
    }


def bucket(g: pd.DataFrame, col: str):
    z = g[[col, "delta_return", "path_active"]].dropna().copy()
    if len(z) < 50 or z[col].nunique() < 5:
        return []
    z["bucket"] = pd.qcut(z[col], 5, labels=False, duplicates="drop") + 1
    out = []
    for b, h in z.groupby("bucket"):
        out.append({
            "bucket": int(b), "n": int(len(h)),
            "pred_mean": float(h[col].mean()),
            "actual_delta_mean": float(h.delta_return.mean()),
            "path_rate": float(h.path_active.mean()),
            "positive_rate": float((h.delta_return > EPS).mean()),
            "negative_rate": float((h.delta_return < -EPS).mean()),
        })
    return out


def main():
    df = pd.read_parquet(INPUT)
    df["label_month"] = df.label_month.astype(str)
    df["delta_return"] = pd.to_numeric(df.delta_return, errors="coerce")
    df["path_active"] = pd.to_numeric(df.path_direct_selection_days, errors="coerce").fillna(0) > 0

    req = set(STAGE_A_FEATURES + CONTEXT_FEATURES + PAIRWISE_FEATURES)
    missing = req - set(df.columns)
    if missing:
        raise RuntimeError(f"V1.3 pairwise features missing: {sorted(missing)}")

    months = sorted(m for m in df.label_month.unique() if m >= START_TEST)
    outs = []
    for m in months:
        tr = df[df.label_month < m].copy()
        te = df[df.label_month == m].copy()
        if te.empty:
            continue

        # Stage A relevance probability.
        a = pipe_logit()
        a.fit(tr[STAGE_A_FEATURES], tr.path_active.astype(int))
        p_active = a.predict_proba(te[STAGE_A_FEATURES])[:, 1]

        atr = tr[tr.path_active].copy()
        if len(atr) < 40 or atr.delta_return.gt(EPS).nunique() < 2:
            continue
        ysign = atr.delta_return.gt(EPS).astype(int)

        # Three fixed sign models: old context, pairwise only, and combined.
        feature_sets = {
            "context": CONTEXT_FEATURES,
            "pairwise": PAIRWISE_FEATURES,
            "context_pairwise": CONTEXT_FEATURES + PAIRWISE_FEATURES,
        }
        sign_preds = {}
        for name, cols in feature_sets.items():
            mod = pipe_logit()
            mod.fit(atr[cols], ysign)
            sign_preds[name] = mod.predict_proba(te[cols])[:, 1]

        pos = atr.loc[atr.delta_return > EPS, "delta_return"]
        neg = atr.loc[atr.delta_return < -EPS, "delta_return"]
        mean_pos = float(pos.mean()) if len(pos) else 0.0
        mean_neg = float(neg.mean()) if len(neg) else 0.0

        out = te[["label_month", "asof_date", "symbol", "delta_return"]].copy()
        out["path_active"] = te.path_active.to_numpy()
        out["p_active"] = p_active
        out["train_active_rows"] = len(atr)
        out["train_mean_positive_delta"] = mean_pos
        out["train_mean_negative_delta"] = mean_neg
        out["oos_period"] = period(m)
        for name, psign in sign_preds.items():
            cond = psign * mean_pos + (1.0 - psign) * mean_neg
            out[f"p_positive_{name}"] = psign
            out[f"cond_ev_{name}"] = cond
            out[f"muv_{name}"] = p_active * cond
        outs.append(out)

    p = pd.concat(outs, ignore_index=True)
    p.to_csv(OUT_PRED, index=False)

    report = {
        "design": {
            "dataset_version": str(df.dataset_version.iloc[0]),
            "test_start": START_TEST,
            "split": "monthly expanding; no random split",
            "hyperparameter_search": False,
            "stage_a_features": STAGE_A_FEATURES,
            "context_features": CONTEXT_FEATURES,
            "pairwise_features": PAIRWISE_FEATURES,
            "sign_model": "LogisticRegression L2 C=1 fixed",
            "magnitude_model": "none; expanding historical positive/negative active means",
        },
        "oos": {
            "rows": int(len(p)), "months": int(p.label_month.nunique()),
            "month_min": str(p.label_month.min()), "month_max": str(p.label_month.max()),
            "stage_a_auc": auc(p.path_active.astype(int), p.p_active),
            "stage_a_brier": float(brier_score_loss(p.path_active.astype(int), p.p_active)),
        },
        "models": {},
        "by_period": {},
        "buckets": {},
        "notes": [
            "Pairwise alternative identity is current decision-time strongest qualified alternative, never future realized replacement.",
            "Path/delta outcomes are never used in X.",
            "Separated positive/negative historical means prevent linear magnitude extrapolation; this is still an expected-value diagnostic, not a multi-removal backtest.",
        ],
    }

    for name in ["context", "pairwise", "context_pairwise"]:
        report["models"][name] = summarize(p, f"muv_{name}", f"p_positive_{name}")
        report["buckets"][name] = bucket(p, f"muv_{name}")

    for per, g in p.groupby("oos_period"):
        report["by_period"][per] = {
            "stage_a_auc": auc(g.path_active.astype(int), g.p_active),
            "models": {
                name: summarize(g, f"muv_{name}", f"p_positive_{name}")
                for name in ["context", "pairwise", "context_pairwise"]
            },
        }

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
