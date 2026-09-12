#!/usr/bin/env python3
"""Build Post-OLS Remaining Trend Life Study V1.

This is a diagnostic research pipeline, not a trading strategy.
It reuses the frozen full-market OLS feature engine, builds several aligned
"detection" contracts inside each raw positive OLS episode, labels remaining
trend life, archives event-level results as Parquet in Supabase Storage, and
emits compact JSON/Markdown diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import boto3
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sqlalchemy import create_engine, text

# Allow importing frozen research engine from research/ when executed as a file.
RESEARCH_DIR = Path(__file__).resolve().parents[1]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from full_market_ols_storage import _db_url, build_features, load_daily_bars  # noqa: E402
from rebuild_raw_ols_episodes import assert_ols_calibration  # noqa: E402

STUDY_VERSION = "v1"
STUDY_START = pd.Timestamp("2021-01-01")
MAX_LIFE = 60
LEADER_PERCENTILE = 0.90
TOP_K = 3

FEATURES = [
    "score", "annual", "r2", "slope", "score_delta", "r2_delta", "slope_delta",
    "current_resid", "ret3", "ret5", "ret10", "ret20", "ret60",
    "dist_high20", "dist_high60", "dist_high120", "vol20", "vol60",
    "efficiency10", "efficiency20", "ma10_dist", "avg_amount60",
    "median_amount60", "nonzero_volume_ratio60", "xpercentile",
    "market_trend_breadth", "class_trend_breadth", "class_median_r2",
    "class_median_score", "class_median_slope",
]

META_COLS = [
    "symbol", "name", "product_type", "asset_class", "region_primary",
    "exposure_level1", "risk_bucket", "is_qdii", "derivative_exposure",
    "currency_exposure", "historical_safe", "needs_review",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--output-dir", type=Path, default=Path("post-ols-life-output"))
    p.add_argument("--summary-path", type=Path, default=Path("post-ols-life-summary.json"))
    p.add_argument("--s3-endpoint", default=os.getenv("SUPABASE_STORAGE_S3_ENDPOINT"))
    p.add_argument("--s3-region", default=os.getenv("SUPABASE_STORAGE_S3_REGION", "ap-southeast-1"))
    p.add_argument("--s3-access-key", default=os.getenv("SUPABASE_STORAGE_S3_ACCESS_KEY_ID"))
    p.add_argument("--s3-secret-key", default=os.getenv("SUPABASE_STORAGE_S3_SECRET_ACCESS_KEY"))
    p.add_argument("--bucket", default=os.getenv("SUPABASE_STORAGE_BUCKET", "etf-research-archive"))
    return p.parse_args()


def load_metadata(engine) -> pd.DataFrame:
    cols = ",".join(META_COLS)
    meta = pd.read_sql_query(text(f"select {cols} from public.instrument_metadata_current"), engine)
    meta["symbol"] = meta["symbol"].astype(str).str.zfill(6)
    if meta["symbol"].duplicated().any():
        raise RuntimeError("instrument_metadata_current contains duplicate symbols")
    return meta


def add_context(features: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    f = features.loc[features["date"] >= STUDY_START].copy()
    f["symbol"] = f["symbol"].astype(str).str.zfill(6)
    f = f.merge(meta, on="symbol", how="left", validate="many_to_one")
    f["asset_class"] = f["asset_class"].fillna("UNKNOWN")
    f["region_primary"] = f["region_primary"].fillna("UNKNOWN")
    f["exposure_level1"] = f["exposure_level1"].fillna("UNKNOWN")
    f["risk_bucket"] = f["risk_bucket"].fillna("UNKNOWN")

    f["market_trend_breadth"] = np.where(
        f["universe_count"] > 0,
        f["trend_count"] / f["universe_count"],
        np.nan,
    )

    keys = [f["date"], f["asset_class"]]
    f["class_universe_count"] = f["universe_eligible"].astype(int).groupby(keys).transform("sum")
    f["class_trend_count"] = f["trend_eligible"].astype(int).groupby(keys).transform("sum")
    f["class_trend_breadth"] = np.where(
        f["class_universe_count"] > 0,
        f["class_trend_count"] / f["class_universe_count"],
        np.nan,
    )
    for col in ("r2", "score", "slope"):
        eligible_values = f[col].where(f["universe_eligible"])
        f[f"class_median_{col}"] = eligible_values.groupby(keys).transform("median")
    return f


def consecutive_future(values: np.ndarray, start: int, cap: int) -> int:
    """Future consecutive TRUE sessions after start, capped at cap."""
    if not bool(values[start]):
        return 0
    count = 0
    last = min(len(values) - 1, start + cap)
    for pos in range(start + 1, last + 1):
        if not bool(values[pos]):
            break
        count += 1
    return count


def first_true(indices: np.ndarray, mask: np.ndarray) -> int | None:
    hits = indices[mask[indices]]
    return int(hits[0]) if len(hits) else None


def event_row(g: pd.DataFrame, raw: np.ndarray, trend: np.ndarray, raw_end: int,
              start: int, detection_type: str, episode_no: int) -> dict[str, Any]:
    close = g["close"].to_numpy(dtype=float)
    ma10_pass = (g["close"] >= g["ma10"]).fillna(False).to_numpy(dtype=bool)
    row = g.iloc[start]

    out: dict[str, Any] = {
        "study_version": STUDY_VERSION,
        "symbol": str(row["symbol"]),
        "raw_episode_no": int(episode_no),
        "detection_type": detection_type,
        "detection_date": pd.Timestamp(row["date"]),
        "close": float(row["close"]),
        "raw_episode_right_censored": bool(raw_end == len(g) - 1),
        "label_complete_60": bool((len(g) - 1 - start) >= MAX_LIFE),
        "raw_survival_days_60": int(min(raw_end - start, MAX_LIFE)),
        "tradable_survival_days_60": int(consecutive_future(trend, start, MAX_LIFE)),
        "ma10_survival_days_60": int(consecutive_future(ma10_pass, start, MAX_LIFE)),
    }

    peak = close[start]
    dd_hit = False
    dd_day = min(MAX_LIFE, len(g) - 1 - start)
    for d in range(1, min(MAX_LIFE, len(g) - 1 - start) + 1):
        peak = max(peak, close[start + d])
        if close[start + d] <= peak * 0.97:
            dd_hit = True
            dd_day = d
            break
    out["days_to_dd3_60"] = int(dd_day)
    out["dd3_hit_60"] = bool(dd_hit)

    p0 = close[start]
    for h in (5, 10, 20, 40):
        out[f"fwd{h}"] = float(close[start + h] / p0 - 1.0) if start + h < len(g) else np.nan
    for h in (20, 40):
        end = min(len(g), start + h + 1)
        future = close[start + 1:end]
        out[f"mfe{h}"] = float(np.max(future / p0 - 1.0)) if len(future) else np.nan
        out[f"mae{h}"] = float(np.min(future / p0 - 1.0)) if len(future) else np.nan

    copy_cols = [
        "score", "annual", "r2", "slope", "score_delta", "r2_delta", "slope_delta",
        "current_resid", "ret3", "ret5", "ret10", "ret20", "ret60",
        "dist_high20", "dist_high60", "dist_high120", "vol20", "vol60",
        "efficiency10", "efficiency20", "ma10_dist", "avg_amount60",
        "median_amount60", "nonzero_volume_ratio60", "xrank", "xpercentile",
        "trend_count", "universe_count", "market_trend_breadth",
        "class_universe_count", "class_trend_count", "class_trend_breadth",
        "class_median_r2", "class_median_score", "class_median_slope",
        "name", "product_type", "asset_class", "region_primary", "exposure_level1",
        "risk_bucket", "is_qdii", "derivative_exposure", "currency_exposure",
        "historical_safe", "needs_review",
    ]
    for col in copy_cols:
        out[col] = row.get(col, np.nan)
    return out


def build_events(features: pd.DataFrame) -> pd.DataFrame:
    events: list[dict[str, Any]] = []
    for _, g0 in features.groupby("symbol", sort=False):
        g = g0.sort_values("date").reset_index(drop=True)
        raw = ((g["annual"] > 0) & (g["r2"] > 0) & (g["score"] > 0)).fillna(False).to_numpy(bool)
        trend = g["trend_eligible"].fillna(False).to_numpy(bool)
        leader10 = (trend & (g["xpercentile"].fillna(-np.inf).to_numpy(float) >= LEADER_PERCENTILE))
        top3 = (trend & (g["xrank"].fillna(np.inf).to_numpy(float) <= TOP_K))
        universe = g["universe_eligible"].fillna(False).to_numpy(bool)

        prev_raw = np.r_[False, raw[:-1]]
        raw_starts = np.flatnonzero(raw & (~prev_raw))
        episode_no = 0
        for rs in raw_starts:
            if pd.Timestamp(g.loc[rs, "date"]) < STUDY_START:
                continue
            episode_no += 1
            re = int(rs)
            while re + 1 < len(g) and raw[re + 1]:
                re += 1
            seg = np.arange(rs, re + 1, dtype=int)

            detections: list[tuple[str, int | None]] = [
                ("raw_start", int(rs) if universe[rs] else None),
                ("tradable_start", first_true(seg, trend)),
                ("leader10_start", first_true(seg, leader10)),
                ("top3_start", first_true(seg, top3)),
            ]
            for dtype, pos in detections:
                if pos is not None:
                    events.append(event_row(g, raw, trend, re, pos, dtype, episode_no))

    out = pd.DataFrame(events)
    if out.empty:
        raise RuntimeError("No detection events generated")
    out["period"] = np.where(
        pd.to_datetime(out["detection_date"]).dt.year <= 2024,
        "2021-2024",
        "2025-2026",
    )
    return out.sort_values(["detection_date", "symbol", "detection_type"]).reset_index(drop=True)


def summarize_group(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    def agg(g: pd.DataFrame) -> pd.Series:
        life = g["raw_survival_days_60"].astype(float)
        return pd.Series({
            "n": len(g),
            "median_raw_life": float(life.median()),
            "mean_raw_life": float(life.mean()),
            "survive_5_rate": float((life >= 5).mean()),
            "survive_10_rate": float((life >= 10).mean()),
            "survive_20_rate": float((life >= 20).mean()),
            "median_tradable_life": float(g["tradable_survival_days_60"].median()),
            "median_days_to_dd3": float(g["days_to_dd3_60"].median()),
            "mean_fwd5": float(g["fwd5"].mean()),
            "mean_fwd10": float(g["fwd10"].mean()),
            "mean_fwd20": float(g["fwd20"].mean()),
            "mean_fwd40": float(g["fwd40"].mean()),
        })
    return df.groupby(group_cols, dropna=False).apply(agg, include_groups=False).reset_index()


def add_all_period(df: pd.DataFrame) -> pd.DataFrame:
    all_copy = df.copy()
    all_copy["period"] = "ALL"
    return pd.concat([df, all_copy], ignore_index=True)


def build_quintiles(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    base = events.loc[events["detection_type"].isin(["tradable_start", "leader10_start"])].copy()
    base = add_all_period(base)
    for (dtype, period), g in base.groupby(["detection_type", "period"]):
        for feature in FEATURES:
            x = pd.to_numeric(g[feature], errors="coerce")
            valid = g.loc[x.notna()].copy()
            if len(valid) < 100 or x.dropna().nunique() < 5:
                continue
            try:
                valid["q"] = pd.qcut(pd.to_numeric(valid[feature], errors="coerce"), 5,
                                     labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
            except ValueError:
                continue
            if valid["q"].nunique() < 4:
                continue
            for q, qg in valid.groupby("q", observed=True):
                rows.append({
                    "detection_type": dtype,
                    "period": period,
                    "feature": feature,
                    "quintile": str(q),
                    "n": len(qg),
                    "feature_median": float(pd.to_numeric(qg[feature], errors="coerce").median()),
                    "median_raw_life": float(qg["raw_survival_days_60"].median()),
                    "survive_10_rate": float((qg["raw_survival_days_60"] >= 10).mean()),
                    "mean_fwd20": float(qg["fwd20"].mean()),
                })
    return pd.DataFrame(rows)


def build_correlations(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    base = events.loc[events["detection_type"].isin(["tradable_start", "leader10_start"])].copy()
    base = add_all_period(base)
    for (dtype, period), g in base.groupby(["detection_type", "period"]):
        for feature in FEATURES:
            for target in ("raw_survival_days_60", "fwd20"):
                pair = g[[feature, target]].apply(pd.to_numeric, errors="coerce").dropna()
                if len(pair) < 100 or pair[feature].nunique() < 3:
                    continue
                rho, p = spearmanr(pair[feature], pair[target])
                rows.append({
                    "detection_type": dtype,
                    "period": period,
                    "feature": feature,
                    "target": target,
                    "n": len(pair),
                    "spearman_rho": float(rho),
                    "p_value": float(p),
                })
    return pd.DataFrame(rows)


def fmt_pct(x: Any) -> str:
    try:
        return f"{float(x) * 100:.2f}%"
    except Exception:
        return "NA"


def md_table(df: pd.DataFrame, cols: list[str], formats: dict[str, Any] | None = None) -> str:
    formats = formats or {}
    if df.empty:
        return "(no rows)"
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for col in cols:
            val = row[col]
            if col in formats:
                val = formats[col](val)
            elif isinstance(val, (float, np.floating)):
                val = f"{float(val):.4f}"
            vals.append(str(val).replace("|", "/"))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def build_report(data_asof: str, events: pd.DataFrame, detection_summary: pd.DataFrame,
                 asset_summary: pd.DataFrame, symbol_summary: pd.DataFrame,
                 correlations: pd.DataFrame) -> str:
    complete = events.loc[events["label_complete_60"]].copy()
    ds = detection_summary.loc[detection_summary["period"] == "ALL"].copy()
    ds = ds.sort_values("detection_type")

    leader_period = detection_summary.loc[detection_summary["detection_type"] == "leader10_start"].copy()
    leader_period = leader_period.sort_values("period")

    assets = asset_summary.loc[
        (asset_summary["detection_type"] == "leader10_start") &
        (asset_summary["period"] == "ALL") &
        (asset_summary["n"] >= 20)
    ].sort_values(["median_raw_life", "n"], ascending=[False, False]).head(12)

    symbols = symbol_summary.loc[
        (symbol_summary["detection_type"] == "leader10_start") &
        (symbol_summary["period"] == "ALL") &
        (symbol_summary["n"] >= 5)
    ].sort_values(["median_raw_life", "n"], ascending=[False, False]).head(15)

    corr = correlations.loc[
        (correlations["detection_type"] == "leader10_start") &
        (correlations["period"] == "ALL") &
        (correlations["target"] == "raw_survival_days_60")
    ].copy()
    corr["abs_rho"] = corr["spearman_rho"].abs()
    corr = corr.sort_values("abs_rho", ascending=False).head(15)

    lines = [
        "# Post-OLS Remaining Trend Life — V1 Stage 1 Report",
        "",
        f"- Data as of: `{data_asof}`",
        f"- Complete 60-session labelled events: `{len(complete)}`",
        f"- Code SHA: `{os.getenv('GITHUB_SHA', 'local')}`",
        "- Status: descriptive diagnostic only; no trading rule is approved by this report.",
        "",
        "## Detection timing comparison",
        "",
        md_table(ds, ["detection_type", "n", "median_raw_life", "survive_10_rate", "mean_fwd20"], {
            "survive_10_rate": fmt_pct, "mean_fwd20": fmt_pct,
        }),
        "",
        "## Leader10 period stability",
        "",
        md_table(leader_period, ["period", "n", "median_raw_life", "survive_10_rate", "mean_fwd20"], {
            "survive_10_rate": fmt_pct, "mean_fwd20": fmt_pct,
        }),
        "",
        "## Asset-class description at first Leader10 detection",
        "",
        "Only classes with at least 20 complete events are shown. This is descriptive and must not be used as a selection rule without walk-forward validation.",
        "",
        md_table(assets, ["asset_class", "n", "median_raw_life", "survive_10_rate", "mean_fwd20"], {
            "survive_10_rate": fmt_pct, "mean_fwd20": fmt_pct,
        }),
        "",
        "## ETF-level description at first Leader10 detection",
        "",
        "Only symbols with at least 5 complete events are shown. This table is explicitly *not* an ex-ante universe recommendation.",
        "",
        md_table(symbols, ["symbol", "name", "n", "median_raw_life", "survive_10_rate", "mean_fwd20"], {
            "survive_10_rate": fmt_pct, "mean_fwd20": fmt_pct,
        }),
        "",
        "## Strongest univariate associations with remaining raw OLS life",
        "",
        md_table(corr, ["feature", "n", "spearman_rho", "p_value"]),
        "",
        "## Interpretation guardrails",
        "",
        "1. High ETF/class historical medians are descriptive evidence, not a rule.",
        "2. Candidate features must keep the same direction in 2021–2024 and 2025–2026 before Stage 2 can promote them.",
        "3. The next stage must use walk-forward/monthly freezing before any comparison against the fixed-pool benchmark.",
        "4. V1 does not tune thresholds from these outcomes.",
        "",
    ]
    return "\n".join(lines)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_outputs(paths: list[Path], args: argparse.Namespace, prefix: str) -> list[dict[str, Any]]:
    required = [args.s3_endpoint, args.s3_access_key, args.s3_secret_key, args.bucket]
    if any(not x for x in required):
        raise RuntimeError("Supabase Storage S3 configuration is incomplete")
    s3 = boto3.client(
        "s3", endpoint_url=args.s3_endpoint, region_name=args.s3_region,
        aws_access_key_id=args.s3_access_key, aws_secret_access_key=args.s3_secret_key,
    )
    uploaded = []
    for path in paths:
        size = path.stat().st_size
        if size > 49 * 1024 * 1024:
            raise RuntimeError(f"Output exceeds safe 49 MB object size: {path} ({size})")
        key = f"{prefix}/{path.name}"
        s3.upload_file(str(path), args.bucket, key)
        uploaded.append({"file": path.name, "key": key, "bytes": size, "sha256": sha256(path)})
    return uploaded


def jsonable(obj: Any) -> Any:
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    raise TypeError(type(obj).__name__)


def main() -> None:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    data_asof = pd.to_datetime(bars["date"]).max().date().isoformat()
    features = build_features(bars)
    assert_ols_calibration(features)
    meta = load_metadata(engine)
    contextual = add_context(features, meta)
    events = build_events(contextual)

    complete = events.loc[events["label_complete_60"]].copy()
    if complete.empty:
        raise RuntimeError("No events have complete 60-session labels")

    det_base = add_all_period(complete)
    detection_summary = summarize_group(det_base, ["detection_type", "period"])

    class_base = complete.loc[complete["historical_safe"].fillna(False).astype(bool)].copy()
    class_base = add_all_period(class_base)
    asset_summary = summarize_group(class_base, ["detection_type", "period", "asset_class"])

    sym_base = add_all_period(complete)
    symbol_summary = summarize_group(sym_base, ["detection_type", "period", "symbol", "name"])

    quintiles = build_quintiles(complete)
    correlations = build_correlations(complete)

    outputs = {
        "events_v1.parquet": events,
        "detection_summary_v1.parquet": detection_summary,
        "asset_class_summary_v1.parquet": asset_summary,
        "symbol_summary_v1.parquet": symbol_summary,
        "feature_quintiles_v1.parquet": quintiles,
        "feature_correlations_v1.parquet": correlations,
    }
    written: list[Path] = []
    for filename, df in outputs.items():
        path = args.output_dir / filename
        df.to_parquet(path, index=False, compression="zstd")
        written.append(path)

    report = build_report(data_asof, events, detection_summary, asset_summary, symbol_summary, correlations)
    report_path = args.output_dir / "report_v1.md"
    report_path.write_text(report, encoding="utf-8")
    written.append(report_path)

    prefix = f"post_ols_life/{STUDY_VERSION}/asof={data_asof}"
    uploaded = upload_outputs(written, args, prefix)

    summary = {
        "study_version": STUDY_VERSION,
        "data_asof": data_asof,
        "code_sha": os.getenv("GITHUB_SHA", "local"),
        "events_all": int(len(events)),
        "events_complete60": int(len(complete)),
        "events_by_detection": {str(k): int(v) for k, v in events.groupby("detection_type").size().items()},
        "complete_by_detection": {str(k): int(v) for k, v in complete.groupby("detection_type").size().items()},
        "storage_bucket": args.bucket,
        "storage_prefix": prefix,
        "uploaded": uploaded,
        "ols_calibration_passed": True,
        "rules_frozen_in": "research/post_ols_life/README.md",
    }
    summary_path_local = args.output_dir / "summary_v1.json"
    summary_path_local.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=jsonable), encoding="utf-8")
    # Upload summary after it contains the manifest of the other durable outputs.
    summary_uploaded = upload_outputs([summary_path_local], args, prefix)
    summary["uploaded"].extend(summary_uploaded)
    args.summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=jsonable), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=jsonable))


if __name__ == "__main__":
    main()
