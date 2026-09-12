#!/usr/bin/env python3
"""MUV retention V1.4: add point-in-time market / competition regime X features.

Stage 4 showed that pairwise sign discrimination alternates strongly by year
(works in 2023/2026, reverses in 2024/2025).  V1.4 adds a deliberately small
set of market-level state variables available at the decision date.  They are
computed only from Fixed15 history through the as-of date and are repeated for
all ETF rows in a month.

No future outcome or future replacement identity is used.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

import build_retention_labels_v1 as v1
import build_retention_labels_v1_2 as v12
import build_retention_labels_v1_3 as v13

VERSION = "muv_retention_labels_v1_4_20260912"
RISK_SYMBOLS = sorted(v1.FIXED15 - {v1.CASH_SIGNAL})


def _identity(x):
    if x is None or pd.isna(x):
        return None
    return str(x)


def _switches(values) -> int:
    vals = [_identity(x) for x in values]
    if len(vals) <= 1:
        return 0
    return int(sum(vals[i] != vals[i - 1] for i in range(1, len(vals))))


def _current_streak(values) -> int:
    vals = [_identity(x) for x in values]
    if not vals:
        return 0
    last = vals[-1]
    n = 0
    for x in reversed(vals):
        if x != last:
            break
        n += 1
    return int(n)


def _hhi(values) -> float:
    vals = [_identity(x) for x in values]
    if not vals:
        return np.nan
    s = pd.Series(["__NONE__" if x is None else x for x in vals])
    p = s.value_counts(normalize=True)
    return float((p * p).sum())


def _finite(vals):
    return [float(x) for x in vals if x is not None and pd.notna(x) and math.isfinite(float(x))]


def _median(vals):
    z = _finite(vals)
    return float(np.median(z)) if z else np.nan


def _std(vals):
    z = _finite(vals)
    return float(np.std(z, ddof=0)) if z else np.nan


def _mean(vals):
    z = _finite(vals)
    return float(np.mean(z)) if z else np.nan


def regime_features(
    features: pd.DataFrame,
    score: pd.DataFrame,
    ret: pd.DataFrame,
    baseline_ranked: pd.Series,
    asof: pd.Timestamp,
) -> dict:
    asof = pd.Timestamp(asof)
    hist_dates = score.index[score.index <= asof]
    d20 = hist_dates[-20:]
    d60 = hist_dates[-60:]
    d120 = hist_dates[-120:]

    raw20 = baseline_ranked.reindex(d20).tolist()
    raw60 = baseline_ranked.reindex(d60).tolist()
    target20 = [v1._target(x) for x in raw20]
    target60 = [v1._target(x) for x in raw60]

    raw20_s = pd.Series([_identity(x) for x in raw20], dtype=object)
    raw60_s = pd.Series([_identity(x) for x in raw60], dtype=object)

    states = []
    for sym in RISK_SYMBOLS:
        row, state_date, age = v13._latest_state(features, sym, asof)
        if row is not None:
            states.append(row)

    def scol(name):
        return [_finite([r.get(name)])[0] for r in states if len(_finite([r.get(name)]))]

    ret20 = scol("ret20")
    ret5 = scol("ret5")
    vol20 = scol("vol20")
    eff10 = scol("efficiency10")
    resid = scol("current_resid")
    raw_score = scol("score")

    corr_median = np.nan
    corr_mean = np.nan
    if len(d120) >= 20:
        cols = [c for c in RISK_SYMBOLS if c in ret.columns]
        if len(cols) >= 2:
            cm = ret.loc[d120, cols].corr(min_periods=min(60, max(2, len(d120) // 2)))
            arr = cm.to_numpy(dtype=float)
            tri = arr[np.triu_indices_from(arr, k=1)]
            tri = tri[np.isfinite(tri)]
            if len(tri):
                corr_median = float(np.median(tri))
                corr_mean = float(np.mean(tri))

    qualified_scores = score.loc[asof].dropna() if asof in score.index else pd.Series(dtype=float)
    risk_qualified = qualified_scores.drop(index=v1.CASH_SIGNAL, errors="ignore")

    return {
        "regime_raw_top1_switches20": _switches(raw20),
        "regime_raw_top1_switches60": _switches(raw60),
        "regime_target_switches20": _switches(target20),
        "regime_target_switches60": _switches(target60),
        "regime_top1_current_streak": _current_streak(raw60),
        "regime_top1_hhi20": _hhi(raw20),
        "regime_top1_hhi60": _hhi(raw60),
        "regime_cash_top1_freq20": float((raw20_s == v1.CASH_SIGNAL).mean()) if len(raw20_s) else np.nan,
        "regime_cash_top1_freq60": float((raw60_s == v1.CASH_SIGNAL).mean()) if len(raw60_s) else np.nan,
        "regime_none_target_freq20": float(pd.Series(target20, dtype=object).isna().mean()) if len(target20) else np.nan,
        "regime_risk_qualified_count": int(len(risk_qualified)),
        "regime_risk_ret20_median": _median(ret20),
        "regime_risk_ret20_std": _std(ret20),
        "regime_risk_ret20_positive_frac": float(np.mean(np.asarray(ret20) > 0)) if ret20 else np.nan,
        "regime_risk_ret5_median": _median(ret5),
        "regime_risk_ret5_std": _std(ret5),
        "regime_risk_vol20_median": _median(vol20),
        "regime_risk_efficiency10_median": _median(eff10),
        "regime_risk_resid_std": _std(resid),
        "regime_risk_score_median_raw": _median(raw_score),
        "regime_risk_score_std_raw": _std(raw_score),
        "regime_risk_corr120_median": corr_median,
        "regime_risk_corr120_mean": corr_mean,
        "regime_state_symbol_count": int(len(states)),
    }


def make_state_rows_regime(
    features: pd.DataFrame,
    score: pd.DataFrame,
    rank: pd.DataFrame,
    counts: pd.Series,
    ret: pd.DataFrame,
    baseline_ranked: pd.Series,
    asof: pd.Timestamp,
    label_period: pd.Period,
    base_metrics: dict,
    counterfactual_by_symbol: dict[str, dict],
) -> list[dict]:
    rows = v13.make_state_rows_pairwise(
        features, score, rank, counts, ret, baseline_ranked,
        asof, label_period, base_metrics, counterfactual_by_symbol,
    )
    reg = regime_features(features, score, ret, baseline_ranked, asof)
    for row in rows:
        row["dataset_version"] = VERSION
        row.update(reg)
    return rows


def main() -> None:
    v1.VERSION = VERSION
    v1.monthly_metrics = v12.monthly_metrics_with_path
    v1.make_state_rows = make_state_rows_regime
    v1.main()


if __name__ == "__main__":
    main()
