#!/usr/bin/env python3
"""Rebuild research.ols_episodes using the frozen RAW-OLS episode contract.

Frozen contract
---------------
A new episode starts on date t iff:
  1. t is point-in-time universe eligible;
  2. raw OLS is positive at t: annual>0, r2>0, score>0;
  3. raw OLS was NOT positive on the immediately preceding trading row for
     the same ETF.

Important: the previous state intentionally ignores universe eligibility.
Liquidity/listing eligibility changes must not manufacture a new OLS episode.
D2 is NOT part of episode identity; it is stored as d2_pass at the start.
OLS lifetime follows future raw-OLS positivity only, independent of D2 and
universe eligibility.

This script uses the existing exact OLS feature engine, validates it against a
known calibration point, then atomically replaces the compact episode table.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from full_market_ols_storage import (
    EPISODE_START,
    LIFE_CAP,
    _db_url,
    build_features,
    first_fail_offset,
    load_daily_bars,
)

CAL_SYMBOL = "518880"
CAL_DATE = pd.Timestamp("2024-04-23")
CAL_SLOPE = 0.00332739987009351
CAL_R2 = 0.426482940137465
CAL_SCORE = 0.553389435240023


def assert_ols_calibration(features: pd.DataFrame) -> None:
    row = features.loc[
        (features["symbol"].astype(str) == CAL_SYMBOL) & (features["date"] == CAL_DATE)
    ]
    if len(row) != 1:
        raise RuntimeError(f"Calibration row missing or duplicated: {CAL_SYMBOL} {CAL_DATE.date()}")
    row = row.iloc[0]
    checks = {
        "slope": (float(row["slope"]), CAL_SLOPE),
        "r2": (float(row["r2"]), CAL_R2),
        "score": (float(row["score"]), CAL_SCORE),
    }
    for name, (got, expected) in checks.items():
        if not np.isclose(got, expected, rtol=1e-9, atol=1e-12):
            raise RuntimeError(f"OLS calibration failed for {name}: got={got!r}, expected={expected!r}")


def build_raw_episodes(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    keep_cols = [
        "symbol", "date", "rn", "score", "annual", "r2", "slope",
        "score_delta", "r2_delta", "slope_delta", "current_resid",
        "ret3", "ret5", "ret10", "ret20", "ret60",
        "dist_high20", "dist_high60", "dist_high120",
        "vol20", "vol60", "efficiency10", "efficiency20", "ma10_dist",
        "xrank", "xpercentile", "trend_count", "universe_count",
    ]

    for _, g in features.groupby("symbol", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        raw = (
            (g["annual"] > 0)
            & (g["r2"] > 0)
            & (g["score"] > 0)
        ).fillna(False).to_numpy(dtype=bool)
        universe = g["universe_eligible"].fillna(False).to_numpy(dtype=bool)
        prev_raw = np.r_[False, raw[:-1]]
        start_mask = universe & raw & (~prev_raw)
        starts = np.flatnonzero(
            start_mask & (g["date"].to_numpy() >= np.datetime64(EPISODE_START))
        )

        close = g["close"].to_numpy(dtype=float)
        ma10_pass = (g["close"] >= g["ma10"]).fillna(False).to_numpy(dtype=bool)
        mom5_pass = g["mom5_pass"].fillna(False).to_numpy(dtype=bool)
        d2_pass_arr = (~g["recent_drop3"].fillna(False)).to_numpy(dtype=bool)

        for s in starts:
            base = g.loc[s, keep_cols].to_dict()
            base["start_date"] = base.pop("date")
            base["start_rn"] = int(base.pop("rn"))
            base["d2_pass"] = bool(d2_pass_arr[s])

            max_future = min(LIFE_CAP, len(g) - 1 - s)
            base["right_censored"] = max_future < LIFE_CAP
            base["ols_life20"] = first_fail_offset(raw, s, LIFE_CAP, start_offset=1)
            base["ma10_life20"] = first_fail_offset(ma10_pass, s, LIFE_CAP, start_offset=0)
            base["mom5_life20"] = first_fail_offset(mom5_pass, s, LIFE_CAP, start_offset=0)

            peak = close[s]
            dd_life = max_future
            for d in range(1, max_future + 1):
                peak = max(peak, close[s + d])
                if close[s + d] <= peak * 0.97:
                    dd_life = d
                    break
            base["dd3_life20"] = int(dd_life)

            p0 = close[s]
            for h in (3, 5, 10, 20):
                base[f"fwd{h}"] = close[s + h] / p0 - 1.0 if s + h < len(g) else np.nan
            for h in (10, 20):
                end = min(len(g), s + h + 1)
                future = close[s + 1:end]
                base[f"mfe{h}"] = float(np.max(future / p0 - 1.0)) if len(future) else np.nan
                base[f"mae{h}"] = float(np.min(future / p0 - 1.0)) if len(future) else np.nan
            rows.append(base)

    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("No raw OLS episodes generated")
    out["xrank"] = pd.to_numeric(out["xrank"], errors="coerce").astype("Int64")
    return out.sort_values(["start_date", "symbol"]).reset_index(drop=True)


def replace_table(engine, episodes: pd.DataFrame) -> None:
    stage = "ols_episodes_stage_raw_contract"
    episodes.to_sql(
        stage, engine, schema="research", if_exists="replace", index=False,
        chunksize=1000, method="multi",
    )
    with engine.begin() as conn:
        conn.execute(text("drop table if exists research.ols_episodes"))
        conn.execute(text(f"alter table research.{stage} rename to ols_episodes"))
        conn.execute(text("alter table research.ols_episodes add primary key(symbol,start_date)"))
        conn.execute(text("create index ols_episodes_date_idx on research.ols_episodes(start_date)"))
        conn.execute(text("create index ols_episodes_symbol_idx on research.ols_episodes(symbol,start_date)"))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="raw-ols-episode-rebuild-summary.json")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    with engine.connect() as conn:
        old_count = int(conn.execute(text("select count(*) from research.ols_episodes")).scalar() or 0)

    bars = load_daily_bars(engine)
    features = build_features(bars)
    assert_ols_calibration(features)
    episodes = build_raw_episodes(features)

    yearly = (
        episodes.assign(year=pd.to_datetime(episodes["start_date"]).dt.year)
        .query("year >= 2021")
        .groupby("year").size().astype(int).to_dict()
    )
    d2_rate = float(episodes.loc[pd.to_datetime(episodes["start_date"]) >= pd.Timestamp("2021-01-01"), "d2_pass"].mean())
    replace_table(engine, episodes)

    result = {
        "contract": "current universe eligible AND raw OLS positive AND previous trading row raw OLS not positive; D2 separate",
        "calibration_passed": True,
        "old_episode_table_rows": old_count,
        "new_episode_rows_all_from_2020_10": int(len(episodes)),
        "new_episode_rows_2021plus": int((pd.to_datetime(episodes["start_date"]) >= pd.Timestamp("2021-01-01")).sum()),
        "yearly_2021plus": {str(k): int(v) for k, v in yearly.items()},
        "d2_pass_rate_2021plus": d2_rate,
    }
    Path(args.summary_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
