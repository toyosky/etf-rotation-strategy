#!/usr/bin/env python3
"""Build the website's daily Breadth x Leadership Gap state-map JSON.

Uses the same frozen 26-session weighted OLS score definition as the research
pipeline: half-life 10, annualization 250, score = annualized slope return * R²
when both are positive.
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict, deque
from datetime import date
from pathlib import Path

import psycopg2

LOOKBACK = 26
HALF_LIFE = 10.0
ANNUALIZATION = 250.0
CASH = "511220"
RISK = (
    "159934", "159985", "161226", "513100", "159957", "159509", "513290",
    "159529", "159981", "501018", "513530", "511380", "164824", "512800",
)
ALL = RISK + (CASH,)
HISTORY = 252
OUT = Path(__file__).resolve().parents[1] / "data"


def database_url() -> str:
    value = os.environ.get("ETF_DAILY_BARS_DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("ETF_DAILY_BARS_DATABASE_URL is not set")
    return value


def weights() -> list[float]:
    # Research code squares q, therefore effective exponent denominator is HALF_LIFE/2.
    return [0.5 ** ((LOOKBACK - 1 - x) / (HALF_LIFE / 2.0)) for x in range(LOOKBACK)]


def ols_score(closes: list[float]) -> float | None:
    if len(closes) != LOOKBACK or min(closes) <= 0:
        return None
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
        return None
    slope = (sw * swxy - swx * swy) / den
    intercept = (swy - slope * swx) / sw
    ybar = swy / sw
    sse = sum(w * (y - (intercept + slope * x)) ** 2 for w, x, y in zip(ws, xs, ys))
    sst = sum(w * (y - ybar) ** 2 for w, y in zip(ws, ys))
    r2 = 1.0 - sse / sst if sst > 0 else 0.0
    annual = math.exp(slope * ANNUALIZATION) - 1.0
    return annual * r2 if annual > 0 and r2 > 0 else 0.0


def load_scores() -> dict[date, dict[str, float]]:
    sql = """
      select symbol,date,close
      from public.daily_bars
      where symbol = any(%s)
      order by symbol,date
    """
    by_symbol: dict[str, list[tuple[date, float]]] = defaultdict(list)
    with psycopg2.connect(database_url(), connect_timeout=30, application_name="github_state_map") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (list(ALL),))
            for symbol, d, close in cur.fetchall():
                by_symbol[str(symbol)].append((d, float(close)))

    scores: dict[date, dict[str, float]] = defaultdict(dict)
    for symbol in ALL:
        window: deque[float] = deque(maxlen=LOOKBACK)
        for d, close in by_symbol.get(symbol, []):
            window.append(close)
            if len(window) == LOOKBACK:
                value = ols_score(list(window))
                if value is not None and math.isfinite(value):
                    scores[d][symbol] = value
    return scores


def quadrant(breadth_pct: float, gap_pct: float) -> str:
    if breadth_pct >= 50 and gap_pct >= 50:
        return "TREND_EXPANSION"
    if breadth_pct >= 50:
        return "ROTATION_CROWDING"
    if gap_pct >= 50:
        return "NARROW_LEADERSHIP"
    return "DEFENSIVE_VOID"


def main() -> None:
    scores = load_scores()
    rows = []
    gap_history: deque[float] = deque(maxlen=HISTORY)
    for d in sorted(scores):
        s = scores[d]
        if CASH not in s:
            continue
        ranked = sorted(((sym, s.get(sym, 0.0)) for sym in RISK), key=lambda x: (-x[1], x[0]))
        top1, top1_score = ranked[0]
        top2, top2_score = ranked[1]
        cash_score = s[CASH]
        breadth_count = sum(1 for _, value in ranked if value > cash_score)
        breadth_pct = breadth_count / len(RISK) * 100.0
        gap_raw = max(top1_score - top2_score, 0.0)
        gap_history.append(gap_raw)
        gap_pct = sum(1 for value in gap_history if value <= gap_raw) / len(gap_history) * 100.0
        rows.append({
            "date": d.isoformat(),
            "breadth_count": breadth_count,
            "breadth_total": len(RISK),
            "breadth_pct": round(breadth_pct, 1),
            "cash_score": round(cash_score, 6),
            "top1": top1,
            "top1_score": round(top1_score, 6),
            "top2": top2,
            "top2_score": round(top2_score, 6),
            "gap_raw": round(gap_raw, 6),
            "gap_percentile": round(gap_pct, 1),
            "quadrant": quadrant(breadth_pct, gap_pct),
        })

    if not rows:
        raise RuntimeError("No state-map rows could be generated")
    history = rows[-HISTORY:]
    latest = history[-1]
    latest["updated_by"] = "github_action"
    latest["definition"] = "breadth=share(score>cash_score); leadership=rolling252 percentile(top1_score-top2_score)"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "state-map-history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "state-map-latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(latest, ensure_ascii=False))


if __name__ == "__main__":
    main()
