#!/usr/bin/env python3
"""Walk-forward candidate-pool research for the full-market ETF OLS strategy.

Design goals
------------
1. No future information in admission thresholds.
2. Admission is decided only when a new OLS-positive episode starts, then frozen
   for the life of that raw OLS episode.
3. Thresholds are natural expanding historical quintiles (20% / 80%), not
   optimized numeric cutoffs.
4. OLS score remains the ranking variable *after* admission filters.
5. Daily research backtest uses signal at close(t), execution at open(t+1), and
   open(t+1)->open(t+2) return. Frozen side cost = 5 bp commission + 1 bp
   slippage = 6 bp per buy/sell side.

This is a structural research engine, not a reproduction of the production
minute-level C2/V1 execution logic.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from full_market_ols_storage import _db_url, build_features, load_daily_bars

BACKTEST_START = pd.Timestamp("2021-01-01")
SIGNAL_WARMUP_START = pd.Timestamp("2020-12-01")
SIDE_COST = 0.0006
MIN_PRIOR_EPISODES = 200

HEALTH_FEATURES = ["slope_delta", "current_resid", "ret5", "dist_high20"]
MATURITY_FEATURES = ["score", "slope"]
VARIANTS = [
    "baseline",
    "h1_slope_delta",
    "h2_plus_resid",
    "h4_health",
    "h4m_health_maturity",
]


def attach_raw_episode_ids(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach raw OLS episode start date to every trend-eligible daily row."""
    parts: list[pd.DataFrame] = []
    for _, g in features.groupby("symbol", sort=False):
        g = g.sort_values("date").copy()
        trend = g["trend_eligible"].fillna(False).astype(bool)
        start = trend & (~trend.shift(1, fill_value=False))
        ep_start = g["date"].where(start).ffill().where(trend)
        g["episode_start_date"] = ep_start
        parts.append(g)

    f = pd.concat(parts, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
    starts = f.loc[
        f["trend_eligible"]
        & f["episode_start_date"].notna()
        & (f["date"] == f["episode_start_date"]),
        [
            "symbol", "date", "score", "slope", "slope_delta", "current_resid",
            "ret5", "dist_high20", "r2", "annual",
        ],
    ].copy()
    starts = starts.rename(columns={"date": "start_date"})
    starts = starts.sort_values(["start_date", "symbol"]).reset_index(drop=True)
    return f, starts


def _prior_date_expanding_quantile(
    starts: pd.DataFrame,
    feature: str,
    q: float,
) -> pd.Series:
    """Expanding quantile using only episodes with start_date < current date.

    Pandas expanding quantile is row based. We evaluate it immediately before
    the first row of each date and broadcast that value to every start on the
    date, so same-day starts never enter one another's calibration history.
    """
    raw = starts[feature].astype(float).expanding(min_periods=MIN_PRIOR_EPISODES).quantile(q).shift(1)
    first_mask = ~starts["start_date"].duplicated()
    date_map = dict(zip(starts.loc[first_mask, "start_date"], raw.loc[first_mask]))
    return starts["start_date"].map(date_map).astype(float)


def add_walk_forward_admission(starts: pd.DataFrame) -> pd.DataFrame:
    s = starts.copy().sort_values(["start_date", "symbol"]).reset_index(drop=True)

    # Number of strictly earlier episode starts available at each date.
    date_counts = s.groupby("start_date", sort=True).size()
    prior_counts = date_counts.cumsum().shift(1, fill_value=0)
    s["prior_episode_count"] = s["start_date"].map(prior_counts).astype(int)

    for feature in HEALTH_FEATURES:
        s[f"{feature}_q20"] = _prior_date_expanding_quantile(s, feature, 0.20)
    for feature in MATURITY_FEATURES:
        s[f"{feature}_q80"] = _prior_date_expanding_quantile(s, feature, 0.80)

    calibrated = s["prior_episode_count"] >= MIN_PRIOR_EPISODES
    s["pass_h1_slope_delta"] = calibrated & (s["slope_delta"] >= s["slope_delta_q20"])
    s["pass_h2_plus_resid"] = (
        s["pass_h1_slope_delta"]
        & (s["current_resid"] >= s["current_resid_q20"])
    )
    s["pass_h4_health"] = (
        s["pass_h2_plus_resid"]
        & (s["ret5"] >= s["ret5_q20"])
        & (s["dist_high20"] >= s["dist_high20_q20"])
    )
    s["pass_h4m_health_maturity"] = (
        s["pass_h4_health"]
        & (s["score"] <= s["score_q80"])
        & (s["slope"] <= s["slope_q80"])
    )
    return s


def merge_admission(features: pd.DataFrame, starts: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "symbol", "start_date", "prior_episode_count",
        "pass_h1_slope_delta", "pass_h2_plus_resid", "pass_h4_health",
        "pass_h4m_health_maturity",
    ]
    q = starts[cols].rename(columns={"start_date": "episode_start_date"})
    f = features.merge(q, on=["symbol", "episode_start_date"], how="left", validate="many_to_one")
    for col in [c for c in cols if c.startswith("pass_")]:
        f[col] = f[col].fillna(False).astype(bool)
    return f


def candidate_mask(f: pd.DataFrame, variant: str) -> pd.Series:
    base = f["trend_eligible"].fillna(False).astype(bool)
    if variant == "baseline":
        return base
    return base & f[f"pass_{variant}"].fillna(False).astype(bool)


def build_daily_targets(
    f: pd.DataFrame,
    variant: str,
) -> tuple[pd.Series, pd.Series]:
    mask = candidate_mask(f, variant) & (f["date"] >= SIGNAL_WARMUP_START)
    d = f.loc[mask, ["date", "symbol", "score"]].copy()
    counts = d.groupby("date").size().astype(int)
    if d.empty:
        return pd.Series(dtype=object), counts
    idx = d.groupby("date", sort=True)["score"].idxmax()
    picks = d.loc[idx, ["date", "symbol"]].sort_values("date")
    targets = picks.set_index("date")["symbol"]
    return targets, counts


def _period_metrics(pnl: pd.DataFrame, start: str, end: str | None = None) -> dict:
    s = pnl.loc[pnl["date"] >= pd.Timestamp(start)].copy()
    if end is not None:
        s = s.loc[s["date"] <= pd.Timestamp(end)].copy()
    if s.empty:
        return {}
    equity = (1.0 + s["net_ret"]).cumprod()
    peak = equity.cummax()
    dd = equity / peak - 1.0
    total = float(equity.iloc[-1] - 1.0)
    days = max(1, int((s["date"].iloc[-1] - s["date"].iloc[0]).days))
    cagr = float((1.0 + total) ** (365.25 / days) - 1.0) if total > -1 else -1.0
    return {
        "trading_days": int(len(s)),
        "total_return": total,
        "cagr": cagr,
        "max_drawdown": float(dd.min()),
        "switch_events": int(s["switch_event"].sum()),
        "turnover_sides": int(s["turnover_sides"].sum()),
        "invested_ratio": float(s["invested"].mean()),
        "missing_quote_days": int(s["missing_quote"].sum()),
    }


def backtest_open_to_open(
    bars: pd.DataFrame,
    targets: pd.Series,
) -> pd.DataFrame:
    calendar = pd.Index(sorted(pd.to_datetime(bars["date"].unique())))
    open_wide = bars.pivot(index="date", columns="symbol", values="open").reindex(calendar)
    target_map = targets.to_dict()

    rows: list[dict] = []
    prev_target: str | None = None
    for i in range(len(calendar) - 2):
        signal_date = pd.Timestamp(calendar[i])
        exec_date = pd.Timestamp(calendar[i + 1])
        exit_date = pd.Timestamp(calendar[i + 2])
        if signal_date < SIGNAL_WARMUP_START:
            continue

        target = target_map.get(signal_date)
        target = str(target) if target is not None and not pd.isna(target) else None

        if target == prev_target:
            sides = 0
            switch_event = 0
        elif prev_target is None and target is not None:
            sides = 1
            switch_event = 1
        elif prev_target is not None and target is None:
            sides = 1
            switch_event = 1
        else:
            sides = 2
            switch_event = 1

        gross = 0.0
        missing_quote = False
        if target is not None:
            try:
                entry = float(open_wide.at[exec_date, target])
                exit_px = float(open_wide.at[exit_date, target])
                if not (math.isfinite(entry) and math.isfinite(exit_px) and entry > 0):
                    missing_quote = True
                else:
                    gross = exit_px / entry - 1.0
            except (KeyError, TypeError, ValueError):
                missing_quote = True

        cost = SIDE_COST * sides
        net = (1.0 + gross) * (1.0 - cost) - 1.0
        rows.append({
            "date": exec_date,
            "signal_date": signal_date,
            "target": target,
            "gross_ret": gross,
            "cost": cost,
            "net_ret": net,
            "switch_event": switch_event,
            "turnover_sides": sides,
            "invested": target is not None,
            "missing_quote": missing_quote,
        })
        prev_target = target

    return pd.DataFrame(rows)


def summarize_variant(
    variant: str,
    pnl: pd.DataFrame,
    targets: pd.Series,
    counts: pd.Series,
) -> dict:
    eval_pnl = pnl.loc[pnl["date"] >= BACKTEST_START].copy()
    eval_counts = counts.loc[counts.index >= BACKTEST_START]
    eval_targets = targets.loc[targets.index >= BACKTEST_START]

    yearly = {}
    for year in range(2021, 2027):
        sub = eval_pnl.loc[eval_pnl["date"].dt.year == year]
        if not sub.empty:
            yearly[str(year)] = float((1.0 + sub["net_ret"]).prod() - 1.0)

    top_symbols = (
        eval_targets.value_counts().head(10).rename_axis("symbol").reset_index(name="signal_days")
    )
    return {
        "variant": variant,
        "full_2021_2026": _period_metrics(eval_pnl, "2021-01-01"),
        "period_2021_2024": _period_metrics(eval_pnl, "2021-01-01", "2024-12-31"),
        "period_2025_2026": _period_metrics(eval_pnl, "2025-01-01"),
        "yearly_returns": yearly,
        "candidate_count_mean": float(eval_counts.mean()) if len(eval_counts) else 0.0,
        "candidate_count_median": float(eval_counts.median()) if len(eval_counts) else 0.0,
        "candidate_count_p10": float(eval_counts.quantile(0.10)) if len(eval_counts) else 0.0,
        "candidate_empty_signal_days": int((eval_counts.reindex(eval_pnl["signal_date"].unique(), fill_value=0) == 0).sum()),
        "top_symbols": top_symbols.to_dict(orient="records"),
    }


def admission_summary(starts: pd.DataFrame) -> dict:
    s = starts.loc[starts["start_date"] >= BACKTEST_START].copy()
    out = {
        "episodes_2021plus": int(len(s)),
        "prior_episode_count_at_2021_start": int(s["prior_episode_count"].iloc[0]) if len(s) else 0,
    }
    for variant in VARIANTS[1:]:
        col = f"pass_{variant}"
        out[variant] = {
            "admitted": int(s[col].sum()),
            "admission_rate": float(s[col].mean()),
        }
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="walk-forward-candidate-pool-summary.json")
    p.add_argument("--daily-path", default="walk-forward-candidate-pool-daily.csv")
    p.add_argument("--episodes-path", default="walk-forward-episode-admission.csv")
    args = p.parse_args()

    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)
    features, starts = attach_raw_episode_ids(features)
    starts = add_walk_forward_admission(starts)
    features = merge_admission(features, starts)

    summary = {
        "design": {
            "backtest_start": str(BACKTEST_START.date()),
            "threshold_history": "all strictly prior raw OLS episode starts (expanding)",
            "health_floor": "historical 20th percentile",
            "maturity_ceiling": "historical 80th percentile",
            "admission_frozen_for_episode": True,
            "signal_execution": "close(t) signal -> open(t+1) execution -> open(t+2) mark",
            "side_cost": SIDE_COST,
            "min_prior_episodes": MIN_PRIOR_EPISODES,
        },
        "bars_rows": int(len(bars)),
        "symbols": int(bars["symbol"].nunique()),
        "raw_episode_starts_all_dates": int(len(starts)),
        "admission": admission_summary(starts),
        "variants": {},
    }

    daily_frames = []
    for variant in VARIANTS:
        targets, counts = build_daily_targets(features, variant)
        pnl = backtest_open_to_open(bars, targets)
        summary["variants"][variant] = summarize_variant(variant, pnl, targets, counts)
        tmp = pnl.copy()
        tmp["variant"] = variant
        daily_frames.append(tmp)

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.concat(daily_frames, ignore_index=True).to_csv(args.daily_path, index=False)

    episode_cols = [
        "symbol", "start_date", "prior_episode_count", "score", "slope", "slope_delta",
        "current_resid", "ret5", "dist_high20",
        "slope_delta_q20", "current_resid_q20", "ret5_q20", "dist_high20_q20",
        "score_q80", "slope_q80",
        "pass_h1_slope_delta", "pass_h2_plus_resid", "pass_h4_health",
        "pass_h4m_health_maturity",
    ]
    starts.loc[starts["start_date"] >= BACKTEST_START, episode_cols].to_csv(args.episodes_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
