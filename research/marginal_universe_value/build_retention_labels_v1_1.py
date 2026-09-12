#!/usr/bin/env python3
"""MUV retention labels V1.1.

V1.1 fixes one audit issue from the first successful V1 run: an incumbent was
previously omitted from the month x ETF panel when it had no quote on the exact
month-end as-of trading date. That creates selection bias for instruments with
an occasional one-day quote lag (for example some LOF/QDII-like instruments).

The portfolio/counterfactual engine is unchanged. For ETF own-state features
only, V1.1 uses the latest observation available on or before the as-of date,
with a maximum calendar staleness of 7 days, and records the state date / quote
age explicitly. If the instrument has never accumulated the 26-price OLS
lookback by then, it is still correctly absent from the retention panel.
"""

from __future__ import annotations

import pandas as pd

import build_retention_labels_v1 as v1

VERSION = "muv_retention_labels_v1_1_20260912"
MAX_STATE_AGE_DAYS = 7
_ORIGINAL_MAKE_STATE_ROWS = v1.make_state_rows


def make_state_rows_latest_available(
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
    asof = pd.Timestamp(asof)
    noncash = sorted(v1.FIXED15 - {v1.CASH_SIGNAL})

    exact = features.loc[features["date"] == asof, "symbol"].astype(str)
    have_exact = set(exact.tolist())
    extras = []
    state_meta: dict[str, tuple[pd.Timestamp, int]] = {}

    for sym in noncash:
        hist = features.loc[
            (features["symbol"].astype(str) == sym)
            & (features["date"] <= asof)
        ].sort_values("date")
        if hist.empty:
            continue
        last = hist.iloc[-1].copy()
        state_date = pd.Timestamp(last["date"])
        age = int((asof.normalize() - state_date.normalize()).days)
        if int(last["history_bars"]) < v1.LOOKBACK or age > MAX_STATE_AGE_DAYS:
            continue
        state_meta[sym] = (state_date, age)
        if sym not in have_exact:
            # Only feature state is carried forward. Ranking/competition remains
            # the actual as-of score matrix, so a no-quote ETF does not magically
            # participate in that day's Top1 competition.
            last["date"] = asof
            extras.append(last)

    if extras:
        feature_view = pd.concat([features, pd.DataFrame(extras)], ignore_index=True)
    else:
        feature_view = features

    rows = _ORIGINAL_MAKE_STATE_ROWS(
        feature_view,
        score,
        rank,
        counts,
        ret,
        baseline_ranked,
        asof,
        label_period,
        base_metrics,
        counterfactual_by_symbol,
    )

    for row in rows:
        sym = str(row["symbol"])
        state_date, age = state_meta[sym]
        row["dataset_version"] = VERSION
        row["x_state_date"] = state_date
        row["x_quote_age_calendar_days"] = age
        row["x_quote_on_asof"] = bool(age == 0)
    return rows


def main() -> None:
    v1.VERSION = VERSION
    v1.make_state_rows = make_state_rows_latest_available
    v1.main()


if __name__ == "__main__":
    main()
