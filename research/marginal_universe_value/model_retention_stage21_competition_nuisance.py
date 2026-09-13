#!/usr/bin/env python3
"""Stage21 competition nuisance mechanism audit.

No predictive model, threshold search, or policy backtest. Uses frozen V1.6
remove-one labels to test whether added switching without marginal return is a
persistent structural phenotype across eras.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

INPUT = Path("muv-retention-labels-v1.parquet")
OUT = Path("muv-retention-stage21-report.json")
OUT_SYMBOL = Path("muv-retention-stage21-symbol-era.csv")


def era(month: str) -> str:
    y = int(str(month)[:4])
    return "2023-24" if y <= 2024 else "2025-26"


def safe_spearman(a: pd.Series, b: pd.Series):
    z = pd.concat([pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")], axis=1).dropna()
    if len(z) < 3 or z.iloc[:, 0].nunique() < 2 or z.iloc[:, 1].nunique() < 2:
        return None
    return float(z.iloc[:, 0].corr(z.iloc[:, 1], method="spearman"))


def block(g: pd.DataFrame) -> dict:
    extra = g["extra_switch"]
    nuisance = g["nuisance_outcome"]
    productive = g["productive_competition"]
    return {
        "n_rows": int(len(g)),
        "extra_switch_share": float(extra.mean()) if len(g) else None,
        "nuisance_outcome_share": float(nuisance.mean()) if len(g) else None,
        "nuisance_given_extra_switch": float(nuisance.sum() / extra.sum()) if extra.sum() else None,
        "nuisance_sum_delta_switches": float(g.loc[nuisance, "delta_switches"].sum()),
        "nuisance_sum_delta_return": float(g.loc[nuisance, "delta_return"].sum()),
        "productive_sum_delta_switches": float(g.loc[productive, "delta_switches"].sum()),
        "productive_sum_delta_return": float(g.loc[productive, "delta_return"].sum()),
    }


def main() -> None:
    df = pd.read_parquet(INPUT).copy()
    required = {"symbol", "label_month", "delta_return", "delta_switches"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Stage21 missing columns: {sorted(missing)}")

    df["label_month"] = df["label_month"].astype(str)
    df = df[df["label_month"] >= "2023-01"].copy()
    df["delta_return"] = pd.to_numeric(df["delta_return"], errors="coerce")
    df["delta_switches"] = pd.to_numeric(df["delta_switches"], errors="coerce")
    df = df.dropna(subset=["delta_return", "delta_switches"]).copy()
    df["era"] = df["label_month"].map(era)
    df["extra_switch"] = df["delta_switches"] > 0
    df["nuisance_outcome"] = (df["delta_switches"] > 0) & (df["delta_return"] <= 0)
    df["productive_competition"] = (df["delta_switches"] > 0) & (df["delta_return"] > 0)

    symbol_rows = []
    for (e, s), g in df.groupby(["era", "symbol"], sort=True):
        sum_sw = float(g["delta_switches"].sum())
        sum_ret = float(g["delta_return"].sum())
        symbol_rows.append({
            "era": str(e),
            "symbol": str(s),
            "n_rows": int(len(g)),
            "sum_delta_switches": sum_sw,
            "mean_delta_switches": float(g["delta_switches"].mean()),
            "sum_delta_return": sum_ret,
            "mean_delta_return": float(g["delta_return"].mean()),
            "extra_switch_share": float(g["extra_switch"].mean()),
            "nuisance_outcome_share": float(g["nuisance_outcome"].mean()),
            "structural_nuisance": bool(sum_sw > 0 and sum_ret <= 0),
        })
    sym = pd.DataFrame(symbol_rows)
    sym.to_csv(OUT_SYMBOL, index=False)

    piv_sw = sym.pivot(index="symbol", columns="era", values="sum_delta_switches")
    piv_ret = sym.pivot(index="symbol", columns="era", values="sum_delta_return")
    piv_flag = sym.pivot(index="symbol", columns="era", values="structural_nuisance")

    eras = ["2023-24", "2025-26"]
    common = piv_flag.dropna(subset=eras) if all(x in piv_flag.columns for x in eras) else pd.DataFrame()
    if not common.empty:
        agreement = float((common[eras[0]].astype(bool) == common[eras[1]].astype(bool)).mean())
        both_flagged = sorted(common.index[(common[eras[0]].astype(bool)) & (common[eras[1]].astype(bool))].astype(str).tolist())
    else:
        agreement = None
        both_flagged = []

    sw_corr = None
    ret_corr = None
    if all(x in piv_sw.columns for x in eras):
        sw_corr = safe_spearman(piv_sw[eras[0]], piv_sw[eras[1]])
    if all(x in piv_ret.columns for x in eras):
        ret_corr = safe_spearman(piv_ret[eras[0]], piv_ret[eras[1]])

    report = {
        "version": "muv_stage21_competition_nuisance_audit_20260913",
        "frozen_question": "Does a persistent competition-nuisance phenotype exist: keeping an ETF adds Top1 switching without adding marginal return?",
        "design": {
            "new_model_fit": False,
            "feature_search": False,
            "threshold_search": False,
            "policy_backtest": False,
            "nuisance_definition": "delta_switches > 0 and delta_return <= 0",
            "structural_nuisance_definition": "sum(delta_switches) > 0 and sum(delta_return) <= 0",
        },
        "overall": block(df),
        "by_era": {e: block(g) for e, g in df.groupby("era")},
        "cross_era": {
            "n_common_symbols": int(len(common)),
            "sum_delta_switches_spearman": sw_corr,
            "sum_delta_return_spearman": ret_corr,
            "structural_nuisance_flag_agreement": agreement,
            "structural_nuisance_both_eras": both_flagged,
            "n_structural_nuisance_both_eras": int(len(both_flagged)),
        },
        "symbol_era_rows": int(len(sym)),
        "interpretation_rule": "Proceed to prospective nuisance-risk identification only if nuisance is non-trivial and shows cross-era persistence in switching burden or literal structural-nuisance identity. Otherwise do not tune nuisance thresholds; branch to opportunity coverage or admission gate."
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
