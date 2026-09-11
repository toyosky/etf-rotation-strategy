#!/usr/bin/env python3
"""Walk-forward validation of an asset-level Trendability prior.

Preregistered before execution in:
  research/trendability_stage1_preregister_20260911.md

Research only. No strategy/backtest threshold is tuned here.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sqlalchemy import create_engine

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from cluster90_resistance_score_v1_test import build_needed_profiles

PRIMARY_START = pd.Timestamp("2021-01-01")
POSTERIOR_START = pd.Timestamp("2025-01-01")
RES_THRESHOLD = 75.0
SHRINK_K = 10.0


def load_taxonomy(engine) -> pd.DataFrame:
    q = """
        select symbol, name, product_type, asset_class, region_primary,
               underlying_key, risk_bucket
        from public.instrument_metadata_current
        where has_daily_bars and underlying_key is not null
    """
    m = pd.read_sql_query(q, engine)
    m["symbol"] = m["symbol"].astype(str)
    return m.drop_duplicates("symbol", keep="last")


def add_forward_labels(features: pd.DataFrame) -> pd.DataFrame:
    f = features.sort_values(["symbol", "date"]).copy()
    g = f.groupby("symbol", sort=False)
    f["fwd10_close"] = g["close"].shift(-10) / f["close"] - 1.0
    f["fwd10_outcome_date"] = g["date"].shift(-10)
    return f


def build_monthly_underlying_reps(features: pd.DataFrame, taxonomy: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    f = features.merge(taxonomy[["symbol", "underlying_key", "risk_bucket"]], on="symbol", how="inner")
    calendar = pd.Index(sorted(pd.to_datetime(f["date"].unique())))
    month_rows: list[dict] = []
    daily_rows: list[dict] = []

    for period, dates in pd.Series(calendar, index=calendar).groupby(calendar.to_period("M")):
        month_dates = pd.Index(dates.values)
        first_date = pd.Timestamp(month_dates[0])
        pos = int(calendar.get_loc(first_date))
        if pos == 0:
            continue
        prev_date = pd.Timestamp(calendar[pos - 1])
        day = f.loc[
            (f["date"] == prev_date)
            & f["universe_eligible"].fillna(False).astype(bool),
            ["symbol", "underlying_key", "risk_bucket", "median_amount60", "avg_amount60", "history_bars"],
        ].dropna(subset=["underlying_key", "median_amount60", "avg_amount60"]).copy()
        if day.empty:
            continue
        day = day.sort_values(
            ["underlying_key", "median_amount60", "avg_amount60", "history_bars", "symbol"],
            ascending=[True, False, False, False, True],
        )
        reps = day.groupby("underlying_key", sort=True, as_index=False).head(1).copy()
        for r in reps.itertuples(index=False):
            month_rows.append({
                "month": str(period), "prev_date": prev_date,
                "symbol": str(r.symbol), "underlying_key": str(r.underlying_key),
                "risk_bucket": str(r.risk_bucket),
                "median_amount60": float(r.median_amount60),
                "avg_amount60": float(r.avg_amount60),
                "history_bars": int(r.history_bars),
                "eligible_products": int(len(day)),
                "representative_count": int(len(reps)),
            })
            for d in month_dates:
                daily_rows.append({"date": pd.Timestamp(d), "symbol": str(r.symbol), "month": str(period)})

    monthly = pd.DataFrame(month_rows)
    daily = pd.DataFrame(daily_rows)
    return monthly, daily


def build_factor_frame(features: pd.DataFrame, rep_daily: pd.DataFrame) -> pd.DataFrame:
    x = rep_daily.merge(
        features[["date", "symbol", "universe_eligible", "fwd10_close"]],
        on=["date", "symbol"], how="left",
    )
    x = x.loc[x["universe_eligible"].fillna(False).astype(bool) & x["fwd10_close"].notna()].copy()
    agg = x.groupby("date")["fwd10_close"].agg(["sum", "count"]).reset_index()
    x = x.merge(agg, on="date", how="left")
    x["factor_ex_self"] = np.where(
        x["count"] > 1,
        (x["sum"] - x["fwd10_close"]) / (x["count"] - 1),
        np.nan,
    )
    return x[["date", "symbol", "factor_ex_self"]]


def build_healthy_events(features: pd.DataFrame, bars: pd.DataFrame, rep_daily: pd.DataFrame) -> pd.DataFrame:
    ever_reps = set(rep_daily["symbol"].astype(str).unique())
    profiles = build_needed_profiles(bars, ever_reps)

    x = features.loc[features["symbol"].astype(str).isin(ever_reps)].copy()
    x = x.merge(rep_daily[["date", "symbol", "month"]], on=["date", "symbol"], how="left")
    x["is_rep"] = x["month"].notna()
    x = x.merge(profiles[["date", "symbol", "resistance_pct252"]], on=["date", "symbol"], how="left")
    x = x.sort_values(["symbol", "date"]).reset_index(drop=True)

    x["rep_trend_state"] = x["is_rep"] & x["trend_eligible"].fillna(False).astype(bool)
    prev_state = x.groupby("symbol", sort=False)["rep_trend_state"].shift(1).fillna(False).astype(bool)
    x["segment_start"] = x["rep_trend_state"] & (~prev_state)
    x["segment_id"] = x.groupby("symbol", sort=False)["segment_start"].cumsum()
    x["healthy_state"] = (
        x["rep_trend_state"]
        & x["score_delta"].notna() & (x["score_delta"] > 0)
        & x["resistance_pct252"].notna() & (x["resistance_pct252"] < RES_THRESHOLD)
    )

    h = x.loc[x["healthy_state"] & (x["segment_id"] > 0)].copy()
    if h.empty:
        raise RuntimeError("No healthy representative-trend events generated")
    h = h.sort_values(["symbol", "segment_id", "date"]).groupby(["symbol", "segment_id"], as_index=False).head(1)
    h = h.rename(columns={"date": "event_date", "month": "event_month"})

    factor = build_factor_frame(features, rep_daily).rename(columns={"date": "event_date"})
    h = h.merge(factor, on=["event_date", "symbol"], how="left")
    h["fwd10_residual"] = h["fwd10_close"] - h["factor_ex_self"]
    return h[[
        "event_date", "event_month", "symbol", "score", "score_delta", "resistance_pct252",
        "fwd10_close", "fwd10_outcome_date", "factor_ex_self", "fwd10_residual",
    ]].sort_values(["event_date", "symbol"]).reset_index(drop=True)


def historical_scores(monthly_reps: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    events = events.dropna(subset=["fwd10_residual", "fwd10_outcome_date"]).copy()
    for month, reps in monthly_reps.groupby("month", sort=True):
        prev_date = pd.Timestamp(reps["prev_date"].iloc[0])
        known = events.loc[pd.to_datetime(events["fwd10_outcome_date"]) <= prev_date].copy()
        if known.empty:
            global_mean = np.nan
            stats = pd.DataFrame(columns=["symbol", "n_prior", "asset_mean"])
        else:
            global_mean = float(known["fwd10_residual"].mean())
            stats = known.groupby("symbol")["fwd10_residual"].agg(n_prior="count", asset_mean="mean").reset_index()

        s = reps[["month", "prev_date", "symbol", "underlying_key", "risk_bucket"]].merge(stats, on="symbol", how="left")
        s["n_prior"] = s["n_prior"].fillna(0).astype(int)
        s["global_mean"] = global_mean
        s["asset_mean"] = pd.to_numeric(s["asset_mean"], errors="coerce")
        s["trendability"] = np.where(
            s["n_prior"] > 0,
            (s["n_prior"] / (s["n_prior"] + SHRINK_K)) * s["asset_mean"]
            + (SHRINK_K / (s["n_prior"] + SHRINK_K)) * global_mean,
            global_mean,
        )
        scored = s["n_prior"] >= 1
        if scored.any():
            pct = s.loc[scored, "trendability"].rank(method="average", pct=True, ascending=True)
            s.loc[scored, "trendability_pct"] = pct
            s.loc[scored, "trendability_quintile"] = np.ceil(pct * 5).clip(1, 5).astype(int)
        rows.extend(s.to_dict("records"))
    return pd.DataFrame(rows)


def merge_scores(events: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    e = events.copy()
    e["month"] = pd.to_datetime(e["event_date"]).dt.to_period("M").astype(str)
    s = scores[["month", "symbol", "n_prior", "global_mean", "asset_mean", "trendability", "trendability_pct", "trendability_quintile"]].copy()
    return e.merge(s, on=["month", "symbol"], how="left")


def safe_spearman(a: pd.Series, b: pd.Series) -> float | None:
    x = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(x) < 3 or x["a"].nunique() < 2 or x["b"].nunique() < 2:
        return None
    return float(spearmanr(x["a"], x["b"]).statistic)


def summarize_sample(g: pd.DataFrame) -> dict:
    total = int(len(g))
    scored = g.loc[(g["n_prior"].fillna(0) >= 1) & g["trendability_quintile"].notna() & g["fwd10_residual"].notna()].copy()
    out: dict = {
        "events_total": total,
        "events_scored": int(len(scored)),
        "scored_coverage": float(len(scored) / total) if total else None,
        "symbols_scored": int(scored["symbol"].nunique()) if len(scored) else 0,
        "spearman_trendability_residual": safe_spearman(scored["trendability"], scored["fwd10_residual"]),
        "quintiles": {},
    }
    for q in range(1, 6):
        z = scored.loc[scored["trendability_quintile"] == q]
        if z.empty:
            out["quintiles"][f"Q{q}"] = {"n": 0}
            continue
        sym = z.groupby("symbol")["fwd10_residual"].mean()
        out["quintiles"][f"Q{q}"] = {
            "n": int(len(z)), "symbols": int(z["symbol"].nunique()),
            "residual_mean": float(z["fwd10_residual"].mean()),
            "residual_median": float(z["fwd10_residual"].median()),
            "residual_symbol_equal": float(sym.mean()),
            "raw_fwd10_mean": float(z["fwd10_close"].mean()),
            "positive_residual_share": float((z["fwd10_residual"] > 0).mean()),
            "mean_prior_n": float(z["n_prior"].mean()),
        }
    qmeans = [out["quintiles"].get(f"Q{q}", {}).get("residual_mean") for q in range(1, 6)]
    if all(v is not None for v in qmeans):
        steps = [qmeans[i+1] - qmeans[i] for i in range(4)]
        out["q5_minus_q1_residual"] = float(qmeans[4] - qmeans[0])
        out["nonnegative_adjacent_steps"] = int(sum(v >= 0 for v in steps))
        out["adjacent_steps"] = [float(v) for v in steps]
    else:
        out["q5_minus_q1_residual"] = None
        out["nonnegative_adjacent_steps"] = None
        out["adjacent_steps"] = None
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="trendability-stage1-summary.json")
    p.add_argument("--events-path", default="trendability-stage1-events.csv")
    p.add_argument("--scores-path", default="trendability-stage1-monthly-scores.csv")
    p.add_argument("--reps-path", default="trendability-stage1-monthly-representatives.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    taxonomy = load_taxonomy(engine)
    features = add_forward_labels(build_features(bars))
    features["symbol"] = features["symbol"].astype(str)

    monthly_reps, rep_daily = build_monthly_underlying_reps(features, taxonomy)
    events = build_healthy_events(features, bars, rep_daily)
    scores = historical_scores(monthly_reps, events)
    eval_events = merge_scores(events, scores)

    primary = eval_events.loc[(eval_events["event_date"] >= PRIMARY_START) & (eval_events["event_date"] < POSTERIOR_START)].copy()
    posterior = eval_events.loc[eval_events["event_date"] >= POSTERIOR_START].copy()
    pstats = summarize_sample(primary)
    qstats = summarize_sample(posterior)

    sp = pstats.get("spearman_trendability_residual")
    spread = pstats.get("q5_minus_q1_residual")
    steps = pstats.get("nonnegative_adjacent_steps")
    keep = (
        sp is not None and sp > 0
        and spread is not None and spread > 0
        and steps is not None and steps >= 3
    )

    years = {}
    e21 = eval_events.loc[eval_events["event_date"] >= PRIMARY_START].copy()
    for year, g in e21.groupby(e21["event_date"].dt.year, sort=True):
        years[str(int(year))] = summarize_sample(g)

    summary = {
        "preregister": "research/trendability_stage1_preregister_20260911.md",
        "frozen_design": {
            "representative": "monthly point-in-time underlying_key representative: median_amount60 desc, avg_amount60 desc, history desc",
            "healthy": "representative trend state; first healthy day per state segment; ScoreDelta>0; ResistancePct252<75",
            "outcome": "fwd10 close return residualized vs equal-weight other monthly representatives",
            "shrinkage_k": SHRINK_K,
            "primary": "2021-2024",
            "posterior": "2025-2026",
            "threshold_sweep": False,
        },
        "data": {
            "bars_rows": int(len(bars)), "symbols": int(bars["symbol"].nunique()),
            "taxonomy_symbols": int(taxonomy["symbol"].nunique()),
            "monthly_rep_rows": int(len(monthly_reps)),
            "ever_representative_symbols": int(monthly_reps["symbol"].nunique()),
            "underlyings_seen": int(monthly_reps["underlying_key"].nunique()),
            "healthy_events_all": int(len(events)),
        },
        "primary_2021_2024": pstats,
        "posterior_2025_2026": qstats,
        "year_by_year": years,
        "decision": "KEEP_CANDIDATE" if keep else "REJECT_STAGE1_V1",
        "decision_rule": "primary Spearman>0 AND Q5-Q1>0 AND >=3/4 nonnegative adjacent quintile steps",
        "known_limitations": [
            "current structural taxonomy is used historically; historical label transformations are not yet fully audited",
            "point-in-time fund scale is unavailable in daily_bars and is not included in this historical validation",
        ],
    }

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    eval_events.to_csv(args.events_path, index=False)
    scores.to_csv(args.scores_path, index=False)
    monthly_reps.to_csv(args.reps_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
