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
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import akshare as ak
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import MetaData, Table

# Workflow trigger/version: v1\nDB_ENV = "ETF_DAILY_BARS_DATABASE_URL"
TABLE = "fund_premium_history"
UNIVERSE_PATH = Path(__file__).with_name("tencent_daily_universe.csv")

# Must match strategy/main.py PREMIUM_MONITOR_POOL:
# 13 risk assets + 513500 carrier. 511220 cash and 510300 benchmark are excluded.
MONITOR_SYMBOLS = {
    "159934", "159985", "161226", "513100", "159957", "159509", "513290",
    "159529", "159981", "501018", "513530", "511380", "164824", "513500",
}


def db_url() -> str:
    value = os.getenv(DB_ENV)
    if not value:
        raise RuntimeError(f"Missing {DB_ENV}")
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://"):]
    return value


def load_universe() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with UNIVERSE_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            symbol = str(row["symbol"]).zfill(6)
            if symbol in MONITOR_SYMBOLS:
                rows.append({
                    "symbol": symbol,
                    "name": row.get("name", ""),
                    "instrument_type": (row.get("instrument_type") or "ETF").upper(),
                })
    missing = MONITOR_SYMBOLS - {x["symbol"] for x in rows}
    if missing:
        raise RuntimeError(f"Premium universe missing symbols: {sorted(missing)}")
    return rows


def _col(df: pd.DataFrame, names: list[str]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def fetch_nav(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    try:
        df = ak.fund_etf_fund_info_em(
            fund=symbol,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        # Fallback covers products that Eastmoney exposes through the general fund endpoint.
        try:
            df = ak.fund_open_fund_info_em(
                symbol=symbol,
                indicator="单位净值走势",
                period="成立来",
            )
        except Exception:
            df = pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

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


def fetch_unadjusted_price(symbol: str, instrument_type: str, start_date: str, end_date: str) -> pd.DataFrame:
    if instrument_type == "LOF":
        df = ak.fund_lof_hist_em(
            symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust=""
        )
    else:
        df = ak.fund_etf_hist_em(
            symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust=""
        )
    if df is None or df.empty:
        return pd.DataFrame()
    date_col = _col(df, ["日期"])
    close_col = _col(df, ["收盘"])
    if not date_col or not close_col:
        return pd.DataFrame()
    out = pd.DataFrame({
        "nav_date": pd.to_datetime(df[date_col], errors="coerce").dt.date,
        "market_close": pd.to_numeric(df[close_col], errors="coerce"),
    })
    out = out.dropna(subset=["nav_date", "market_close"])
    out = out[out["market_close"] > 0]
    return out.sort_values("nav_date").drop_duplicates("nav_date", keep="last")


def build_rows(meta: dict[str, str], start_date: str, end_date: str, phase: str) -> list[dict]:
    symbol = meta["symbol"]
    nav = fetch_nav(symbol, start_date, end_date)
    px = fetch_unadjusted_price(symbol, meta["instrument_type"], start_date, end_date)
    if nav.empty or px.empty:
        return []
    merged = nav.merge(px, on="nav_date", how="inner")
    if merged.empty:
        return []

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
            "source_nav": "eastmoney_akshare",
            "source_price": "eastmoney_akshare_unadjusted",
            "first_seen_at": now if live_observation else None,
            "first_seen_phase": "preopen" if live_observation else None,
            "pit_safe": live_observation,
            "backfilled": not live_observation,
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
    return int(result.rowcount or 0)


def table_count(engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f"select count(*) from public.{TABLE}")).scalar_one())


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
    ap.add_argument("--start-date", default="20000101")
    ap.add_argument("--lookback-days", type=int, default=45)
    ap.add_argument("--summary", default="premium-history-sync-summary.json")
    args = ap.parse_args()

    engine = create_engine(db_url(), pool_pre_ping=True)
    existing = table_count(engine)
    mode = args.mode
    if mode == "auto":
        mode = "backfill" if existing == 0 else "preopen"

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
    for meta in load_universe():
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
        "upserted": total,
        "symbols": per_symbol,
        "errors": errors,
        "latest": latest_summary(engine),
    }
    Path(args.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 1 if errors and len(errors) == len(MONITOR_SYMBOLS) else 0


if __name__ == "__main__":
    raise SystemExit(main())
