#!/usr/bin/env python3
"""Cross-sectional extreme-score diagnostic for Cluster90.

Research question
-----------------
Why did an expanded, correlation-deduplicated ETF universe hurt 2021-24 but
help 2025-26 even though the same daily OLS ranking rule was used?

This is a mechanism diagnostic, not a strategy optimization.  It uses the
point-in-time monthly Cluster90 representative pool, keeps the existing daily
trend eligibility and OLS Score unchanged, and inspects the top three eligible
scores each day.

For each date we record:
- Top1 / Top2 / Top3 Score and symbols;
- Top1-vs-Top2 and Top1-vs-Top3 score ratios;
- Top1 Score relative to the candidate-set median;
- Top1 raw OLS episode age and remaining raw / MA10 trend life;
- forward 5/10-day close returns for Top1/2/3;
- whether Top1 remains continuously Top1 for 1/3/5 more trading days.

Diagnostics are reported separately for 2021-24 and 2025-26, both on all
signal days and on Top1 leadership-entry days.  Natural within-period quartiles
are used only descriptively; no threshold is optimized and no trading rule is
created from them.
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
from monthly_liquidity_cluster_universe import build_monthly_rep_pools
from monthly_frozen_universe import frozen_mask
from selected_top1_lifespan_diagnostic import add_life_labels

START = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")


def _period(d: pd.Timestamp) -> str:
    return "2021-2024" if d < SPLIT else "2025-2026"


def build_daily_top3(features: pd.DataFrame, pools: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    allowed = frozen_mask(features, pools["cluster90"])
    mask = (
        allowed
        & features["trend_eligible"].fillna(False).astype(bool)
        & (features["date"] >= START)
    )
    cols = [
        "date", "symbol", "score", "raw_episode_age", "remaining_raw20",
        "remaining_ma10_20", "remaining_mom5_20", "fwd5_close", "fwd10_close",
    ]
    d = features.loc[mask, cols].copy()
    d["symbol"] = d["symbol"].astype(str)
    d = d.sort_values(["date", "score", "symbol"], ascending=[True, False, True]).reset_index(drop=True)
    d["rank"] = d.groupby("date").cumcount() + 1
    d["candidate_count"] = d.groupby("date")["symbol"].transform("size").astype(int)
    d["candidate_median_score"] = d.groupby("date")["score"].transform("median")
    top3 = d.loc[d["rank"] <= 3].copy()

    all_dates = pd.Index(
        sorted(pd.to_datetime(features.loc[features["date"] >= START, "date"].unique())),
        name="date",
    )
    date_pos = {pd.Timestamp(x): i for i, x in enumerate(all_dates)}
    grouped = {pd.Timestamp(k): g for k, g in top3.groupby("date", sort=True)}
    rows: list[dict] = []
    for dt in all_dates:
        dt = pd.Timestamp(dt)
        g = grouped.get(dt)
        if g is None or g.empty:
            rows.append({"date": dt, "period": _period(dt), "candidate_count": 0})
            continue
        g = g.sort_values("rank")
        row: dict = {
            "date": dt,
            "period": _period(dt),
            "candidate_count": int(g["candidate_count"].iloc[0]),
            "candidate_median_score": float(g["candidate_median_score"].iloc[0]),
        }
        for r in (1, 2, 3):
            rr = g.loc[g["rank"] == r]
            if rr.empty:
                continue
            x = rr.iloc[0]
            row[f"top{r}_symbol"] = str(x["symbol"])
            row[f"score{r}"] = float(x["score"])
            row[f"age{r}"] = float(x["raw_episode_age"]) if pd.notna(x["raw_episode_age"]) else np.nan
            row[f"remaining_raw{r}"] = float(x["remaining_raw20"]) if pd.notna(x["remaining_raw20"]) else np.nan
            row[f"remaining_ma10_{r}"] = float(x["remaining_ma10_20"]) if pd.notna(x["remaining_ma10_20"]) else np.nan
            row[f"remaining_mom5_{r}"] = float(x["remaining_mom5_20"]) if pd.notna(x["remaining_mom5_20"]) else np.nan
            row[f"fwd5_{r}"] = float(x["fwd5_close"]) if pd.notna(x["fwd5_close"]) else np.nan
            row[f"fwd10_{r}"] = float(x["fwd10_close"]) if pd.notna(x["fwd10_close"]) else np.nan
        s1 = row.get("score1", np.nan)
        s2 = row.get("score2", np.nan)
        s3 = row.get("score3", np.nan)
        med = row.get("candidate_median_score", np.nan)
        row["score_ratio12"] = s1 / s2 if pd.notna(s1) and pd.notna(s2) and s2 > 0 else np.nan
        row["score_ratio13"] = s1 / s3 if pd.notna(s1) and pd.notna(s3) and s3 > 0 else np.nan
        row["score_gap12"] = s1 - s2 if pd.notna(s1) and pd.notna(s2) else np.nan
        row["top1_to_median"] = s1 / med if pd.notna(s1) and pd.notna(med) and med > 0 else np.nan
        row["fwd5_1_minus_2"] = row.get("fwd5_1", np.nan) - row.get("fwd5_2", np.nan)
        row["fwd10_1_minus_2"] = row.get("fwd10_1", np.nan) - row.get("fwd10_2", np.nan)
        row["fwd10_1_minus_3"] = row.get("fwd10_1", np.nan) - row.get("fwd10_3", np.nan)
        rows.append(row)

    daily = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    # New leadership entry vs continuation. Cash/no-candidate breaks tenure.
    prev = daily["top1_symbol"].shift(1)
    daily["top1_entry"] = daily["top1_symbol"].notna() & (
        prev.isna() | (daily["top1_symbol"].astype(object) != prev.astype(object))
    )

    # Continuous survival of the current Top1 for h additional trading days.
    syms = daily["top1_symbol"].astype(object).to_numpy()
    for h in (1, 3, 5):
        vals = np.full(len(daily), np.nan)
        for i in range(len(daily)):
            if pd.isna(syms[i]) or i + h >= len(daily):
                continue
            vals[i] = float(all(pd.notna(syms[j]) and syms[j] == syms[i] for j in range(i + 1, i + h + 1)))
        daily[f"top1_survive{h}"] = vals

    return daily, top3


def _corr(g: pd.DataFrame, x: str, y: str) -> float | None:
    z = g[[x, y]].dropna()
    if len(z) < 5 or z[x].nunique() < 2 or z[y].nunique() < 2:
        return None
    v = z[x].corr(z[y], method="spearman")
    return float(v) if pd.notna(v) else None


def basic_summary(g: pd.DataFrame) -> dict:
    x = g.loc[g["top1_symbol"].notna()].copy()
    if x.empty:
        return {}
    return {
        "days": int(len(x)),
        "leadership_entries": int(x["top1_entry"].sum()),
        "candidate_count_mean": float(x["candidate_count"].mean()),
        "candidate_count_median": float(x["candidate_count"].median()),
        "score1_median": float(x["score1"].median()),
        "score_ratio12_median": float(x["score_ratio12"].median()),
        "score_ratio13_median": float(x["score_ratio13"].median()),
        "top1_to_median_median": float(x["top1_to_median"].median()),
        "top1_age_mean": float(x["age1"].mean()),
        "top1_age_median": float(x["age1"].median()),
        "top1_remaining_raw_mean": float(x["remaining_raw1"].mean()),
        "top1_remaining_ma10_mean": float(x["remaining_ma10_1"].mean()),
        "top1_fwd5_mean": float(x["fwd5_1"].mean()),
        "top1_fwd10_mean": float(x["fwd10_1"].mean()),
        "top1_minus_top2_fwd10_mean": float(x["fwd10_1_minus_2"].mean()),
        "top1_survive3_share": float(x["top1_survive3"].mean()),
        "top1_survive5_share": float(x["top1_survive5"].mean()),
        "spearman": {
            "score1_vs_fwd10": _corr(x, "score1", "fwd10_1"),
            "score_ratio12_vs_fwd10": _corr(x, "score_ratio12", "fwd10_1"),
            "score_ratio12_vs_top1_minus_top2_fwd10": _corr(x, "score_ratio12", "fwd10_1_minus_2"),
            "top1_to_median_vs_fwd10": _corr(x, "top1_to_median", "fwd10_1"),
            "age1_vs_fwd10": _corr(x, "age1", "fwd10_1"),
            "score_ratio12_vs_age1": _corr(x, "score_ratio12", "age1"),
        },
    }


def rank_summary(top3: pd.DataFrame) -> dict:
    t = top3.copy()
    t["period"] = np.where(t["date"] < SPLIT, "2021-2024", "2025-2026")
    out: dict[str, dict] = {}
    for period, g in t.groupby("period", sort=True):
        p: dict[str, dict] = {}
        for rank, r in g.groupby("rank", sort=True):
            p[f"top{int(rank)}"] = {
                "observations": int(len(r)),
                "score_median": float(r["score"].median()),
                "age_mean": float(r["raw_episode_age"].mean()),
                "remaining_raw_mean": float(r["remaining_raw20"].mean()),
                "remaining_ma10_mean": float(r["remaining_ma10_20"].mean()),
                "fwd5_mean": float(r["fwd5_close"].mean()),
                "fwd10_mean": float(r["fwd10_close"].mean()),
            }
        out[str(period)] = p
    return out


def quartile_table(g: pd.DataFrame, variable: str, scope: str) -> pd.DataFrame:
    x = g.loc[g["top1_symbol"].notna()].copy()
    if scope == "entries":
        x = x.loc[x["top1_entry"]].copy()
    pieces: list[pd.DataFrame] = []
    for period, p in x.groupby("period", sort=True):
        qbase = p[variable].dropna()
        if len(qbase) < 8 or qbase.nunique() < 4:
            continue
        try:
            bins = pd.qcut(qbase.rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"])
        except ValueError:
            continue
        p = p.copy()
        p["quartile"] = pd.Series(index=qbase.index, data=bins.astype(str))
        for q, z in p.groupby("quartile", sort=True):
            pieces.append(pd.DataFrame([{
                "scope": scope,
                "period": str(period),
                "variable": variable,
                "quartile": str(q),
                "n": int(len(z)),
                "variable_median": float(z[variable].median()),
                "score_ratio12_median": float(z["score_ratio12"].median()),
                "top1_to_median_median": float(z["top1_to_median"].median()),
                "age1_mean": float(z["age1"].mean()),
                "age1_median": float(z["age1"].median()),
                "remaining_raw1_mean": float(z["remaining_raw1"].mean()),
                "remaining_ma10_1_mean": float(z["remaining_ma10_1"].mean()),
                "fwd5_1_mean": float(z["fwd5_1"].mean()),
                "fwd10_1_mean": float(z["fwd10_1"].mean()),
                "fwd10_1_minus_2_mean": float(z["fwd10_1_minus_2"].mean()),
                "top1_survive3_share": float(z["top1_survive3"].mean()),
                "top1_survive5_share": float(z["top1_survive5"].mean()),
            }]))
    return pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()


def old_extreme_corner(g: pd.DataFrame, scope: str) -> dict:
    x = g.loc[g["top1_symbol"].notna()].copy()
    if scope == "entries":
        x = x.loc[x["top1_entry"]].copy()
    out: dict[str, dict] = {}
    for period, p in x.groupby("period", sort=True):
        z = p.dropna(subset=["score_ratio12", "age1"]).copy()
        if len(z) < 20:
            continue
        gap75 = float(z["score_ratio12"].quantile(0.75))
        age75 = float(z["age1"].quantile(0.75))
        corner = z.loc[(z["score_ratio12"] >= gap75) & (z["age1"] >= age75)]
        other = z.loc[~((z["score_ratio12"] >= gap75) & (z["age1"] >= age75))]
        out[str(period)] = {
            "scope": scope,
            "gap_q75": gap75,
            "age_q75": age75,
            "old_extreme_n": int(len(corner)),
            "other_n": int(len(other)),
            "old_extreme_fwd5_mean": float(corner["fwd5_1"].mean()) if len(corner) else None,
            "other_fwd5_mean": float(other["fwd5_1"].mean()) if len(other) else None,
            "old_extreme_fwd10_mean": float(corner["fwd10_1"].mean()) if len(corner) else None,
            "other_fwd10_mean": float(other["fwd10_1"].mean()) if len(other) else None,
            "old_extreme_top1_minus_top2_fwd10": float(corner["fwd10_1_minus_2"].mean()) if len(corner) else None,
            "other_top1_minus_top2_fwd10": float(other["fwd10_1_minus_2"].mean()) if len(other) else None,
            "old_extreme_survive5_share": float(corner["top1_survive5"].mean()) if len(corner) else None,
            "other_survive5_share": float(other["top1_survive5"].mean()) if len(other) else None,
        }
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="cross-sectional-extreme-score-summary.json")
    p.add_argument("--daily-path", default="cross-sectional-extreme-score-daily.csv")
    p.add_argument("--quartile-path", default="cross-sectional-extreme-score-quartiles.csv")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = add_life_labels(build_features(bars))
    pools, _ = build_monthly_rep_pools(bars, features)
    daily, top3 = build_daily_top3(features, pools)

    summaries: dict[str, dict] = {}
    for period, g in daily.groupby("period", sort=True):
        summaries[str(period)] = {
            "all_days": basic_summary(g),
            "leadership_entries": basic_summary(g.loc[g["top1_entry"]]),
        }

    qt = pd.concat([
        quartile_table(daily, "score_ratio12", "all_days"),
        quartile_table(daily, "score_ratio12", "entries"),
        quartile_table(daily, "top1_to_median", "all_days"),
        quartile_table(daily, "top1_to_median", "entries"),
        quartile_table(daily, "age1", "all_days"),
        quartile_table(daily, "age1", "entries"),
    ], ignore_index=True)

    summary = {
        "question": "When is the cross-sectional raw OLS Score champion trustworthy?",
        "design": {
            "universe": "monthly liquidity-first Cluster90 representatives, frozen within month",
            "daily_selector": "unchanged trend_eligible raw OLS Score ranking",
            "future_labels": "diagnostic only; close-to-close 5/10 trading-day returns",
            "quartiles": "within-period natural quartiles, descriptive only, not optimized thresholds",
            "entry_subset": "dates when non-cash Top1 differs from prior trading day",
        },
        "period_summary": summaries,
        "rank_1_2_3": rank_summary(top3),
        "old_and_extreme_q4_corner": {
            "all_days": old_extreme_corner(daily, "all_days"),
            "leadership_entries": old_extreme_corner(daily, "entries"),
        },
        "quartile_rows": int(len(qt)),
    }

    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    daily.to_csv(args.daily_path, index=False)
    qt.to_csv(args.quartile_path, index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nQUARTILES\n")
    print(qt.to_csv(index=False))


if __name__ == "__main__":
    main()
