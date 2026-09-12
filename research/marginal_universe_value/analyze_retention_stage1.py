#!/usr/bin/env python3
"""Stage 1 descriptive economics for MUV retention labels.

This script deliberately does NOT fit a production model or optimize a trading
threshold.  It decomposes retention value into:

1) path impact: does removing the incumbent change any next-month strategy
   outcome at all?
2) return impact: does removal change next-month portfolio return?
3) conditional value: when return impact is non-zero, is retaining the ETF
   beneficial or harmful, and which point-in-time features are associated with
   that sign/magnitude?

The main stability check is 2021-2024 versus 2025-2026.  Quantile summaries are
for descriptive diagnostics only and must not be reused as backtest thresholds.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

INPUT = Path("muv-retention-labels-v1.parquet")
OUT_JSON = Path("muv-retention-stage1-report.json")
OUT_FEATURES = Path("muv-retention-stage1-features.csv")
OUT_SYMBOLS = Path("muv-retention-stage1-symbols.csv")
OUT_QUANTILES = Path("muv-retention-stage1-quantiles.csv")
EPS = 1e-10


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def auc_binary(y: pd.Series, x: pd.Series):
    z = pd.DataFrame({"y": y, "x": x}).dropna()
    if len(z) < 10:
        return None
    yy = z["y"].astype(int).to_numpy()
    xx = z["x"].astype(float).to_numpy()
    pos = yy == 1
    n1 = int(pos.sum())
    n0 = int((~pos).sum())
    if n1 == 0 or n0 == 0 or np.nanstd(xx) == 0:
        return None
    r = rankdata(xx, method="average")
    auc = (r[pos].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)
    return float(auc)


def spear(x: pd.Series, y: pd.Series):
    z = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(z) < 10 or z["x"].nunique() < 3 or z["y"].nunique() < 3:
        return None
    r = spearmanr(z["x"].astype(float), z["y"].astype(float)).statistic
    return fnum(r)


def standardized_diff(x: pd.Series, y: pd.Series):
    z = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(z) < 10:
        return None
    a = z.loc[z.y == 1, "x"].astype(float)
    b = z.loc[z.y == 0, "x"].astype(float)
    if len(a) < 3 or len(b) < 3:
        return None
    pooled = math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0)
    if not math.isfinite(pooled) or pooled == 0:
        return None
    return float((a.mean() - b.mean()) / pooled)


def feature_group(name: str) -> str:
    competition_tokens = (
        "asof_", "candidate_count", "own_score_rank", "own_score_gap_top1",
        "own_score_ratio_top1", "top1_freq", "top3_freq", "days_since_top1",
        "corr120_",
    )
    if name.startswith(competition_tokens):
        return "competition"
    if name.startswith("x_"):
        return "own_state"
    return "other"


def safe_same_sign(a, b, min_abs=0.0):
    if a is None or b is None:
        return False
    if abs(a) <= min_abs or abs(b) <= min_abs:
        return False
    return (a > 0) == (b > 0)


def period_summary(g: pd.DataFrame) -> dict:
    active = g["return_active"]
    nz = g.loc[active]
    return {
        "rows": int(len(g)),
        "months": int(g["label_month"].nunique()),
        "symbols": int(g["symbol"].nunique()),
        "any_path_effect_rate": float(g["impact_any"].mean()),
        "return_effect_rate": float(g["return_active"].mean()),
        "positive_return_value_rate_all": float(g["return_positive"].mean()),
        "negative_return_value_rate_all": float(g["return_negative"].mean()),
        "positive_share_conditional_nonzero": float((nz["delta_return"] > EPS).mean()) if len(nz) else None,
        "delta_return_mean_all": float(g["delta_return"].mean()),
        "delta_return_mean_nonzero": float(nz["delta_return"].mean()) if len(nz) else None,
        "delta_return_median_nonzero": float(nz["delta_return"].median()) if len(nz) else None,
        "delta_return_p10_nonzero": float(nz["delta_return"].quantile(0.10)) if len(nz) else None,
        "delta_return_p90_nonzero": float(nz["delta_return"].quantile(0.90)) if len(nz) else None,
    }


def main():
    if not INPUT.exists():
        raise FileNotFoundError(INPUT)
    df = pd.read_parquet(INPUT)
    if df.empty:
        raise RuntimeError("retention panel is empty")

    df["label_month"] = df["label_month"].astype(str)
    df["year"] = df["label_month"].str.slice(0, 4).astype(int)
    df["period"] = np.where(df["year"] <= 2024, "2021-24", "2025-26")

    delta_cols = [c for c in df.columns if c.startswith("delta_")]
    numeric_delta_cols = []
    for c in delta_cols:
        s = pd.to_numeric(df[c], errors="coerce")
        if s.notna().any():
            df[c] = s
            numeric_delta_cols.append(c)

    if "delta_return" not in df.columns:
        raise RuntimeError("delta_return missing")

    delta_abs = pd.DataFrame({c: df[c].abs().fillna(0.0) for c in numeric_delta_cols})
    df["impact_any"] = delta_abs.max(axis=1) > EPS
    df["return_active"] = df["delta_return"].abs() > EPS
    df["return_positive"] = df["delta_return"] > EPS
    df["return_negative"] = df["delta_return"] < -EPS

    exclude_prefixes = ("base_", "cf_", "delta_")
    exclude_exact = {
        "baseline_universe_size", "counterfactual_universe_size",
        "year", "impact_any", "return_active", "return_positive", "return_negative",
    }
    feature_cols = []
    for c in df.columns:
        if c in exclude_exact or c.startswith(exclude_prefixes):
            continue
        if c in {"dataset_version", "decision_type", "asof_date", "label_month", "symbol", "baseline_universe", "period", "x_state_date"}:
            continue
        if pd.api.types.is_bool_dtype(df[c]):
            df[c] = df[c].astype(float)
        elif not pd.api.types.is_numeric_dtype(df[c]):
            converted = pd.to_numeric(df[c], errors="coerce")
            if converted.notna().mean() >= 0.5:
                df[c] = converted
            else:
                continue
        if df[c].notna().mean() < 0.5 or df[c].nunique(dropna=True) < 3:
            continue
        feature_cols.append(c)

    rows = []
    early = df["period"] == "2021-24"
    late = df["period"] == "2025-26"
    nz = df["return_active"]

    for c in feature_cols:
        auc_all = auc_binary(df["impact_any"], df[c])
        auc_e = auc_binary(df.loc[early, "impact_any"], df.loc[early, c])
        auc_l = auc_binary(df.loc[late, "impact_any"], df.loc[late, c])
        auc_dir_e = None if auc_e is None else auc_e - 0.5
        auc_dir_l = None if auc_l is None else auc_l - 0.5

        rho_all = spear(df[c], df["delta_return"])
        rho_nz = spear(df.loc[nz, c], df.loc[nz, "delta_return"])
        rho_e = spear(df.loc[early & nz, c], df.loc[early & nz, "delta_return"])
        rho_l = spear(df.loc[late & nz, c], df.loc[late & nz, "delta_return"])

        sign_auc = auc_binary(
            df.loc[nz, "return_positive"],
            df.loc[nz, c],
        )
        sign_auc_e = auc_binary(
            df.loc[early & nz, "return_positive"],
            df.loc[early & nz, c],
        )
        sign_auc_l = auc_binary(
            df.loc[late & nz, "return_positive"],
            df.loc[late & nz, c],
        )

        impact_stable = safe_same_sign(auc_dir_e, auc_dir_l, 0.005)
        value_stable = safe_same_sign(rho_e, rho_l, 0.02)
        stable_impact_strength = (
            min(abs(auc_dir_e), abs(auc_dir_l)) if impact_stable else 0.0
        )
        stable_value_strength = (
            min(abs(rho_e), abs(rho_l)) if value_stable else 0.0
        )

        rows.append({
            "feature": c,
            "group": feature_group(c),
            "coverage": float(df[c].notna().mean()),
            "n_unique": int(df[c].nunique(dropna=True)),
            "impact_auc_all": auc_all,
            "impact_auc_2021_24": auc_e,
            "impact_auc_2025_26": auc_l,
            "impact_smd_all": standardized_diff(df[c], df["impact_any"]),
            "impact_direction_stable": impact_stable,
            "stable_impact_strength": stable_impact_strength,
            "rho_delta_all": rho_all,
            "rho_delta_nonzero": rho_nz,
            "rho_delta_nonzero_2021_24": rho_e,
            "rho_delta_nonzero_2025_26": rho_l,
            "value_direction_stable": value_stable,
            "stable_value_strength": stable_value_strength,
            "positive_sign_auc_nonzero": sign_auc,
            "positive_sign_auc_nonzero_2021_24": sign_auc_e,
            "positive_sign_auc_nonzero_2025_26": sign_auc_l,
        })

    feat = pd.DataFrame(rows)
    feat = feat.sort_values(["stable_impact_strength", "stable_value_strength"], ascending=False)
    feat.to_csv(OUT_FEATURES, index=False)

    sym_rows = []
    for sym, g in df.groupby("symbol", sort=True):
        nzg = g[g["return_active"]]
        sym_rows.append({
            "symbol": str(sym),
            "rows": int(len(g)),
            "first_month": str(g["label_month"].min()),
            "last_month": str(g["label_month"].max()),
            "any_path_effect_rate": float(g["impact_any"].mean()),
            "return_effect_rate": float(g["return_active"].mean()),
            "positive_rate_all": float(g["return_positive"].mean()),
            "negative_rate_all": float(g["return_negative"].mean()),
            "positive_share_nonzero": float((nzg["delta_return"] > EPS).mean()) if len(nzg) else None,
            "mean_delta_return_all": float(g["delta_return"].mean()),
            "mean_delta_return_nonzero": float(nzg["delta_return"].mean()) if len(nzg) else None,
            "median_delta_return_nonzero": float(nzg["delta_return"].median()) if len(nzg) else None,
        })
    syms = pd.DataFrame(sym_rows).sort_values("mean_delta_return_all", ascending=False)
    syms.to_csv(OUT_SYMBOLS, index=False)

    # Descriptive quartiles for the most time-stable features only.  Bins are
    # recomputed within each period, so this is a shape/stability diagnostic,
    # not a global historical threshold search.
    top_names = []
    for source, scorecol in [
        (feat.sort_values("stable_impact_strength", ascending=False), "stable_impact_strength"),
        (feat.sort_values("stable_value_strength", ascending=False), "stable_value_strength"),
    ]:
        for c in source.loc[source[scorecol] > 0, "feature"].head(6):
            if c not in top_names:
                top_names.append(c)
    qrows = []
    for c in top_names[:10]:
        for p, g in df.groupby("period"):
            valid = g[[c, "impact_any", "return_active", "delta_return"]].dropna().copy()
            if valid[c].nunique() < 4:
                continue
            try:
                valid["quartile"] = pd.qcut(valid[c], 4, labels=False, duplicates="drop") + 1
            except ValueError:
                continue
            for q, h in valid.groupby("quartile"):
                nz_h = h[h["return_active"]]
                qrows.append({
                    "feature": c,
                    "group": feature_group(c),
                    "period": p,
                    "quartile": int(q),
                    "n": int(len(h)),
                    "x_median": float(h[c].median()),
                    "impact_rate": float(h["impact_any"].mean()),
                    "return_effect_rate": float(h["return_active"].mean()),
                    "delta_return_mean_all": float(h["delta_return"].mean()),
                    "delta_return_mean_nonzero": float(nz_h["delta_return"].mean()) if len(nz_h) else None,
                    "positive_share_nonzero": float((nz_h["delta_return"] > EPS).mean()) if len(nz_h) else None,
                })
    qdf = pd.DataFrame(qrows)
    qdf.to_csv(OUT_QUANTILES, index=False)

    group_summary = []
    for grp, g in feat.groupby("group"):
        group_summary.append({
            "group": grp,
            "features": int(len(g)),
            "stable_impact_features": int(g["impact_direction_stable"].sum()),
            "stable_value_features": int(g["value_direction_stable"].sum()),
            "max_stable_impact_strength": float(g["stable_impact_strength"].max()) if len(g) else None,
            "max_stable_value_strength": float(g["stable_value_strength"].max()) if len(g) else None,
            "median_abs_impact_auc_distance": float((g["impact_auc_all"] - 0.5).abs().median()),
            "median_abs_rho_nonzero": float(g["rho_delta_nonzero"].abs().median()),
        })

    top_impact = feat.sort_values("stable_impact_strength", ascending=False).head(12)
    top_value = feat.sort_values("stable_value_strength", ascending=False).head(12)
    top_sign = feat.assign(
        sign_sep=(feat["positive_sign_auc_nonzero"] - 0.5).abs()
    ).sort_values("sign_sep", ascending=False).head(12)

    report = {
        "dataset": {
            "rows": int(len(df)),
            "months": int(df["label_month"].nunique()),
            "symbols": int(df["symbol"].nunique()),
            "month_min": str(df["label_month"].min()),
            "month_max": str(df["label_month"].max()),
            "numeric_delta_columns": numeric_delta_cols,
            "candidate_features": int(len(feature_cols)),
        },
        "target_decomposition": {
            "all": period_summary(df),
            "2021-24": period_summary(df[early]),
            "2025-26": period_summary(df[late]),
            "path_effect_without_return_effect_rate": float((df["impact_any"] & ~df["return_active"]).mean()),
        },
        "feature_group_summary": group_summary,
        "top_stable_impact_features": top_impact.replace({np.nan: None}).to_dict(orient="records"),
        "top_stable_conditional_value_features": top_value.replace({np.nan: None}).to_dict(orient="records"),
        "top_positive_vs_negative_features": top_sign.replace({np.nan: None}).to_dict(orient="records"),
        "symbol_summary": syms.replace({np.nan: None}).to_dict(orient="records"),
        "notes": [
            "impact_any means at least one stored counterfactual delta changed; it is not a trading threshold.",
            "conditional value statistics only use rows with non-zero delta_return.",
            "stable_* requires same directional association in 2021-24 and 2025-26; no threshold optimization is performed.",
            "quartiles are recomputed separately within each period and are descriptive only.",
        ],
    }

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
