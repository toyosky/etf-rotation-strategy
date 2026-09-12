#!/usr/bin/env python3
"""MUV Stage 0 V1: monthly Fixed15 retention/remove-one counterfactual labels.

Purpose
-------
Build a point-in-time month x ETF label panel for the Marginal Universe Value
project. The baseline universe is the frozen Fixed15 benchmark. Cash signal
511220 is always retained and is not itself labeled.

At each month-end as-of date:
- features use only information available through that close;
- baseline keeps Fixed15 for the next month;
- counterfactual removes exactly one incumbent for the next month;
- the OLS Top1 selector and transaction-cost model are unchanged;
- labels are baseline outcome minus remove-one counterfactual outcome.

Execution convention follows existing research code:
close(t) signal -> open(t+1) execute -> open(t+2) return.
Monthly outcome membership is assigned by execution date.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import resource
import tempfile
from pathlib import Path

import boto3
import numpy as np
import pandas as pd
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text

import sys
RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import LOOKBACK, _db_url, build_features
from walk_forward_candidate_pool import SIDE_COST
from universe.oracle_replacement_v1 import FIXED15, CASH_SIGNAL

VERSION = "muv_retention_labels_v1_20260912"
LABEL_START = pd.Period("2021-01", freq="M")


def peak_rss_mb() -> float:
    # GitHub-hosted runner is Linux: ru_maxrss is KiB.
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def load_fixed15_bars(engine) -> pd.DataFrame:
    syms = ",".join(f"'{s}'" for s in sorted(FIXED15))
    q = f"""
        select symbol, date, open, high, low, close, volume, amount
        from public.daily_bars
        where symbol in ({syms})
        order by symbol, date
    """
    df = pd.read_sql_query(text(q), engine, parse_dates=["date"])
    numeric = ["open", "high", "low", "close", "volume", "amount"]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df.empty:
        raise RuntimeError("Fixed15 daily bars are empty")
    if df[numeric].isna().any().any():
        raise RuntimeError("Fixed15 daily bars contain null/non-numeric OHLCV/amount")
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    return df


def prepare_wides(bars: pd.DataFrame, features: pd.DataFrame):
    calendar = pd.Index(sorted(pd.to_datetime(bars["date"].unique())), name="date")

    f = features.loc[features["symbol"].astype(str).isin(FIXED15)].copy()
    fixed15_positive = (
        (f["annual"] > 0)
        & (f["r2"] > 0)
        & (f["score"] > 0)
        & (~f["recent_drop3"].fillna(False))
    )
    f["pool_score"] = f["score"].where(fixed15_positive)

    score = (
        f.pivot(index="date", columns="symbol", values="pool_score")
        .reindex(calendar)
        .reindex(columns=sorted(FIXED15))
    )
    rank = score.rank(axis=1, method="min", ascending=False)
    counts = score.notna().sum(axis=1).astype(int)

    op = (
        bars.pivot(index="date", columns="symbol", values="open")
        .reindex(calendar)
        .reindex(columns=sorted(FIXED15))
    )
    oo = op.shift(-2) / op.shift(-1) - 1.0

    close = (
        bars.pivot(index="date", columns="symbol", values="close")
        .reindex(calendar)
        .reindex(columns=sorted(FIXED15))
    )
    ret = close.pct_change(fill_method=None)

    return calendar, score, rank, counts, oo, close, ret


def rank_pool(score: pd.DataFrame, pool: set[str]) -> tuple[pd.Series, pd.Series]:
    cols = [c for c in score.columns if c in pool]
    if not cols:
        return (
            pd.Series(None, index=score.index, dtype=object),
            pd.Series(0, index=score.index, dtype=int),
        )
    sub = score.loc[:, cols]
    counts = sub.notna().sum(axis=1).astype(int)
    ranked = pd.Series(None, index=score.index, dtype=object)
    m = counts > 0
    if bool(m.any()):
        ranked.loc[m] = sub.loc[m].idxmax(axis=1).astype(str)
    return ranked, counts


def _target(raw_ranked_value):
    if raw_ranked_value is None or pd.isna(raw_ranked_value):
        return None
    s = str(raw_ranked_value)
    return None if s == CASH_SIGNAL else s


def monthly_metrics(
    ranked: pd.Series,
    counts: pd.Series,
    oo: pd.DataFrame,
    calendar: pd.Index,
    label_period: pd.Period,
    initial_prev_target: str | None,
) -> dict:
    rows = []
    prev = initial_prev_target

    for i in range(len(calendar) - 2):
        signal = pd.Timestamp(calendar[i])
        exec_date = pd.Timestamp(calendar[i + 1])
        if exec_date.to_period("M") != label_period:
            continue

        raw = ranked.iloc[i]
        t = _target(raw)

        if t == prev:
            sides = 0
        elif prev is None or t is None:
            sides = 1
        else:
            sides = 2

        gross = 0.0
        missing = False
        if t is not None:
            try:
                gross = float(oo.at[signal, t])
                if not math.isfinite(gross):
                    gross = 0.0
                    missing = True
            except Exception:
                gross = 0.0
                missing = True

        net = (1.0 + gross) * (1.0 - SIDE_COST * sides) - 1.0
        rows.append(
            {
                "date": exec_date,
                "signal_date": signal,
                "raw_top1": None if raw is None or pd.isna(raw) else str(raw),
                "target": t,
                "gross": gross,
                "net": net,
                "switch": int(t != prev),
                "sides": int(sides),
                "missing": bool(missing),
                "candidate_count": int(counts.iloc[i]),
            }
        )
        prev = t

    p = pd.DataFrame(rows)
    if p.empty:
        return {
            "total_return": np.nan,
            "max_drawdown": np.nan,
            "switches": 0,
            "turnover_sides": 0,
            "mean_top1_tenure": np.nan,
            "invested_ratio": np.nan,
            "missing_quote_days": 0,
            "candidate_mean": np.nan,
            "execution_days": 0,
        }

    eq = (1.0 + p["net"]).cumprod()
    dd = eq / eq.cummax() - 1.0

    raw = p["raw_top1"].dropna().astype(str)
    groups = (raw != raw.shift()).cumsum()
    runs = raw.groupby(groups).size() if len(raw) else pd.Series(dtype=float)

    return {
        "total_return": float(eq.iloc[-1] - 1.0),
        "max_drawdown": float(dd.min()),
        "switches": int(p["switch"].sum()),
        "turnover_sides": int(p["sides"].sum()),
        "mean_top1_tenure": float(runs.mean()) if len(runs) else np.nan,
        "invested_ratio": float(p["target"].notna().mean()),
        "missing_quote_days": int(p["missing"].sum()),
        "candidate_mean": float(p["candidate_count"].mean()),
        "execution_days": int(len(p)),
    }


def safe_float(v):
    if v is None or pd.isna(v):
        return np.nan
    return float(v)


def make_state_rows(
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
    hist_dates = score.index[score.index <= asof]
    if len(hist_dates) == 0:
        return []
    last20 = hist_dates[-20:]
    last60 = hist_dates[-60:]
    last120 = hist_dates[-120:]

    asof_scores = score.loc[asof].dropna().sort_values(ascending=False)
    top1_symbol = str(asof_scores.index[0]) if len(asof_scores) else None
    top1_score = safe_float(asof_scores.iloc[0]) if len(asof_scores) else np.nan
    top2_score = safe_float(asof_scores.iloc[1]) if len(asof_scores) >= 2 else np.nan
    median_score = safe_float(asof_scores.median()) if len(asof_scores) else np.nan
    score_std = safe_float(asof_scores.std(ddof=0)) if len(asof_scores) else np.nan

    universe_count20_mean = safe_float(counts.loc[last20].mean()) if len(last20) else np.nan
    top1_margin = (
        top1_score - top2_score
        if math.isfinite(top1_score) and math.isfinite(top2_score)
        else np.nan
    )

    feature_cols = [
        "history_bars", "listing_age_days",
        "avg_amount60", "median_amount60", "nonzero_volume_ratio60",
        "slope", "annual", "r2", "score", "current_resid",
        "score_delta", "r2_delta", "slope_delta",
        "ret3", "ret5", "ret10", "ret20", "ret60",
        "dist_high20", "dist_high60", "dist_high120",
        "vol20", "vol60", "efficiency10", "efficiency20",
        "ma10_dist", "recent_drop3",
    ]
    day = features.loc[features["date"] == asof].copy()
    day["symbol"] = day["symbol"].astype(str)
    day = day.set_index("symbol", drop=False)

    corr120 = ret.loc[last120].corr(min_periods=min(60, max(2, len(last120) // 2))) if len(last120) >= 20 else pd.DataFrame()

    rows = []
    for sym in sorted(FIXED15 - {CASH_SIGNAL}):
        if sym not in day.index:
            continue
        srow = day.loc[sym]
        if int(srow["history_bars"]) < LOOKBACK:
            continue

        cf = counterfactual_by_symbol[sym]
        own_score = safe_float(score.at[asof, sym]) if sym in score.columns else np.nan
        own_rank = safe_float(rank.at[asof, sym]) if sym in rank.columns else np.nan

        top1_freq20 = safe_float((rank.loc[last20, sym] == 1).mean()) if sym in rank.columns and len(last20) else np.nan
        top3_freq20 = safe_float((rank.loc[last20, sym] <= 3).mean()) if sym in rank.columns and len(last20) else np.nan
        top1_freq60 = safe_float((rank.loc[last60, sym] == 1).mean()) if sym in rank.columns and len(last60) else np.nan

        days_since_top1 = np.nan
        if sym in rank.columns and len(hist_dates):
            h = rank.loc[hist_dates, sym]
            hits = np.flatnonzero((h == 1).to_numpy())
            if len(hits):
                days_since_top1 = int(len(h) - 1 - hits[-1])

        other_corrs = []
        corr_with_top1 = np.nan
        if not corr120.empty and sym in corr120.index:
            for other in sorted(FIXED15 - {sym}):
                if other in corr120.columns:
                    v = corr120.at[sym, other]
                    if pd.notna(v):
                        other_corrs.append(float(v))
            if top1_symbol and top1_symbol != sym and top1_symbol in corr120.columns:
                v = corr120.at[sym, top1_symbol]
                if pd.notna(v):
                    corr_with_top1 = float(v)

        max_corr = max(other_corrs) if other_corrs else np.nan
        median_corr = float(np.median(other_corrs)) if other_corrs else np.nan

        row = {
            "dataset_version": VERSION,
            "decision_type": "retention",
            "asof_date": asof,
            "label_month": str(label_period),
            "symbol": sym,
            "baseline_universe": "Fixed15",
            "baseline_universe_size": int(len(FIXED15)),
            "counterfactual_universe_size": int(len(FIXED15) - 1),

            "asof_candidate_count": int(counts.at[asof]),
            "candidate_count20_mean": universe_count20_mean,
            "asof_top1_symbol": top1_symbol,
            "asof_top1_score": top1_score,
            "asof_top2_score": top2_score,
            "asof_top1_margin": top1_margin,
            "asof_score_median": median_score,
            "asof_score_std": score_std,

            "own_score_rank": own_rank,
            "own_score_gap_top1": (
                own_score - top1_score
                if math.isfinite(own_score) and math.isfinite(top1_score)
                else np.nan
            ),
            "own_score_ratio_top1": (
                own_score / top1_score
                if math.isfinite(own_score) and math.isfinite(top1_score) and top1_score != 0
                else np.nan
            ),
            "top1_freq20": top1_freq20,
            "top3_freq20": top3_freq20,
            "top1_freq60": top1_freq60,
            "days_since_top1": days_since_top1,
            "corr120_max_with_universe": max_corr,
            "corr120_median_with_universe": median_corr,
            "corr120_with_current_top1": corr_with_top1,

            "base_return": base_metrics["total_return"],
            "base_max_drawdown": base_metrics["max_drawdown"],
            "base_switches": base_metrics["switches"],
            "base_turnover_sides": base_metrics["turnover_sides"],
            "base_mean_top1_tenure": base_metrics["mean_top1_tenure"],
            "base_invested_ratio": base_metrics["invested_ratio"],
            "base_missing_quote_days": base_metrics["missing_quote_days"],
            "base_candidate_mean": base_metrics["candidate_mean"],

            "cf_return": cf["total_return"],
            "cf_max_drawdown": cf["max_drawdown"],
            "cf_switches": cf["switches"],
            "cf_turnover_sides": cf["turnover_sides"],
            "cf_mean_top1_tenure": cf["mean_top1_tenure"],
            "cf_invested_ratio": cf["invested_ratio"],
            "cf_missing_quote_days": cf["missing_quote_days"],
            "cf_candidate_mean": cf["candidate_mean"],

            # Retention value convention: base (keep) minus remove-one.
            "delta_return": base_metrics["total_return"] - cf["total_return"],
            "delta_max_drawdown": base_metrics["max_drawdown"] - cf["max_drawdown"],
            "delta_switches": base_metrics["switches"] - cf["switches"],
            "delta_turnover_sides": base_metrics["turnover_sides"] - cf["turnover_sides"],
            "delta_mean_top1_tenure": base_metrics["mean_top1_tenure"] - cf["mean_top1_tenure"],
            "delta_invested_ratio": base_metrics["invested_ratio"] - cf["invested_ratio"],
            "delta_missing_quote_days": base_metrics["missing_quote_days"] - cf["missing_quote_days"],
        }

        for col in feature_cols:
            v = srow[col]
            if isinstance(v, (np.bool_, bool)):
                row[f"x_{col}"] = bool(v)
            elif pd.isna(v):
                row[f"x_{col}"] = np.nan
            else:
                row[f"x_{col}"] = float(v)

        rows.append(row)

    return rows


def build_panel(bars: pd.DataFrame, features: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    calendar, score, rank, counts, oo, close, ret = prepare_wides(bars, features)
    baseline_ranked, baseline_counts = rank_pool(score, set(FIXED15))

    # Current data ends in an incomplete September 2026, so the last complete
    # label month is the previous calendar month.
    max_date = pd.Timestamp(calendar.max())
    current_period = max_date.to_period("M")
    last_label_period = current_period - 1

    months = pd.period_range(LABEL_START, last_label_period, freq="M")
    all_rows = []
    month_audit = []

    for label_period in months:
        first_exec_candidates = calendar[
            pd.Index([pd.Timestamp(d).to_period("M") == label_period for d in calendar])
        ]
        if len(first_exec_candidates) == 0:
            continue
        first_exec = pd.Timestamp(first_exec_candidates[0])
        first_pos = int(calendar.get_loc(first_exec))
        if first_pos == 0:
            continue
        asof = pd.Timestamp(calendar[first_pos - 1])

        prev_signal_pos = first_pos - 2
        initial_prev = None
        if prev_signal_pos >= 0:
            initial_prev = _target(baseline_ranked.iloc[prev_signal_pos])

        base_metrics = monthly_metrics(
            baseline_ranked, baseline_counts, oo, calendar, label_period, initial_prev
        )
        if base_metrics["execution_days"] == 0:
            continue

        cf_by_symbol = {}
        for sym in sorted(FIXED15 - {CASH_SIGNAL}):
            cf_ranked, cf_counts = rank_pool(score, set(FIXED15) - {sym})
            cf_by_symbol[sym] = monthly_metrics(
                cf_ranked, cf_counts, oo, calendar, label_period, initial_prev
            )

        rows = make_state_rows(
            features, score, rank, counts, ret, baseline_ranked,
            asof, label_period, base_metrics, cf_by_symbol
        )
        all_rows.extend(rows)
        month_audit.append(
            {
                "label_month": str(label_period),
                "asof_date": asof,
                "rows": len(rows),
                "base_return": base_metrics["total_return"],
                "base_max_drawdown": base_metrics["max_drawdown"],
                "base_switches": base_metrics["switches"],
                "execution_days": base_metrics["execution_days"],
            }
        )

    panel = pd.DataFrame(all_rows)
    if panel.empty:
        raise RuntimeError("No MUV retention labels generated")
    panel = panel.sort_values(["asof_date", "symbol"]).reset_index(drop=True)

    audit = {
        "months": int(panel["label_month"].nunique()),
        "rows": int(len(panel)),
        "symbols": int(panel["symbol"].nunique()),
        "asof_min": str(pd.Timestamp(panel["asof_date"].min()).date()),
        "asof_max": str(pd.Timestamp(panel["asof_date"].max()).date()),
        "label_month_min": str(panel["label_month"].min()),
        "label_month_max": str(panel["label_month"].max()),
        "positive_delta_return_share": float((panel["delta_return"] > 0).mean()),
        "zero_delta_return_share": float(np.isclose(panel["delta_return"], 0.0, atol=1e-12).mean()),
        "delta_return_median": float(panel["delta_return"].median()),
        "delta_return_mean": float(panel["delta_return"].mean()),
        "month_audit": month_audit,
    }
    return panel, audit


def ensure_bucket(s3, bucket: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(Bucket=bucket)


def upload_outputs(panel: pd.DataFrame, summary: dict, args) -> dict:
    s3 = boto3.client(
        "s3",
        endpoint_url=args.s3_endpoint,
        region_name=args.s3_region,
        aws_access_key_id=args.s3_access_key,
        aws_secret_access_key=args.s3_secret_key,
    )
    ensure_bucket(s3, args.bucket)

    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        pq = td / "retention_labels.parquet"
        manifest = td / "manifest.json"
        panel.to_parquet(pq, index=False, compression="zstd")
        manifest.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

        prefix = "marginal_universe_value/v1/retention"
        pq_key = f"{prefix}/retention_labels.parquet"
        manifest_key = f"{prefix}/manifest.json"
        s3.upload_file(str(pq), args.bucket, pq_key)
        s3.upload_file(str(manifest), args.bucket, manifest_key)
        return {
            "bucket": args.bucket,
            "parquet_key": pq_key,
            "parquet_bytes": int(pq.stat().st_size),
            "manifest_key": manifest_key,
            "manifest_bytes": int(manifest.stat().st_size),
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--s3-endpoint", default=os.getenv("SUPABASE_STORAGE_S3_ENDPOINT"))
    ap.add_argument("--s3-region", default=os.getenv("SUPABASE_STORAGE_S3_REGION", "ap-southeast-1"))
    ap.add_argument("--s3-access-key", default=os.getenv("SUPABASE_STORAGE_S3_ACCESS_KEY_ID"))
    ap.add_argument("--s3-secret-key", default=os.getenv("SUPABASE_STORAGE_S3_SECRET_ACCESS_KEY"))
    ap.add_argument("--bucket", default=os.getenv("SUPABASE_STORAGE_BUCKET", "etf-research-archive"))
    ap.add_argument("--summary-path", default="muv-retention-v1-summary.json")
    ap.add_argument("--local-parquet-path", default="muv-retention-labels-v1.parquet")
    ap.add_argument("--skip-upload", action="store_true")
    args = ap.parse_args()

    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    if not args.skip_upload and not all([args.s3_endpoint, args.s3_access_key, args.s3_secret_key]):
        raise SystemExit("Missing Supabase Storage S3 credentials")

    mem0 = peak_rss_mb()
    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)

    bars = load_fixed15_bars(engine)
    mem_after_bars = peak_rss_mb()

    features = build_features(bars)
    mem_after_features = peak_rss_mb()

    panel, audit = build_panel(bars, features)
    mem_after_panel = peak_rss_mb()

    local_parquet = Path(args.local_parquet_path)
    panel.to_parquet(local_parquet, index=False, compression="zstd")

    summary = {
        "version": VERSION,
        "git_sha": os.getenv("GITHUB_SHA"),
        "source": "public.daily_bars",
        "baseline_universe": "Fixed15",
        "cash_signal_forced": CASH_SIGNAL,
        "retention_symbols": sorted(FIXED15 - {CASH_SIGNAL}),
        "execution": {
            "selector": "annual>0, r2>0, score>0, D2 pass; highest score",
            "signal_to_execution": "close(t) -> open(t+1)",
            "return_alignment": "open(t+1) -> open(t+2)",
            "side_cost": float(SIDE_COST),
            "monthly_membership": "execution date",
        },
        "bars": {
            "rows": int(len(bars)),
            "symbols": int(bars["symbol"].nunique()),
            "date_min": str(pd.Timestamp(bars["date"].min()).date()),
            "date_max": str(pd.Timestamp(bars["date"].max()).date()),
        },
        "panel": audit,
        "local_parquet_bytes": int(local_parquet.stat().st_size),
        "memory_peak_mb": {
            "startup": mem0,
            "after_bars": mem_after_bars,
            "after_features": mem_after_features,
            "after_panel": mem_after_panel,
            "final_before_upload": peak_rss_mb(),
        },
    }

    if not args.skip_upload:
        summary["storage"] = upload_outputs(panel, summary, args)
        summary["memory_peak_mb"]["after_upload"] = peak_rss_mb()

    Path(args.summary_path).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
