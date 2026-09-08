#!/usr/bin/env python3
"""Monthly diagnostic monitor for ETF-to-OLS strategy fit.

This module is intentionally separate from strategy/main.py. It never changes
ETF_POOL and never generates trading orders. It reads frozen strategy signals
and daily bars, evaluates what happened after historical Top1 states, and writes
an immutable-by-date diagnostic snapshot to Supabase.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from supabase import Client, create_client

MONITOR_VERSION = "ASSET_HEALTH_V1"
DEFAULT_STRATEGY_VERSION = "FROZEN_C2@20260903T_fixed_window_v2"
DEFAULT_NEAR_HIGH_TOLERANCE = 0.005
DEFAULT_MIN_ALL_NEAR_HIGH = 10
DEFAULT_MIN_RECENT_2Y_NEAR_HIGH = 5
DEFAULT_WARNING_WIN_RATE = 0.35
DEFAULT_WATCH_WIN_RATE = 0.40
DEFAULT_STALE_DAYS = 10
CASH_PROXY_SYMBOL = "511220"
PAGE_SIZE = 1000
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class Event:
    symbol: str
    signal_date: date
    fwd5: float
    fwd10: float
    near_high: bool
    score: float | None
    r2: float | None


def parse_iso_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value[:10])


def mean_or_none(values: Iterable[float]) -> float | None:
    seq = list(values)
    return statistics.fmean(seq) if seq else None


def median_or_none(values: Iterable[float]) -> float | None:
    seq = list(values)
    return statistics.median(seq) if seq else None


def win_rate_or_none(values: Iterable[float]) -> float | None:
    seq = list(values)
    return (sum(v > 0 for v in seq) / len(seq)) if seq else None


def summarize(events: list[Event]) -> dict[str, float | int | None]:
    fwd5 = [e.fwd5 for e in events]
    fwd10 = [e.fwd10 for e in events]
    return {
        "count": len(events),
        "fwd5_mean": mean_or_none(fwd5),
        "fwd5_median": median_or_none(fwd5),
        "fwd5_win_rate": win_rate_or_none(fwd5),
        "fwd10_mean": mean_or_none(fwd10),
        "fwd10_median": median_or_none(fwd10),
        "fwd10_win_rate": win_rate_or_none(fwd10),
    }


def classify_health(
    *,
    all_near_high: dict[str, float | int | None],
    recent_2y_near_high: dict[str, float | int | None],
    min_all: int = DEFAULT_MIN_ALL_NEAR_HIGH,
    min_recent_2y: int = DEFAULT_MIN_RECENT_2Y_NEAR_HIGH,
    warning_win_rate: float = DEFAULT_WARNING_WIN_RATE,
    watch_win_rate: float = DEFAULT_WATCH_WIN_RATE,
) -> tuple[str, str]:
    """Frozen V1 classification.

    V1 is deliberately conservative and diagnostic-only. A negative recent
    window can trigger WATCH, but WARNING requires both long-history and recent
    evidence. No status modifies the trading strategy automatically.
    """
    n_all = int(all_near_high["count"] or 0)
    n_recent = int(recent_2y_near_high["count"] or 0)
    if n_all < min_all or n_recent < min_recent_2y:
        return (
            "INSUFFICIENT_DATA",
            f"near-high samples insufficient: all={n_all}/{min_all}, recent_2y={n_recent}/{min_recent_2y}",
        )

    all_mean = all_near_high["fwd10_mean"]
    recent_mean = recent_2y_near_high["fwd10_mean"]
    all_win = all_near_high["fwd10_win_rate"]
    recent_win = recent_2y_near_high["fwd10_win_rate"]

    assert isinstance(all_mean, float)
    assert isinstance(recent_mean, float)
    assert isinstance(all_win, float)
    assert isinstance(recent_win, float)

    if all_mean < 0 and recent_mean < 0:
        if all_win < warning_win_rate and recent_win < warning_win_rate:
            return (
                "WARNING",
                "near-high Top1 continuation is negative in both full history and recent 2y, with both 10d win rates below 35%",
            )
        return (
            "WATCH",
            "near-high Top1 10d mean return is negative in both full history and recent 2y",
        )

    if recent_mean < 0 and recent_win < watch_win_rate:
        return (
            "WATCH",
            "recent-2y near-high Top1 continuation deteriorated: negative 10d mean and win rate below 40%",
        )

    return "HEALTHY", "no frozen V1 deterioration condition triggered"


def fetch_all(
    client: Client,
    table: str,
    columns: str,
    *,
    eq_filters: dict[str, Any] | None = None,
    lte_filters: dict[str, Any] | None = None,
    order_by: list[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        q = client.table(table).select(columns)
        for key, value in (eq_filters or {}).items():
            q = q.eq(key, value)
        for key, value in (lte_filters or {}).items():
            q = q.lte(key, value)
        for col in order_by or []:
            q = q.order(col)
        response = q.range(offset, offset + PAGE_SIZE - 1).execute()
        page = response.data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def get_strategy_pool(client: Client, strategy_version: str) -> list[str]:
    response = (
        client.table("strategy_runs")
        .select("parameters")
        .eq("version", strategy_version)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise RuntimeError(f"strategy version not found in strategy_runs: {strategy_version}")
    pool = (((rows[0].get("parameters") or {}).get("ranking") or {}).get("pool") or [])
    symbols = []
    for raw in pool:
        symbol = str(raw).split(".", 1)[0]
        if len(symbol) == 6 and symbol.isdigit():
            symbols.append(symbol)
    if not symbols:
        raise RuntimeError(f"strategy pool missing from parameters.ranking.pool: {strategy_version}")
    return sorted(set(symbols))


def build_events(
    bars_rows: list[dict[str, Any]],
    signal_rows: list[dict[str, Any]],
    score_rows: list[dict[str, Any]],
    *,
    near_high_tolerance: float,
) -> tuple[dict[str, list[Event]], dict[str, dict[str, int]]]:
    bars_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in bars_rows:
        row = dict(row)
        row["_date"] = parse_iso_date(row["date"])
        bars_by_symbol[row["symbol"]].append(row)
    for symbol in bars_by_symbol:
        bars_by_symbol[symbol].sort(key=lambda r: r["_date"])

    idx_by_symbol_date: dict[str, dict[date, int]] = {}
    for symbol, rows in bars_by_symbol.items():
        idx_by_symbol_date[symbol] = {r["_date"]: i for i, r in enumerate(rows)}

    score_map: dict[tuple[str, date], tuple[float | None, float | None]] = {}
    for row in score_rows:
        score_map[(row["symbol"], parse_iso_date(row["date"]))] = (
            float(row["score"]) if row.get("score") is not None else None,
            float(row["r2"]) if row.get("r2") is not None else None,
        )

    events_by_symbol: dict[str, list[Event]] = defaultdict(list)
    exclusions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for sig in signal_rows:
        symbol = sig.get("top1")
        signal_date_raw = sig.get("signal_date")
        if not symbol or not signal_date_raw:
            continue
        signal_date = parse_iso_date(signal_date_raw)
        bars = bars_by_symbol.get(symbol)
        idx = idx_by_symbol_date.get(symbol, {}).get(signal_date)
        if not bars or idx is None:
            exclusions[symbol]["missing_signal_bar"] += 1
            continue
        if idx < 19:
            exclusions[symbol]["insufficient_lookback"] += 1
            continue
        if idx + 10 >= len(bars):
            exclusions[symbol]["unmatured_fwd10"] += 1
            continue

        source_window = {str(r.get("source")) for r in bars[idx - 19 : idx + 11]}
        if len(source_window) > 1:
            exclusions[symbol]["mixed_source_window"] += 1
            continue

        close0 = float(bars[idx]["close"])
        high20_close = max(float(r["close"]) for r in bars[idx - 19 : idx + 1])
        near_high = close0 >= high20_close * (1.0 - near_high_tolerance)
        fwd5 = float(bars[idx + 5]["close"]) / close0 - 1.0
        fwd10 = float(bars[idx + 10]["close"]) / close0 - 1.0
        score, r2 = score_map.get((symbol, signal_date), (None, None))
        events_by_symbol[symbol].append(
            Event(
                symbol=symbol,
                signal_date=signal_date,
                fwd5=fwd5,
                fwd10=fwd10,
                near_high=near_high,
                score=score,
                r2=r2,
            )
        )

    return events_by_symbol, exclusions


def fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f}%"


def render_markdown(rows: list[dict[str, Any]]) -> str:
    status_order = {"WARNING": 0, "WATCH": 1, "HEALTHY": 2, "INSUFFICIENT_DATA": 3}
    ordered = sorted(rows, key=lambda r: (status_order.get(r["status"], 9), r["symbol"]))
    lines = [
        f"# Asset Health Monitor — {MONITOR_VERSION}",
        "",
        "> Diagnostic only. This monitor never edits the trading pool or places orders.",
        "",
        "| Symbol | Status | Data | Near-high n | 10d mean | 10d win | Recent 2y n | Recent 2y 10d mean | Recent 2y win |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ordered:
        lines.append(
            "| {symbol} | {status} | {data_status} | {near_high_count} | {all_mean} | {all_win} | {n2} | {mean2} | {win2} |".format(
                symbol=row["symbol"],
                status=row["status"],
                data_status=row["data_status"],
                near_high_count=row["near_high_count"],
                all_mean=fmt_pct(row["near_high_fwd10_mean"]),
                all_win=fmt_pct(row["near_high_fwd10_win_rate"]),
                n2=row["recent_2y_near_high_count"],
                mean2=fmt_pct(row["recent_2y_near_high_fwd10_mean"]),
                win2=fmt_pct(row["recent_2y_near_high_fwd10_win_rate"]),
            )
        )
    lines += ["", "## Reasons", ""]
    for row in ordered:
        lines.append(f"- **{row['symbol']} — {row['status']}**: {row['reason']}")
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "missing SUPABASE_URL and SUPABASE_SECRET_KEY (legacy SUPABASE_SERVICE_ROLE_KEY is accepted as fallback)"
        )
    client = create_client(supabase_url, supabase_key)

    snapshot_date = parse_iso_date(args.snapshot_date) if args.snapshot_date else datetime.now(SHANGHAI_TZ).date()
    strategy_version = args.strategy_version
    pool = get_strategy_pool(client, strategy_version)

    bars_rows = fetch_all(
        client,
        "daily_bars",
        "symbol,date,close,source",
        lte_filters={"date": snapshot_date.isoformat()},
        order_by=["symbol", "date"],
    )
    signal_rows = fetch_all(
        client,
        "signals",
        "date,signal_date,top1",
        eq_filters={"strategy_version": strategy_version},
        lte_filters={"signal_date": snapshot_date.isoformat()},
        order_by=["signal_date"],
    )
    score_rows = fetch_all(
        client,
        "daily_scores",
        "date,symbol,score,r2,rank",
        eq_filters={"strategy_version": strategy_version, "rank": 1},
        lte_filters={"date": snapshot_date.isoformat()},
        order_by=["date", "symbol"],
    )

    if not bars_rows or not signal_rows:
        raise RuntimeError("daily_bars or signals returned no data")

    bars_max_date = max(parse_iso_date(r["date"]) for r in bars_rows)
    signals_max_date = max(parse_iso_date(r["signal_date"]) for r in signal_rows if r.get("signal_date"))
    data_cutoff = min(snapshot_date, bars_max_date, signals_max_date)
    data_status = (
        "FRESH"
        if (snapshot_date - bars_max_date).days <= args.stale_days
        and (snapshot_date - signals_max_date).days <= args.stale_days
        else "STALE"
    )

    events_by_symbol, exclusions = build_events(
        bars_rows,
        signal_rows,
        score_rows,
        near_high_tolerance=args.near_high_tolerance,
    )

    recent_2y_start = data_cutoff - timedelta(days=730)
    recent_1y_start = data_cutoff - timedelta(days=365)
    output_rows: list[dict[str, Any]] = []

    for symbol in pool:
        if symbol == CASH_PROXY_SYMBOL:
            continue
        events = [e for e in events_by_symbol.get(symbol, []) if e.signal_date <= data_cutoff]
        near = [e for e in events if e.near_high]
        near_2y = [e for e in near if e.signal_date >= recent_2y_start]
        near_1y = [e for e in near if e.signal_date >= recent_1y_start]

        all_summary = summarize(events)
        near_summary = summarize(near)
        near_2y_summary = summarize(near_2y)
        near_1y_summary = summarize(near_1y)

        status, reason = classify_health(
            all_near_high=near_summary,
            recent_2y_near_high=near_2y_summary,
            min_all=args.min_all_near_high,
            min_recent_2y=args.min_recent_2y_near_high,
        )

        scores = [e.score for e in events if e.score is not None]
        r2s = [e.r2 for e in events if e.r2 is not None]
        output_rows.append(
            {
                "snapshot_date": snapshot_date.isoformat(),
                "symbol": symbol,
                "monitor_version": MONITOR_VERSION,
                "source_strategy_version": strategy_version,
                "data_cutoff": data_cutoff.isoformat(),
                "bars_max_date": bars_max_date.isoformat(),
                "signals_max_date": signals_max_date.isoformat(),
                "data_status": data_status,
                "top1_count": all_summary["count"],
                "top1_fwd5_mean": all_summary["fwd5_mean"],
                "top1_fwd5_median": all_summary["fwd5_median"],
                "top1_fwd5_win_rate": all_summary["fwd5_win_rate"],
                "top1_fwd10_mean": all_summary["fwd10_mean"],
                "top1_fwd10_median": all_summary["fwd10_median"],
                "top1_fwd10_win_rate": all_summary["fwd10_win_rate"],
                "near_high_count": near_summary["count"],
                "near_high_fwd5_mean": near_summary["fwd5_mean"],
                "near_high_fwd5_median": near_summary["fwd5_median"],
                "near_high_fwd5_win_rate": near_summary["fwd5_win_rate"],
                "near_high_fwd10_mean": near_summary["fwd10_mean"],
                "near_high_fwd10_median": near_summary["fwd10_median"],
                "near_high_fwd10_win_rate": near_summary["fwd10_win_rate"],
                "recent_2y_near_high_count": near_2y_summary["count"],
                "recent_2y_near_high_fwd10_mean": near_2y_summary["fwd10_mean"],
                "recent_2y_near_high_fwd10_win_rate": near_2y_summary["fwd10_win_rate"],
                "recent_1y_near_high_count": near_1y_summary["count"],
                "recent_1y_near_high_fwd10_mean": near_1y_summary["fwd10_mean"],
                "recent_1y_near_high_fwd10_win_rate": near_1y_summary["fwd10_win_rate"],
                "avg_top1_score": mean_or_none([float(v) for v in scores]),
                "avg_top1_r2": mean_or_none([float(v) for v in r2s]),
                "status": status,
                "reason": reason,
                "metrics": {
                    "config": {
                        "near_high_tolerance": args.near_high_tolerance,
                        "min_all_near_high": args.min_all_near_high,
                        "min_recent_2y_near_high": args.min_recent_2y_near_high,
                        "warning_win_rate": DEFAULT_WARNING_WIN_RATE,
                        "watch_win_rate": DEFAULT_WATCH_WIN_RATE,
                        "stale_days": args.stale_days,
                        "cash_proxy_excluded": CASH_PROXY_SYMBOL,
                    },
                    "recent_1y": near_1y_summary,
                    "exclusions": dict(exclusions.get(symbol, {})),
                },
                "computed_at": datetime.now(SHANGHAI_TZ).isoformat(),
            }
        )

    if not args.dry_run:
        if not output_rows:
            raise RuntimeError("no asset-health rows produced")
        (
            client.table("asset_health_snapshots")
            .upsert(
                output_rows,
                on_conflict="snapshot_date,symbol,monitor_version,source_strategy_version",
            )
            .execute()
        )

    markdown = render_markdown(output_rows)
    print(markdown)
    if args.summary_path:
        path = Path(args.summary_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_rows


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Compute prospective ETF Asset Health snapshots")
    p.add_argument(
        "--strategy-version",
        default=os.getenv("ASSET_HEALTH_STRATEGY_VERSION", DEFAULT_STRATEGY_VERSION),
        help="strategy_runs.version whose historical Top1 signals are evaluated",
    )
    p.add_argument("--snapshot-date", help="YYYY-MM-DD; defaults to current Asia/Shanghai date")
    p.add_argument("--summary-path", help="optional Markdown output path")
    p.add_argument("--json-path", help="optional JSON output path")
    p.add_argument("--dry-run", action="store_true", help="compute without writing asset_health_snapshots")
    p.add_argument("--near-high-tolerance", type=float, default=DEFAULT_NEAR_HIGH_TOLERANCE)
    p.add_argument("--min-all-near-high", type=int, default=DEFAULT_MIN_ALL_NEAR_HIGH)
    p.add_argument("--min-recent-2y-near-high", type=int, default=DEFAULT_MIN_RECENT_2Y_NEAR_HIGH)
    p.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    return p


if __name__ == "__main__":
    run(build_parser().parse_args())
