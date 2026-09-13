#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

BOOT_N = 2000
BOOT_SEED = 20260914
LOW = (3, 7)
MID = (8, 15)
HIGH = (16, 30)


def era_from_month(s: pd.Series) -> np.ndarray:
    y = s.astype(str).str[:4].astype(int)
    return np.where(y <= 2024, "2021-24", "2025-26")


def month_shape(dist: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for m, g in dist.groupby("month", sort=True):
        g = g.sort_values("k")
        slope = float(np.polyfit(g["k"], g["return_mean"], 1)[0])
        best_k = int(g.loc[g["return_mean"].idxmax(), "k"])
        def band(lo, hi):
            x = g[g["k"].between(lo, hi)]["return_mean"]
            return float(x.mean()) if len(x) else np.nan
        rows.append({
            "month": m,
            "year": int(str(m)[:4]),
            "era": "2021-24" if int(str(m)[:4]) <= 2024 else "2025-26",
            "k_slope": slope,
            "best_k_descriptive_only": best_k,
            "return_low_k3_7": band(*LOW),
            "return_mid_k8_15": band(*MID),
            "return_high_k16_30": band(*HIGH),
        })
    out = pd.DataFrame(rows)
    out["high_minus_low"] = out["return_high_k16_30"] - out["return_low_k3_7"]
    return out


def bootstrap_months(ms: pd.DataFrame) -> dict:
    rng = np.random.default_rng(BOOT_SEED)
    out = {}
    for era, g in ms.groupby("era", sort=True):
        vals = g[["k_slope", "high_minus_low"]].dropna().to_numpy(float)
        n = len(vals)
        boots = np.empty((BOOT_N, 2), float)
        for b in range(BOOT_N):
            idx = rng.integers(0, n, n)
            boots[b] = vals[idx].mean(axis=0)
        out[era] = {
            "months": n,
            "k_slope_mean": float(vals[:, 0].mean()),
            "k_slope_ci95": [float(np.quantile(boots[:, 0], .025)), float(np.quantile(boots[:, 0], .975))],
            "high_minus_low_mean": float(vals[:, 1].mean()),
            "high_minus_low_ci95": [float(np.quantile(boots[:, 1], .025)), float(np.quantile(boots[:, 1], .975))],
            "positive_slope_month_share": float((vals[:, 0] > 0).mean()),
            "positive_high_minus_low_month_share": float((vals[:, 1] > 0).mean()),
        }
    return out


def nested_summary(nested: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    x = nested.copy()
    x["era"] = era_from_month(x["month"])
    step = x.groupby(["era", "k_from", "k_to"])["delta"].agg(
        n="size", mean="mean", median="median", positive_share=lambda s: float((s > 0).mean())
    ).reset_index()
    cumulative = x.groupby(["month", "path_id"], as_index=False)["delta"].sum().rename(columns={"delta": "k3_minus_k15"})
    cumulative["era"] = era_from_month(cumulative["month"])
    rep = {}
    for era, g in cumulative.groupby("era"):
        monthly = g.groupby("month")["k3_minus_k15"].mean()
        rep[era] = {
            "path_count": int(len(g)),
            "path_mean": float(g["k3_minus_k15"].mean()),
            "path_median": float(g["k3_minus_k15"].median()),
            "path_positive_share": float((g["k3_minus_k15"] > 0).mean()),
            "monthly_mean": float(monthly.mean()),
            "monthly_median": float(monthly.median()),
            "monthly_positive_share": float((monthly > 0).mean()),
        }
    return step, rep


def within_month_spearman(detail: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    rows = []
    mc = detail[detail["source"] == "same_k_mc"].copy()
    mc["era"] = era_from_month(mc["month"])
    for m, g in mc.groupby("month", sort=True):
        for metric in metrics:
            z = g[["total_return", metric]].replace([np.inf, -np.inf], np.nan).dropna()
            rho = np.nan
            if len(z) >= 20 and z[metric].nunique() > 1 and z["total_return"].nunique() > 1:
                rho = float(z["total_return"].rank().corr(z[metric].rank()))
            rows.append({"month": m, "era": g["era"].iloc[0], "metric": metric, "spearman": rho, "n": len(z)})
    return pd.DataFrame(rows)


def mechanism_summary(detail: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    mc = detail[detail["source"] == "same_k_mc"].copy()
    mc["era"] = era_from_month(mc["month"])
    metrics = ["winner_coverage", "dormant_member_share", "switches", "mean_top1_tenure", "mean_pairwise_corr", "effective_n"]
    ksum = mc.groupby(["era", "k"], as_index=False).agg(
        n=("total_return", "size"),
        return_mean=("total_return", "mean"),
        winner_coverage=("winner_coverage", "mean"),
        dormant_member_share=("dormant_member_share", "mean"),
        switches=("switches", "mean"),
        mean_top1_tenure=("mean_top1_tenure", "mean"),
        mean_pairwise_corr=("mean_pairwise_corr", "mean"),
        effective_n=("effective_n", "mean"),
    )
    wm = within_month_spearman(mc, metrics)
    rep = {}
    for era, g in wm.groupby("era"):
        rep[era] = {}
        for metric, h in g.groupby("metric"):
            s = h["spearman"].dropna()
            rep[era][metric] = {
                "months": int(len(s)),
                "mean_within_month_spearman": float(s.mean()) if len(s) else None,
                "median_within_month_spearman": float(s.median()) if len(s) else None,
                "positive_month_share": float((s > 0).mean()) if len(s) else None,
            }
    return ksum, wm, rep


def sampling_halves(detail: pd.DataFrame) -> dict:
    mc = detail[detail["source"] == "same_k_mc"].copy()
    def half(uid: str) -> int:
        return int.from_bytes(hashlib.blake2b(str(uid).encode(), digest_size=2).digest(), "little") % 2
    mc["half"] = mc["universe_id"].map(half)
    h = mc.groupby(["month", "k", "half"], as_index=False)["total_return"].mean()
    p = h.pivot_table(index=["month", "k"], columns="half", values="total_return").dropna()
    absdiff = (p[0] - p[1]).abs()
    curves = []
    for half_id in (0, 1):
        z = h[h["half"] == half_id].groupby("k")["total_return"].mean()
        curves.append(z)
    common = curves[0].index.intersection(curves[1].index)
    curve_corr = float(curves[0].loc[common].corr(curves[1].loc[common]))
    return {
        "median_abs_month_k_mean_return_difference": float(absdiff.median()),
        "p90_abs_month_k_mean_return_difference": float(absdiff.quantile(.90)),
        "aggregate_k_curve_correlation": curve_corr,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", required=True)
    ap.add_argument("--output-dir", default="stage1a-structure-output")
    args = ap.parse_args()
    src, out = Path(args.source_dir), Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    dist = pd.read_csv(src / "monthly_k_distribution.csv")
    nested = pd.read_csv(src / "nested_15_to_3_deltas.csv")
    detail = pd.read_parquet(src / "sampled_universe_detail.parquet")
    pool = pd.read_csv(src / "monthly_parent_pool_snapshots.csv")

    dist["era"] = era_from_month(dist["month"])
    dist["year"] = dist["month"].astype(str).str[:4].astype(int)
    ms = month_shape(dist)
    boot = bootstrap_months(ms)
    nstep, nrep = nested_summary(nested)
    kmech, wm, mrep = mechanism_summary(detail)
    halves = sampling_halves(detail)

    overall_k = dist.groupby("k", as_index=False).agg(
        months=("month", "nunique"), return_mean=("return_mean", "mean"), return_median=("return_median", "median"),
        return_p10=("return_p10", "mean"), return_p25=("return_p25", "mean"), return_p75=("return_p75", "mean"),
        return_p90=("return_p90", "mean"), top_decile_probability=("top_decile_probability", "mean"),
        switches=("switches_median", "mean"), tenure=("tenure_median", "mean"),
        winner_coverage=("winner_coverage_median", "mean"), dormant_share=("dormant_share_median", "mean"),
        effective_n=("effective_n_median", "mean"),
    )
    era_k = dist.groupby(["era", "k"], as_index=False).agg(
        months=("month", "nunique"), return_mean=("return_mean", "mean"), return_median=("return_median", "median"),
        top_decile_probability=("top_decile_probability", "mean"), switches=("switches_median", "mean"),
        tenure=("tenure_median", "mean"), winner_coverage=("winner_coverage_median", "mean"),
        dormant_share=("dormant_share_median", "mean"), effective_n=("effective_n_median", "mean"),
    )
    yearly = dist.groupby(["year", "k"], as_index=False)["return_mean"].mean()
    year_rep = {}
    for y, g in yearly.groupby("year"):
        year_rep[str(y)] = {
            "k_slope": float(np.polyfit(g["k"], g["return_mean"], 1)[0]),
            "descriptive_best_k": int(g.loc[g["return_mean"].idxmax(), "k"]),
            "low_k3_7": float(g[g["k"].between(*LOW)]["return_mean"].mean()),
            "mid_k8_15": float(g[g["k"].between(*MID)]["return_mean"].mean()),
            "high_k16_30": float(g[g["k"].between(*HIGH)]["return_mean"].mean()),
        }

    pool_counts = pool.groupby("month")["symbol"].nunique()
    report = {
        "stage": "new_stage_1a",
        "source_run": 34772895471,
        "source_artifact": "universe-size-stage1-repair-34772895471",
        "months": int(dist["month"].nunique()),
        "parent_pool_monthly_count": {
            "mean": float(pool_counts.mean()), "median": float(pool_counts.median()),
            "min": int(pool_counts.min()), "max": int(pool_counts.max())},
        "month_cluster_bootstrap": boot,
        "nested_k3_minus_k15": nrep,
        "yearly_structure": year_rep,
        "mechanism_within_month_spearman": mrep,
        "sampling_hash_half_stability": halves,
        "interpretation": {
            "precise_k_selected": False,
            "stage1_status": "open_pending_predeclared_robustness",
            "decision_rule": "Era reversal requires alternative-seed and corr_threshold=0.90 replication before any stable-K freeze."
        }
    }

    overall_k.to_csv(out / "stage1a_overall_k.csv", index=False)
    era_k.to_csv(out / "stage1a_era_k.csv", index=False)
    ms.to_csv(out / "stage1a_month_shapes.csv", index=False)
    nstep.to_csv(out / "stage1a_nested_step_summary.csv", index=False)
    kmech.to_csv(out / "stage1a_k_mechanisms.csv", index=False)
    wm.to_csv(out / "stage1a_within_month_mechanism_spearman.csv", index=False)
    (out / "stage1a_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
