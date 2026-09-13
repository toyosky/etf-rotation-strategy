#!/usr/bin/env python3
"""New Stage2: intrinsic trend-episode remaining-life mechanism audit.

Hindsight structural audit only. The episode definition is frozen in
STAGE2_TREND_EPISODE_REMAINING_LIFE_DESIGN_20260914.md.
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
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

BOOT_SEED = 20260914
BOOT_N = 5000
K_LOW = 3
K_HIGH = 30


def find_one(root: Path, name: str) -> Path:
    hits = list(root.rglob(name))
    if len(hits) != 1:
        raise RuntimeError(f"Expected exactly one {name} under {root}, found {len(hits)}")
    return hits[0]


def spearman_by_month(g: pd.DataFrame, value_col: str) -> float:
    z = g[["k", value_col]].dropna()
    if len(z) < 3 or z["k"].nunique() < 3 or z[value_col].nunique() < 2:
        return np.nan
    return float(z["k"].corr(z[value_col], method="spearman"))


def month_contrasts(mk: pd.DataFrame, value_col: str) -> pd.DataFrame:
    p = mk.pivot(index="month", columns="k", values=value_col)
    if K_LOW not in p.columns or K_HIGH not in p.columns:
        return pd.DataFrame(columns=["month", "contrast"])
    z = (p[K_HIGH] - p[K_LOW]).dropna().rename("contrast").reset_index()
    return z


def bootstrap_mean(values: pd.Series, seed_offset: int = 0) -> dict:
    x = values.dropna().to_numpy(float)
    if len(x) == 0:
        return {"n_months": 0, "mean": None, "ci_low": None, "ci_high": None}
    rng = np.random.default_rng(BOOT_SEED + seed_offset)
    sims = np.empty(BOOT_N, dtype=float)
    for i in range(BOOT_N):
        sims[i] = float(np.mean(rng.choice(x, size=len(x), replace=True)))
    return {
        "n_months": int(len(x)),
        "mean": float(np.mean(x)),
        "ci_low": float(np.quantile(sims, 0.025)),
        "ci_high": float(np.quantile(sims, 0.975)),
    }


def build_episode_map(cal: pd.Index, score: pd.DataFrame, close: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    rows = []
    cal = pd.DatetimeIndex(cal)
    for sym in symbols:
        if sym not in score.columns:
            continue
        active = score[sym].notna().to_numpy(bool)
        if not active.any():
            continue
        # Group maximal consecutive active runs on the full market calendar.
        starts = active & np.r_[True, ~active[:-1]]
        ends = active & np.r_[~active[1:], True]
        start_idx = np.flatnonzero(starts)
        end_idx = np.flatnonzero(ends)
        for a, b in zip(start_idx, end_idx):
            total = int(b - a + 1)
            start_date = pd.Timestamp(cal[a])
            end_date = pd.Timestamp(cal[b])
            end_px = close.at[end_date, sym] if sym in close.columns else np.nan
            for pos in range(a, b + 1):
                d = pd.Timestamp(cal[pos])
                age = int(pos - a + 1)
                rem = int(b - pos)
                p0 = close.at[d, sym] if sym in close.columns else np.nan
                remret = np.nan
                if pd.notna(p0) and pd.notna(end_px) and float(p0) > 0:
                    remret = float(end_px / p0 - 1.0)
                rows.append({
                    "symbol": str(sym),
                    "admission_signal_date": d,
                    "episode_start": start_date,
                    "episode_end": end_date,
                    "age_days": age,
                    "remaining_days": rem,
                    "total_episode_days": total,
                    "trend_age_ratio": float(age / total),
                    "remaining_close_return": remret,
                })
    return pd.DataFrame(rows)


def aggregate_episodes(events: pd.DataFrame, episode_map: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    e = events.copy()
    e["admission_signal_date"] = pd.to_datetime(e["admission_signal_date"])
    e["symbol"] = e["symbol"].astype(str)
    e = e[e["source"].eq("same_k_mc")].copy()
    e = e.sort_values("admission_signal_date").drop_duplicates(["month", "universe_id", "symbol"], keep="first")
    lab = e.merge(episode_map, on=["symbol", "admission_signal_date"], how="left", validate="many_to_one")
    if lab["episode_end"].isna().any():
        miss = int(lab["episode_end"].isna().sum())
        raise RuntimeError(f"{miss} first-admission rows failed intrinsic episode mapping")

    uni = lab.groupby(["month", "k", "universe_id"], as_index=False).agg(
        first_admissions=("symbol", "size"),
        age_days_median=("age_days", "median"),
        trend_age_ratio_median=("trend_age_ratio", "median"),
        remaining_days_median=("remaining_days", "median"),
        remaining_close_return_median=("remaining_close_return", "median"),
        age_days_mean=("age_days", "mean"),
        trend_age_ratio_mean=("trend_age_ratio", "mean"),
        remaining_days_mean=("remaining_days", "mean"),
        remaining_close_return_mean=("remaining_close_return", "mean"),
    )
    mk = uni.groupby(["month", "k"], as_index=False).agg(
        universes=("universe_id", "size"),
        first_admissions_median=("first_admissions", "median"),
        age_days=("age_days_median", "median"),
        trend_age_ratio=("trend_age_ratio_median", "median"),
        remaining_days=("remaining_days_median", "median"),
        remaining_close_return=("remaining_close_return_median", "median"),
    )
    return lab, mk


def era_of(month: str) -> str:
    y = int(str(month)[:4])
    return "2021-24" if y <= 2024 else "2025-26"


def summarize_metric(mk: pd.DataFrame, metric: str, seed_offset: int) -> dict:
    out = {}
    temp = mk.copy()
    temp["era"] = temp["month"].map(era_of)
    for era, g in temp.groupby("era"):
        rhos = g.groupby("month", group_keys=False).apply(lambda x: spearman_by_month(x, metric), include_groups=False)
        con = month_contrasts(g, metric)
        out[era] = {
            "months": int(g["month"].nunique()),
            "mean_month_spearman_k_metric": float(rhos.dropna().mean()) if rhos.notna().any() else None,
            "negative_month_spearman_share": float((rhos.dropna() < 0).mean()) if rhos.notna().any() else None,
            "k30_minus_k3": bootstrap_mean(con["contrast"], seed_offset),
        }
    return out


def pairwise_supplement(detail: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = detail[detail["source"].eq("same_k_mc")].copy()
    mk = d.groupby(["month", "k"], as_index=False).agg(
        return_mean=("total_return", "mean"),
        mean_pairwise_corr=("mean_pairwise_corr", "median"),
        effective_n=("effective_n", "median"),
        switches=("switches", "median"),
        observed_top1_tenure=("mean_top1_tenure", "median"),
        winner_coverage=("winner_coverage", "median"),
        dormant_share=("dormant_member_share", "median"),
    )
    mk["era"] = mk["month"].map(era_of)
    rep = {}
    for era, g in mk.groupby("era"):
        rep[era] = {}
        for col in ["mean_pairwise_corr", "effective_n", "switches", "observed_top1_tenure", "winner_coverage", "dormant_share", "return_mean"]:
            agg = g.groupby("k", as_index=False)[col].mean()
            rep[era][f"spearman_k_{col}"] = float(agg["k"].corr(agg[col], method="spearman"))
        # Across month-k cells, diagnostic only; inference remains month-level.
        z = g[["return_mean", "mean_pairwise_corr", "effective_n"]].dropna()
        rep[era]["cell_spearman_return_mean_pairwise_corr"] = float(z["return_mean"].corr(z["mean_pairwise_corr"], method="spearman")) if len(z) else None
        rep[era]["cell_spearman_return_effective_n"] = float(z["return_mean"].corr(z["effective_n"], method="spearman")) if len(z) else None
    return mk, rep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage1-artifact-dir", required=True)
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="stage2-remaining-trend-life-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    root = Path(args.stage1_artifact_dir)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    events = pd.read_parquet(find_one(root, "top1_admission_events.parquet"))
    detail = pd.read_parquet(find_one(root, "sampled_universe_detail.parquet"))
    stage1_mk = pd.read_csv(find_one(root, "monthly_k_distribution.csv"))

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    bars["symbol"] = bars["symbol"].astype(str)
    bars["date"] = pd.to_datetime(bars["date"])
    features = build_features(bars)
    features["symbol"] = features["symbol"].astype(str)
    features["date"] = pd.to_datetime(features["date"])
    cal, score, _r2, _slope, close, _op, _gross, _ret = build_wides(bars, features)

    primary_events = events[events["source"].eq("same_k_mc")].copy()
    symbols = sorted(primary_events["symbol"].astype(str).unique())
    epmap = build_episode_map(cal, score, close, symbols)
    labels, mk = aggregate_episodes(primary_events, epmap)

    # Carry forward the opposing small-K coverage and competition diagnostics.
    carry_cols = ["month", "k", "return_mean", "switches_median", "tenure_median", "winner_coverage_median", "dormant_share_median", "effective_n_median"]
    mk = mk.merge(stage1_mk[carry_cols], on=["month", "k"], how="left", validate="one_to_one")

    pair_mk, pair_report = pairwise_supplement(detail)
    pair_mk.to_csv(out / "stage1_pairwise_corr_supplement.csv", index=False)
    mk.to_csv(out / "stage2_monthly_k_mechanism.csv", index=False)
    labels.to_parquet(out / "stage2_first_admission_episode_labels.parquet", index=False, compression="zstd")

    metrics = ["age_days", "trend_age_ratio", "remaining_days", "remaining_close_return", "winner_coverage_median", "switches_median", "tenure_median"]
    report = {
        "stage": "new_stage_2",
        "name": "intrinsic_trend_episode_remaining_life",
        "lookahead": True,
        "executable": False,
        "source_stage1_run": 34772895471,
        "episode_definition": "maximal consecutive full-market trading-day run where frozen Stage1 pool_score is non-null",
        "admission_definition": "first Top1 admission per month/universe_id/symbol; same_k_mc only",
        "primary_remaining_return": "close(episode_end)/close(admission_signal_date)-1",
        "first_admission_rows": int(len(labels)),
        "months": int(mk["month"].nunique()),
        "metrics": {m: summarize_metric(mk, m, i * 37) for i, m in enumerate(metrics)},
        "stage1_pairwise_corr_supplement": pair_report,
        "rules": {
            "effective_inference_unit": "month",
            "bootstrap_resamples": BOOT_N,
            "no_k_selection": True,
            "no_episode_retuning": True,
        },
    }
    (out / "stage2_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
