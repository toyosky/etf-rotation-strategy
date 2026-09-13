from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

PRED_PATH = Path("muv-retention-stage3-predictions.csv")
OUT_REPORT = Path("muv-retention-stage16-report.json")
OUT_CURVE = Path("muv-retention-stage16-activity-curve.csv")
OUT_PERIOD = Path("muv-retention-stage16-period-curve.csv")
CUTOFFS = [i / 10 for i in range(10)]


def safe_auc(y: pd.Series, score: pd.Series) -> float | None:
    y = y.astype(int)
    if len(y) < 10 or y.nunique() < 2:
        return None
    return float(roc_auc_score(y, score.astype(float)))


def safe_spearman(a: pd.Series, b: pd.Series) -> float | None:
    z = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(z) < 3 or z["a"].nunique() < 2 or z["b"].nunique() < 2:
        return None
    v = spearmanr(z["a"], z["b"]).statistic
    return None if not np.isfinite(v) else float(v)


def slice_diag(g: pd.DataFrame) -> dict:
    negative = g[g["muv_pairwise"] < 0].copy()
    miss = negative[negative["delta_return"] > 0]
    correct = negative[negative["delta_return"] < 0]
    return {
        "active_n": int(len(g)),
        "sign_auc": safe_auc(g["delta_return"] > 0, g["p_positive_pairwise"]),
        "muv_spearman": safe_spearman(g["muv_pairwise"], g["delta_return"]),
        "negative_prediction_n": int(len(negative)),
        "false_negative_positive_regret_sum": float(miss["delta_return"].sum()),
        "correct_negative_value_sum": float(-correct["delta_return"].sum()),
        "largest_positive_miss": float(miss["delta_return"].max()) if len(miss) else None,
    }


def main() -> None:
    df = pd.read_csv(PRED_PATH)
    df["label_month"] = df["label_month"].astype(str)
    df["path_active"] = df["path_active"].astype(bool)
    df["activity_percentile"] = df.groupby("label_month")["p_active"].rank(method="average", pct=True)

    active = df[df["path_active"]].copy()

    curve_rows = []
    for cutoff in CUTOFFS:
        g = active[active["activity_percentile"] > cutoff].copy()
        row = {"activity_percentile_gt": cutoff, **slice_diag(g)}
        curve_rows.append(row)
    curve = pd.DataFrame(curve_rows)
    curve.to_csv(OUT_CURVE, index=False)

    period_rows = []
    for period in sorted(active["oos_period"].dropna().astype(str).unique()):
        p = active[active["oos_period"].astype(str) == period]
        for cutoff in CUTOFFS:
            g = p[p["activity_percentile"] > cutoff].copy()
            period_rows.append({
                "oos_period": period,
                "activity_percentile_gt": cutoff,
                "active_n": int(len(g)),
                "sign_auc": safe_auc(g["delta_return"] > 0, g["p_positive_pairwise"]),
                "muv_spearman": safe_spearman(g["muv_pairwise"], g["delta_return"]),
            })
    period_curve = pd.DataFrame(period_rows)
    period_curve.to_csv(OUT_PERIOD, index=False)

    report = {
        "version": "muv_stage16_activity_conditional_sign_20260913",
        "design": {
            "source": "frozen Stage-3 expanding-window OOS predictions",
            "new_feature_search": False,
            "new_model_fit": False,
            "threshold_search": False,
            "policy_backtest": False,
            "activity_percentile_cutoffs": CUTOFFS,
            "interpretation_rule": (
                "Conditional identifiability requires broad monotone cross-period improvement as activity rank is tightened; "
                "local or period-specific bumps are insufficient."
            ),
        },
        "all_active_baseline": slice_diag(active),
        "top_activity_examples": {
            "above_50pct": slice_diag(active[active["activity_percentile"] > 0.5]),
            "above_80pct": slice_diag(active[active["activity_percentile"] > 0.8]),
            "above_90pct": slice_diag(active[active["activity_percentile"] > 0.9]),
        },
        "interpretation": (
            "Inspect the complete activity curve and frozen-period curves. Do not choose a cutoff from these results. "
            "If conditional sign/value metrics remain weak or improve inconsistently across periods, high predicted path activity "
            "does not repair signed-MUV identification."
        ),
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
