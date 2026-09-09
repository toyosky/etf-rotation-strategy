#!/usr/bin/env python3
"""Monthly liquidity-first correlation representative research.

Goal
----
Test a neutral slow-frequency universe layer that does *not* predict next
month's winner.  It only removes redundant ETFs so that every distinct market
opportunity can still compete in the original daily OLS ranking.

At the start of each calendar month:
1. use only information available through the previous trading day;
2. take point-in-time universe-eligible ETFs;
3. compute trailing-120 daily-return correlations;
4. sort ETFs by trailing average amount (liquidity) descending;
5. retain an ETF unless it is highly correlated with an already-retained, more
   liquid representative.  Thus every removed ETF maps to a more liquid highly
   similar representative; there is no global Top-K truncation or trend score
   in the monthly layer;
6. freeze the representatives for the whole next month;
7. within that frozen set, use the original daily trend_eligible filter and raw
   OLS Score Top1 unchanged.

Correlation thresholds 0.90 and 0.95 are robustness points, not optimized
parameters.  No H4 health, maturity veto, V1, VP, or volume execution overlay
is used here.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from validate_fixed15_vs_full_market import FIXED15
from walk_forward_candidate_pool import backtest_open_to_open, summarize_variant
from monthly_frozen_universe import build_baseline_targets, build_targets_from_mask, frozen_mask

CORR_LOOKBACK = 120
CORR_THRESHOLDS = (0.90, 0.95)
MIN_CORR_OBS = 60


def _liquidity_first_representatives(
    ranked: pd.DataFrame,
    corr: pd.DataFrame,
    threshold: float,
) -> tuple[list[str], dict[str, str]]:
    """Greedy representative set ordered by liquidity, with no top-K cap."""
    reps: list[str] = []
    mapped_to: dict[str, str] = {}
    for sym in ranked["symbol"].astype(str):
        best_rep = None
        best_corr = -np.inf
        for rep in reps:
            c = corr.at[sym, rep] if sym in corr.index and rep in corr.columns else np.nan
            if pd.notna(c) and float(c) >= threshold and float(c) > best_corr:
                best_corr = float(c)
                best_rep = rep
        if best_rep is None:
            reps.append(sym)
            mapped_to[sym] = sym
        else:
            mapped_to[sym] = best_rep
    return reps, mapped_to


def build_monthly_rep_pools(
    bars: pd.DataFrame,
    features: pd.DataFrame,
) -> tuple[dict[str, dict[pd.Timestamp, set[str]]], pd.DataFrame]:
    calendar = pd.Index(sorted(pd.to_datetime(bars["date"].unique())))
    close = bars.pivot(index="date", columns="symbol", values="close").reindex(calendar)
    ret = close.pct_change(fill_method=None)

    state = features[["date", "symbol", "universe_eligible", "avg_amount60"]].copy()
    state["symbol"] = state["symbol"].astype(str)

    months = pd.Series(calendar, index=calendar).groupby(calendar.to_period("M"))
    pools = {f"cluster{int(t*100)}": {} for t in CORR_THRESHOLDS}
    audit_rows: list[dict] = []

    for period, dates_series in months:
        month_dates = pd.Index(dates_series.values)
        first_date = pd.Timestamp(month_dates[0])
        first_pos = int(calendar.get_loc(first_date))
        if first_pos == 0:
            continue
        prev_date = pd.Timestamp(calendar[first_pos - 1])
        corr_start = max(0, first_pos - CORR_LOOKBACK)
        corr_dates = calendar[corr_start:first_pos]
        if len(corr_dates) < MIN_CORR_OBS:
            continue

        ranked = state.loc[
            (state["date"] == prev_date)
            & state["universe_eligible"].fillna(False).astype(bool),
            ["symbol", "avg_amount60"],
        ].dropna(subset=["avg_amount60"]).copy()
        if ranked.empty:
            continue
        ranked = ranked.sort_values(["avg_amount60", "symbol"], ascending=[False, True]).reset_index(drop=True)
        eligible = [s for s in ranked["symbol"].astype(str) if s in ret.columns]
        ranked = ranked.loc[ranked["symbol"].isin(eligible)].reset_index(drop=True)
        if ranked.empty:
            continue

        corr = ret.loc[corr_dates, eligible].corr(min_periods=MIN_CORR_OBS)

        for threshold in CORR_THRESHOLDS:
            name = f"cluster{int(threshold*100)}"
            reps, mapped = _liquidity_first_representatives(ranked, corr, threshold)
            chosen = set(reps)
            for d in month_dates:
                pools[name][pd.Timestamp(d)] = chosen

            group_sizes = pd.Series(list(mapped.values())).value_counts()
            for sym in ranked["symbol"].astype(str):
                rep = mapped.get(sym, sym)
                audit_rows.append({
                    "month": str(period),
                    "prev_date": prev_date,
                    "threshold": threshold,
                    "symbol": sym,
                    "representative": rep,
                    "is_representative": sym == rep,
                    "group_size": int(group_sizes.get(rep, 1)),
                    "avg_amount60": float(ranked.loc[ranked["symbol"] == sym, "avg_amount60"].iloc[0]),
                    "eligible_count": int(len(ranked)),
                    "representative_count": int(len(reps)),
                })

    return pools, pd.DataFrame(audit_rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="monthly-liquidity-cluster-summary.json")
    p.add_argument("--audit-path", default="monthly-liquidity-cluster-audit.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)
    pools, audit = build_monthly_rep_pools(bars, features)

    summary = {
        "design": {
            "monthly_freeze": True,
            "monthly_layer": "liquidity-first removal of trailing-120 highly correlated ETF duplicates",
            "correlation_thresholds": list(CORR_THRESHOLDS),
            "no_top_k_truncation": True,
            "representative_rule": "highest trailing avg_amount60 encountered first",
            "daily_ranking": "unchanged raw OLS Score among trend_eligible monthly representatives",
            "extra_health_or_maturity_filter": False,
        },
        "variants": {},
        "pool_audit": {},
    }

    for label, ff in [
        ("full_market_baseline", features),
        ("fixed15_baseline", features.loc[features["symbol"].astype(str).isin(FIXED15)].copy()),
    ]:
        targets, counts = build_baseline_targets(ff)
        pnl = backtest_open_to_open(bars, targets)
        summary["variants"][label] = summarize_variant(label, pnl, targets, counts)

    for threshold in CORR_THRESHOLDS:
        name = f"cluster{int(threshold*100)}"
        allowed = frozen_mask(features, pools[name])
        targets, counts = build_targets_from_mask(features, allowed)
        pnl = backtest_open_to_open(bars, targets)
        summary["variants"][name] = summarize_variant(name, pnl, targets, counts)

        a = audit.loc[audit["threshold"] == threshold]
        reps = a.loc[a["is_representative"]]
        summary["pool_audit"][name] = {
            "months": int(a["month"].nunique()) if len(a) else 0,
            "mean_eligible_count": float(a.groupby("month")["eligible_count"].first().mean()) if len(a) else 0.0,
            "mean_representative_count": float(a.groupby("month")["representative_count"].first().mean()) if len(a) else 0.0,
            "median_representative_count": float(a.groupby("month")["representative_count"].first().median()) if len(a) else 0.0,
            "mean_group_size_for_reps": float(reps["group_size"].mean()) if len(reps) else 0.0,
            "max_group_size": int(reps["group_size"].max()) if len(reps) else 0,
        }

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    audit.to_csv(args.audit_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
