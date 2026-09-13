#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

MIN_TRAIN = 24
ANCHOR_K = 15
BOOTSTRAP_SEED = 20260914
BOOTSTRAP_N = 5000


def logsum(s: pd.Series) -> float:
    x = pd.to_numeric(s, errors="coerce").dropna().to_numpy(float)
    if len(x) == 0 or np.any(x <= -1):
        return float("nan")
    return float(np.log1p(x).sum())


def metrics(g: pd.DataFrame, col: str) -> dict:
    x = pd.to_numeric(g[col], errors="coerce").dropna()
    return {
        "n": int(len(x)),
        "mean": float(x.mean()) if len(x) else None,
        "median": float(x.median()) if len(x) else None,
        "log_sum": logsum(x),
    }


def bootstrap_mean_ci(x: np.ndarray, seed=BOOTSTRAP_SEED, n=BOOTSTRAP_N) -> list[float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if not len(x):
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    vals = np.empty(n, float)
    for i in range(n):
        vals[i] = rng.choice(x, size=len(x), replace=True).mean()
    return [float(np.quantile(vals, .025)), float(np.quantile(vals, .975))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage1-dir", required=True)
    ap.add_argument("--output-dir", default="stage3b-output")
    args = ap.parse_args()
    src = Path(args.stage1_dir) / "monthly_k_distribution.csv"
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(src)
    d["month"] = d["month"].astype(str)
    d["k"] = d["k"].astype(int)
    d = d[(d.k >= 3) & (d.k <= 30)].copy()
    months = sorted(d.month.unique())
    rows = []
    for i, month in enumerate(months):
        if i < MIN_TRAIN:
            continue
        hist_months = months[:i]
        hist = d[d.month.isin(hist_months)].copy()
        cur = d[d.month == month].set_index("k")
        byk = hist.groupby("k").return_mean.agg(["mean", "std", "count"]).sort_index()
        byk["se"] = byk["std"] / np.sqrt(byk["count"].clip(lower=1))
        best_mean = byk["mean"].max()
        best_candidates = byk.index[np.isclose(byk["mean"], best_mean, rtol=0, atol=1e-15)]
        train_best_k = int(min(best_candidates))
        best_se = float(byk.loc[train_best_k, "se"]) if np.isfinite(byk.loc[train_best_k, "se"]) else 0.0
        threshold = float(best_mean - best_se)
        admissible = [int(k) for k, r in byk.iterrows() if float(r["mean"]) >= threshold]
        lo, hi = min(admissible), max(admissible)
        med = int(round(float(np.median(admissible))))
        hindsight_best_k = int(cur.return_mean.idxmax())
        rows.append({
            "month": month,
            "year": int(month[:4]),
            "train_best_k": train_best_k,
            "anchor_k": ANCHOR_K,
            "range_lo": lo,
            "range_hi": hi,
            "range_width": hi-lo,
            "range_median_k": med,
            "hindsight_best_k": hindsight_best_k,
            "train_best_return": float(cur.loc[train_best_k, "return_mean"]),
            "anchor_return": float(cur.loc[ANCHOR_K, "return_mean"]),
            "range_median_return": float(cur.loc[med, "return_mean"]),
            "hindsight_best_return": float(cur.loc[hindsight_best_k, "return_mean"]),
            "paired_delta_trainbest_minus_anchor": float(cur.loc[train_best_k, "return_mean"] - cur.loc[ANCHOR_K, "return_mean"]),
        })
    r = pd.DataFrame(rows)
    r.to_csv(out/"stage3b_expanding_size_fallback.csv", index=False)
    if len(r):
        r["era"] = np.where(r.year <= 2024, "2023-24", "2025-26")
    summary = {
        "stage": "new_stage_3b",
        "name": "conservative_size_fallback_audit",
        "source": "frozen New Stage1 base monthly_k_distribution.csv",
        "min_train_months": MIN_TRAIN,
        "anchor_k": ANCHOR_K,
        "bootstrap_n": BOOTSTRAP_N,
        "overall": {
            "train_best": metrics(r, "train_best_return"),
            "anchor_k15": metrics(r, "anchor_return"),
            "range_median": metrics(r, "range_median_return"),
            "hindsight_ceiling": metrics(r, "hindsight_best_return"),
            "paired_delta_mean": float(r.paired_delta_trainbest_minus_anchor.mean()) if len(r) else None,
            "paired_delta_median": float(r.paired_delta_trainbest_minus_anchor.median()) if len(r) else None,
            "paired_delta_bootstrap_95pct": bootstrap_mean_ci(r.paired_delta_trainbest_minus_anchor.to_numpy(float)) if len(r) else [None, None],
            "train_best_k_mean": float(r.train_best_k.mean()) if len(r) else None,
            "train_best_k_median": float(r.train_best_k.median()) if len(r) else None,
            "train_best_k_changes": int((r.train_best_k != r.train_best_k.shift()).sum()-1) if len(r) else 0,
            "range_width_mean": float(r.range_width.mean()) if len(r) else None,
            "range_width_median": float(r.range_width.median()) if len(r) else None,
        },
        "by_era": {},
    }
    if len(r):
        for era, g in r.groupby("era"):
            summary["by_era"][era] = {
                "train_best": metrics(g, "train_best_return"),
                "anchor_k15": metrics(g, "anchor_return"),
                "paired_delta_mean": float(g.paired_delta_trainbest_minus_anchor.mean()),
                "paired_delta_bootstrap_95pct": bootstrap_mean_ci(g.paired_delta_trainbest_minus_anchor.to_numpy(float), seed=BOOTSTRAP_SEED + (1 if era=="2025-26" else 0)),
                "train_best_k_mean": float(g.train_best_k.mean()),
                "train_best_k_median": float(g.train_best_k.median()),
                "range_width_mean": float(g.range_width.mean()),
            }
    (out/"stage3b_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
