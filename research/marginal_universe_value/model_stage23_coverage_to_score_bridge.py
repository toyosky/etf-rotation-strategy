#!/usr/bin/env python3
"""Stage23 coverage-to-score bridge audit.

Mechanism audit only. No model fit, threshold search, asset selection, or policy
backtest. Tests whether missed full-market oracle winners were already near the
top of the point-in-time OLS score ordering.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from validate_fixed15_vs_full_market import FIXED15

START = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")
CASH = "511220"
OUT = Path("muv-stage23-coverage-to-score-bridge-report.json")
OUT_EVENTS = Path("muv-stage23-coverage-to-score-bridge-events.csv")


def add_fwd20(features: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for _, g0 in features.groupby("symbol", sort=False):
        g = g0.sort_values("date").copy()
        close = pd.to_numeric(g["close"], errors="coerce").to_numpy(dtype=float)
        vals = np.full(len(g), np.nan, dtype=float)
        if len(g) > 20:
            vals[:-20] = close[20:] / close[:-20] - 1.0
        g["fwd20_close"] = vals
        parts.append(g)
    return pd.concat(parts, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)


def month_end_dates(features: pd.DataFrame) -> list[pd.Timestamp]:
    d = pd.DataFrame({"date": pd.to_datetime(features.loc[features["date"] >= START, "date"].drop_duplicates())})
    d["month"] = d["date"].dt.to_period("M")
    return [pd.Timestamp(x) for x in d.groupby("month")["date"].max().sort_values().tolist()]


def finite_mean(s: pd.Series):
    x = pd.to_numeric(s, errors="coerce").dropna()
    return float(x.mean()) if len(x) else None


def finite_median(s: pd.Series):
    x = pd.to_numeric(s, errors="coerce").dropna()
    return float(x.median()) if len(x) else None


def summarize(g: pd.DataFrame) -> dict:
    if g.empty:
        return {"n_events": 0}
    rank = pd.to_numeric(g["score_rank_all"], errors="coerce")
    pct = pd.to_numeric(g["score_rank_pct_all"], errors="coerce")
    return {
        "n_events": int(len(g)),
        "score_rank_all_mean": finite_mean(rank),
        "score_rank_all_median": finite_median(rank),
        "score_rank_outsiders_median": finite_median(g["score_rank_outsiders"]),
        "score_rank_pct_all_median": finite_median(pct),
        "score_top1_capture_share": float((rank <= 1).mean()),
        "score_top3_capture_share": float((rank <= 3).mean()),
        "score_top5_capture_share": float((rank <= 5).mean()),
        "score_top10_capture_share": float((rank <= 10).mean()),
        "fixed_empty_share": float(g["fixed_empty"].mean()),
        "candidate_count_mean": finite_mean(g["candidate_count_all"]),
    }


def support_block(s: dict) -> bool:
    return (
        s.get("n_events", 0) > 0
        and s.get("score_top10_capture_share") is not None
        and s.get("score_rank_pct_all_median") is not None
        and s["score_top10_capture_share"] >= 0.50
        and s["score_rank_pct_all_median"] <= 0.15
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output", default=str(OUT))
    ap.add_argument("--events-output", default=str(OUT_EVENTS))
    args = ap.parse_args()
    if not args.database_url:
        raise RuntimeError("ETF_DAILY_BARS_DATABASE_URL is required")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = add_fwd20(build_features(bars))
    features["symbol"] = features["symbol"].astype(str)

    fixed_set = set(map(str, FIXED15)) - {CASH}
    rows = []

    for d in month_end_dates(features):
        base = features.loc[
            (features["date"] == d)
            & features["trend_eligible"].fillna(False).astype(bool)
            & (features["symbol"] != CASH),
            ["symbol", "score", "fwd20_close"],
        ].dropna(subset=["score", "fwd20_close"]).copy()
        if base.empty:
            continue

        by_future = base.sort_values(["fwd20_close", "symbol"], ascending=[False, True]).reset_index(drop=True)
        winner = by_future.iloc[0]
        winner_symbol = str(winner["symbol"])
        if winner_symbol in fixed_set:
            continue

        by_score = base.sort_values(["score", "symbol"], ascending=[False, True]).reset_index(drop=True)
        rank_map = {str(sym): i + 1 for i, sym in enumerate(by_score["symbol"])}
        outsiders = by_score.loc[~by_score["symbol"].isin(fixed_set)].reset_index(drop=True)
        outsider_rank_map = {str(sym): i + 1 for i, sym in enumerate(outsiders["symbol"])}

        fixed = base.loc[base["symbol"].isin(fixed_set)]
        r_all = float(rank_map[winner_symbol])
        r_out = float(outsider_rank_map[winner_symbol])
        n_all = int(len(base))
        rows.append({
            "date": d,
            "period": "2021-24" if d < SPLIT else "2025-26",
            "oracle_outsider_symbol": winner_symbol,
            "oracle_outsider_fwd20": float(winner["fwd20_close"]),
            "oracle_outsider_score": float(winner["score"]),
            "candidate_count_all": n_all,
            "candidate_count_outsiders": int(len(outsiders)),
            "score_rank_all": r_all,
            "score_rank_outsiders": r_out,
            "score_rank_pct_all": r_all / n_all if n_all else np.nan,
            "fixed_empty": bool(fixed.empty),
        })

    ev = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    if ev.empty:
        raise RuntimeError("Stage23 produced no missed-outside oracle events")
    ev.to_csv(args.events_output, index=False)

    overall = summarize(ev)
    by_era = {str(p): summarize(g) for p, g in ev.groupby("period", sort=True)}
    supported = bool(support_block(overall) and len(by_era) == 2 and all(support_block(v) for v in by_era.values()))

    report = {
        "version": "muv_stage23_coverage_to_score_bridge_20260913",
        "frozen_question": "When the full-market ex-post best 20-day continuation is outside Fixed15, was that missed outsider already near the top of the point-in-time OLS score ordering at month-end?",
        "design": {
            "new_model_fit": False,
            "feature_search": False,
            "threshold_search": False,
            "policy_backtest": False,
            "decision_dates": "trading month-end",
            "candidate_rule": "existing frozen trend_eligible",
            "outcome": "forward 20-trading-day close return; label-side only",
            "audit_event": "full-market oracle-best eligible ETF is outside Fixed15",
            "support_top10_capture_min": 0.50,
            "support_median_rank_percentile_max": 0.15,
        },
        "overall": overall,
        "by_era": by_era,
        "predeclared_interpretation": {
            "existing_score_provides_conservative_admission_bridge": supported,
            "rule": "Support only if score Top10 captures at least 50% of missed oracle-best outsider events and median all-market score-rank percentile is <=15%, overall and separately in 2021-24 and 2025-26. No cutoff tuning on this sample.",
        },
    }
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
