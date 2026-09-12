#!/usr/bin/env python3
"""MUV Stage 5: prequential diagnostics for regime dependence of pairwise sign model.

This does not fit a regime gate.  The Stage-3 pairwise model is frozen.  We ask
whether its OOS discrimination varies systematically with a small, predeclared
set of market-level state variables.

For every OOS month, each regime variable is converted to a percentile using
ONLY earlier monthly observations.  Low/mid/high terciles therefore do not use
future distribution information.  Terciles are diagnostics, not thresholds.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

DATA = Path("muv-retention-labels-v1.parquet")
PRED = Path("muv-retention-stage3-predictions.csv")
OUT_JSON = Path("muv-retention-stage5-report.json")
OUT_MONTH = Path("muv-retention-stage5-monthly-regimes.csv")
OUT_TERCILE = Path("muv-retention-stage5-terciles.csv")
EPS = 1e-10

REGIME_FEATURES = [
    "regime_raw_top1_switches20",
    "regime_top1_current_streak",
    "asof_score_std",
    "regime_risk_ret20_median",
    "regime_risk_ret20_std",
    "regime_risk_ret20_positive_frac",
    "regime_risk_corr120_median",
    "regime_cash_top1_freq20",
    "regime_risk_qualified_count",
]


def auc(y, p):
    z = pd.DataFrame({"y": y, "p": p}).dropna()
    if len(z) < 8 or z.y.nunique() < 2:
        return None
    return float(roc_auc_score(z.y.astype(int), z.p.astype(float)))


def percentile_from_prior(prior: pd.Series, current):
    z = pd.to_numeric(prior, errors="coerce").dropna().to_numpy(dtype=float)
    if len(z) < 12 or current is None or pd.isna(current):
        return np.nan
    cur = float(current)
    # Mid-rank empirical CDF, using prior months only.
    lt = np.sum(z < cur)
    eq = np.sum(z == cur)
    return float((lt + 0.5 * eq) / len(z))


def tercile(p):
    if pd.isna(p):
        return None
    if p < 1.0 / 3.0:
        return "low"
    if p < 2.0 / 3.0:
        return "mid"
    return "high"


def main():
    d = pd.read_parquet(DATA)
    p = pd.read_csv(PRED)
    d["label_month"] = d.label_month.astype(str)
    p["label_month"] = p.label_month.astype(str)
    p["delta_return"] = pd.to_numeric(p.delta_return, errors="coerce")
    p["path_active"] = p.path_active.astype(str).str.lower().isin(["true", "1"])
    p["positive"] = p.delta_return > EPS

    missing = set(REGIME_FEATURES) - set(d.columns)
    if missing:
        raise RuntimeError(f"V1.4 regime features missing: {sorted(missing)}")
    if "p_positive_pairwise" not in p.columns:
        raise RuntimeError("Stage3 pairwise predictions missing")

    monthly = (
        d.sort_values(["label_month", "symbol"])
        .groupby("label_month", as_index=False)[REGIME_FEATURES]
        .first()
        .sort_values("label_month")
        .reset_index(drop=True)
    )

    for f in REGIME_FEATURES:
        vals = []
        for i, row in monthly.iterrows():
            prior = monthly.loc[: i - 1, f] if i > 0 else pd.Series(dtype=float)
            vals.append(percentile_from_prior(prior, row[f]))
        monthly[f + "__pct_prior"] = vals
        monthly[f + "__tercile"] = [tercile(x) for x in vals]

    monthly.to_csv(OUT_MONTH, index=False)
    z = p.merge(monthly, on="label_month", how="left", validate="many_to_one")
    active = z[z.path_active].copy()

    tercile_rows = []
    feature_reports = []
    for f in REGIME_FEATURES:
        pct = f + "__pct_prior"
        tc = f + "__tercile"
        groups = []
        for level in ["low", "mid", "high"]:
            g = active[active[tc] == level]
            years = sorted(g.label_month.str[:4].unique().tolist()) if len(g) else []
            rec = {
                "feature": f,
                "tercile": level,
                "months": int(g.label_month.nunique()),
                "active_rows": int(len(g)),
                "sign_auc": auc(g.positive, g.p_positive_pairwise),
                "actual_positive_share": float(g.positive.mean()) if len(g) else None,
                "pred_positive_mean": float(g.p_positive_pairwise.mean()) if len(g) else None,
                "years": years,
            }
            tercile_rows.append(rec)
            groups.append(rec)

        # Does the regime variable itself linearly align with model correctness?
        a = active[[pct, "positive", "p_positive_pairwise", "label_month"]].dropna().copy()
        a["pred_label"] = a.p_positive_pairwise >= 0.5
        a["correct_05"] = a.pred_label == a.positive
        corr = a[[pct, "correct_05"]].corr(method="spearman").iloc[0, 1] if len(a) >= 10 else np.nan
        feature_reports.append({
            "feature": f,
            "oos_months_with_percentile": int(a.label_month.nunique()),
            "active_rows_with_percentile": int(len(a)),
            "spearman_regime_pct_vs_correct05": float(corr) if np.isfinite(corr) else None,
            "terciles": groups,
        })

    pd.DataFrame(tercile_rows).to_csv(OUT_TERCILE, index=False)

    # Year profile expressed as prior-history percentiles, allowing 2023/26 vs
    # 2024/25 comparison without putting heterogeneous units on one scale.
    year_profiles = {}
    test_months = sorted(p.label_month.unique())
    mtest = monthly[monthly.label_month.isin(test_months)].copy()
    for year, g in mtest.groupby(mtest.label_month.str[:4]):
        year_profiles[str(year)] = {
            f: {
                "mean_prior_percentile": float(g[f + "__pct_prior"].mean()) if g[f + "__pct_prior"].notna().any() else None,
                "median_prior_percentile": float(g[f + "__pct_prior"].median()) if g[f + "__pct_prior"].notna().any() else None,
                "raw_mean": float(pd.to_numeric(g[f], errors="coerce").mean()) if pd.to_numeric(g[f], errors="coerce").notna().any() else None,
            }
            for f in REGIME_FEATURES
        }

    yearly_model = {}
    for year, g in active.groupby(active.label_month.str[:4]):
        yearly_model[str(year)] = {
            "active_rows": int(len(g)),
            "months": int(g.label_month.nunique()),
            "pairwise_sign_auc": auc(g.positive, g.p_positive_pairwise),
            "positive_share": float(g.positive.mean()),
        }

    report = {
        "design": {
            "dataset_version": str(d.dataset_version.iloc[0]),
            "pairwise_model": "frozen Stage3 expanding logistic predictions",
            "regime_features": REGIME_FEATURES,
            "binning": "empirical prior-month percentile, then fixed terciles",
            "min_prior_months_for_percentile": 12,
            "regime_model_fitted": False,
            "threshold_search": False,
        },
        "oos": {
            "months": int(p.label_month.nunique()),
            "active_rows": int(len(active)),
            "overall_pairwise_sign_auc": auc(active.positive, active.p_positive_pairwise),
        },
        "yearly_pairwise_model": yearly_model,
        "yearly_regime_profiles": year_profiles,
        "regime_feature_diagnostics": feature_reports,
        "notes": [
            "All regime percentiles use only earlier months; no future distribution is used.",
            "Tercile AUCs are descriptive and are not selected as a gate in this stage.",
            "Small active samples can make subgroup AUC noisy; look for coherent patterns across related regime variables rather than one best feature.",
        ],
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
