#!/usr/bin/env python3
"""Walk-forward candidate-pool research for the full-market ETF OLS strategy.

Architecture
------------
A. Episode-start health admission is frozen for the raw OLS-positive episode.
B. Maturity is a *daily* veto, because an episode can begin healthy and become
   overextended later.
C. All thresholds are expanding historical quintiles based only on strictly
   earlier raw OLS episode starts. No optimized fixed numeric cutoffs.
D. After filtering, raw OLS score remains the ranking variable.
E. Signal at close(t), execute at open(t+1), mark open(t+1)->open(t+2).

This is a structural daily research engine, not a minute-level reproduction of
production C2/V1 execution logic.
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
    "h4m_static_start_maturity",
    "h1_dynamic_score80",
    "h2_dynamic_score80",
    "h4_dynamic_score80",
    "h4_dynamic_score_slope80",
]

ADMISSION_PASS_COLUMNS = {
    "h1_slope_delta": "pass_h1_slope_delta",
    "h2_plus_resid": "pass_h2_plus_resid",
    "h4_health": "pass_h4_health",
    "h4m_static_start_maturity": "pass_h4m_static_start_maturity",
}


def attach_raw_episode_ids(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    parts: list[pd.DataFrame] = []
    for _, g in features.groupby("symbol", sort=False):
        g = g.sort_values("date").copy()
        trend = g["trend_eligible"].fillna(False).astype(bool)
        start = trend & (~trend.shift(1, fill_value=False))
        g["episode_start_date"] = g["date"].where(start).ffill().where(trend)
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


def _prior_date_expanding_quantile(starts: pd.DataFrame, feature: str, q: float) -> pd.Series:
    raw = starts[feature].astype(float).expanding(min_periods=MIN_PRIOR_EPISODES).quantile(q).shift(1)
    first_mask = ~starts["start_date"].duplicated()
    date_map = dict(zip(starts.loc[first_mask, "start_date"], raw.loc[first_mask]))
    return starts["start_date"].map(date_map).astype(float)


def add_walk_forward_admission(starts: pd.DataFrame) -> pd.DataFrame:
    s = starts.copy().sort_values(["start_date", "symbol"]).reset_index(drop=True)

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
    s["pass_h4m_static_start_maturity"] = (
        s["pass_h4_health"]
        & (s["score"] <= s["score_q80"])
        & (s["slope"] <= s["slope_q80"])
    )
    return s


def merge_episode_admission(features: pd.DataFrame, starts: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "symbol", "start_date", "prior_episode_count",
        "pass_h1_slope_delta", "pass_h2_plus_resid", "pass_h4_health",
        "pass_h4m_static_start_maturity",
    ]
    q = starts[cols].rename(columns={"start_date": "episode_start_date"})
    f = features.merge(q, on=["symbol", "episode_start_date"], how="left", validate="many_to_one")
    for col in [c for c in cols if c.startswith("pass_")]:
        f[col] = f[col].astype("boolean").fillna(False).astype(bool)
    return f


def attach_daily_maturity_thresholds(features: pd.DataFrame, starts: pd.DataFrame) -> pd.DataFrame:
    first = starts.loc[
        ~starts["start_date"].duplicated(),
        ["start_date", "score_q80", "slope_q80"],
    ].copy()
    first = first.rename(columns={
        "start_date": "date",
        "score_q80": "daily_score_q80",
        "slope_q80": "daily_slope_q80",
    }).set_index("date")

    calendar = pd.Index(sorted(pd.to_datetime(features["date"].unique())), name="date")
    daily = first.reindex(calendar).ffill().reset_index()
    return features.merge(daily, on="date", how="left", validate="many_to_one")


def candidate_mask(f: pd.DataFrame, variant: str) -> pd.Series:
    base = f["trend_eligible"].fillna(False).astype(bool)
    if variant == "baseline":
        return base
    if variant in ADMISSION_PASS_COLUMNS:
        return base & f[ADMISSION_PASS_COLUMNS[variant]].fillna(False).astype(bool)

    if variant.startswith("h1_dynamic"):
        health = f["pass_h1_slope_delta"].fillna(False).astype(bool)
    elif variant.startswith("h2_dynamic"):
        health = f["pass_h2_plus_resid"].fillna(False).astype(bool)
    elif variant.startswith("h4_dynamic"):
        health = f["pass_h4_health"].fillna(False).astype(bool)
    else:
        raise ValueError(f"Unknown variant: {variant}")

    score_ok = f["daily_score_q80"].notna() & (f["score"] <= f["daily_score_q80"])
    mask = base & health & score_ok
    if variant == "h4_dynamic_score_slope80":
        slope_ok = f["daily_slope_q80"].notna() & (f["slope"] <= f["daily_slope_q80"])
        mask = mask & slope_ok
    return mask


def build_daily_targets(f: pd.DataFrame, variant: str) -> tuple[pd.Series, pd.Series]:
    all_dates = pd.Index(
        sorted(pd.to_datetime(f.loc[f["date"] >= SIGNAL_WARMUP_START, "date"].unique())),
        name="date",
    )
    mask = candidate_mask(f, variant) & (f["date"] >= SIGNAL_WARMUP_START)
    d = f.loc[mask, ["date", "symbol", "score"]].copy()
    counts = d.groupby("date").size().reindex(all_dates, fill_value=0).astype(int)
    if d.empty:
        return pd.Series(dtype=object), counts
    idx = d.groupby("date", sort=True)["score"].idxmax()
    targets = d.loc[idx, ["date", "symbol"]].sort_values("date").set_index("date")["symbol"]
    return targets, counts


def _cagr(total: float, first_date: pd.Timestamp, last_date: pd.Timestamp) -> float:
    days = max(1, int((last_date - first_date).days))
    return float((1.0 + total) ** (365.25 / days) - 1.0) if total > -1 else -1.0


def _period_metrics(pnl: pd.DataFrame, start: str, end: str | None = None) -> dict:
    s = pnl.loc[pnl["date"] >= pd.Timestamp(start)].copy()
    if end is not None:
        s = s.loc[s["date"] <= pd.Timestamp(end)].copy()
    if s.empty:
        return {}

    net_equity = (1.0 + s["net_ret"]).cumprod()
    gross_equity = (1.0 + s["gross_ret"]).cumprod()
    net_dd = net_equity / net_equity.cummax() - 1.0
    gross_dd = gross_equity / gross_equity.cummax() - 1.0
    net_total = float(net_equity.iloc[-1] - 1.0)
    gross_total = float(gross_equity.iloc[-1] - 1.0)

    return {
        "trading_days": int(len(s)),
        "total_return": net_total,
        "gross_total_return": gross_total,
        "cagr": _cagr(net_total, s["date"].iloc[0], s["date"].iloc[-1]),
        "gross_cagr": _cagr(gross_total, s["date"].iloc[0], s["date"].iloc[-1]),
        "max_drawdown": float(net_dd.min()),
        "gross_max_drawdown": float(gross_dd.min()),
        "switch_events": int(s["switch_event"].sum()),
        "turnover_sides": int(s["turnover_sides"].sum()),
        "invested_ratio": float(s["invested"].mean()),
        "missing_quote_days": int(s["missing_quote"].sum()),
    }


def backtest_open_to_open(bars: pd.DataFrame, targets: pd.Series) -> pd.DataFrame:
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
            sides, switch_event = 0, 0
        elif prev_target is None or target is None:
            sides, switch_event = 1, 1
        else:
            sides, switch_event = 2, 1

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


def summarize_variant(variant: str, pnl: pd.DataFrame, targets: pd.Series, counts: pd.Series) -> dict:
    eval_pnl = pnl.loc[pnl["date"] >= BACKTEST_START].copy()
    eval_counts = counts.loc[counts.index >= BACKTEST_START]
    eval_targets = targets.loc[targets.index >= BACKTEST_START]

    yearly = {}
    for year in range(2021, 2027):
        sub = eval_pnl.loc[eval_pnl["date"].dt.year == year]
        if not sub.empty:
            yearly[str(year)] = {
                "net": float((1.0 + sub["net_ret"]).prod() - 1.0),
                "gross": float((1.0 + sub["gross_ret"]).prod() - 1.0),
            }

    top_symbols = eval_targets.value_counts().head(10).rename_axis("symbol").reset_index(name="signal_days")
    return {
        "variant": variant,
        "full_2021_2026": _period_metrics(eval_pnl, "2021-01-01"),
        "period_2021_2024": _period_metrics(eval_pnl, "2021-01-01", "2024-12-31"),
        "period_2025_2026": _period_metrics(eval_pnl, "2025-01-01"),
        "yearly_returns": yearly,
        "candidate_count_mean": float(eval_counts.mean()) if len(eval_counts) else 0.0,
        "candidate_count_median": float(eval_counts.median()) if len(eval_counts) else 0.0,
        "candidate_count_p10": float(eval_counts.quantile(0.10)) if len(eval_counts) else 0.0,
        "candidate_empty_signal_days": int((eval_counts == 0).sum()),
        "top_symbols": top_symbols.to_dict(orient="records"),
    }


def admission_summary(starts: pd.DataFrame) -> dict:
    s = starts.loc[starts["start_date"] >= BACKTEST_START].copy()
    out = {
        "episodes_2021plus": int(len(s)),
        "prior_episode_count_at_2021_start": int(s["prior_episode_count"].iloc[0]) if len(s) else 0,
    }
    for variant, col in ADMISSION_PASS_COLUMNS.items():
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
    features = merge_episode_admission(features, starts)
    features = attach_daily_maturity_thresholds(features, starts)

    summary = {
        "design": {
            "backtest_start": str(BACKTEST_START.date()),
            "threshold_history": "all strictly prior raw OLS episode starts (expanding)",
            "health_floor": "historical 20th percentile at episode start; frozen for episode",
            "dynamic_maturity_ceiling": "daily current score/slope vs prior-history episode-start 80th percentile",
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
        "pass_h4m_static_start_maturity",
    ]
    starts.loc[starts["start_date"] >= BACKTEST_START, episode_cols].to_csv(args.episodes_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
