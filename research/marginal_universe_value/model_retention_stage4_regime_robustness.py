#!/usr/bin/env python3
"""MUV Stage 4: robustness of the pairwise sign signal to training horizon.

No feature search and no hyperparameter search.  The exact Stage-3 pairwise
feature set and LogisticRegression specification are frozen.  We compare only
information windows:

- expanding history
- trailing 36 label months
- trailing 24 label months

The purpose is diagnostic: determine whether the 2025-26 pairwise signal is
consistent with regime adaptation or is likely a small-sample accident.
Recent-period AUC uncertainty is estimated by resampling whole label months,
not individual ETF rows, preserving cross-sectional dependence within month.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

INPUT = Path("muv-retention-labels-v1.parquet")
OUT_JSON = Path("muv-retention-stage4-report.json")
OUT_PRED = Path("muv-retention-stage4-predictions.csv")
START_TEST = "2023-01"
EPS = 1e-10
SEED = 20260912
N_BOOT = 4000

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


def model():
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


def cutoff_month(test_month: str, window: int | None):
    if window is None:
        return None
    p = pd.Period(test_month, freq="M") - window
    return str(p)


def bootstrap_month_auc(g: pd.DataFrame, pred_col: str):
    z = g.loc[g.path_active, ["label_month", "positive", pred_col]].dropna().copy()
    months = np.array(sorted(z.label_month.unique()), dtype=object)
    observed = auc(z.positive, z[pred_col])
    if observed is None or len(months) < 6:
        return {"observed": observed, "n_months": int(len(months)), "n_rows": int(len(z))}
    rng = np.random.default_rng(SEED)
    vals = []
    grouped = {m: z[z.label_month == m] for m in months}
    for _ in range(N_BOOT):
        picks = rng.choice(months, size=len(months), replace=True)
        parts = [grouped[m] for m in picks]
        b = pd.concat(parts, ignore_index=True)
        v = auc(b.positive, b[pred_col])
        if v is not None:
            vals.append(v)
    a = np.asarray(vals, dtype=float)
    return {
        "observed": observed,
        "n_months": int(len(months)),
        "n_rows": int(len(z)),
        "bootstrap_valid": int(len(a)),
        "ci95_low": float(np.quantile(a, 0.025)) if len(a) else None,
        "ci95_high": float(np.quantile(a, 0.975)) if len(a) else None,
        "bootstrap_prob_auc_gt_0_5": float((a > 0.5).mean()) if len(a) else None,
    }


def main():
    df = pd.read_parquet(INPUT)
    df["label_month"] = df.label_month.astype(str)
    df["delta_return"] = pd.to_numeric(df.delta_return, errors="coerce")
    df["path_active"] = pd.to_numeric(df.path_direct_selection_days, errors="coerce").fillna(0) > 0
    df["positive"] = df.delta_return > EPS

    missing = set(PAIRWISE_FEATURES) - set(df.columns)
    if missing:
        raise RuntimeError(f"pairwise features missing: {sorted(missing)}")

    windows = {"expanding": None, "rolling36": 36, "rolling24": 24}
    months = sorted(m for m in df.label_month.unique() if m >= START_TEST)
    outs = []

    for m in months:
        test = df[df.label_month == m].copy()
        for name, win in windows.items():
            train = df[df.label_month < m].copy()
            cut = cutoff_month(m, win)
            if cut is not None:
                train = train[train.label_month >= cut]
            atr = train[train.path_active].copy()
            if len(atr) < 35 or atr.positive.nunique() < 2:
                continue
            mod = model()
            mod.fit(atr[PAIRWISE_FEATURES], atr.positive.astype(int))
            pred = mod.predict_proba(test[PAIRWISE_FEATURES])[:, 1]
            o = test[["label_month", "symbol", "path_active", "positive", "delta_return"]].copy()
            o["window"] = name
            o["p_positive"] = pred
            o["train_months"] = int(train.label_month.nunique())
            o["train_active_rows"] = int(len(atr))
            outs.append(o)

    p = pd.concat(outs, ignore_index=True)
    p.to_csv(OUT_PRED, index=False)

    report = {
        "design": {
            "dataset_version": str(df.dataset_version.iloc[0]),
            "features": PAIRWISE_FEATURES,
            "model": "LogisticRegression L2 C=1 fixed",
            "test_start": START_TEST,
            "windows": windows,
            "bootstrap": f"{N_BOOT} whole-month resamples; seed={SEED}",
            "hyperparameter_search": False,
        },
        "windows": {},
        "recent_bootstrap_2025_26": {},
        "yearly": {},
        "notes": [
            "A rolling window is not selected as a production parameter here; all predeclared windows are reported.",
            "Bootstrap resamples months to preserve dependence among ETFs evaluated in the same month.",
            "AUC is evaluated only on realized path-active rows because Stage B is conditional on participation.",
        ],
    }

    for name in windows:
        g = p[p.window == name]
        a = g[g.path_active]
        report["windows"][name] = {
            "rows": int(len(g)),
            "months": int(g.label_month.nunique()),
            "active_rows": int(len(a)),
            "active_auc_all": auc(a.positive, a.p_positive),
            "active_brier_all": float(brier_score_loss(a.positive.astype(int), a.p_positive)),
            "active_auc_2023_24": auc(
                a[a.label_month.str[:4].astype(int) <= 2024].positive,
                a[a.label_month.str[:4].astype(int) <= 2024].p_positive,
            ),
            "active_auc_2025_26": auc(
                a[a.label_month.str[:4].astype(int) >= 2025].positive,
                a[a.label_month.str[:4].astype(int) >= 2025].p_positive,
            ),
        }
        recent = g[g.label_month.str[:4].astype(int) >= 2025]
        report["recent_bootstrap_2025_26"][name] = bootstrap_month_auc(recent, "p_positive")

    years = sorted(p.label_month.str[:4].astype(int).unique())
    for y in years:
        report["yearly"][str(y)] = {}
        for name in windows:
            g = p[(p.window == name) & (p.label_month.str[:4].astype(int) == y) & p.path_active]
            report["yearly"][str(y)][name] = {
                "active_rows": int(len(g)),
                "active_auc": auc(g.positive, g.p_positive),
                "actual_positive_share": float(g.positive.mean()) if len(g) else None,
                "pred_positive_mean": float(g.p_positive.mean()) if len(g) else None,
            }

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
