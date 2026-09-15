#!/usr/bin/env python3
from __future__ import annotations

import json, os, sys
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
import optimal_universe_reverse_engineering.oure_stage6c_fullmarket_2022_2024_k_frontier as s6c

FIX15 = [
    "518880","159985","159825","161226","513100","159915","511220",
    "159509","513290","159529","159981","501018","513920","511380","164824",
]

TARGETS = [
    ("B04","2023-07-27","2024-01-29"),
    ("B05","2024-01-30","2024-08-08"),
    ("B06","2024-08-09","2025-02-20"),
    ("B07","2025-02-21","2025-08-22"),
    ("B08","2025-08-25","2026-03-06"),
    ("B09","2026-03-09","2026-09-07"),
]

ROBUST_RET = {
    "B04": -0.15276825910683878,
    "B05": 0.1438503724566773,
    "B06": 0.07376398602952694,
    "B07": 0.2729717479320859,
    "B08": 0.2526681339372321,
    "B09": 0.3160724791573444,
}


def main():
    url = os.getenv("ETF_DAILY_BARS_DATABASE_URL")
    if not url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(os.getenv("OUTPUT_DIR", "oure-stage7a-fix15-compare-output"))
    out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(url), pool_pre_ping=True)
    bars = load_daily_bars(eng); bars["symbol"] = bars["symbol"].astype(str)
    feat = build_features(bars); feat["symbol"] = feat["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)

    missing = [s for s in FIX15 if s not in score.columns]
    if missing:
        raise RuntimeError(f"Fix15 missing from score columns: {missing}")

    rows = []
    risk_candidates = [s for s in score.columns if s != s6c.CASH]
    for bid, start, end in TARGETS:
        start = pd.Timestamp(start); end = pd.Timestamp(end)
        dates = cal[(cal >= start) & (cal <= end)]
        if len(dates) != 126:
            raise RuntimeError(f"{bid} expected 126 sessions, got {len(dates)}")
        ev = s6c.Eval(score, gross, dates, risk_candidates)
        rec = ev.evaluate(FIX15)
        rows.append({
            "block": bid,
            "start": str(start.date()),
            "end": str(end.date()),
            "sessions": len(dates),
            "fix15_total_return": rec["total_return"],
            "fix15_log_growth": rec["log_growth"],
            "fix15_max_drawdown": rec["max_drawdown"],
            "fix15_switch_events": rec["switch_events"],
            "fix15_mean_top1_tenure": rec["mean_top1_tenure"],
            "robust30_total_return": ROBUST_RET[bid],
        })

    df = pd.DataFrame(rows)
    df["robust_minus_fix15"] = df["robust30_total_return"] - df["fix15_total_return"]
    df.to_csv(out / "stage7a_fix15_compare.csv", index=False)

    fix15_comp = float((1.0 + df["fix15_total_return"]).prod() - 1.0)
    robust_comp = float((1.0 + df["robust30_total_return"]).prod() - 1.0)
    summary = {
        "blocks": len(df),
        "fix15_compounded_return": fix15_comp,
        "robust30_compounded_return": robust_comp,
        "robust30_minus_fix15_compounded_pp": robust_comp - fix15_comp,
        "fix15_worst_block": float(df["fix15_total_return"].min()),
        "robust30_worst_block": float(df["robust30_total_return"].min()),
        "robust30_blocks_beating_fix15": int((df["robust30_total_return"] > df["fix15_total_return"]).sum()),
        "fix15_members": FIX15,
    }
    (out / "stage7a_fix15_compare_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(df.to_string(index=False))
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
