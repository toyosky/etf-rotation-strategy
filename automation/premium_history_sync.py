#!/usr/bin/env python3
"""Sync ETF/LOF unit-NAV premium history into Supabase.

Historical backfill:
- Eastmoney/AKShare unit NAV + same-day unadjusted exchange close.
- first_seen_at is intentionally NULL because historical publication timing is unknown.
- pit_safe=False.

Forward pre-open collection:
- Records the first time a NAV row is actually observed by this job.
- first_seen_at can then be compared with a strategy decision timestamp.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import MetaData, Table

# Workflow trigger/version: v1
DB_ENV = "ETF_DAILY_BARS_DATABASE_URL"
TABLE = "fund_premium_history"
UNIVERSE_PATH = Path(__file__).with_name("tencent_daily_universe.csv")

# Routine coverage comes from the universe CSV; signal-driven funds are added
# dynamically, including newly listed ETFs/LOFs not present in that file.
DEFAULT_EXCLUDED = {"511220", "510300"}  # cash carrier and benchmark only

TENCENT_KLINE_PACKAGE = "westock-data-skillhub@1.0.5"
TENCENT_NAV_PACKAGE = "westock-data-skillhub@1.0.3"


def tencent_code(symbol: str) -> str:
    return ("sh" if symbol.startswith(("5", "6")) else "sz") + symbol


def run_westock(package: str, args: list[str], raw: bool = False, attempts: int = 3) -> str:
    npx = shutil.which("npx")
    if not npx:
        raise RuntimeError("npx is unavailable")
    cmd = [npx, "-y", package, *args]
    if raw:
        cmd.append("--raw")
    last_error = ""
    for attempt in range(attempts):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=180
            )
        except subprocess.TimeoutExpired as exc:
            last_error = f"timeout: {exc}"
        else:
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
            last_error = (result.stderr or result.stdout or "westock failed")[-1200:]
        if attempt + 1 < attempts:
            time.sleep(min(2 ** attempt, 5))
    raise RuntimeError(last_error or "westockdata request failed")


def tencent_nav_fallback(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Best-effort fallback for ETFs supported by Tencent's etf-nav command."""
    try:
        output = run_westock(
            TENCENT_NAV_PACKAGE,
            [
                "etf-nav", tencent_code(symbol),
                "--start", pd.to_datetime(start_date).date().isoformat(),
                "--end", pd.to_datetime(end_date).date().isoformat(),
            ],
            raw=False,
            attempts=2,
        )
    except Exception:
        return pd.DataFrame()

    rows = []
    for line in output.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        parts = [x.strip() for x in line.strip("|").split("|")]
        if len(parts) < 2:
            continue
        dt = pd.to_datetime(parts[0], errors="coerce")
        nav = pd.to_numeric(parts[1], errors="coerce")
        if pd.isna(dt) or pd.isna(nav) or float(nav) <= 0:
            continue
        rows.append({
            "nav_date": dt.date(),
            "unit_nav": float(nav),
            "cumulative_nav": None,
            "nav_daily_growth_pct": None,
            "subscription_status": None,
            "redemption_status": None,
        })
    return pd.DataFrame(rows).sort_values("nav_date").drop_duplicates("nav_date", keep="last") if rows else pd.DataFrame()


def db_url() -> str:
    value = os.getenv(DB_ENV)
    if not value:
        raise RuntimeError(f"Missing {DB_ENV}")
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://"):]
    if value.startswith("postgresql://"):
        value = "postgresql+psycopg2://" + value[len("postgresql://"):]
    return value


def normalize_symbols(values) -> set[str]:
    selected = set()
    for value in values:
        if value is None or str(value).upper() in {"", "CASH", "NONE"}:
            continue
        symbol = str(value).strip()
        if not re.fullmatch(r"[0-9]{6}", symbol):
            raise ValueError(f"Invalid ETF/LOF symbol: {symbol!r}")
        selected.add(symbol)
    return selected


def read_signal_symbols(path: str) -> set[str]:
    if not path:
        return set()
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    target = report.get("next_strategy_target") or {}
    holding = report.get("current_holding") or {}
    values = [target.get("model_target"), target.get("symbol"),
              target.get("holding_target"), holding.get("symbol")]
    if isinstance(holding.get("symbols"), list):
        values.extend(item.get("symbol") if isinstance(item, dict) else item
                      for item in holding["symbols"])
    return normalize_symbols(values)


def load_universe(engine, selected: set[str] | None = None, only_selected=False) -> list[dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    with UNIVERSE_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            symbol = str(row["symbol"]).zfill(6)
            if (row.get("instrument_type") or "ETF").upper() not in ("ETF", "LOF"):
                continue
            if only_selected and symbol not in (selected or set()):
                continue
            if not only_selected and symbol in DEFAULT_EXCLUDED and symbol not in (selected or set()):
                continue
            records[symbol] = {
                "symbol": symbol, "name": row.get("name", ""),
                "instrument_type": (row.get("instrument_type") or "ETF").upper()
            }
    missing = (selected or set()) - set(records)
    if missing:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT symbol, name, product_type
                FROM public.instrument_metadata
                WHERE symbol = ANY(:symbols) AND product_type IN ('ETF', 'LOF')
                      AND current_exchange_listed IS TRUE
            """), {"symbols": sorted(missing)}).mappings().all()
        for row in rows:
            sym = str(row["symbol"]).zfill(6)
            records[sym] = {"symbol": sym, "name": str(row["name"] or ""),
                            "instrument_type": str(row["product_type"])}
    unresolved = (selected or set()) - set(records)
    if unresolved:
        raise RuntimeError(f"Unlisted or unsupported ETF/LOF symbols: {sorted(unresolved)}")
    # Prioritize currently actionable symbols; there is no asset-specific rule.
    return sorted(records.values(),
                  key=lambda rec: (rec["symbol"] not in (selected or set()), rec["symbol"]))


def _col(df: pd.DataFrame, names: list[str]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def fetch_nav(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch unit-NAV history directly from Eastmoney with bounded retries/timeouts.

    AKShare's fund_etf_fund_info_em currently paginates at 20 rows per request
    without an explicit timeout. That is unnecessarily slow for multi-year,
    multi-symbol backfills and makes CI more vulnerable to transient Eastmoney
    throttling. This uses the same public Eastmoney endpoint with larger pages.
    """
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
        ),
        "Referer": f"https://fundf10.eastmoney.com/jjjz_{symbol}.html",
    }
    page_size = 200
    params = {
        "fundCode": symbol,
        "pageIndex": 1,
        "pageSize": page_size,
        "startDate": f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}",
        "endDate": f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}",
    }

    session = requests.Session()

    def get_page(page: int) -> dict:
        last_exc: Exception | None = None
        for attempt in range(5):
            try:
                params["pageIndex"] = page
                params["_"] = int(time.time() * 1000)
                resp = session.get(url, params=params, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    raise ValueError("Eastmoney NAV response is not a JSON object")
                return data
            except Exception as exc:
                last_exc = exc
                if attempt < 4:
                    time.sleep(min(2.0 * (attempt + 1), 8.0))
        assert last_exc is not None
        raise last_exc

    try:
        first = get_page(1)
    except Exception:
        fallback = tencent_nav_fallback(symbol, start_date, end_date)
        if not fallback.empty:
            return fallback
        raise
    total = int(first.get("TotalCount") or 0)
    data_block = first.get("Data") or {}
    first_rows = data_block.get("LSJZList") or []
    if total <= 0 or not first_rows:
        return pd.DataFrame()

    pages = max(1, math.ceil(total / page_size))
    rows = list(first_rows)
    for page in range(2, pages + 1):
        data = get_page(page)
        block = data.get("Data") or {}
        rows.extend(block.get("LSJZList") or [])
        time.sleep(0.15)

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()

    rename = {
        "FSRQ": "净值日期",
        "DWJZ": "单位净值",
        "LJJZ": "累计净值",
        "JZZZL": "日增长率",
        "SGZT": "申购状态",
        "SHZT": "赎回状态",
    }
    df = df.rename(columns=rename)
    date_col = _col(df, ["净值日期", "日期"])
    nav_col = _col(df, ["单位净值"])
    if not date_col or not nav_col:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["nav_date"] = pd.to_datetime(df[date_col], errors="coerce").dt.date
    out["unit_nav"] = pd.to_numeric(df[nav_col], errors="coerce")

    cum_col = _col(df, ["累计净值"])
    growth_col = _col(df, ["日增长率"])
    sub_col = _col(df, ["申购状态"])
    red_col = _col(df, ["赎回状态"])

    out["cumulative_nav"] = pd.to_numeric(df[cum_col], errors="coerce") if cum_col else None
    out["nav_daily_growth_pct"] = pd.to_numeric(df[growth_col], errors="coerce") if growth_col else None
    out["subscription_status"] = df[sub_col].astype(str) if sub_col else None
    out["redemption_status"] = df[red_col].astype(str) if red_col else None

    start = pd.to_datetime(start_date).date()
    end = pd.to_datetime(end_date).date()
    out = out[(out["nav_date"] >= start) & (out["nav_date"] <= end)]
    out = out.dropna(subset=["nav_date", "unit_nav"])
    out = out[out["unit_nav"] > 0]
    return out.sort_values("nav_date").drop_duplicates("nav_date", keep="last")

def fetch_eastmoney_unadjusted_price(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fallback: fetch unadjusted daily closes directly from Eastmoney."""
    secid = ("1." if symbol.startswith(("5", "6")) else "0.") + symbol
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "klt": "101",
        "fqt": "0",
        "beg": pd.to_datetime(start_date).strftime("%Y%m%d"),
        "end": pd.to_datetime(end_date).strftime("%Y%m%d"),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://quote.eastmoney.com/",
    }
    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            klines = (data or {}).get("klines") or []
            rows = []
            for line in klines:
                parts = str(line).split(",")
                if len(parts) < 3:
                    continue
                rows.append({"nav_date": parts[0], "market_close": parts[2]})
            out = pd.DataFrame(rows)
            if out.empty:
                raise RuntimeError(f"Eastmoney BFQ returned no rows for {symbol}")
            out["nav_date"] = pd.to_datetime(out["nav_date"], errors="coerce").dt.date
            out["market_close"] = pd.to_numeric(out["market_close"], errors="coerce")
            out = out.dropna(subset=["nav_date", "market_close"])
            out = out[out["market_close"] > 0]
            out = out.sort_values("nav_date").drop_duplicates("nav_date", keep="last")
            if out.empty:
                raise RuntimeError(f"Eastmoney BFQ normalized to no rows for {symbol}")
            out.attrs["source_price"] = "eastmoney_push2his_bfq"
            return out
        except Exception as exc:
            last_exc = exc
            if attempt < 4:
                time.sleep(min(2.0 * (attempt + 1), 8.0))
    assert last_exc is not None
    raise last_exc


def fetch_unadjusted_price(symbol: str, instrument_type: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch unadjusted daily closes, preferring Tencent with Eastmoney fallback."""
    tencent_error: Exception | None = None
    try:
        output = run_westock(
            TENCENT_KLINE_PACKAGE,
            [
                "kline", tencent_code(symbol),
                "--period", "day",
                "--start", pd.to_datetime(start_date).date().isoformat(),
                "--end", pd.to_datetime(end_date).date().isoformat(),
                "--fq", "bfq",
            ],
            raw=True,
            attempts=4,
        )
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Tencent BFQ returned invalid JSON: {exc}; tail={output[-600:]}") from exc
        raw_rows = payload.get("data", []) if isinstance(payload, dict) else payload
        if not isinstance(raw_rows, list):
            raw_rows = []
        rows = []
        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            bar_date = row.get("date")
            close = row.get("last", row.get("close"))
            if bar_date is None or close is None:
                continue
            rows.append({"nav_date": bar_date, "market_close": close})
        out = pd.DataFrame(rows)
        if not out.empty:
            out["nav_date"] = pd.to_datetime(out["nav_date"], errors="coerce").dt.date
            out["market_close"] = pd.to_numeric(out["market_close"], errors="coerce")
            out = out.dropna(subset=["nav_date", "market_close"])
            out = out[out["market_close"] > 0]
            out = out.sort_values("nav_date").drop_duplicates("nav_date", keep="last")
        if not out.empty:
            out.attrs["source_price"] = "tencent_westock_bfq"
            return out
        tencent_error = RuntimeError(f"Tencent BFQ returned no usable rows for {symbol}")
    except Exception as exc:
        tencent_error = exc

    try:
        return fetch_eastmoney_unadjusted_price(symbol, start_date, end_date)
    except Exception as eastmoney_error:
        raise RuntimeError(
            f"Both BFQ sources failed for {symbol}; "
            f"Tencent={type(tencent_error).__name__}: {tencent_error}; "
            f"Eastmoney={type(eastmoney_error).__name__}: {eastmoney_error}"
        ) from eastmoney_error

def build_rows(meta: dict[str, str], start_date: str, end_date: str, phase: str) -> list[dict]:
    symbol = meta["symbol"]
    nav = fetch_nav(symbol, start_date, end_date)
    if nav.empty:
        raise RuntimeError(f"No NAV rows returned for {symbol}")
    px = fetch_unadjusted_price(symbol, meta["instrument_type"], start_date, end_date)
    if px.empty:
        raise RuntimeError(f"No BFQ price rows returned for {symbol}; nav_rows={len(nav)}")
    price_source = px.attrs.get("source_price", "unknown_bfq")
    merged = nav.merge(px, on="nav_date", how="inner")
    if merged.empty:
        raise RuntimeError(
            f"NAV/price date intersection empty for {symbol}; "
            f"nav={nav['nav_date'].min()}..{nav['nav_date'].max()} ({len(nav)}), "
            f"px={px['nav_date'].min()}..{px['nav_date'].max()} ({len(px)})"
        )

    now = datetime.now(timezone.utc)
    live_observation = phase == "preopen"
    rows = []
    for x in merged.to_dict("records"):
        unit_nav = float(x["unit_nav"])
        market_close = float(x["market_close"])
        premium = market_close / unit_nav - 1.0
        rows.append({
            "symbol": symbol,
            "nav_date": x["nav_date"],
            "unit_nav": unit_nav,
            "cumulative_nav": None if pd.isna(x.get("cumulative_nav")) else float(x["cumulative_nav"]),
            "market_close": market_close,
            "premium": premium,
            "nav_daily_growth_pct": None if pd.isna(x.get("nav_daily_growth_pct")) else float(x["nav_daily_growth_pct"]),
            "subscription_status": None if pd.isna(x.get("subscription_status")) else str(x.get("subscription_status")),
            "redemption_status": None if pd.isna(x.get("redemption_status")) else str(x.get("redemption_status")),
            "source_nav": "eastmoney_direct_or_tencent_fallback",
            "source_price": price_source,
            # Prior NAV dates are backfilled today, NOT point-in-time safe on their NAV date.
            "first_seen_at": now if live_observation else None,
            "first_seen_phase": "sync_observed" if live_observation else None,
            "pit_safe": False,
            "backfilled": True,
            "updated_at": now,
        })
    return rows


def upsert_rows(engine, rows: list[dict]) -> int:
    if not rows:
        return 0
    md = MetaData()
    table = Table(TABLE, md, schema="public", autoload_with=engine)
    stmt = insert(table).values(rows)
    ex = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=[table.c.symbol, table.c.nav_date],
        set_={
            "unit_nav": ex.unit_nav,
            "cumulative_nav": ex.cumulative_nav,
            "market_close": ex.market_close,
            "premium": ex.premium,
            "nav_daily_growth_pct": ex.nav_daily_growth_pct,
            "subscription_status": ex.subscription_status,
            "redemption_status": ex.redemption_status,
            "source_nav": ex.source_nav,
            "source_price": ex.source_price,
            "first_seen_at": text(
                "CASE WHEN public.fund_premium_history.first_seen_at IS NULL "
                "THEN EXCLUDED.first_seen_at "
                "WHEN EXCLUDED.first_seen_at IS NULL THEN public.fund_premium_history.first_seen_at "
                "ELSE LEAST(public.fund_premium_history.first_seen_at, EXCLUDED.first_seen_at) END"
            ),
            "first_seen_phase": text(
                "CASE WHEN public.fund_premium_history.first_seen_at IS NULL "
                "THEN EXCLUDED.first_seen_phase ELSE public.fund_premium_history.first_seen_phase END"
            ),
            "pit_safe": text("public.fund_premium_history.pit_safe OR EXCLUDED.pit_safe"),
            "backfilled": text("public.fund_premium_history.backfilled AND EXCLUDED.backfilled"),
            "updated_at": ex.updated_at,
        },
    )
    with engine.begin() as conn:
        result = conn.execute(stmt)
    return len(rows)


def table_count(engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f"select count(*) from public.{TABLE}")).scalar_one())


def coverage_summary(engine, symbols: set[str]) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            select symbol, count(*) as n, min(nav_date) as min_date, max(nav_date) as max_date
            from public.{TABLE}
            where symbol = any(:symbols)
            group by symbol
        """), {"symbols": sorted(symbols)}).mappings().all()
    by_symbol = {str(r["symbol"]): dict(r) for r in rows}
    missing = sorted(symbols - set(by_symbol))
    return {"by_symbol": by_symbol, "missing_symbols": missing}


def latest_summary(engine) -> list[dict]:
    sql = text(f"""
        select distinct on (symbol)
               symbol, nav_date, unit_nav, market_close, premium,
               first_seen_at, first_seen_phase, pit_safe
        from public.{TABLE}
        order by symbol, nav_date desc
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [
        {
            **dict(r),
            "nav_date": str(r["nav_date"]),
            "first_seen_at": r["first_seen_at"].isoformat() if r["first_seen_at"] else None,
            "premium_pct": round(float(r["premium"]) * 100.0, 4),
        }
        for r in rows
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto", "backfill", "preopen"], default="auto")
    ap.add_argument("--start-date", default="20210101")
    ap.add_argument("--lookback-days", type=int, default=45)
    ap.add_argument("--summary", default="premium-history-sync-summary.json")
    ap.add_argument("--symbols", default="", help="Additional comma-separated ETF/LOF symbols")
    ap.add_argument("--signals-file", default="", help="Daily strategy JSON containing dynamic candidates")
    ap.add_argument("--only-selected", action="store_true", help="Sync only supplied candidate symbols")
    args = ap.parse_args()

    engine = create_engine(db_url(), pool_pre_ping=True)
    selected = normalize_symbols(args.symbols.split(",") if args.symbols else [])
    selected |= read_signal_symbols(args.signals_file)
    if args.only_selected and not selected:
        raise RuntimeError("No selected ETF/LOF symbols supplied for candidate premium sync")
    universe = load_universe(engine, selected, args.only_selected)
    tracked = {rec["symbol"] for rec in universe}
    existing = table_count(engine)
    coverage_before = coverage_summary(engine, tracked)
    mode = args.mode
    if mode == "auto":
        # Prioritize current operational coverage. Full multi-year backfills
        # repeatedly timed out before the daily price/NAV snapshot was usable.
        mode = "preopen"

    today = datetime.now(timezone.utc).date()
    if mode == "backfill":
        start_date = args.start_date
        phase = "backfill"
    else:
        start_date = (today - timedelta(days=args.lookback_days)).strftime("%Y%m%d")
        phase = "preopen"
    end_date = today.strftime("%Y%m%d")

    per_symbol = {}
    errors = {}
    total = 0
    for meta in universe:
        try:
            rows = build_rows(meta, start_date, end_date, phase)
            changed = upsert_rows(engine, rows)
            per_symbol[meta["symbol"]] = {"rows": len(rows), "upserted": changed}
            total += changed
        except Exception as exc:
            errors[meta["symbol"]] = f"{type(exc).__name__}: {exc}"

    summary = {
        "mode": mode,
        "range": [start_date, end_date],
        "existing_before": existing,
        "coverage_before": coverage_before,
        "coverage_after": coverage_summary(engine, tracked),
        "selected_symbols": sorted(selected),
        "tracked_symbols": sorted(tracked),
        "upserted": total,
        "symbols": per_symbol,
        "errors": errors,
        "latest": latest_summary(engine),
    }
    Path(args.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    missed_candidates = sorted(selected - set(per_symbol))
    if missed_candidates:
        print(f"ERROR: candidate premium sync failed: {missed_candidates}", flush=True)
        return 1
    return 1 if errors and total == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
