#!/usr/bin/env python3
"""Asset Health monitor for the current repository architecture.

Data boundaries:
- ACTIVE risk universe: data/fundamental-audit-trigger.json latest_risk_pool.
- Historical market data: ETF_daily_bars public.daily_bars via ETF_DAILY_BARS_DATABASE_URL.
- Historical Top1: replayed from the frozen 26-session weighted OLS definition.
- Health classification thresholds: unchanged from ASSET_HEALTH_V1.

This is intentionally versioned separately from the legacy V1 monitor because
legacy V1 consumed historical strategy signals stored in the retired Supabase
project. The replay source is explicit so the two histories are not silently
mixed.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
TRIGGER = ROOT / "data" / "fundamental-audit-trigger.json"
MONITOR_VERSION = "ASSET_HEALTH_V1_CURRENT_UNIVERSE_REPLAY_V1"
SOURCE_STRATEGY_VERSION = "CURRENT_ACTIVE_UNIVERSE_REPLAY_V1"

LOOKBACK = 26
HALF_LIFE = 10.0
ANNUALIZATION = 250.0
NEAR_HIGH_TOLERANCE = 0.005
MIN_ALL_NEAR_HIGH = 10
MIN_RECENT_2Y_NEAR_HIGH = 5
WARNING_WIN_RATE = 0.35
WATCH_WIN_RATE = 0.40
STALE_DAYS = 10
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class Event:
    symbol: str
    signal_date: date
    fwd5: float
    fwd10: float
    near_high: bool
    score: float
    r2: float


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
    f5 = [e.fwd5 for e in events]
    f10 = [e.fwd10 for e in events]
    return {
        "count": len(events),
        "fwd5_mean": mean_or_none(f5),
        "fwd5_median": median_or_none(f5),
        "fwd5_win_rate": win_rate_or_none(f5),
        "fwd10_mean": mean_or_none(f10),
        "fwd10_median": median_or_none(f10),
        "fwd10_win_rate": win_rate_or_none(f10),
    }


def classify_health(all_near: dict, recent_near: dict) -> tuple[str, str]:
    n_all = int(all_near["count"] or 0)
    n_recent = int(recent_near["count"] or 0)
    if n_all < MIN_ALL_NEAR_HIGH or n_recent < MIN_RECENT_2Y_NEAR_HIGH:
        return (
            "INSUFFICIENT_DATA",
            f"near-high samples insufficient: all={n_all}/{MIN_ALL_NEAR_HIGH}, "
            f"recent_2y={n_recent}/{MIN_RECENT_2Y_NEAR_HIGH}",
        )
    all_mean = float(all_near["fwd10_mean"])
    recent_mean = float(recent_near["fwd10_mean"])
    all_win = float(all_near["fwd10_win_rate"])
    recent_win = float(recent_near["fwd10_win_rate"])
    if all_mean < 0 and recent_mean < 0:
        if all_win < WARNING_WIN_RATE and recent_win < WARNING_WIN_RATE:
            return (
                "WARNING",
                "near-high Top1 continuation is negative in both full history and recent 2y, "
                "with both 10d win rates below 35%",
            )
        return (
            "WATCH",
            "near-high Top1 10d mean return is negative in both full history and recent 2y",
        )
    if recent_mean < 0 and recent_win < WATCH_WIN_RATE:
        return (
            "WATCH",
            "recent-2y near-high Top1 continuation deteriorated: negative 10d mean "
            "and win rate below 40%",
        )
    return "HEALTHY", "no frozen V1 deterioration condition triggered"


def load_pool() -> tuple[list[str], str | None]:
    data = json.loads(TRIGGER.read_text(encoding="utf-8"))
    rows = data.get("latest_risk_pool") or []
    symbols = []
    for row in rows:
        s = str(row.get("symbol", ""))
        if len(s) == 6 and s.isdigit():
            symbols.append(s)
    symbols = sorted(set(symbols))
    if not symbols:
        raise RuntimeError("fundamental-audit-trigger.json latest_risk_pool is empty")
    return symbols, data.get("market_data_date")


def weights() -> list[float]:
    # Same effective weights used by the frozen research/state-map implementation.
    return [0.5 ** ((LOOKBACK - 1 - x) / (HALF_LIFE / 2.0)) for x in range(LOOKBACK)]


def ols_score(closes: list[float]) -> tuple[float, float]:
    if len(closes) != LOOKBACK or min(closes) <= 0:
        raise ValueError("invalid OLS window")
    ys = [math.log(v) for v in closes]
    xs = list(range(LOOKBACK))
    ws = weights()
    sw = sum(ws)
    swx = sum(w * x for w, x in zip(ws, xs))
    swxx = sum(w * x * x for w, x in zip(ws, xs))
    swy = sum(w * y for w, y in zip(ws, ys))
    swxy = sum(w * x * y for w, x, y in zip(ws, xs, ys))
    den = sw * swxx - swx * swx
    if den == 0:
        return 0.0, 0.0
    slope = (sw * swxy - swx * swy) / den
    intercept = (swy - slope * swx) / sw
    ybar = swy / sw
    sse = sum(w * (y - (intercept + slope * x)) ** 2 for w, x, y in zip(ws, xs, ys))
    sst = sum(w * (y - ybar) ** 2 for w, y in zip(ws, ys))
    r2 = 1.0 - sse / sst if sst > 0 else 0.0
    annual = math.exp(slope * ANNUALIZATION) - 1.0
    score = annual * r2 if annual > 0 and r2 > 0 else 0.0
    return score, r2


def load_bars(db_url: str, pool: list[str], snapshot_date: date):
    sql = """
      select symbol,date,close
      from public.daily_bars
      where symbol = any(%s) and date <= %s
      order by symbol,date
    """
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    with psycopg2.connect(db_url, connect_timeout=30, application_name="asset_health_monitor") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (pool, snapshot_date.isoformat()))
            for symbol, d, close in cur.fetchall():
                by_symbol[str(symbol)].append(
                    {"date": d, "close": float(close)}
                )
    return by_symbol


def replay_events(by_symbol: dict[str, list[dict]], pool: list[str]) -> dict[str, list[Event]]:
    scores_by_date: dict[date, dict[str, tuple[float, float]]] = defaultdict(dict)
    index_by_symbol_date: dict[str, dict[date, int]] = {}

    for symbol in pool:
        rows = by_symbol.get(symbol, [])
        index_by_symbol_date[symbol] = {r["date"]: i for i, r in enumerate(rows)}
        for i in range(LOOKBACK - 1, len(rows)):
            closes = [float(r["close"]) for r in rows[i - LOOKBACK + 1 : i + 1]]
            score, r2 = ols_score(closes)
            scores_by_date[rows[i]["date"]][symbol] = (score, r2)

    top1_by_date: dict[date, tuple[str, float, float]] = {}
    for d, smap in scores_by_date.items():
        ranked = sorted(
            ((s, sr[0], sr[1]) for s, sr in smap.items() if sr[0] > 0),
            key=lambda x: (-x[1], x[0]),
        )
        if ranked:
            top1_by_date[d] = ranked[0]

    events: dict[str, list[Event]] = defaultdict(list)
    for d in sorted(top1_by_date):
        symbol, score, r2 = top1_by_date[d]
        rows = by_symbol.get(symbol, [])
        idx = index_by_symbol_date.get(symbol, {}).get(d)
        if idx is None or idx < 19 or idx + 10 >= len(rows):
            continue
        close0 = float(rows[idx]["close"])
        high20 = max(float(r["close"]) for r in rows[idx - 19 : idx + 1])
        near_high = close0 >= high20 * (1.0 - NEAR_HIGH_TOLERANCE)
        fwd5 = float(rows[idx + 5]["close"]) / close0 - 1.0
        fwd10 = float(rows[idx + 10]["close"]) / close0 - 1.0
        events[symbol].append(Event(symbol, d, fwd5, fwd10, near_high, score, r2))
    return events


def fmt_pct(v):
    return "—" if v is None else f"{float(v)*100:.2f}%"


def render(rows: list[dict]) -> str:
    order = {"WARNING": 0, "WATCH": 1, "HEALTHY": 2, "INSUFFICIENT_DATA": 3}
    rows = sorted(rows, key=lambda r: (order.get(r["status"], 9), r["symbol"]))
    lines = [
        f"# Asset Health Monitor — {MONITOR_VERSION}",
        "",
        "> Diagnostic only. Frozen V1 health thresholds; historical Top1 is replayed "
        "from current ACTIVE universe because the legacy strategy-signal database is retired.",
        "",
        "| Symbol | Status | Data | Near-high n | 10d mean | 10d win | Recent 2y n | Recent 2y 10d mean | Recent 2y win |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['symbol']} | {r['status']} | {r['data_status']} | {r['near_high_count']} | "
            f"{fmt_pct(r['near_high_fwd10_mean'])} | {fmt_pct(r['near_high_fwd10_win_rate'])} | "
            f"{r['recent_2y_near_high_count']} | {fmt_pct(r['recent_2y_near_high_fwd10_mean'])} | "
            f"{fmt_pct(r['recent_2y_near_high_fwd10_win_rate'])} |"
        )
    lines += ["", "## Reasons", ""]
    for r in rows:
        lines.append(f"- **{r['symbol']} — {r['status']}**: {r['reason']}")
    return "\n".join(lines) + "\n"


def run(args) -> list[dict]:
    db_url = os.getenv("ETF_DAILY_BARS_DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("ETF_DAILY_BARS_DATABASE_URL is not set")
    snapshot_date = date.fromisoformat(args.snapshot_date) if args.snapshot_date else datetime.now(SHANGHAI_TZ).date()
    pool, trigger_market_data_date = load_pool()
    bars = load_bars(db_url, pool, snapshot_date)
    nonempty = [rows for rows in bars.values() if rows]
    if not nonempty:
        raise RuntimeError("daily_bars returned no rows for current ACTIVE universe")
    bars_max_date = max(r["date"] for rows in nonempty for r in rows)
    data_cutoff = min(snapshot_date, bars_max_date)
    data_status = "FRESH" if (snapshot_date - bars_max_date).days <= STALE_DAYS else "STALE"
    events_by_symbol = replay_events(bars, pool)

    recent_2y_start = data_cutoff - timedelta(days=730)
    recent_1y_start = data_cutoff - timedelta(days=365)
    output = []
    for symbol in pool:
        events = [e for e in events_by_symbol.get(symbol, []) if e.signal_date <= data_cutoff]
        near = [e for e in events if e.near_high]
        near2 = [e for e in near if e.signal_date >= recent_2y_start]
        near1 = [e for e in near if e.signal_date >= recent_1y_start]
        all_s, near_s, near2_s, near1_s = map(summarize, [events, near, near2, near1])
        status, reason = classify_health(near_s, near2_s)
        output.append({
            "snapshot_date": snapshot_date.isoformat(),
            "symbol": symbol,
            "monitor_version": MONITOR_VERSION,
            "source_strategy_version": SOURCE_STRATEGY_VERSION,
            "ranking_source": "replayed_frozen_26d_weighted_ols_current_active_universe",
            "trigger_market_data_date": trigger_market_data_date,
            "data_cutoff": data_cutoff.isoformat(),
            "bars_max_date": bars_max_date.isoformat(),
            "data_status": data_status,
            "top1_count": all_s["count"],
            "top1_fwd5_mean": all_s["fwd5_mean"],
            "top1_fwd5_median": all_s["fwd5_median"],
            "top1_fwd5_win_rate": all_s["fwd5_win_rate"],
            "top1_fwd10_mean": all_s["fwd10_mean"],
            "top1_fwd10_median": all_s["fwd10_median"],
            "top1_fwd10_win_rate": all_s["fwd10_win_rate"],
            "near_high_count": near_s["count"],
            "near_high_fwd5_mean": near_s["fwd5_mean"],
            "near_high_fwd5_median": near_s["fwd5_median"],
            "near_high_fwd5_win_rate": near_s["fwd5_win_rate"],
            "near_high_fwd10_mean": near_s["fwd10_mean"],
            "near_high_fwd10_median": near_s["fwd10_median"],
            "near_high_fwd10_win_rate": near_s["fwd10_win_rate"],
            "recent_2y_near_high_count": near2_s["count"],
            "recent_2y_near_high_fwd10_mean": near2_s["fwd10_mean"],
            "recent_2y_near_high_fwd10_win_rate": near2_s["fwd10_win_rate"],
            "recent_1y_near_high_count": near1_s["count"],
            "recent_1y_near_high_fwd10_mean": near1_s["fwd10_mean"],
            "recent_1y_near_high_fwd10_win_rate": near1_s["fwd10_win_rate"],
            "avg_top1_score": mean_or_none(e.score for e in events),
            "avg_top1_r2": mean_or_none(e.r2 for e in events),
            "status": status,
            "reason": reason,
            "metrics": {
                "config": {
                    "lookback": LOOKBACK,
                    "half_life": HALF_LIFE,
                    "annualization": ANNUALIZATION,
                    "near_high_tolerance": NEAR_HIGH_TOLERANCE,
                    "min_all_near_high": MIN_ALL_NEAR_HIGH,
                    "min_recent_2y_near_high": MIN_RECENT_2Y_NEAR_HIGH,
                    "warning_win_rate": WARNING_WIN_RATE,
                    "watch_win_rate": WATCH_WIN_RATE,
                    "stale_days": STALE_DAYS,
                }
            },
            "computed_at": datetime.now(SHANGHAI_TZ).isoformat(),
        })

    markdown = render(output)
    print(markdown)
    if args.summary_path:
        Path(args.summary_path).write_text(markdown, encoding="utf-8")
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot-date")
    p.add_argument("--summary-path")
    p.add_argument("--json-path")
    return p


if __name__ == "__main__":
    run(build_parser().parse_args())
