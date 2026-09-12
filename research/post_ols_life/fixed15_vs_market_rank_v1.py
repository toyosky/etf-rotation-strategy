#!/usr/bin/env python3
"""Compare daily OLS leader tenure: full Fixed15 vs point-in-time full market.

Purpose
-------
Test whether the previously observed shortening of Fixed15 Top1 tenure in
2025-2026 is a property of the fixed pool itself or a market-wide ranking
phenomenon.

Important design choice:
- Fixed15 ranking does NOT apply the full-market universe liquidity/listing
  gate. All 15 frozen symbols are allowed, matching the intent of a fixed pool.
- Full-market ranking DOES use the frozen point-in-time `trend_eligible` gate.
- Both sides reuse the same frozen OLS feature engine and D2 filter.
- This is diagnostic only; it does not alter the strategy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH_DIR = Path(__file__).resolve().parents[1]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from full_market_ols_storage import _db_url, build_features, load_daily_bars  # noqa: E402
from rebuild_raw_ols_episodes import assert_ols_calibration  # noqa: E402

START = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")
FIXED15 = [
    "518880", "159985", "159825", "161226", "513100", "159915", "511220",
    "159509", "513290", "159529", "159981", "501018", "513920", "511380",
    "164824",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", type=Path, default=Path("fixed15-vs-market-rank-summary.json"))
    p.add_argument("--report-path", type=Path, default=Path("fixed15-vs-market-rank-report.md"))
    return p.parse_args()


def period_of_date(d: pd.Timestamp) -> str:
    return "2021-2024" if d < SPLIT else "2025-2026"


def build_daily_rank(features: pd.DataFrame, mode: str) -> pd.DataFrame:
    f = features.loc[features["date"] >= START].copy()
    f["symbol"] = f["symbol"].astype(str).str.zfill(6)

    if mode == "fixed15":
        mask = (
            f["symbol"].isin(FIXED15)
            & (f["annual"] > 0)
            & (f["r2"] > 0)
            & (f["score"] > 0)
            & (~f["recent_drop3"].fillna(False))
        )
    elif mode == "market":
        mask = f["trend_eligible"].fillna(False)
    else:
        raise ValueError(mode)

    cand = f.loc[mask, ["date", "symbol", "score"]].copy()
    cand = cand.sort_values(["date", "score", "symbol"], ascending=[True, False, False])
    cand["daily_rank"] = cand.groupby("date", sort=False).cumcount() + 1

    counts = cand.groupby("date").size().rename("candidate_count")
    top1 = cand.loc[cand["daily_rank"] == 1, ["date", "symbol", "score"]].rename(
        columns={"symbol": "leader_symbol", "score": "top1_score"}
    )
    top2 = cand.loc[cand["daily_rank"] == 2, ["date", "score"]].rename(
        columns={"score": "top2_score"}
    )

    dates = pd.DataFrame({"date": sorted(f["date"].drop_duplicates())})
    out = dates.merge(counts, on="date", how="left").merge(top1, on="date", how="left").merge(top2, on="date", how="left")
    out["candidate_count"] = out["candidate_count"].fillna(0).astype(int)
    out["gap_abs"] = out["top1_score"] - out["top2_score"]
    out["gap_rel"] = np.where(
        out["top2_score"].notna() & (out["top1_score"].abs() > 1e-12),
        out["gap_abs"] / out["top1_score"].abs(),
        np.nan,
    )
    out["period"] = out["date"].map(period_of_date)
    out["mode"] = mode
    return out


def leader_runs(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for period, g in daily.groupby("period", sort=False):
        g = g.sort_values("date")
        current: str | None = None
        start: pd.Timestamp | None = None
        last: pd.Timestamp | None = None
        length = 0

        def flush() -> None:
            nonlocal current, start, last, length
            if current is not None and length > 0:
                rows.append({
                    "mode": str(g["mode"].iloc[0]),
                    "period": period,
                    "leader_symbol": current,
                    "start_date": start,
                    "end_date": last,
                    "tenure_days": length,
                })
            current, start, last, length = None, None, None, 0

        for row in g.itertuples(index=False):
            sym = row.leader_symbol if isinstance(row.leader_symbol, str) else None
            if sym is None:
                flush()
                continue
            if current == sym:
                length += 1
                last = row.date
            else:
                flush()
                current = sym
                start = row.date
                last = row.date
                length = 1
        flush()
    return pd.DataFrame(rows)


def summarize(daily: pd.DataFrame, runs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for period, g in daily.groupby("period", sort=False):
        r = runs.loc[runs["period"] == period]
        active = g.loc[g["leader_symbol"].notna()].copy()
        consecutive = g[["leader_symbol"]].copy()
        prev = consecutive["leader_symbol"].shift(1)
        both = consecutive["leader_symbol"].notna() & prev.notna()
        change_rate = float((consecutive.loc[both, "leader_symbol"] != prev.loc[both]).mean()) if both.any() else np.nan
        rows.append({
            "mode": str(g["mode"].iloc[0]),
            "period": period,
            "trading_days": int(len(g)),
            "leader_days": int(len(active)),
            "leader_coverage": float(len(active) / len(g)) if len(g) else np.nan,
            "leader_runs": int(len(r)),
            "mean_tenure": float(r["tenure_days"].mean()) if len(r) else np.nan,
            "median_tenure": float(r["tenure_days"].median()) if len(r) else np.nan,
            "p75_tenure": float(r["tenure_days"].quantile(0.75)) if len(r) else np.nan,
            "max_tenure": int(r["tenure_days"].max()) if len(r) else 0,
            "unique_leaders": int(active["leader_symbol"].nunique()),
            "leader_change_rate": change_rate,
            "mean_candidate_count": float(g["candidate_count"].mean()),
            "median_candidate_count": float(g["candidate_count"].median()),
            "median_gap_rel": float(g["gap_rel"].median(skipna=True)),
            "mean_gap_rel": float(g["gap_rel"].mean(skipna=True)),
        })
    return pd.DataFrame(rows)


def top_leaders(runs: pd.DataFrame) -> pd.DataFrame:
    if runs.empty:
        return runs
    out = (
        runs.groupby(["mode", "period", "leader_symbol"], as_index=False)
        .agg(runs=("tenure_days", "size"), leader_days=("tenure_days", "sum"), mean_tenure=("tenure_days", "mean"), max_tenure=("tenure_days", "max"))
    )
    out["rank"] = out.groupby(["mode", "period"])["leader_days"].rank(method="first", ascending=False)
    return out.loc[out["rank"] <= 15].sort_values(["mode", "period", "rank"])


def fixed_raw_episode_summary(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    f = features.copy()
    f["symbol"] = f["symbol"].astype(str).str.zfill(6)
    f = f.loc[f["symbol"].isin(FIXED15)].copy()

    for symbol, g in f.groupby("symbol", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        raw = ((g["annual"] > 0) & (g["r2"] > 0) & (g["score"] > 0)).fillna(False).to_numpy(bool)
        prev = np.r_[False, raw[:-1]]
        starts = np.flatnonzero(raw & (~prev))
        close = g["close"].to_numpy(float)
        for s in starts:
            d = pd.Timestamp(g.loc[s, "date"])
            if d < START or s + 20 >= len(g):
                continue
            life = 20
            for k in range(1, 21):
                if not raw[s + k]:
                    life = k
                    break
            future = close[s + 1:s + 21] / close[s] - 1.0
            rows.append({
                "symbol": symbol,
                "period": period_of_date(d),
                "start_date": d,
                "life20": int(life),
                "fwd20": float(close[s + 20] / close[s] - 1.0),
                "mfe20": float(np.max(future)),
                "mae20": float(np.min(future)),
            })

    events = pd.DataFrame(rows)
    if events.empty:
        raise RuntimeError("No Fixed15 raw episodes generated")
    summary = (
        events.groupby("period", as_index=False)
        .agg(
            n=("life20", "size"),
            mean_life20=("life20", "mean"),
            median_life20=("life20", "median"),
            survive10=("life20", lambda x: float((x >= 10).mean())),
            mean_fwd20=("fwd20", "mean"),
            mean_mfe20=("mfe20", "mean"),
            mean_mae20=("mae20", "mean"),
        )
    )
    sym = (
        events.groupby(["symbol", "period"], as_index=False)
        .agg(
            n=("life20", "size"),
            median_life20=("life20", "median"),
            survive10=("life20", lambda x: float((x >= 10).mean())),
            mean_fwd20=("fwd20", "mean"),
        )
    )
    return summary, sym


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "(no rows)"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in df.itertuples(index=False, name=None):
        vals = []
        for val in row:
            if isinstance(val, (float, np.floating)):
                vals.append(f"{float(val):.4f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)
    assert_ols_calibration(features)

    fixed_daily = build_daily_rank(features, "fixed15")
    market_daily = build_daily_rank(features, "market")
    fixed_runs = leader_runs(fixed_daily)
    market_runs = leader_runs(market_daily)
    rank_summary = pd.concat([
        summarize(fixed_daily, fixed_runs),
        summarize(market_daily, market_runs),
    ], ignore_index=True)
    leaders = top_leaders(pd.concat([fixed_runs, market_runs], ignore_index=True))
    fixed_episode_summary, fixed_symbol_summary = fixed_raw_episode_summary(features)

    # Compact summaries only; no daily feature matrix is persisted to Postgres.
    rank_summary.to_sql("post_ols_rank_tenure_v1", engine, schema="research", if_exists="replace", index=False)
    leaders.to_sql("post_ols_rank_leaders_v1", engine, schema="research", if_exists="replace", index=False)
    fixed_episode_summary.to_sql("post_ols_fixed15_raw_summary_v1", engine, schema="research", if_exists="replace", index=False)
    fixed_symbol_summary.to_sql("post_ols_fixed15_raw_symbol_v1", engine, schema="research", if_exists="replace", index=False)

    data_asof = pd.to_datetime(bars["date"]).max().date().isoformat()
    report = "\n".join([
        "# Fixed15 vs Full Market — OLS Rank Tenure V1",
        "",
        f"Data as of: `{data_asof}`",
        "",
        "## Daily Top1 tenure",
        "",
        md_table(rank_summary),
        "",
        "## Fixed15 raw OLS episodes without full-market universe gate",
        "",
        md_table(fixed_episode_summary),
        "",
        "## Most frequent leaders",
        "",
        md_table(leaders),
        "",
        "Diagnostic only. No strategy rule is changed by this report.",
    ])
    args.report_path.write_text(report, encoding="utf-8")

    result = {
        "status": "PASS",
        "data_asof": data_asof,
        "fixed15_symbols": FIXED15,
        "rank_summary": rank_summary.to_dict(orient="records"),
        "fixed_raw_episode_summary": fixed_episode_summary.to_dict(orient="records"),
        "code_sha": os.getenv("GITHUB_SHA", "local"),
    }
    args.summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
