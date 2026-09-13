from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

PRED_PATH = Path("muv-retention-stage13-bootstrap-predictions.csv")
STAGE7_PATH = Path("muv-retention-stage7-monthly-policy.csv")
OUT_PRED = Path("muv-retention-stage14-residual-stress.csv")
OUT_STAGE7 = Path("muv-retention-stage14-stage7-veto.csv")
OUT_REPORT = Path("muv-retention-stage14-report.json")

MIN_PRIOR_MONTHS = 12
COVERAGE = 0.90


def wealth(x: pd.Series) -> float:
    return float(np.prod(1.0 + x.astype(float).to_numpy()))


def main() -> None:
    pred = pd.read_csv(PRED_PATH)
    stage7 = pd.read_csv(STAGE7_PATH)
    pred["label_month"] = pred["label_month"].astype(str)
    pred["forecast_error"] = pred["delta_return"] - pred["muv_pairwise"]

    out = []
    for month in sorted(pred["label_month"].unique()):
        prior = pred[pred["label_month"] < month]
        prior_months = sorted(prior["label_month"].unique())
        q90 = np.nan
        if len(prior_months) >= MIN_PRIOR_MONTHS:
            month_max = prior.groupby("label_month")["forecast_error"].max()
            q90 = float(np.quantile(month_max.to_numpy(), COVERAGE, method="higher"))

        cur = pred[pred["label_month"] == month].copy()
        cur["residual_stress_q90"] = q90
        cur["residual_stress_ucb"] = cur["muv_pairwise"] + q90 if np.isfinite(q90) else np.nan
        cur["residual_stress_safe"] = (
            np.isfinite(cur["residual_stress_ucb"]) & (cur["residual_stress_ucb"] < 0)
        )
        out.append(cur)

    stress = pd.concat(out, ignore_index=True)
    stress.to_csv(OUT_PRED, index=False)

    s7 = stage7[[
        "label_month",
        "base_return",
        "act_primary_regime90",
        "symbol_primary_regime90",
        "ret_primary_regime90",
        "selected_delta_return_primary_regime90",
    ]].copy()
    s7["label_month"] = s7["label_month"].astype(str)
    s7["symbol_primary_regime90"] = pd.to_numeric(s7["symbol_primary_regime90"], errors="coerce")

    lookup = stress[[
        "label_month", "symbol", "residual_stress_q90", "residual_stress_ucb", "residual_stress_safe"
    ]].copy()
    lookup["symbol"] = pd.to_numeric(lookup["symbol"], errors="coerce")

    merged = s7.merge(
        lookup,
        left_on=["label_month", "symbol_primary_regime90"],
        right_on=["label_month", "symbol"],
        how="left",
    )
    merged["residual_stress_safe"] = merged["residual_stress_safe"].fillna(False).astype(bool)
    acted = merged["act_primary_regime90"].astype(bool)
    merged["residual_stress_veto"] = acted & (~merged["residual_stress_safe"])
    merged["stage7_residual_stress_return"] = np.where(
        merged["residual_stress_veto"], merged["base_return"], merged["ret_primary_regime90"]
    )
    merged.to_csv(OUT_STAGE7, index=False)

    calibrated = stress[np.isfinite(stress["residual_stress_q90"])].copy()
    named = {}
    for month, symbol in [("2024-09", 159915), ("2025-04", 518880)]:
        z = stress[(stress["label_month"] == month) & (pd.to_numeric(stress["symbol"], errors="coerce") == symbol)]
        if not z.empty:
            r = z.iloc[0]
            named[f"{month}_{symbol}"] = {
                "delta_return": float(r["delta_return"]),
                "point_muv": float(r["muv_pairwise"]),
                "residual_stress_q90": float(r["residual_stress_q90"]),
                "residual_stress_ucb": float(r["residual_stress_ucb"]),
                "safe_remove": bool(r["residual_stress_safe"]),
            }

    action_rows = merged[acted].copy()
    report = {
        "version": "muv_stage14_residual_stress_20260913",
        "design": {
            "prediction": "frozen Stage-3 pairwise expected MUV",
            "calibration_unit": "prior OOS label_month",
            "calibration_score": "monthly maximum of realized retention value - predicted expected MUV",
            "min_prior_months": MIN_PRIOR_MONTHS,
            "coverage": COVERAGE,
            "quantile_method": "higher",
            "feature_search": False,
            "model_fit": False,
            "threshold_search": False,
        },
        "diagnostics": {
            "calibrated_rows": int(len(calibrated)),
            "calibrated_months": int(calibrated["label_month"].nunique()),
            "safe_rows": int(calibrated["residual_stress_safe"].sum()),
            "safe_share": float(calibrated["residual_stress_safe"].mean()) if len(calibrated) else None,
            "negative_point_muv_rows": int((calibrated["muv_pairwise"] < 0).sum()),
            "negative_point_muv_safe_rows": int(((calibrated["muv_pairwise"] < 0) & calibrated["residual_stress_safe"]).sum()),
            "named_audits": named,
        },
        "stage7_plus_residual_stress": {
            "stage7_final_wealth": wealth(merged["ret_primary_regime90"]),
            "guarded_final_wealth": wealth(merged["stage7_residual_stress_return"]),
            "stage7_actions": int(acted.sum()),
            "vetoes": int(merged["residual_stress_veto"].sum()),
            "surviving_actions": int((acted & merged["residual_stress_safe"]).sum()),
            "sum_selected_delta_vetoed": float(action_rows.loc[~action_rows["residual_stress_safe"], "selected_delta_return_primary_regime90"].sum()),
        },
        "interpretation": (
            "This is a diagnostic certification test. If safe coverage collapses, do not tune coverage downward; "
            "the result means observed historical tail miss magnitude is too large for the current model to certify removals."
        ),
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
