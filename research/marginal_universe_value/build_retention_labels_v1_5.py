#!/usr/bin/env python3
"""MUV retention V1.5: local-Universe relational state.

Purpose
-------
Test the hypothesis that signed conditional MUV depends on the ETF's relation
to the *current competing set*, not only on ETF own state, one strongest
alternative, or coarse regime summaries.

This file intentionally adds only a small, frozen family of point-in-time
relationship summaries.  No future path identity, future return, label, or
post-hoc threshold is used.

For each incumbent i at month-end t, define the strongest three currently
qualified alternatives by exact as-of OLS score after excluding i.  Record:
  * i score relative to the mean of those alternatives;
  * score depth/spread among those alternatives;
  * i's 120d return-correlation to that local top-3 set;
  * i's 120d return-correlation to the rest of the risk Universe.

These are descriptive state variables only.  Stage 17 decides whether they add
strict expanding-window OOS sign information on path-active observations.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

import build_retention_labels_v1 as v1
import build_retention_labels_v1_2 as v12
import build_retention_labels_v1_3 as v13
import build_retention_labels_v1_4 as v14

VERSION = "muv_retention_labels_v1_5_local_relational_20260913"
LOCAL_K = 3
RISK_SYMBOLS = sorted(v1.FIXED15 - {v1.CASH_SIGNAL})


def _finite(x):
    try:
        z = float(x)
        return z if math.isfinite(z) else np.nan
    except Exception:
        return np.nan


def _agg(vals, how: str):
    z = np.asarray([_finite(x) for x in vals], dtype=float)
    z = z[np.isfinite(z)]
    if len(z) == 0:
        return np.nan
    if how == "mean":
        return float(np.mean(z))
    if how == "max":
        return float(np.max(z))
    if how == "std":
        return float(np.std(z, ddof=0))
    raise ValueError(how)


def _corr(corr120: pd.DataFrame, a: str, b: str):
    if corr120.empty or a not in corr120.index or b not in corr120.columns:
        return np.nan
    return _finite(corr120.at[a, b])


def make_state_rows_local_relational(
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
    rows = v14.make_state_rows_regime(
        features, score, rank, counts, ret, baseline_ranked,
        asof, label_period, base_metrics, counterfactual_by_symbol,
    )

    asof = pd.Timestamp(asof)
    hist_dates = score.index[score.index <= asof]
    d120 = hist_dates[-120:]

    corr120 = pd.DataFrame()
    if len(d120) >= 20:
        cols = [c for c in RISK_SYMBOLS if c in ret.columns]
        if len(cols) >= 2:
            corr120 = ret.loc[d120, cols].corr(
                min_periods=min(60, max(2, len(d120) // 2))
            )

    current_scores = (
        score.loc[asof].dropna().sort_values(ascending=False)
        if asof in score.index else pd.Series(dtype=float)
    )

    for out in rows:
        sym = str(out["symbol"])
        alternatives = current_scores.drop(index=sym, errors="ignore")
        local = alternatives.iloc[:LOCAL_K]
        local_syms = [str(x) for x in local.index]
        local_scores = [float(x) for x in local.to_numpy(dtype=float)]

        own_score = _finite(score.at[asof, sym]) if sym in score.columns and asof in score.index else np.nan
        local_mean_score = _agg(local_scores, "mean")

        out["dataset_version"] = VERSION
        out["local_alt_count"] = int(len(local_syms))
        for k in range(LOCAL_K):
            out[f"local_alt{k+1}_symbol"] = local_syms[k] if k < len(local_syms) else None
            out[f"local_alt{k+1}_score"] = local_scores[k] if k < len(local_scores) else np.nan

        out["local_own_minus_alt_top3_mean_score"] = (
            own_score - local_mean_score
            if math.isfinite(own_score) and math.isfinite(local_mean_score)
            else np.nan
        )
        out["local_alt_top3_score_std"] = _agg(local_scores, "std")
        out["local_alt1_minus_alt3_score"] = (
            local_scores[0] - local_scores[2] if len(local_scores) >= 3 else np.nan
        )

        top_corr = [_corr(corr120, sym, a) for a in local_syms]
        out["local_corr120_top3_mean"] = _agg(top_corr, "mean")
        out["local_corr120_top3_max"] = _agg(top_corr, "max")
        out["local_corr120_top3_std"] = _agg(top_corr, "std")

        rest = [
            a for a in RISK_SYMBOLS
            if a != sym and a not in set(local_syms)
        ]
        rest_corr = [_corr(corr120, sym, a) for a in rest]
        out["local_corr120_rest_mean"] = _agg(rest_corr, "mean")
        out["local_corr120_rest_max"] = _agg(rest_corr, "max")

        # A simple uniqueness contrast with no fitted threshold: positive means
        # i is more correlated to its immediate competitors than to the rest.
        tc = _finite(out["local_corr120_top3_mean"])
        rc = _finite(out["local_corr120_rest_mean"])
        out["local_corr120_top3_minus_rest_mean"] = (
            tc - rc if math.isfinite(tc) and math.isfinite(rc) else np.nan
        )

    return rows


def main() -> None:
    v1.VERSION = VERSION
    v1.monthly_metrics = v12.monthly_metrics_with_path
    v1.make_state_rows = make_state_rows_local_relational
    v1.main()


if __name__ == "__main__":
    main()
