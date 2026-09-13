from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

PRED_PATH = Path("muv-retention-stage3-predictions.csv")
OUT_REPORT = Path("muv-retention-stage15-report.json")
OUT_QUINTILES = Path("muv-retention-stage15-quintiles.csv")
OUT_MONTHLY = Path("muv-retention-stage15-monthly-ranks.csv")


def safe_auc(y: pd.Series, score: pd.Series) -> float | None:
    y = y.astype(int)
    if y.nunique() < 2:
        return None
    return float(roc_auc_score(y, score.astype(float)))


def safe_spearman(a: pd.Series, b: pd.Series) -> float | None:
    z = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(z) < 3 or z["a"].nunique() < 2 or z["b"].nunique() < 2:
        return None
    v = spearmanr(z["a"], z["b"]).statistic
    return None if not np.isfinite(v) else float(v)


def period_diag(g: pd.DataFrame) -> dict:
    active = g[g["path_active"].astype(bool)].copy()
    negative_point = g[g["muv_pairwise"] < 0].copy()
    false_negative = negative_point[negative_point["delta_return"] > 0]
    correct_negative = negative_point[negative_point["delta_return"] < 0]

    return {
        "rows": int(len(g)),
        "active_rows": int(len(active)),
        "path_activity_auc": safe_auc(g["path_active"], g["p_active"]),
        "p_active_vs_abs_delta_spearman": safe_spearman(g["p_active"], g["delta_return"].abs()),
        "active_sign_auc": safe_auc(active["delta_return"] > 0, active["p_positive_pairwise"]),
        "active_muv_vs_delta_spearman": safe_spearman(active["muv_pairwise"], active["delta_return"]),
        "negative_point_muv": {
            "rows": int(len(negative_point)),
            "positive_actual_share": float((negative_point["delta_return"] > 0).mean()) if len(negative_point) else None,
            "false_negative_positive_regret_sum": float(false_negative["delta_return"].sum()),
            "correct_negative_value_sum": float(-correct_negative["delta_return"].sum()),
            "largest_positive_miss": float(false_negative["delta_return"].max()) if len(false_negative) else None,
        },
    }


def main() -> None:
    df = pd.read_csv(PRED_PATH)
    df["label_month"] = df["label_month"].astype(str)
    df["path_active"] = df["path_active"].astype(bool)

    diagnostics = {"all": period_diag(df)}
    for period in sorted(df["oos_period"].dropna().astype(str).unique()):
        diagnostics[period] = period_diag(df[df["oos_period"].astype(str) == period])

    monthly_rows = []
    for month, g in df.groupby("label_month", sort=True):
        a = g[g["path_active"]].copy()
        rho = safe_spearman(a["muv_pairwise"], a["delta_return"])
        if rho is not None and len(a) >= 3:
            monthly_rows.append({
                "label_month": month,
                "active_rows": int(len(a)),
                "active_rank_spearman": rho,
            })
    monthly = pd.DataFrame(monthly_rows)
    monthly.to_csv(OUT_MONTHLY, index=False)

    if len(monthly):
        monthly_summary = {
            "eligible_months": int(len(monthly)),
            "mean_active_rank_spearman": float(monthly["active_rank_spearman"].mean()),
            "median_active_rank_spearman": float(monthly["active_rank_spearman"].median()),
            "positive_month_share": float((monthly["active_rank_spearman"] > 0).mean()),
        }
    else:
        monthly_summary = {
            "eligible_months": 0,
            "mean_active_rank_spearman": None,
            "median_active_rank_spearman": None,
            "positive_month_share": None,
        }

    q_frames = []
    for variable, target_name in [("p_active", "activity"), ("muv_pairwise", "muv")]:
        z = df[["label_month", "symbol", "delta_return", "path_active", variable]].dropna().copy()
        z["quintile"] = pd.qcut(z[variable], 5, labels=False, duplicates="drop") + 1
        q = z.groupby("quintile", as_index=False).agg(
            n=("symbol", "size"),
            predictor_mean=(variable, "mean"),
            path_rate=("path_active", "mean"),
            mean_delta=("delta_return", "mean"),
        )
        q["mean_abs_delta"] = z.groupby("quintile")["delta_return"].apply(lambda x: float(np.abs(x).mean())).to_numpy()
        q["positive_rate"] = z.groupby("quintile")["delta_return"].apply(lambda x: float((x > 0).mean())).to_numpy()
        q["negative_rate"] = z.groupby("quintile")["delta_return"].apply(lambda x: float((x < 0).mean())).to_numpy()
        q.insert(0, "diagnostic", target_name)
        q_frames.append(q)
    quintiles = pd.concat(q_frames, ignore_index=True)
    quintiles.to_csv(OUT_QUINTILES, index=False)

    report = {
        "version": "muv_stage15_hurdle_identifiability_20260913",
        "design": {
            "source": "frozen Stage-3 expanding-window OOS predictions",
            "new_feature_search": False,
            "new_model_fit": False,
            "threshold_search": False,
            "policy_backtest": False,
            "purpose": "separate competition-path relevance predictability from conditional direction/value predictability",
        },
        "diagnostics": diagnostics,
        "monthly_active_rank": monthly_summary,
        "interpretation_rule": (
            "Stable path-activity discrimination with weak or unstable conditional sign/value discrimination means current "
            "observables identify competition relevance better than directional marginal value; that supports attention/risk "
            "budgeting but not unconstrained dynamic retention deletion."
        ),
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
