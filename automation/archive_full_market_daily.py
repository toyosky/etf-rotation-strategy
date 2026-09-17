#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import os
from datetime import datetime, timezone

import boto3
import pandas as pd
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text

DB_ENV = "ETF_DAILY_BARS_DATABASE_URL"
S3_ENDPOINT = os.getenv("SUPABASE_STORAGE_S3_ENDPOINT", "https://gsyziuzezmmnvgdoazkg.storage.supabase.co/storage/v1/s3")
S3_REGION = os.getenv("SUPABASE_STORAGE_S3_REGION", "ap-southeast-1")
S3_ACCESS = os.getenv("SUPABASE_STORAGE_S3_ACCESS_KEY_ID")
S3_SECRET = os.getenv("SUPABASE_STORAGE_S3_SECRET_ACCESS_KEY")
BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "etf-research-archive")
PREFIX = "raw_daily_bars/frozen_20260917"
SUMMARY_PATH = "full-market-daily-archive-summary.json"


def db_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://") and "+psycopg2" not in raw:
        raw = "postgresql+psycopg2://" + raw[len("postgresql://"):]
    return raw


def ensure_bucket(s3) -> None:
    try:
        s3.head_bucket(Bucket=BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=BUCKET)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    raw_db = os.getenv(DB_ENV, "").strip()
    if not raw_db:
        raise RuntimeError(f"{DB_ENV} is not set")
    if not S3_ACCESS or not S3_SECRET:
        raise RuntimeError("Supabase Storage S3 credentials are not set")

    engine = create_engine(db_url(raw_db), pool_pre_ping=True)
    sql = text("""
        select symbol, date, open, high, low, close, volume, amount,
               instrument_type, ingested_on
        from public.daily_bars
        order by date, symbol
    """)
    df = pd.read_sql_query(sql, engine, parse_dates=["date", "ingested_on"])
    if df.empty:
        raise RuntimeError("public.daily_bars is empty")

    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    expected_rows = int(len(df))
    expected_symbols = int(df["symbol"].nunique())
    min_date = str(df["date"].min().date())
    max_date = str(df["date"].max().date())

    if expected_rows < 1_000_000 or expected_symbols < 1000:
        raise RuntimeError(
            f"Refusing archive: source unexpectedly small rows={expected_rows} symbols={expected_symbols}"
        )

    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name=S3_REGION,
        aws_access_key_id=S3_ACCESS,
        aws_secret_access_key=S3_SECRET,
    )
    ensure_bucket(s3)

    objects = []
    archived_rows = 0
    for year, part in df.groupby(df["date"].dt.year, sort=True):
        part = part.reset_index(drop=True)
        buf = io.BytesIO()
        part.to_parquet(buf, index=False, compression="zstd", engine="pyarrow")
        payload = buf.getvalue()
        key = f"{PREFIX}/year={int(year)}/daily_bars.parquet"
        digest = sha256_bytes(payload)
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=payload,
            ContentType="application/octet-stream",
            Metadata={"sha256": digest, "rows": str(len(part))},
        )
        head = s3.head_object(Bucket=BUCKET, Key=key)
        if int(head.get("ContentLength", -1)) != len(payload):
            raise RuntimeError(f"Storage size verification failed for {key}")
        if (head.get("Metadata") or {}).get("sha256") != digest:
            raise RuntimeError(f"Storage hash metadata verification failed for {key}")
        archived_rows += int(len(part))
        objects.append({
            "year": int(year),
            "key": key,
            "rows": int(len(part)),
            "bytes": len(payload),
            "sha256": digest,
            "min_date": str(part["date"].min().date()),
            "max_date": str(part["date"].max().date()),
        })

    if archived_rows != expected_rows:
        raise RuntimeError(f"Row-count mismatch source={expected_rows} archive={archived_rows}")

    symbol_counts = (
        df.groupby("symbol", sort=True).size().rename("rows").reset_index().to_dict("records")
    )
    manifest = {
        "archive_version": 1,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "source": "public.daily_bars",
        "source_rows": expected_rows,
        "source_symbols": expected_symbols,
        "source_min_date": min_date,
        "source_max_date": max_date,
        "columns": list(df.columns),
        "objects": objects,
        "archived_rows_verified": archived_rows,
        "symbol_counts": symbol_counts,
        "restore_note": "Concatenate yearly parquet partitions and upsert by (symbol,date). This archive is the pre-production-shrink full-market raw daily-bar snapshot.",
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    manifest_key = f"{PREFIX}/manifest.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=manifest_key,
        Body=manifest_bytes,
        ContentType="application/json; charset=utf-8",
        Metadata={"sha256": sha256_bytes(manifest_bytes), "rows": str(expected_rows)},
    )
    head = s3.head_object(Bucket=BUCKET, Key=manifest_key)
    if int(head.get("ContentLength", -1)) != len(manifest_bytes):
        raise RuntimeError("Manifest storage verification failed")

    summary = {
        "status": "PASS",
        "bucket": BUCKET,
        "prefix": PREFIX,
        "manifest_key": manifest_key,
        "source_rows": expected_rows,
        "source_symbols": expected_symbols,
        "source_min_date": min_date,
        "source_max_date": max_date,
        "partition_count": len(objects),
        "archive_rows_verified": archived_rows,
        "archive_bytes": int(sum(x["bytes"] for x in objects) + len(manifest_bytes)),
    }
    with open(SUMMARY_PATH, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
