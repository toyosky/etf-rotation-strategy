#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "fundamental-audit-trigger.json"
LIVE = ROOT / "data" / "live-forward.json"
ACTUAL = ROOT / "data" / "actual-holding.json"

RISK_POOL = [
    "159934", "159985", "161226", "513100", "159957", "159509",
    "513290", "159529", "159981", "501018", "513530", "511380", "164824",
    "520870", "159100", "512800",  # Brazil and bank research carriers; not production Top1 universe
]
NAMES = {
    "159934": "黄金", "159985": "豆粕", "161226": "白银", "513100": "纳指100",
    "159957": "创业板", "159509": "纳指科技", "513290": "纳指生物",
    "159529": "标普消费", "159981": "能源化工", "501018": "原油",
    "513530": "港股红利", "511380": "可转债", "164824": "印度",
    "511220": "城投债/现金", "513500": "标普500 Carrier",
    "520870": "巴西ETF易方达", "159100": "巴西ETF华夏", "512800": "银行ETF华宝",
}

LOOKBACK = 26
HALF_LIFE = 10.0
ANNUALIZATION = 250.0


def db_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        raw = "postgresql+psycopg2://" + raw[len("postgresql://"):]
    return raw


def calc_ols(close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(close)
    annual_out = np.full(n, np.nan, dtype=float)
    r2_out = np.full(n, np.nan, dtype=float)
    if n < LOOKBACK:
        return annual_out, r2_out

    y = np.log(close.astype(float))
    windows = np.lib.stride_tricks.sliding_window_view(y, LOOKBACK)
    x = np.arange(LOOKBACK, dtype=float)
    q = np.power(0.5, (LOOKBACK - 1 - x) / HALF_LIFE)
    w = q * q  # frozen production/research effective fit weights

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
    r2 = np.clip(r2, 0.0, 1.0)
    annual = np.exp(slope * ANNUALIZATION) - 1.0

    annual_out[LOOKBACK - 1:] = annual
    r2_out[LOOKBACK - 1:] = r2
    return annual_out, r2_out


def finite(v):
    if v is None:
        return None
    try:
        x = float(v)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def load_live() -> dict:
    if not LIVE.exists():
        return {}
    return json.loads(LIVE.read_text(encoding="utf-8"))


def current_holding_from_live(live: dict) -> dict:
    if ACTUAL.exists():
        actual = json.loads(ACTUAL.read_text(encoding="utf-8"))
        symbols = actual.get("symbols")
        if isinstance(symbols, list) and len(symbols) == 0:
            return {"symbol": None, "name": "现金（实际空仓）",
                    "as_of": actual.get("as_of"), "source": "data/actual-holding.json (user-reported)"}
        if isinstance(symbols, list) and len(symbols) == 1:
            symbol = str(symbols[0])
            return {"symbol": symbol, "name": NAMES.get(symbol, symbol),
                    "as_of": actual.get("as_of"), "source": "data/actual-holding.json (user-reported)"}
    mtm = ((live.get("mark_to_market") or {}).get("baseline") or {})
    target = mtm.get("target")
    if not target:
        series = ((live.get("series") or {}).get("baseline") or [])
        if series:
            target = series[-1].get("target")
    if not target:
        target = ((live.get("latest") or {}).get("target"))
    return {
        "symbol": target,
        "name": NAMES.get(target, "现金") if target else "现金",
        "source": "data/live-forward.json baseline holding/mark-to-market",
    }


def next_target_from_live(live: dict) -> dict:
    latest = live.get("latest") or {}
    if "raw_top1" not in latest or "v1_target" not in latest:
        raise ValueError("Live snapshot lacks independent raw OLS/V1 fields; do not mislabel defensive target as Top1")
    target = latest.get("target")
    raw_top1 = latest.get("raw_top1")
    strategy = latest.get("model_target")
    v1 = latest.get("v1_target")
    return {
        "symbol": target,
        "name": NAMES.get(target, "现金") if target else "现金",
        "model_target": raw_top1,
        "model_target_name": NAMES.get(raw_top1, "无有效风险资产Top1") if raw_top1 else "无有效风险资产Top1",
        "raw_top1_score": latest.get("raw_top1_score"),
        "raw_top1_qualifies_cash": latest.get("raw_top1_qualifies_cash"),
        "v1_target": v1,
        "v1_target_name": NAMES.get(v1, "现金") if v1 else "现金",
        "strategy_model_target": strategy,
        "strategy_model_target_name": NAMES.get(strategy, "现金") if strategy else "现金",
        "holding_target": latest.get("holding_target"),
        "execution_status": latest.get("execution_status"),
        "execution_filter": latest.get("execution_filter"),
        "signal_date": latest.get("date"),
        "decision": latest.get("decision"),
    }


def main() -> None:
    raw_db = os.getenv("ETF_DAILY_BARS_DATABASE_URL")
    if not raw_db:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    eng = create_engine(db_url(raw_db), pool_pre_ping=True)
    quoted = ",".join("'" + s + "'" for s in RISK_POOL)
    sql = f"""
        select symbol, date, close
        from public.daily_bars
        where symbol in ({quoted})
        order by symbol, date
    """
    bars = pd.read_sql_query(sql, eng, parse_dates=["date"])
    bars["symbol"] = bars["symbol"].astype(str).str.zfill(6)
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")
    bars = bars.dropna(subset=["close"]).copy()
    if bars.empty:
        raise RuntimeError("No risk-pool daily bars found")

    latest_market_date = pd.Timestamp(bars["date"].max())
    rows = []
    for symbol in RISK_POOL:
        g = bars[bars["symbol"] == symbol].sort_values("date").copy().reset_index(drop=True)
        if len(g) < LOOKBACK + 4:
            continue
        annual, r2 = calc_ols(g["close"].to_numpy(dtype=float))
        g["annual"] = annual
        g["r2"] = r2
        g["raw_score"] = g["annual"] * g["r2"]
        g["prev_annual"] = g["annual"].shift(1)
        g["dr2_1"] = g["r2"] - g["r2"].shift(1)
        g["dr2_3"] = g["r2"] - g["r2"].shift(3)
        g["dannual_1"] = g["annual"] - g["annual"].shift(1)
        g["dannual_3"] = g["annual"] - g["annual"].shift(3)
        g["cross"] = (g["prev_annual"] <= 0) & (g["annual"] > 0)

        latest = g.iloc[-1]
        if pd.Timestamp(latest["date"]) != latest_market_date:
            continue

        cross_pos = None
        start = max(0, len(g) - 4)
        for pos in range(len(g) - 1, start - 1, -1):
            if bool(g.iloc[pos]["cross"]):
                cross_pos = pos
                break

        cross_age = None if cross_pos is None else len(g) - 1 - cross_pos
        cross_date = None
        cross_r2 = None
        r2_since_cross = None
        stage = None
        qualifies = False

        if cross_pos is not None:
            cross_row = g.iloc[cross_pos]
            cross_date = pd.Timestamp(cross_row["date"]).strftime("%Y-%m-%d")
            cross_r2 = finite(cross_row["r2"])
            current_annual = finite(latest["annual"])
            current_r2 = finite(latest["r2"])
            dr2_1 = finite(latest["dr2_1"])
            if current_r2 is not None and cross_r2 is not None:
                r2_since_cross = current_r2 - cross_r2

            if cross_age == 0 and current_annual is not None and current_annual > 0:
                stage = "CROSS_DETECTED"
            elif (
                cross_age is not None and 1 <= cross_age <= 3
                and current_annual is not None and current_annual > 0
                and dr2_1 is not None and dr2_1 > 0
                and r2_since_cross is not None and r2_since_cross > 0
            ):
                stage = "REBUILDING_QUALIFIED"
                qualifies = True
            elif (
                cross_age is not None and 1 <= cross_age <= 3
                and current_annual is not None and current_annual > 0
            ):
                stage = "REBUILD_WATCH"

        rows.append({
            "symbol": symbol,
            "name": NAMES.get(symbol, symbol),
            "date": latest_market_date.strftime("%Y-%m-%d"),
            "annual": finite(latest["annual"]),
            "r2": finite(latest["r2"]),
            "raw_score": finite(latest["raw_score"]),
            "delta_annual_1": finite(latest["dannual_1"]),
            "delta_annual_3": finite(latest["dannual_3"]),
            "delta_r2_1": finite(latest["dr2_1"]),
            "delta_r2_3": finite(latest["dr2_3"]),
            "cross_date": cross_date,
            "cross_age_sessions": cross_age,
            "r2_at_cross": cross_r2,
            "r2_change_since_cross": finite(r2_since_cross),
            "stage": stage,
            "fundamental_audit_qualified": qualifies,
        })

    positive = [x for x in rows if x["annual"] is not None and x["annual"] > 0 and x["raw_score"] is not None]
    positive.sort(key=lambda x: x["raw_score"], reverse=True)
    rank_map = {x["symbol"]: i + 1 for i, x in enumerate(positive)}
    for x in rows:
        x["raw_positive_rank"] = rank_map.get(x["symbol"])

    qualified = [x for x in rows if x["fundamental_audit_qualified"]]
    watches = [x for x in rows if x["stage"] in {"CROSS_DETECTED", "REBUILD_WATCH"}]
    qualified.sort(key=lambda x: (x["raw_positive_rank"] is None, x["raw_positive_rank"] or 999))
    watches.sort(key=lambda x: (x["raw_positive_rank"] is None, x["raw_positive_rank"] or 999))

    live = load_live()
    live_date = str((live.get("latest") or {}).get("date") or "")
    if live_date != latest_market_date.strftime("%Y-%m-%d"):
        raise RuntimeError(f"Live OLS data stale: {live_date} != market {latest_market_date:%Y-%m-%d}; refuse PushPlus")
    payload = {
        "version": "fundamental-audit-trigger-v1",
        "market_data_date": latest_market_date.strftime("%Y-%m-%d"),
        "generated_from": "Supabase public.daily_bars + data/live-forward.json",
        "signal_definition": {
            "cross": "annual changes from <=0 to >0",
            "qualified_rebuild": "cross age 1-3 sessions; annual remains >0; delta_r2_1 > 0; current r2 > r2 at cross",
            "note": "Research trigger only. It does not alter production ranking or execute trades.",
        },
        "current_holding": current_holding_from_live(live),
        "next_strategy_target": next_target_from_live(live),
        "audit_required": bool(qualified),
        "qualified_candidates": qualified,
        "trend_watch": watches,
        "latest_risk_pool": sorted(rows, key=lambda x: (x["raw_positive_rank"] is None, x["raw_positive_rank"] or 999)),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "market_data_date": payload["market_data_date"],
        "current_holding": payload["current_holding"],
        "next_strategy_target": payload["next_strategy_target"],
        "audit_required": payload["audit_required"],
        "qualified_candidates": [
            {"symbol": x["symbol"], "stage": x["stage"], "rank": x["raw_positive_rank"]}
            for x in qualified
        ],
        "trend_watch": [
            {"symbol": x["symbol"], "stage": x["stage"], "rank": x["raw_positive_rank"]}
            for x in watches
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
