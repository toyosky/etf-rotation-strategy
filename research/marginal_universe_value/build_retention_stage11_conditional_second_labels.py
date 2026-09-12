#!/usr/bin/env python3
"""Stage 11: build conditional second-order retention labels.

Frozen in STAGE11_CONDITIONAL_SECOND_LABELS_DESIGN_20260913.md.

Observation unit:
    label_month x hypothetical first_removed_i x second_candidate_j

Conditional second-order retention value:
    MUV2(j | U-i) = V(U-i) - V(U-i-j)

This stage is diagnostic only. It does not fit a predictive policy and does not
search features or thresholds.
"""

from __future__ import annotations

import json
import math
import os
import resource
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_retention_labels_v1 as v1
import build_retention_labels_v1_2 as v12
import model_retention_stage10_dynamic_second as s10
from full_market_ols_storage import _db_url, build_features
from universe.oracle_replacement_v1 import FIXED15, CASH_SIGNAL

FIRST_LABELS = Path("muv-retention-labels-v1.parquet")
STAGE7_MONTHLY = Path("muv-retention-stage7-monthly-policy.csv")
OUT_PARQUET = Path("muv-retention-stage11-conditional-second.parquet")
OUT_STAGE7_SLICE = Path("muv-retention-stage11-stage7-slice.csv")
OUT_REPORT = Path("muv-retention-stage11-report.json")

EPS = 1e-12
VERSION = "muv_stage11_conditional_second_20260913"


def peak_rss_mb() -> float:
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def _symbol(v) -> str:
    s = str(v)
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(6)


def _finite(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else np.nan
    except Exception:
        return np.nan


def _basic_label_stats(df: pd.DataFrame, prefix: str = "") -> dict:
    if df.empty:
        return {
            f"{prefix}rows": 0,
            f"{prefix}zero_share": None,
            f"{prefix}positive_share": None,
            f"{prefix}negative_share": None,
            f"{prefix}path_active_share": None,
        }
    d = pd.to_numeric(df["delta_return"], errors="coerce")
    active = pd.to_numeric(df["path_direct_selection_days"], errors="coerce").fillna(0).gt(0)
    return {
        f"{prefix}rows": int(len(df)),
        f"{prefix}zero_share": float(np.isclose(d, 0.0, atol=EPS).mean()),
        f"{prefix}positive_share": float(d.gt(EPS).mean()),
        f"{prefix}negative_share": float(d.lt(-EPS).mean()),
        f"{prefix}path_active_share": float(active.mean()),
        f"{prefix}active_positive_share": float(d[active].gt(EPS).mean()) if active.any() else None,
        f"{prefix}active_negative_share": float(d[active].lt(-EPS).mean()) if active.any() else None,
        f"{prefix}mean_abs_delta_return": float(d.abs().mean()),
        f"{prefix}median_abs_delta_return": float(d.abs().median()),
    }


def _transport_diagnostics(cond: pd.DataFrame, first: pd.DataFrame) -> dict:
    orig = first[["label_month", "symbol", "delta_return", "path_direct_selection_days"]].copy()
    orig["label_month"] = orig["label_month"].astype(str)
    orig["symbol"] = orig["symbol"].map(_symbol)
    orig = orig.rename(columns={
        "symbol": "second_candidate",
        "delta_return": "first_order_delta_return",
        "path_direct_selection_days": "first_order_direct_days",
    })

    z = cond.merge(orig, on=["label_month", "second_candidate"], how="left")
    a = pd.to_numeric(z["first_order_delta_return"], errors="coerce")
    b = pd.to_numeric(z["delta_return"], errors="coerce")
    a0 = np.isclose(a, 0.0, atol=EPS)
    b0 = np.isclose(b, 0.0, atol=EPS)
    both_nonzero = (~a0) & (~b0) & a.notna() & b.notna()

    sign_flip = np.zeros(len(z), dtype=bool)
    if both_nonzero.any():
        sign_flip[both_nonzero.to_numpy()] = (
            np.sign(a[both_nonzero].to_numpy(dtype=float))
            != np.sign(b[both_nonzero].to_numpy(dtype=float))
        )

    both = z.loc[both_nonzero, ["first_order_delta_return", "delta_return"]].dropna()
    pearson = None
    spearman = None
    if len(both) >= 3 and both.iloc[:, 0].nunique() > 1 and both.iloc[:, 1].nunique() > 1:
        pearson = float(both.corr(method="pearson").iloc[0, 1])
        spearman = float(both.corr(method="spearman").iloc[0, 1])

    return {
        "matched_rows": int(a.notna().sum()),
        "both_nonzero_rows": int(both_nonzero.sum()),
        "sign_flip_share_given_both_nonzero": float(sign_flip[both_nonzero.to_numpy()].mean()) if both_nonzero.any() else None,
        "first_zero_to_conditional_nonzero_share": float((a0 & ~b0 & a.notna() & b.notna()).mean()),
        "first_nonzero_to_conditional_zero_share": float((~a0 & b0 & a.notna() & b.notna()).mean()),
        "absolute_change_gt_1pp_share": float(((a - b).abs() > 0.01).mean()),
        "absolute_change_gt_3pp_share": float(((a - b).abs() > 0.03).mean()),
        "pearson_given_both_nonzero": pearson,
        "spearman_given_both_nonzero": spearman,
    }


def _interaction_dispersion(cond: pd.DataFrame) -> dict:
    g = (
        cond.groupby(["label_month", "second_candidate"])["delta_return"]
        .agg(["count", "std", "min", "max"])
        .reset_index()
    )
    g = g[g["count"] >= 2].copy()
    if g.empty:
        return {"groups": 0}
    g["range"] = g["max"] - g["min"]
    return {
        "groups": int(len(g)),
        "median_within_state_std": float(g["std"].median()),
        "mean_within_state_std": float(g["std"].mean()),
        "median_within_state_range": float(g["range"].median()),
        "share_range_gt_1pp": float((g["range"] > 0.01).mean()),
        "share_range_gt_3pp": float((g["range"] > 0.03).mean()),
        "max_within_state_range": float(g["range"].max()),
    }


def main() -> None:
    db = os.getenv("ETF_DAILY_BARS_DATABASE_URL")
    if not db:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    mem0 = peak_rss_mb()
    first = pd.read_parquet(FIRST_LABELS)
    first["label_month"] = first["label_month"].astype(str)
    first["symbol"] = first["symbol"].map(_symbol)
    first["delta_return"] = pd.to_numeric(first["delta_return"], errors="coerce")

    stage7 = pd.read_csv(STAGE7_MONTHLY)
    stage7["label_month"] = stage7["label_month"].astype(str)

    engine = create_engine(_db_url(db), pool_pre_ping=True)
    bars = v1.load_fixed15_bars(engine)
    mem_bars = peak_rss_mb()
    features = build_features(bars)
    mem_features = peak_rss_mb()

    calendar, score, _, _, oo, _, ret = v1.prepare_wides(bars, features)
    baseline_ranked, _ = v1.rank_pool(score, set(FIXED15))

    rows = []
    month_audit = []
    for mo in sorted(first["label_month"].unique()):
        lp = pd.Period(mo, freq="M")
        asof, initial_prev = s10.month_setup(calendar, baseline_ranked, lp)
        first_candidates = sorted(first.loc[first.label_month == mo, "symbol"].unique())
        pair_cache: dict[frozenset[str], dict] = {}
        before = len(rows)

        for first_removed in first_candidates:
            if first_removed == CASH_SIGNAL or first_removed not in FIXED15:
                continue
            u1 = set(FIXED15) - {first_removed}
            rank1, count1 = v1.rank_pool(score, u1)
            base = v12.monthly_metrics_with_path(
                rank1, count1, oo, calendar, lp, initial_prev
            )
            x = s10.reduced_feature_frame(u1, asof, features, score, ret)
            if x.empty:
                continue

            for _, xr in x.iterrows():
                second = _symbol(xr["symbol"])
                if second == CASH_SIGNAL or second == first_removed or second not in u1:
                    continue

                key = frozenset((first_removed, second))
                cf = pair_cache.get(key)
                if cf is None:
                    rank2, count2 = v1.rank_pool(score, u1 - {second})
                    cf = v12.monthly_metrics_with_path(
                        rank2, count2, oo, calendar, lp, initial_prev
                    )
                    pair_cache[key] = cf

                row = {
                    "dataset_version": VERSION,
                    "decision_type": "conditional_second_retention",
                    "label_month": mo,
                    "asof_date": asof,
                    "first_removed": first_removed,
                    "second_candidate": second,
                    "conditional_universe_size": int(len(u1)),
                    "prev_target": initial_prev,
                    "first_removed_is_prev_target": bool(initial_prev is not None and first_removed == initial_prev),
                    "second_candidate_is_prev_target": bool(initial_prev is not None and second == initial_prev),
                    "base_u1_return": float(base["total_return"]),
                    "base_u1_max_drawdown": float(base["max_drawdown"]),
                    "base_u1_switches": int(base["switches"]),
                    "base_u1_turnover_sides": int(base["turnover_sides"]),
                    "cf_u2_return": float(cf["total_return"]),
                    "cf_u2_max_drawdown": float(cf["max_drawdown"]),
                    "cf_u2_switches": int(cf["switches"]),
                    "cf_u2_turnover_sides": int(cf["turnover_sides"]),
                    "delta_return": float(base["total_return"] - cf["total_return"]),
                    "delta_max_drawdown": float(base["max_drawdown"] - cf["max_drawdown"]),
                    "delta_switches": int(base["switches"] - cf["switches"]),
                    "delta_turnover_sides": int(base["turnover_sides"] - cf["turnover_sides"]),
                }
                row.update(v12.path_labels(second, base, cf))

                for col, val in xr.items():
                    if col == "symbol":
                        continue
                    if isinstance(val, (np.bool_, bool)):
                        row[col] = bool(val)
                    elif pd.isna(val):
                        row[col] = np.nan
                    elif isinstance(val, (np.integer, int)):
                        row[col] = int(val)
                    elif isinstance(val, (np.floating, float)):
                        row[col] = float(val)
                    else:
                        row[col] = val
                rows.append(row)

        month_audit.append({
            "label_month": mo,
            "asof_date": str(asof.date()),
            "first_candidate_count": int(len(first_candidates)),
            "conditional_rows": int(len(rows) - before),
        })

    panel = pd.DataFrame(rows)
    if panel.empty:
        raise RuntimeError("Stage11 produced no conditional second-order labels")
    panel = panel.sort_values(["label_month", "first_removed", "second_candidate"]).reset_index(drop=True)
    panel.to_parquet(OUT_PARQUET, index=False, compression="zstd")
    mem_panel = peak_rss_mb()

    # Slice to the actual frozen Stage-7 first-removal states.
    acts = stage7[stage7["act_primary_regime90"]].copy()
    acts["first_removed"] = acts["symbol_primary_regime90"].map(_symbol)
    actual = panel.merge(
        acts[["label_month", "first_removed"]],
        on=["label_month", "first_removed"],
        how="inner",
    )
    actual.to_csv(OUT_STAGE7_SLICE, index=False)

    report = {
        "version": VERSION,
        "design": {
            "unit": "label_month x hypothetical first_removed x second_candidate",
            "label": "V(U-i) - V(U-i-j)",
            "baseline_universe": "Fixed15",
            "cash_signal_forced": CASH_SIGNAL,
            "feature_search": False,
            "threshold_search": False,
            "policy_fit": False,
        },
        "panel": {
            "rows": int(len(panel)),
            "months": int(panel.label_month.nunique()),
            "first_removed_symbols": int(panel.first_removed.nunique()),
            "second_candidate_symbols": int(panel.second_candidate.nunique()),
            "label_month_min": str(panel.label_month.min()),
            "label_month_max": str(panel.label_month.max()),
            "parquet_bytes": int(OUT_PARQUET.stat().st_size),
            **_basic_label_stats(panel),
        },
        "transport_vs_first_order": _transport_diagnostics(panel, first),
        "interaction_dispersion": _interaction_dispersion(panel),
        "actual_stage7_first_removal_states": {
            "first_action_months": int(acts.label_month.nunique()),
            "rows": int(len(actual)),
            **_basic_label_stats(actual, prefix="conditional_"),
            "transport_vs_first_order": _transport_diagnostics(actual, first),
        },
        "memory_peak_mb": {
            "startup": mem0,
            "after_bars": mem_bars,
            "after_features": mem_features,
            "after_panel": mem_panel,
            "final": peak_rss_mb(),
        },
        "month_audit": month_audit,
        "notes": [
            "Stage11 is diagnostic only; no second-step model or policy threshold is fit.",
            "Expanded rows are heavily clustered by month and counterfactual universe; row count must not be treated as independent sample size.",
            "Any future Stage12 model must be walk-forward and use month-balanced sample weighting or equivalent clustering controls.",
        ],
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
