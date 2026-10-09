#!/usr/bin/env python3
"""Incrementally upsert Tencent HFQ ETF/LOF daily bars into Supabase."""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import execute_values


PACKAGE = "westock-data-skillhub@1.0.5"
SOURCE = "tencent_westockdata"
ADJUSTMENT = "hfq"
SHANGHAI = ZoneInfo("Asia/Shanghai")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", type=Path, default=Path(__file__).with_name("tencent_daily_universe.csv"))
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(SHANGHAI).date())
    parser.add_argument("--lookback-days", type=int, default=14)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--summary", type=Path, default=Path("tencent-daily-sync-summary.json"))
    return parser.parse_args()


def load_universe(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"symbol", "name", "tencent_symbol", "instrument_type"}
    if not rows or required - set(rows[0]):
        raise ValueError(f"Universe must contain {sorted(required)}")
    seen: set[str] = set()
    for row in rows:
        symbol = row["symbol"].zfill(6)
        if symbol in seen or len(symbol) != 6 or not symbol.isdigit():
            raise ValueError(f"Invalid or duplicate symbol: {symbol}")
        if row["instrument_type"] not in {"ETF", "LOF"}:
            raise ValueError(f"Invalid instrument type for {symbol}")
        if not row["tencent_symbol"].endswith(symbol):
            raise ValueError(f"Tencent code mismatch for {symbol}")
        row["symbol"] = symbol
        seen.add(symbol)
    return rows


def run_westock(codes: list[str], start: date, end: date, attempts: int) -> Any:
    npx = shutil.which("npx")
    if not npx:
        raise RuntimeError("npx is unavailable")
    command = [
        npx, "-y", PACKAGE, "kline", ",".join(codes),
        "--period", "day", "--start", start.isoformat(), "--end", end.isoformat(),
        "--fq", ADJUSTMENT, "--raw",
    ]
    error = ""
    for attempt in range(attempts):
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        try:
            payload = json.loads(result.stdout) if result.stdout.strip() else None
        except json.JSONDecodeError as exc:
            payload = None
            error = f"invalid JSON: {exc}"
        if result.returncode == 0 and payload is not None:
            if not (isinstance(payload, dict) and payload.get("success") is False):
                return payload
            error = str(payload.get("error") or payload)
        else:
            error = (result.stderr or error or result.stdout)[-1000:]
        if attempt + 1 < attempts:
            time.sleep(min(2**attempt, 10))
    raise RuntimeError(error or "westockdata request failed")


def payload_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get("data", [])
    return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


def normalize(payload: Any, requested: list[str], types: dict[str, str], run_date: date) -> list[tuple[Any, ...]]:
    raw = payload_rows(payload)
    if len(requested) == 1:
        for row in raw:
            row.setdefault("symbol", requested[0])
    output: dict[tuple[str, date], tuple[Any, ...]] = {}
    for row in raw:
        symbol = str(row.get("symbol", ""))[-6:]
        if symbol not in types:
            continue
        try:
            bar_date = date.fromisoformat(str(row["date"])[:10])
            open_, high, low = (float(row[key]) for key in ("open", "high", "low"))
            close = float(row.get("last", row.get("close")))
            volume_lots = float(row["volume"])
            amount = float(row["amount"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Malformed Tencent row for {symbol}: {exc}") from exc
        if min(open_, high, low, close) <= 0 or volume_lots < 0 or amount < 0:
            raise ValueError(f"Invalid non-positive/negative OHLCV for {symbol} {bar_date}")
        if high < max(open_, low, close) or low > min(open_, high, close):
            raise ValueError(f"Invalid OHLC ordering for {symbol} {bar_date}")
        output[(symbol, bar_date)] = (
            symbol, bar_date, open_, high, low, close, volume_lots * 100.0, amount,
            types[symbol], run_date,
        )
    return list(output.values())


def fetch_batch(rows: list[dict[str, str]], start: date, end: date, attempts: int) -> tuple[list[tuple[Any, ...]], list[str]]:
    codes = [row["tencent_symbol"] for row in rows]
    types = {row["symbol"]: row["instrument_type"] for row in rows}
    bars = normalize(run_westock(codes, start, end, attempts), codes, types, end)
    received = {bar[0] for bar in bars}
    missing = [row for row in rows if row["symbol"] not in received]
    still_missing: list[str] = []
    for row in missing:
        single = normalize(run_westock([row["tencent_symbol"]], start, end, attempts), [row["tencent_symbol"]], types, end)
        if single:
            bars.extend(single)
        else:
            still_missing.append(row["symbol"])
    return list({(bar[0], bar[1]): bar for bar in bars}.values()), still_missing


def database_url() -> str:
    value = os.environ.get("ETF_DAILY_BARS_DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("ETF_DAILY_BARS_DATABASE_URL is not set")
    return value


def upsert(conn: Any, bars: list[tuple[Any, ...]]) -> None:
    sql = """
        INSERT INTO public.daily_bars
          (symbol,date,open,high,low,close,volume,amount,instrument_type,ingested_on)
        VALUES %s
        ON CONFLICT (symbol,date) DO UPDATE SET
          open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close,
          volume=EXCLUDED.volume, amount=EXCLUDED.amount,
          instrument_type=EXCLUDED.instrument_type, ingested_on=EXCLUDED.ingested_on
    """
    with conn.cursor() as cursor:
        execute_values(cursor, sql, bars, page_size=2000)


def main() -> None:
    args = parse_args()
    if args.lookback_days < 3 or args.batch_size < 1 or args.workers < 1:
        raise ValueError("Invalid lookback/batch/worker setting")
    universe = load_universe(args.universe)
    start = args.as_of - timedelta(days=args.lookback_days)
    # First-time symbols get full backfill; existing symbols get rolling refresh.
    with psycopg2.connect(database_url(), connect_timeout=30) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT symbol FROM public.daily_bars WHERE symbol = ANY(%s)",
                           ([row["symbol"] for row in universe],))
            present = {row[0] for row in cursor.fetchall()}
    bootstrap = [row for row in universe if row["symbol"] not in present]
    routine = [row for row in universe if row["symbol"] in present]
    batches = [(routine[i:i + args.batch_size], start)
               for i in range(0, len(routine), args.batch_size)]
    bootstrap_start = args.as_of - timedelta(days=1095)
    batches.extend((bootstrap[i:i + args.batch_size], bootstrap_start)
                   for i in range(0, len(bootstrap), args.batch_size))
    print(f"bootstrap symbols: {[row['symbol'] for row in bootstrap]}", flush=True)
    bars: list[tuple[Any, ...]] = []
    missing: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch_batch, batch, window_start, args.as_of, args.max_attempts) for batch, window_start in batches]
        for done, future in enumerate(as_completed(futures), 1):
            fetched, absent = future.result()
            bars.extend(fetched)
            missing.extend(absent)
            print(f"completed fetch batch {done}/{len(futures)}: {len(fetched)} rows", flush=True)
    bars = list({(bar[0], bar[1]): bar for bar in bars}.values())
    if not bars:
        raise RuntimeError("Tencent returned no valid bars")

    symbols = [row["symbol"] for row in universe]
    with psycopg2.connect(database_url(), connect_timeout=30, application_name="github_tencent_daily_sync") as conn:
        upsert(conn, bars)
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT symbol,max(date) FROM public.daily_bars WHERE symbol = ANY(%s) GROUP BY symbol",
                (symbols,),
            )
            latest = dict(cursor.fetchall())
        stale = sorted(symbol for symbol in symbols if symbol not in latest or (args.as_of - latest[symbol]).days > 7)
        if stale:
            raise RuntimeError(f"{len(stale)} universe symbols are stale by more than 7 days: {stale[:20]}")

    counts: dict[str, int] = {}
    for bar in bars:
        counts[bar[0]] = counts.get(bar[0], 0) + 1
    summary = {
        "status": "PASS", "as_of": args.as_of.isoformat(), "fetch_start": start.isoformat(),
        "universe_symbols": len(universe), "upsert_rows": len(bars), "updated_symbols": len(counts),
        "no_rows_in_window": sorted(set(missing)), "source": SOURCE, "adjustment": ADJUSTMENT,
        "storage_schema": "compact_v1", "bootstrap_symbols": [row["symbol"] for row in bootstrap],
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
