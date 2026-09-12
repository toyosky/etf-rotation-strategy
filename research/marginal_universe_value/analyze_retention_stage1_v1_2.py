#!/usr/bin/env python3
"""Path-aware Stage 1 analysis for MUV retention V1.2.

Outcome fields (`delta_*`, `path_*`) are explicitly excluded from predictors.
No model threshold is optimized here.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import analyze_retention_stage1 as a1

INPUT = Path("muv-retention-labels-v1.parquet")
OUT_JSON = Path("muv-retention-stage1-v1_2-report.json")
OUT_FEATURES = Path("muv-retention-stage1-v1_2-features.csv")
OUT_SYMBOLS = Path("muv-retention-stage1-v1_2-symbols.csv")
EPS = 1e-10


def summary(g: pd.DataFrame) -> dict:
    path = g["path_active"]
    ret = g["return_active"]
    nz = g.loc[ret]
    pa = g.loc[path]
    return {
        "rows": int(len(g)),
        "months": int(g["label_month"].nunique()),
        "path_effect_rate": float(path.mean()),
        "return_effect_rate": float(ret.mean()),
        "path_only_effect_rate": float((path & ~ret).mean()),
        "return_without_path_rate": float((ret & ~path).mean()),
        "positive_rate_all": float((g["delta_return"] > EPS).mean()),
        "negative_rate_all": float((g["delta_return"] < -EPS).mean()),
        "positive_share_nonzero": float((nz["delta_return"] > EPS).mean()) if len(nz) else None,
        "delta_return_mean_all": float(g["delta_return"].mean()),
        "delta_return_mean_nonzero": float(nz["delta_return"].mean()) if len(nz) else None,
        "delta_return_median_nonzero": float(nz["delta_return"].median()) if len(nz) else None,
        "target_changed_days_mean_if_path": float(pa["path_target_changed_days"].mean()) if len(pa) else None,
        "raw_top1_changed_days_mean_if_path": float(pa["path_raw_top1_changed_days"].mean()) if len(pa) else None,
        "direct_selection_days_mean_if_path": float(pa["path_direct_selection_days"].mean()) if len(pa) else None,
        "spillover_changed_days_mean_if_path": float(pa["path_spillover_changed_days"].mean()) if len(pa) else None,
        "beneficial_days_mean_if_path": float(pa["path_beneficial_days"].mean()) if len(pa) else None,
        "harmful_days_mean_if_path": float(pa["path_harmful_days"].mean()) if len(pa) else None,
    }


def main() -> None:
    df = pd.read_parquet(INPUT)
    if df.empty:
        raise RuntimeError("empty panel")
    required = {
        "path_raw_top1_changed_days", "path_target_changed_days",
        "path_direct_selection_days", "path_spillover_changed_days",
        "path_beneficial_days", "path_harmful_days", "delta_return",
    }
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"V1.2 path labels missing: {sorted(missing)}")

    df["label_month"] = df["label_month"].astype(str)
    df["year"] = df["label_month"].str[:4].astype(int)
    df["period"] = np.where(df["year"] <= 2024, "2021-24", "2025-26")
    df["path_active"] = (
        (pd.to_numeric(df["path_raw_top1_changed_days"], errors="coerce").fillna(0) > 0)
        | (pd.to_numeric(df["path_target_changed_days"], errors="coerce").fillna(0) > 0)
    )
    df["return_active"] = df["delta_return"].abs() > EPS
    df["return_positive"] = df["delta_return"] > EPS

    excluded_prefixes = ("base_", "cf_", "delta_", "path_")
    excluded_exact = {
        "dataset_version", "decision_type", "asof_date", "label_month", "symbol",
        "baseline_universe", "period", "year", "x_state_date",
        "baseline_universe_size", "counterfactual_universe_size",
        "return_active", "return_positive",
    }
    features = []
    for c in df.columns:
        if c in excluded_exact or c.startswith(excluded_prefixes):
            continue
        if pd.api.types.is_bool_dtype(df[c]):
            df[c] = df[c].astype(float)
        elif not pd.api.types.is_numeric_dtype(df[c]):
            z = pd.to_numeric(df[c], errors="coerce")
            if z.notna().mean() < 0.5:
                continue
            df[c] = z
        if df[c].notna().mean() >= 0.5 and df[c].nunique(dropna=True) >= 3:
            features.append(c)

    early = df["period"] == "2021-24"
    late = df["period"] == "2025-26"
    nz = df["return_active"]
    rows = []
    for c in features:
        auc_all = a1.auc_binary(df["path_active"], df[c])
        auc_e = a1.auc_binary(df.loc[early, "path_active"], df.loc[early, c])
        auc_l = a1.auc_binary(df.loc[late, "path_active"], df.loc[late, c])
        de = None if auc_e is None else auc_e - 0.5
        dl = None if auc_l is None else auc_l - 0.5
        impact_stable = a1.safe_same_sign(de, dl, 0.005)

        rho = a1.spear(df.loc[nz, c], df.loc[nz, "delta_return"])
        rho_e = a1.spear(df.loc[nz & early, c], df.loc[nz & early, "delta_return"])
        rho_l = a1.spear(df.loc[nz & late, c], df.loc[nz & late, "delta_return"])
        value_stable = a1.safe_same_sign(rho_e, rho_l, 0.02)

        sign_auc = a1.auc_binary(df.loc[nz, "return_positive"], df.loc[nz, c])
        sign_auc_e = a1.auc_binary(df.loc[nz & early, "return_positive"], df.loc[nz & early, c])
        sign_auc_l = a1.auc_binary(df.loc[nz & late, "return_positive"], df.loc[nz & late, c])

        rows.append({
            "feature": c,
            "group": a1.feature_group(c),
            "coverage": float(df[c].notna().mean()),
            "path_auc_all": auc_all,
            "path_auc_2021_24": auc_e,
            "path_auc_2025_26": auc_l,
            "path_direction_stable": bool(impact_stable),
            "stable_path_strength": min(abs(de), abs(dl)) if impact_stable else 0.0,
            "rho_delta_nonzero": rho,
            "rho_delta_nonzero_2021_24": rho_e,
            "rho_delta_nonzero_2025_26": rho_l,
            "value_direction_stable": bool(value_stable),
            "stable_value_strength": min(abs(rho_e), abs(rho_l)) if value_stable else 0.0,
            "positive_sign_auc_nonzero": sign_auc,
            "positive_sign_auc_2021_24": sign_auc_e,
            "positive_sign_auc_2025_26": sign_auc_l,
        })
    feat = pd.DataFrame(rows).sort_values(
        ["stable_path_strength", "stable_value_strength"], ascending=False
    )
    feat.to_csv(OUT_FEATURES, index=False)

    sym_rows = []
    for sym, g in df.groupby("symbol", sort=True):
        p = g[g["path_active"]]
        nzg = g[g["return_active"]]
        sym_rows.append({
            "symbol": str(sym),
            "rows": int(len(g)),
            "path_effect_rate": float(g["path_active"].mean()),
            "return_effect_rate": float(g["return_active"].mean()),
            "path_only_rate": float((g["path_active"] & ~g["return_active"]).mean()),
            "mean_target_changed_days_if_path": float(p["path_target_changed_days"].mean()) if len(p) else None,
            "mean_spillover_days_if_path": float(p["path_spillover_changed_days"].mean()) if len(p) else None,
            "positive_share_nonzero": float((nzg["delta_return"] > EPS).mean()) if len(nzg) else None,
            "mean_delta_return_all": float(g["delta_return"].mean()),
            "median_delta_return_nonzero": float(nzg["delta_return"].median()) if len(nzg) else None,
        })
    syms = pd.DataFrame(sym_rows).sort_values("mean_delta_return_all", ascending=False)
    syms.to_csv(OUT_SYMBOLS, index=False)

    top_path = feat.sort_values("stable_path_strength", ascending=False).head(12)
    top_value = feat.sort_values("stable_value_strength", ascending=False).head(12)
    top_sign = feat.assign(sign_sep=(feat["positive_sign_auc_nonzero"] - 0.5).abs()).sort_values("sign_sep", ascending=False).head(12)

    report = {
        "dataset": {
            "version": str(df["dataset_version"].iloc[0]),
            "rows": int(len(df)),
            "months": int(df["label_month"].nunique()),
            "symbols": int(df["symbol"].nunique()),
            "candidate_features": int(len(features)),
            "outcome_path_columns": sorted([c for c in df.columns if c.startswith("path_")]),
        },
        "target_decomposition": {
            "all": summary(df),
            "2021-24": summary(df[early]),
            "2025-26": summary(df[late]),
        },
        "mechanics": {
            "rows_with_spillover": int((df["path_spillover_changed_days"] > 0).sum()),
            "spillover_rate_all": float((df["path_spillover_changed_days"] > 0).mean()),
            "rows_with_direct_selection": int((df["path_direct_selection_days"] > 0).sum()),
            "direct_selection_rate_all": float((df["path_direct_selection_days"] > 0).mean()),
            "changed_target_equal_net_rows": int((df["path_changed_target_equal_net_days"] > 0).sum()),
            "changed_target_equal_net_rate_all": float((df["path_changed_target_equal_net_days"] > 0).mean()),
            "total_beneficial_days": int(df["path_beneficial_days"].sum()),
            "total_harmful_days": int(df["path_harmful_days"].sum()),
        },
        "top_stable_path_features": top_path.replace({np.nan: None}).to_dict(orient="records"),
        "top_stable_conditional_value_features": top_value.replace({np.nan: None}).to_dict(orient="records"),
        "top_positive_vs_negative_features": top_sign.replace({np.nan: None}).to_dict(orient="records"),
        "symbol_summary": syms.replace({np.nan: None}).to_dict(orient="records"),
        "notes": [
            "All path_* and delta_* fields are outcomes and are excluded from predictors.",
            "Stage 1 is descriptive only; no threshold is selected.",
            "A stable path predictor need not be a stable value predictor.",
        ],
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
