#!/usr/bin/env python3
"""MUV retention V1.3: add point-in-time ETF-vs-alternative features.

The remove-one audit in V1.2 showed zero spillover: removing ETF i changes the
next-month path only on days when i itself would have won OLS Top1.  Therefore
conditional value is naturally relative to the strongest available alternative.

V1.3 adds only decision-time X features.  No future counterfactual replacement
identity is used.  `alt_symbol_asof` is the highest *current as-of* qualified
score among Fixed15 excluding the subject ETF.  Feature state for both sides is
the latest observation known on/before as-of, max 7 calendar days, matching
V1.1's point-in-time policy.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

import build_retention_labels_v1 as v1
import build_retention_labels_v1_1 as v11
import build_retention_labels_v1_2 as v12

VERSION = "muv_retention_labels_v1_3_20260912"

PAIR_COLS = [
    "score", "annual", "r2", "current_resid", "score_delta", "r2_delta",
    "slope_delta", "ret3", "ret5", "ret10", "ret20", "ret60",
    "dist_high20", "dist_high60", "vol20", "vol60",
    "efficiency10", "efficiency20", "ma10_dist",
    "avg_amount60", "median_amount60",
]


def _latest_state(features: pd.DataFrame, sym: str, asof: pd.Timestamp):
    h = features.loc[
        (features["symbol"].astype(str) == str(sym))
        & (features["date"] <= asof)
    ].sort_values("date")
    if h.empty:
        return None, None, None
    row = h.iloc[-1]
    d = pd.Timestamp(row["date"])
    age = int((asof.normalize() - d.normalize()).days)
    if int(row["history_bars"]) < v1.LOOKBACK or age > v11.MAX_STATE_AGE_DAYS:
        return None, None, None
    return row, d, age


def _days_since_rank1(rank: pd.DataFrame, sym: str, hist_dates: pd.Index):
    if sym not in rank.columns or len(hist_dates) == 0:
        return np.nan
    h = rank.loc[hist_dates, sym]
    hits = np.flatnonzero((h == 1).to_numpy())
    return int(len(h) - 1 - hits[-1]) if len(hits) else np.nan


def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else np.nan
    except Exception:
        return np.nan


def make_state_rows_pairwise(
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
    rows = v12.make_state_rows_v1_2(
        features, score, rank, counts, ret, baseline_ranked,
        asof, label_period, base_metrics, counterfactual_by_symbol,
    )
    asof = pd.Timestamp(asof)
    hist_dates = score.index[score.index <= asof]
    last20 = hist_dates[-20:]
    last120 = hist_dates[-120:]
    corr120 = (
        ret.loc[last120].corr(min_periods=min(60, max(2, len(last120) // 2)))
        if len(last120) >= 20 else pd.DataFrame()
    )

    current_scores = score.loc[asof].dropna().sort_values(ascending=False)

    for out in rows:
        sym = str(out["symbol"])
        alternatives = current_scores.drop(index=sym, errors="ignore")
        alt = str(alternatives.index[0]) if len(alternatives) else None
        alt_score_exact = _num(alternatives.iloc[0]) if len(alternatives) else np.nan

        own_state, own_state_date, own_age = _latest_state(features, sym, asof)
        alt_state, alt_state_date, alt_age = (
            _latest_state(features, alt, asof) if alt is not None else (None, None, None)
        )

        out["dataset_version"] = VERSION
        out["alt_symbol_asof"] = alt
        out["alt_is_cash_signal"] = bool(alt == v1.CASH_SIGNAL) if alt is not None else False
        out["alt_score_exact_asof"] = alt_score_exact
        out["alt_state_date"] = alt_state_date
        out["alt_quote_age_calendar_days"] = alt_age if alt_age is not None else np.nan

        own_score_exact = _num(score.at[asof, sym]) if sym in score.columns else np.nan
        out["pair_score_exact_gap_alt"] = (
            own_score_exact - alt_score_exact
            if math.isfinite(own_score_exact) and math.isfinite(alt_score_exact)
            else np.nan
        )
        out["pair_score_exact_ratio_alt"] = (
            own_score_exact / alt_score_exact
            if math.isfinite(own_score_exact) and math.isfinite(alt_score_exact) and alt_score_exact != 0
            else np.nan
        )

        alt_top1_freq20 = np.nan
        alt_top3_freq20 = np.nan
        alt_days_since_top1 = np.nan
        if alt is not None and alt in rank.columns and len(last20):
            alt_top1_freq20 = float((rank.loc[last20, alt] == 1).mean())
            alt_top3_freq20 = float((rank.loc[last20, alt] <= 3).mean())
            alt_days_since_top1 = _days_since_rank1(rank, alt, hist_dates)
        out["alt_top1_freq20"] = alt_top1_freq20
        out["alt_top3_freq20"] = alt_top3_freq20
        out["alt_days_since_top1"] = alt_days_since_top1
        out["pair_top1_freq20_gap_alt"] = (
            _num(out.get("top1_freq20")) - alt_top1_freq20
            if math.isfinite(_num(out.get("top1_freq20"))) and math.isfinite(_num(alt_top1_freq20))
            else np.nan
        )
        out["pair_top3_freq20_gap_alt"] = (
            _num(out.get("top3_freq20")) - alt_top3_freq20
            if math.isfinite(_num(out.get("top3_freq20"))) and math.isfinite(_num(alt_top3_freq20))
            else np.nan
        )

        corr_alt = np.nan
        if alt is not None and not corr120.empty and sym in corr120.index and alt in corr120.columns:
            corr_alt = _num(corr120.at[sym, alt])
        out["pair_corr120_with_alt"] = corr_alt

        for col in PAIR_COLS:
            ov = _num(own_state[col]) if own_state is not None and col in own_state else np.nan
            av = _num(alt_state[col]) if alt_state is not None and col in alt_state else np.nan
            out[f"alt_{col}"] = av
            out[f"pair_{col}_gap_alt"] = ov - av if math.isfinite(ov) and math.isfinite(av) else np.nan
            out[f"pair_{col}_ratio_alt"] = (
                ov / av if math.isfinite(ov) and math.isfinite(av) and av != 0 else np.nan
            )

    return rows


def main() -> None:
    v1.VERSION = VERSION
    v1.monthly_metrics = v12.monthly_metrics_with_path
    v1.make_state_rows = make_state_rows_pairwise
    v1.main()


if __name__ == "__main__":
    main()
