#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage5_history_transfer as s5
import optimal_universe_reverse_engineering.oure_stage6c_fullmarket_2022_2024_k_frontier as s6c
import optimal_universe_reverse_engineering.oure_stage6f_rf_surrogate_value as s6g
import optimal_universe_reverse_engineering.oure_stage7b_quarterly_robust_horizon_friction as s7b
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

SEED = 20260914
H = 126
K = 30
TRAIN_BLOCKS = 3
FREEZE_DATE = pd.Timestamp("2026-09-15")
COSTS = [0.0006, 0.0012, 0.0020]


def rank_pct(x: pd.Series) -> pd.Series:
    return s6g.rank_pct(pd.Series(x, dtype=float))


def deployment_starts(cal: pd.DatetimeIndex, start0: int):
    out, b, pos = [], 1, int(start0)
    while pos <= len(cal) - 1:
        out.append((b, pos)); b += 1; pos += H
    return out


def select_universe(bno: int, pos: int, starts_map: dict[int, int], cal, score, gross, close, meta):
    hist_bnos = [bno-3, bno-2, bno-1]
    if any(x not in starts_map for x in hist_bnos):
        raise RuntimeError(f"B{bno:02d}: insufficient completed historical blocks")
    hist = [(hb, starts_map[hb]) for hb in hist_bnos]
    pools = [set(s5.available_pool(close, meta, cal, int(hp))) for _, hp in hist]
    pools.append(set(s5.available_pool(close, meta, cal, int(pos))))
    common = sorted(set.intersection(*pools))
    if len(common) < K:
        raise RuntimeError(f"B{bno:02d}: common pool too small {len(common)}")

    recent_dates = pd.DatetimeIndex(cal[pos-H:pos])
    recent_ev = s6c.Eval(score, gross, recent_dates, common)
    rng = np.random.default_rng(SEED + bno * 1009)
    combo_family, _, _ = s6g.build_family_library(recent_ev, common, rng)
    combos = list(combo_family.keys())
    hist_evs = [s6c.Eval(score, gross, pd.DatetimeIndex(cal[hp:hp+H]), common) for _, hp in hist]

    rows = []
    for u in combos:
        vals = [float(ev.evaluate(u)["log_growth"]) for ev in hist_evs]
        rows.append({"members": ",".join(u), "hist1": vals[0], "hist2": vals[1], "hist3": vals[2]})
    df = pd.DataFrame(rows)
    for j in (1,2,3):
        df[f"r{j}"] = rank_pct(df[f"hist{j}"]).to_numpy()
    rv = df[["r1","r2","r3"]].to_numpy(float)
    df["median_rank"] = np.median(rv, axis=1)
    df["q25_rank"] = np.quantile(rv, 0.25, axis=1)
    df["robust_score"] = 0.5 * df["median_rank"] + 0.5 * df["q25_rank"]
    win = df.nlargest(1, "robust_score").iloc[0]
    members = tuple(str(win["members"]).split(","))
    return {
        "block_no": int(bno),
        "decision_pos": int(pos),
        "decision_date": pd.Timestamp(cal[pos]),
        "members": members,
        "robust_score": float(win["robust_score"]),
        "min_hist_rank": float(min(win["r1"], win["r2"], win["r3"])),
        "hist_ranks": [float(win["r1"]), float(win["r2"]), float(win["r3"])],
        "common_pool_n": int(len(common)),
        "candidate_n": int(len(df)),
    }


def target_series(score, gross, dates: pd.DatetimeIndex, members: tuple[str, ...]):
    if len(dates) == 0:
        return []
    ev = s6c.Eval(score, gross, dates, sorted(set(members)))
    return s7b.target_symbols(ev, members)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage7f-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng); bars["symbol"] = bars["symbol"].astype(str)
    feat = build_features(bars); feat["symbol"] = feat["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)
    meta = pd.read_sql_query(text("select symbol,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    latest_pos = len(cal) - 1
    latest_date = pd.Timestamp(cal[latest_pos])
    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    starts = deployment_starts(cal, start0)
    starts_map = {b:p for b,p in starts}
    eligible_starts = [(b,p) for b,p in starts if b >= 4 and p <= latest_pos]
    if not eligible_starts:
        raise RuntimeError("No deployable 126-session Universe block")

    # Cache deterministic Universe selections for every observed deployment block.
    selections = {}
    for bno, pos in eligible_starts:
        selections[bno] = select_universe(bno, pos, starts_map, cal, score, gross, close, meta)

    active_bno, active_pos = max(eligible_starts, key=lambda x: x[1])
    active = selections[active_bno]
    current_target = s7b.one_day_target(score, gross, latest_date, active["members"])
    sessions_elapsed = latest_pos - active_pos
    sessions_to_refresh = max(0, H - sessions_elapsed)

    universe_df = pd.DataFrame({
        "block": [f"B{active_bno:02d}"] * len(active["members"]),
        "decision_date": [str(active["decision_date"].date())] * len(active["members"]),
        "symbol": list(active["members"]),
    })
    universe_df.to_csv(out / "stage7f_current_universe.csv", index=False)

    # Prospective path only: sessions strictly after the research freeze date.
    fwd_dates = pd.DatetimeIndex([d for d in cal if pd.Timestamp(d) > FREEZE_DATE])
    daily_rows = []
    prev_target = None
    if len(fwd_dates):
        # Walk through observed scheduled blocks; select each Universe only from prior completed history.
        for bno, pos in eligible_starts:
            next_pos = starts_map.get(bno + 1, latest_pos + 1)
            block_dates = pd.DatetimeIndex([d for i,d in enumerate(cal) if i >= pos and i < next_pos and pd.Timestamp(d) > FREEZE_DATE])
            if len(block_dates) == 0:
                continue
            members = selections[bno]["members"]
            syms = target_series(score, gross, block_dates, members)
            for d, sym in zip(block_dates, syms):
                if sym == prev_target:
                    sides = 0
                elif sym is None or prev_target is None:
                    sides = 1
                else:
                    sides = 2
                g = 0.0 if sym is None else float(gross.loc[d, sym])
                if not np.isfinite(g):
                    g = 0.0
                row = {"date": str(pd.Timestamp(d).date()), "universe_block": f"B{bno:02d}", "target": sym, "gross": g, "sides": sides}
                for c in COSTS:
                    bp = int(round(c*10000))
                    net = (1.0 + g) * (1.0 - c*sides) - 1.0
                    row[f"net_{bp}bp"] = float(net)
                    row[f"log_net_{bp}bp"] = float(np.log1p(net))
                daily_rows.append(row)
                prev_target = sym
    daily = pd.DataFrame(daily_rows)
    if len(daily):
        for c in COSTS:
            bp = int(round(c*10000))
            daily[f"cum_return_{bp}bp"] = np.exp(daily[f"log_net_{bp}bp"].cumsum()) - 1.0
    else:
        daily = pd.DataFrame(columns=["date","universe_block","target","gross","sides","net_6bp","log_net_6bp","net_12bp","log_net_12bp","net_20bp","log_net_20bp","cum_return_6bp","cum_return_12bp","cum_return_20bp"])
    daily.to_csv(out / "stage7f_forward_daily.csv", index=False)

    snapshot = {
        "study": "OURE Stage7F frozen Robust30 prospective monitor",
        "status": "active",
        "research_freeze_date": str(FREEZE_DATE.date()),
        "prospective_start_rule": "sessions strictly after 2026-09-15",
        "latest_market_data_date": str(latest_date.date()),
        "active_universe_block": f"B{active_bno:02d}",
        "active_universe_decision_date": str(active["decision_date"].date()),
        "active_universe_robust_score": active["robust_score"],
        "active_universe_min_hist_rank": active["min_hist_rank"],
        "active_universe_hist_ranks": active["hist_ranks"],
        "active_universe_common_pool_n": active["common_pool_n"],
        "active_universe_candidate_n": active["candidate_n"],
        "current_ols_target": current_target,
        "sessions_elapsed_in_universe": int(sessions_elapsed),
        "sessions_until_next_scheduled_refresh": int(sessions_to_refresh),
        "prospective_sessions": int(len(daily)),
        "prospective_turnover_sides": int(daily["sides"].sum()) if len(daily) else 0,
        "prospective_total_return_6bp": float(daily["cum_return_6bp"].iloc[-1]) if len(daily) else None,
        "prospective_total_return_12bp": float(daily["cum_return_12bp"].iloc[-1]) if len(daily) else None,
        "prospective_total_return_20bp": float(daily["cum_return_20bp"].iloc[-1]) if len(daily) else None,
        "checkpoints": [21,63,126],
    }
    (out / "stage7f_snapshot.json").write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
