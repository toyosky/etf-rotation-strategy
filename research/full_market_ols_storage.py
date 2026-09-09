#!/usr/bin/env python3
"""Full-market ETF OLS research pipeline.

Architecture:
- Source of truth stays in Supabase Postgres: public.daily_bars.
- Large daily derived features are computed in GitHub Actions and archived as
  compressed Parquet in Supabase Storage (S3 API), partitioned by quarter.
- Only compact episode-level research data is written back to Postgres.

This intentionally avoids recreating the ~459 MB daily feature table inside the
Free-plan database.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from pathlib import Path

import boto3
import numpy as np
import pandas as pd
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text

LOOKBACK = 26
HALF_LIFE = 10.0
ANNUALIZATION = 250.0
D2_FLOOR = 0.97
UNIVERSE_MIN_HISTORY = 200
UNIVERSE_MIN_LISTING_DAYS = 365
AVG_AMOUNT60_MIN = 20_000_000.0
MEDIAN_AMOUNT60_MIN = 10_000_000.0
NONZERO60_MIN = 0.95
EPISODE_START = pd.Timestamp("2021-01-01")
LIFE_CAP = 20


def _db_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        raw = "postgresql+psycopg2://" + raw[len("postgresql://") :]
    return raw


def load_daily_bars(engine) -> pd.DataFrame:
    sql = """
        select symbol, date, open, high, low, close, volume, amount
        from public.daily_bars
        order by symbol, date
    """
    df = pd.read_sql_query(sql, engine, parse_dates=["date"])
    numeric = ["open", "high", "low", "close", "volume", "amount"]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df.empty:
        raise RuntimeError("public.daily_bars is empty")
    if df[numeric].isna().any().any():
        raise RuntimeError("daily_bars contains null/non-numeric OHLCV/amount values")
    return df


def calc_ols_arrays(close: np.ndarray) -> dict[str, np.ndarray]:
    n = len(close)
    nan = np.full(n, np.nan, dtype=float)
    out = {
        "slope": nan.copy(),
        "intercept": nan.copy(),
        "annual": nan.copy(),
        "r2": nan.copy(),
        "score": nan.copy(),
        "current_resid": nan.copy(),
    }
    if n < LOOKBACK:
        return out

    y = np.log(close.astype(float))
    windows = np.lib.stride_tricks.sliding_window_view(y, LOOKBACK)
    x = np.arange(LOOKBACK, dtype=float)
    q = np.power(0.5, (LOOKBACK - 1 - x) / HALF_LIFE)
    w = q * q  # frozen fit and R² weights
    sw = float(w.sum())
    swx = float((w * x).sum())
    swxx = float((w * x * x).sum())
    den = sw * swxx - swx * swx

    wy = windows @ w
    wxy = windows @ (w * x)
    slope = (sw * wxy - swx * wy) / den
    intercept = (wy - slope * swx) / sw

    fitted = intercept[:, None] + slope[:, None] * x[None, :]
    resid = windows - fitted
    sse = (resid * resid) @ w
    ybar = wy / sw
    centered = windows - ybar[:, None]
    sst = (centered * centered) @ w
    r2 = np.where(sst > 0, 1.0 - sse / sst, 0.0)
    annual = np.exp(slope * ANNUALIZATION) - 1.0
    score = np.where(
        (annual > 0) & (r2 > 0),
        annual * r2,
        np.where((annual < 0) & (r2 < 0), np.abs(annual) * np.abs(r2), 0.0),
    )
    current_resid = windows[:, -1] - (slope * (LOOKBACK - 1) + intercept)

    sl = slice(LOOKBACK - 1, None)
    out["slope"][sl] = slope
    out["intercept"][sl] = intercept
    out["annual"][sl] = annual
    out["r2"][sl] = r2
    out["score"][sl] = score
    out["current_resid"][sl] = current_resid
    return out


def feature_one_symbol(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("date").copy().reset_index(drop=True)
    n = len(g)
    g["rn"] = np.arange(1, n + 1, dtype=np.int32)
    first_date = g.loc[0, "date"]
    g["history_bars"] = g["rn"]
    g["listing_age_days"] = (g["date"] - first_date).dt.days.astype(np.int32)

    c = g["close"].astype(float)
    a = g["amount"].astype(float)
    v = g["volume"].astype(float)
    logret = np.log(c / c.shift(1))
    ratio1 = c / c.shift(1)

    g["avg_amount60"] = a.rolling(60, min_periods=60).mean()
    g["median_amount60"] = a.rolling(60, min_periods=60).median()
    g["nonzero_volume_ratio60"] = (v > 0).astype(float).rolling(60, min_periods=60).mean()

    high20 = c.rolling(20, min_periods=1).max()
    high60 = c.rolling(60, min_periods=1).max()
    high120 = c.rolling(120, min_periods=1).max()
    g["dist_high20"] = c / high20 - 1.0
    g["dist_high60"] = c / high60 - 1.0
    g["dist_high120"] = c / high120 - 1.0
    g["vol20"] = logret.rolling(20, min_periods=2).std(ddof=1)
    g["vol60"] = logret.rolling(60, min_periods=2).std(ddof=1)

    for k in (3, 5, 10, 20, 60):
        g[f"ret{k}"] = c / c.shift(k) - 1.0

    absret10 = logret.abs().rolling(10, min_periods=10).sum()
    absret20 = logret.abs().rolling(20, min_periods=20).sum()
    g["efficiency10"] = np.where(
        absret10 > 0, np.abs(np.log(c / c.shift(10))) / absret10, np.nan
    )
    g["efficiency20"] = np.where(
        absret20 > 0, np.abs(np.log(c / c.shift(20))) / absret20, np.nan
    )

    ma10 = c.rolling(10, min_periods=10).mean()
    g["ma10"] = ma10
    g["ma10_dist"] = c / ma10 - 1.0
    g["mom5_pass"] = c > c.shift(5)

    ols = calc_ols_arrays(c.to_numpy())
    for key, values in ols.items():
        g[key] = values

    g["recent_drop3"] = ratio1.rolling(3, min_periods=3).min() < D2_FLOOR
    g["universe_eligible"] = (
        (g["history_bars"] >= UNIVERSE_MIN_HISTORY)
        & (g["listing_age_days"] >= UNIVERSE_MIN_LISTING_DAYS)
        & (g["avg_amount60"] >= AVG_AMOUNT60_MIN)
        & (g["median_amount60"] >= MEDIAN_AMOUNT60_MIN)
        & (g["nonzero_volume_ratio60"] >= NONZERO60_MIN)
    )
    g["trend_eligible"] = (
        g["universe_eligible"]
        & (g["annual"] > 0)
        & (g["r2"] > 0)
        & (g["score"] > 0)
        & (~g["recent_drop3"].fillna(False))
    )

    g["score_delta"] = g["score"] - g["score"].shift(1)
    g["r2_delta"] = g["r2"] - g["r2"].shift(1)
    g["slope_delta"] = g["slope"] - g["slope"].shift(1)
    return g


def build_features(bars: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for _, g in bars.groupby("symbol", sort=False):
        parts.append(feature_one_symbol(g))
    f = pd.concat(parts, ignore_index=True)

    f["universe_count"] = f.groupby("date")["universe_eligible"].transform("sum").astype(np.int32)
    f["trend_count"] = f.groupby("date")["trend_eligible"].transform("sum").astype(np.int32)
    f["xrank"] = np.nan
    f["xpercentile"] = np.nan
    mask = f["trend_eligible"]
    f.loc[mask, "xrank"] = (
        f.loc[mask].groupby("date")["score"].rank(method="first", ascending=False)
    )
    # Highest score -> percentile near 1.0.
    f.loc[mask, "xpercentile"] = (
        f.loc[mask].groupby("date")["score"].rank(method="average", pct=True, ascending=True)
    )
    return f.sort_values(["symbol", "date"]).reset_index(drop=True)


def first_fail_offset(values: np.ndarray, start: int, cap: int, start_offset: int = 0) -> int:
    last = min(len(values) - 1, start + cap)
    for pos in range(start + start_offset, last + 1):
        if not bool(values[pos]):
            return pos - start
    return last - start


def build_episodes(features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    keep_cols = [
        "symbol", "date", "rn", "score", "annual", "r2", "slope", "score_delta", "r2_delta", "slope_delta",
        "current_resid", "ret3", "ret5", "ret10", "ret20", "ret60", "dist_high20", "dist_high60", "dist_high120",
        "vol20", "vol60", "efficiency10", "efficiency20", "ma10_dist", "xrank", "xpercentile", "trend_count",
        "universe_count",
    ]

    for symbol, g in features.groupby("symbol", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        trend = g["trend_eligible"].fillna(False).to_numpy(dtype=bool)
        prev = np.r_[False, trend[:-1]]
        starts = np.flatnonzero(trend & (~prev) & (g["date"].to_numpy() >= np.datetime64(EPISODE_START)))
        close = g["close"].to_numpy(dtype=float)
        ma10_pass = (g["close"] >= g["ma10"]).fillna(False).to_numpy(dtype=bool)
        mom5_pass = g["mom5_pass"].fillna(False).to_numpy(dtype=bool)

        for s in starts:
            base = g.loc[s, keep_cols].to_dict()
            base["start_date"] = base.pop("date")
            base["start_rn"] = int(base.pop("rn"))
            base["d2_pass"] = True

            max_future = min(LIFE_CAP, len(g) - 1 - s)
            base["right_censored"] = max_future < LIFE_CAP
            base["ols_life20"] = first_fail_offset(trend, s, LIFE_CAP, start_offset=1)
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
                future = close[s + 1 : end]
                base[f"mfe{h}"] = float(np.max(future / p0 - 1.0)) if len(future) else np.nan
                base[f"mae{h}"] = float(np.min(future / p0 - 1.0)) if len(future) else np.nan
            rows.append(base)

    e = pd.DataFrame(rows)
    if e.empty:
        raise RuntimeError("No OLS episodes were generated")
    e["xrank"] = pd.to_numeric(e["xrank"], errors="coerce").astype("Int64")
    return e.sort_values(["start_date", "symbol"]).reset_index(drop=True)


def ensure_bucket(s3, bucket: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(Bucket=bucket)


def upload_file(s3, bucket: str, local: Path, key: str) -> None:
    size = local.stat().st_size
    if size > 49 * 1024 * 1024:
        raise RuntimeError(f"Parquet object exceeds safe Free-plan 49 MB limit: {local} ({size} bytes)")
    s3.upload_file(str(local), bucket, key)


def archive_to_storage(features: pd.DataFrame, episodes: pd.DataFrame, args) -> dict:
    s3 = boto3.client(
        "s3",
        endpoint_url=args.s3_endpoint,
        region_name=args.s3_region,
        aws_access_key_id=args.s3_access_key,
        aws_secret_access_key=args.s3_secret_key,
    )
    ensure_bucket(s3, args.bucket)

    archive_cols = [
        "date", "symbol", "close", "amount", "volume", "history_bars", "listing_age_days",
        "avg_amount60", "median_amount60", "nonzero_volume_ratio60", "universe_eligible",
        "slope", "intercept", "annual", "r2", "score", "current_resid", "recent_drop3", "trend_eligible",
        "score_delta", "r2_delta", "slope_delta", "ret3", "ret5", "ret10", "ret20", "ret60",
        "dist_high20", "dist_high60", "dist_high120", "vol20", "vol60", "efficiency10", "efficiency20",
        "ma10_dist", "xrank", "xpercentile", "trend_count", "universe_count",
    ]
    f = features.loc[features["date"] >= EPISODE_START, archive_cols].copy()
    f["year"] = f["date"].dt.year
    f["quarter"] = f["date"].dt.quarter

    uploaded = []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for (year, quarter), part in f.groupby(["year", "quarter"], sort=True):
            local = td / f"ols_daily_features_{year}_Q{quarter}.parquet"
            part.drop(columns=["year", "quarter"]).to_parquet(local, index=False, compression="zstd")
            key = f"full_market_ols/daily_features/year={year}/quarter=Q{quarter}/features.parquet"
            upload_file(s3, args.bucket, local, key)
            uploaded.append({"key": key, "bytes": local.stat().st_size, "rows": len(part)})

        ep_local = td / "ols_episodes.parquet"
        episodes.to_parquet(ep_local, index=False, compression="zstd")
        ep_key = "full_market_ols/episodes/ols_episodes.parquet"
        upload_file(s3, args.bucket, ep_local, ep_key)
        uploaded.append({"key": ep_key, "bytes": ep_local.stat().st_size, "rows": len(episodes)})

        manifest = {
            "version": "full_market_ols_v1_20260909",
            "source": "public.daily_bars",
            "ols": {"lookback_prices": 26, "half_life": 10, "fit_weights": "q^2", "annualization": 250},
            "universe": {
                "history_bars_min": 200,
                "listing_age_days_min": 365,
                "avg_amount60_min": AVG_AMOUNT60_MIN,
                "median_amount60_min": MEDIAN_AMOUNT60_MIN,
                "nonzero_volume_ratio60_min": NONZERO60_MIN,
            },
            "episode_count": int(len(episodes)),
            "feature_rows_2021plus": int(len(f)),
            "objects": uploaded,
        }
        manifest_local = td / "manifest.json"
        manifest_local.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest_key = "full_market_ols/manifest.json"
        upload_file(s3, args.bucket, manifest_local, manifest_key)
        uploaded.append({"key": manifest_key, "bytes": manifest_local.stat().st_size, "rows": None})
    return {"bucket": args.bucket, "objects": uploaded}


def replace_episode_table(engine, episodes: pd.DataFrame) -> None:
    stage = "ols_episodes_stage"
    episodes.to_sql(stage, engine, schema="research", if_exists="replace", index=False, chunksize=1000, method="multi")
    with engine.begin() as conn:
        conn.execute(text("drop table if exists research.ols_episodes"))
        conn.execute(text(f"alter table research.{stage} rename to ols_episodes"))
        conn.execute(text("alter table research.ols_episodes add primary key(symbol,start_date)"))
        conn.execute(text("create index ols_episodes_date_idx on research.ols_episodes(start_date)"))
        conn.execute(text("create index ols_episodes_symbol_idx on research.ols_episodes(symbol,start_date)"))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--s3-endpoint", default=os.getenv("SUPABASE_STORAGE_S3_ENDPOINT"))
    p.add_argument("--s3-region", default=os.getenv("SUPABASE_STORAGE_S3_REGION", "ap-southeast-1"))
    p.add_argument("--s3-access-key", default=os.getenv("SUPABASE_STORAGE_S3_ACCESS_KEY_ID"))
    p.add_argument("--s3-secret-key", default=os.getenv("SUPABASE_STORAGE_S3_SECRET_ACCESS_KEY"))
    p.add_argument("--bucket", default=os.getenv("SUPABASE_STORAGE_BUCKET", "etf-research-archive"))
    p.add_argument("--skip-upload", action="store_true")
    p.add_argument("--skip-db-episodes", action="store_true")
    p.add_argument("--summary-path", default="full-market-ols-summary.json")
    args = p.parse_args()

    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    if not args.skip_upload and not all([args.s3_endpoint, args.s3_access_key, args.s3_secret_key]):
        raise SystemExit("Missing Supabase Storage S3 endpoint/access-key/secret-key")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)
    episodes = build_episodes(features)

    result = {
        "bars_rows": int(len(bars)),
        "symbols": int(bars["symbol"].nunique()),
        "feature_rows": int(len(features)),
        "episodes": int(len(episodes)),
        "date_min": str(bars["date"].min().date()),
        "date_max": str(bars["date"].max().date()),
    }

    if not args.skip_upload:
        result["storage"] = archive_to_storage(features, episodes, args)
    if not args.skip_db_episodes:
        replace_episode_table(engine, episodes)
        result["episodes_written_to_db"] = int(len(episodes))

    Path(args.summary_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
