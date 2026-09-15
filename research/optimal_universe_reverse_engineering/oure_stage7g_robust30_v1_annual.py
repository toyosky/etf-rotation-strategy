#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import cluster90_resistance_score_v1_test as v1lib
import optimal_universe_reverse_engineering.oure_stage7f_forward_monitor as s7f
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

H = 126
START_EXEC = pd.Timestamp("2021-01-01")
CASH = "511220"
COSTS = [0.0006, 0.0012, 0.0020]
RES_THRESHOLD = 75.0
EXPECTED_B10 = (
    "159518","159519","159658","159663","159687","159782","159811","159915","159949","159977",
    "159994","510570","512770","513220","513310","513500","513530","515700","515920","516640",
    "517520","517770","518880","560780","560800","561300","588160","588260","588320","588800",
)


def extended_starts(cal: pd.DatetimeIndex, start0: int) -> list[tuple[int,int]]:
    out = []
    b, pos = 1, int(start0)
    while pos <= len(cal) - 1:
        out.append((b, pos)); b += 1; pos += H
    b, pos = 0, int(start0) - H
    while pos >= 0:
        out.append((b, pos)); b -= 1; pos -= H
    return sorted(out, key=lambda x: x[1])


def raw_score_wide(feat: pd.DataFrame, cal: pd.DatetimeIndex, syms: list[str]) -> pd.DataFrame:
    z = feat.copy(); z["symbol"] = z["symbol"].astype(str)
    return z.pivot(index="date", columns="symbol", values="score").reindex(index=cal, columns=syms)


def choose_raw_target(score: pd.DataFrame, d: pd.Timestamp, members: tuple[str,...]) -> str | None:
    vals = score.loc[d, list(members)].astype(float)
    vals = vals[np.isfinite(vals)]
    if vals.empty:
        return None
    risk = str(vals.idxmax())
    riskv = float(vals.loc[risk])
    cashv = float(score.at[d, CASH]) if CASH in score.columns and pd.notna(score.at[d, CASH]) else -np.inf
    return risk if np.isfinite(riskv) and riskv > cashv else None


def annual_mdd(r: np.ndarray) -> float:
    if len(r) == 0:
        return np.nan
    eq = np.cumprod(1.0 + np.asarray(r, float))
    peak = np.maximum.accumulate(np.r_[1.0, eq])[1:]
    dd = eq / peak - 1.0
    return float(np.min(dd))


def target_sides(targets: list[str | None]) -> np.ndarray:
    sides = np.zeros(len(targets), dtype=np.int8)
    if not targets:
        return sides
    prev = targets[0]
    # Position is already carried into the requested window by warm-up; the caller
    # computes sides on the full warm-up path, so this helper is not used for that path.
    for i in range(1, len(targets)):
        cur = targets[i]
        if cur == prev:
            s = 0
        elif cur is None or prev is None:
            s = 1
        else:
            s = 2
        sides[i] = s; prev = cur
    return sides


def divergence_stats(df: pd.DataFrame) -> dict:
    z = df.loc[df["execution_date"] >= START_EXEC].copy()
    z["different"] = z["baseline_target"].fillna("__CASH__") != z["v1_target"].fillna("__CASH__")
    if not bool(z["different"].any()):
        return {"segments": 0, "v1_win_share_6bp": None, "alpha_pp_sum_6bp": 0.0}
    z["seg"] = (z["different"] != z["different"].shift(fill_value=False)).cumsum()
    alphas = []
    for _, g in z.loc[z["different"]].groupby("seg"):
        rb = float(np.prod(1.0 + g["baseline_net_6bp"].to_numpy(float)) - 1.0)
        rv = float(np.prod(1.0 + g["v1_net_6bp"].to_numpy(float)) - 1.0)
        alphas.append((rv-rb)*100.0)
    a = np.asarray(alphas, float)
    return {
        "segments": int(len(a)),
        "v1_win_share_6bp": float(np.mean(a > 0)),
        "alpha_pp_mean_6bp": float(np.mean(a)),
        "alpha_pp_median_6bp": float(np.median(a)),
        "alpha_pp_sum_6bp": float(np.sum(a)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage7g-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng); bars["symbol"] = bars["symbol"].astype(str)
    feat = build_features(bars); feat["symbol"] = feat["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)
    syms = list(score.columns.astype(str))
    raw_score = raw_score_wide(feat, cal, syms)
    raw_delta = raw_score.diff()
    meta = pd.read_sql_query(text("select symbol,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    if len(cal) < 3:
        raise RuntimeError("insufficient market calendar")
    last_signal_pos = len(cal) - 3
    last_signal_date = pd.Timestamp(cal[last_signal_pos])
    last_exec_date = pd.Timestamp(cal[last_signal_pos + 1])
    last_return_end = pd.Timestamp(cal[last_signal_pos + 2])

    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    starts = extended_starts(cal, start0)
    starts_map = {b:p for b,p in starts}

    # Identify the signal immediately before the first 2021 execution session.
    first_exec_pos = int(cal.searchsorted(START_EXEC, side="left"))
    first_signal_needed = max(0, first_exec_pos - 1)
    active_candidates = [(b,p) for b,p in starts if p <= first_signal_needed]
    if not active_candidates:
        raise RuntimeError("no block active before requested start")
    warm_bno, warm_pos = max(active_candidates, key=lambda x:x[1])

    # Build every Robust30 needed for warm-up through the last fully evaluable signal.
    needed_blocks = []
    for b,p in starts:
        np_ = starts_map.get(b+1, len(cal))
        if np_ <= warm_pos or p > last_signal_pos:
            continue
        if all(x in starts_map for x in (b-3,b-2,b-1)):
            needed_blocks.append((b,p))
    if not needed_blocks or needed_blocks[0][0] != warm_bno:
        raise RuntimeError(f"earliest requested block B{warm_bno} lacks 3 completed history blocks")

    selections = {}
    selection_rows = []
    for bno,pos in needed_blocks:
        sel = s7f.select_universe(bno, pos, starts_map, cal, score, gross, close, meta)
        selections[bno] = sel
        selection_rows.append({
            "block_no": bno,
            "block": f"B{bno:+03d}",
            "decision_date": str(sel["decision_date"].date()),
            "robust_score": sel["robust_score"],
            "min_hist_rank": sel["min_hist_rank"],
            "hist_r1": sel["hist_ranks"][0],
            "hist_r2": sel["hist_ranks"][1],
            "hist_r3": sel["hist_ranks"][2],
            "common_pool_n": sel["common_pool_n"],
            "candidate_n": sel["candidate_n"],
            "members": ",".join(sel["members"]),
        })

    if 10 in selections:
        got = tuple(selections[10]["members"])
        if got != EXPECTED_B10:
            raise RuntimeError(f"B10 reproduction guard failed: {got}")

    # Build raw daily Top1 path from warm-up block onward.
    rows = []
    for bno,pos in needed_blocks:
        next_pos = starts_map.get(bno+1, len(cal))
        end_pos = min(next_pos - 1, last_signal_pos)
        if end_pos < pos:
            continue
        members = tuple(selections[bno]["members"])
        for i in range(pos, end_pos + 1):
            d = pd.Timestamp(cal[i])
            challenger = choose_raw_target(score, d, members)
            sd = np.nan
            if challenger is not None and challenger in raw_delta.columns:
                v = raw_delta.at[d, challenger]
                sd = float(v) if pd.notna(v) and np.isfinite(v) else np.nan
            rows.append({
                "signal_pos": i,
                "signal_date": d,
                "execution_date": pd.Timestamp(cal[i+1]),
                "return_end_date": pd.Timestamp(cal[i+2]),
                "block_no": bno,
                "block": f"B{bno:+03d}",
                "members": members,
                "raw_target": challenger,
                "score_delta_new": sd,
            })
    daily = pd.DataFrame(rows).sort_values("signal_pos").reset_index(drop=True)
    if daily.empty:
        raise RuntimeError("no daily path")

    # Profile only symbols that ever become a raw challenger.
    needed_symbols = set(daily["raw_target"].dropna().astype(str).unique())
    profiles = v1lib.build_needed_profiles(bars, needed_symbols)
    prof = profiles.set_index(["date","symbol"])["resistance_pct252"].to_dict()

    # Sequential baseline and V1 states. Warm-up is retained so Jan-2021 does not
    # receive an artificial entry cost if a position was already held in 2020.
    base_cur = None
    v1_cur = None
    event_rows = []
    base_targets = []
    v1_targets = []
    base_sides = []
    v1_sides = []
    base_prev = None
    v1_prev = None

    for _, r in daily.iterrows():
        d = pd.Timestamp(r["signal_date"])
        challenger = r["raw_target"] if pd.notna(r["raw_target"]) else None
        challenger = str(challenger) if challenger is not None else None
        members = tuple(r["members"])

        # Baseline is raw target-state output.
        base_cur = challenger

        decision = "HOLD"
        rp = np.nan
        sd = float(r["score_delta_new"]) if pd.notna(r["score_delta_new"]) else np.nan
        old = v1_cur
        if challenger == v1_cur:
            decision = "HOLD"
        elif challenger is None:
            v1_cur = None
            decision = "EXIT_CASH"
        elif v1_cur is None:
            v1_cur = challenger
            decision = "ENTER"
        else:
            cashv = float(score.at[d, CASH]) if CASH in score.columns and pd.notna(score.at[d, CASH]) else -np.inf
            oldv = float(score.at[d, v1_cur]) if v1_cur in score.columns and pd.notna(score.at[d, v1_cur]) else np.nan
            incumbent_valid = bool(v1_cur in set(members) and np.isfinite(oldv) and oldv > cashv)
            rp0 = prof.get((d, challenger), np.nan)
            rp = float(rp0) if pd.notna(rp0) and np.isfinite(rp0) else np.nan
            if not incumbent_valid:
                v1_cur = challenger
                decision = "SWITCH_OLD_INVALID"
            elif math.isfinite(rp) and rp >= RES_THRESHOLD and math.isfinite(sd) and sd <= 0.0:
                decision = "VETO_V1"
            else:
                v1_cur = challenger
                decision = "SWITCH_NORMAL"

        def sides(cur, prev):
            if cur == prev: return 0
            if cur is None or prev is None: return 1
            return 2
        bs = sides(base_cur, base_prev)
        vs = sides(v1_cur, v1_prev)
        base_prev = base_cur; v1_prev = v1_cur
        base_targets.append(base_cur); v1_targets.append(v1_cur)
        base_sides.append(bs); v1_sides.append(vs)

        if decision not in ("HOLD",):
            event_rows.append({
                "signal_date": str(d.date()),
                "execution_date": str(pd.Timestamp(r["execution_date"]).date()),
                "block": r["block"],
                "incumbent": old,
                "challenger": challenger,
                "resistance_pct252": rp,
                "score_delta_new": sd,
                "decision": decision,
                "v1_target_after": v1_cur,
            })

    daily["baseline_target"] = base_targets
    daily["v1_target"] = v1_targets
    daily["baseline_sides"] = base_sides
    daily["v1_sides"] = v1_sides

    for i, r in daily.iterrows():
        d = pd.Timestamp(r["signal_date"])
        for name in ("baseline", "v1"):
            target = r[f"{name}_target"]
            g = 0.0
            if pd.notna(target) and target is not None:
                v = gross.at[d, str(target)] if str(target) in gross.columns else np.nan
                g = float(v) if pd.notna(v) and np.isfinite(v) else 0.0
            daily.at[i, f"{name}_gross"] = g
            sdcount = int(r[f"{name}_sides"])
            for c in COSTS:
                bp = int(round(c*10000))
                net = (1.0 + g) * (1.0 - c * sdcount) - 1.0
                daily.at[i, f"{name}_net_{bp}bp"] = float(net)

    # Requested window only; warm-up rows stay out of reported performance.
    rpt = daily.loc[daily["execution_date"] >= START_EXEC].copy()
    rpt = rpt.loc[rpt["execution_date"] <= last_exec_date].copy()
    events = pd.DataFrame(event_rows)
    if len(events):
        events["execution_date"] = pd.to_datetime(events["execution_date"])

    annual_rows = []
    for year in range(2021, 2027):
        g = rpt.loc[rpt["execution_date"].dt.year == year].copy()
        if g.empty:
            continue
        rec = {
            "year": year,
            "sessions": int(len(g)),
            "start_execution_date": str(g["execution_date"].iloc[0].date()),
            "end_execution_date": str(g["execution_date"].iloc[-1].date()),
            "baseline_turnover_sides": int(g["baseline_sides"].sum()),
            "v1_turnover_sides": int(g["v1_sides"].sum()),
            "v1_veto_count": int(events.loc[(events["execution_date"].dt.year == year) & (events["decision"] == "VETO_V1")].shape[0]) if len(events) else 0,
        }
        for c in COSTS:
            bp = int(round(c*10000))
            rb = g[f"baseline_net_{bp}bp"].to_numpy(float)
            rv = g[f"v1_net_{bp}bp"].to_numpy(float)
            bre = float(np.prod(1.0 + rb) - 1.0)
            vre = float(np.prod(1.0 + rv) - 1.0)
            rec[f"baseline_return_{bp}bp"] = bre
            rec[f"v1_return_{bp}bp"] = vre
            rec[f"v1_minus_baseline_pp_{bp}bp"] = (vre-bre)*100.0
            rec[f"baseline_mdd_{bp}bp"] = annual_mdd(rb)
            rec[f"v1_mdd_{bp}bp"] = annual_mdd(rv)
        annual_rows.append(rec)
    annual = pd.DataFrame(annual_rows)

    full = {}
    for c in COSTS:
        bp = int(round(c*10000))
        rb = rpt[f"baseline_net_{bp}bp"].to_numpy(float)
        rv = rpt[f"v1_net_{bp}bp"].to_numpy(float)
        full[f"baseline_total_return_{bp}bp"] = float(np.prod(1.0 + rb) - 1.0)
        full[f"v1_total_return_{bp}bp"] = float(np.prod(1.0 + rv) - 1.0)
        full[f"baseline_mdd_{bp}bp"] = annual_mdd(rb)
        full[f"v1_mdd_{bp}bp"] = annual_mdd(rv)

    summary = {
        "study": "OURE Stage7G Robust30 + frozen V1 annual backtest",
        "status": "completed",
        "window": {
            "requested_start_execution_date": str(START_EXEC.date()),
            "first_reported_execution_date": str(rpt["execution_date"].iloc[0].date()),
            "last_fully_evaluable_signal_date": str(last_signal_date.date()),
            "last_reported_execution_date": str(last_exec_date.date()),
            "last_return_end_date": str(last_return_end.date()),
            "reported_sessions": int(len(rpt)),
        },
        "robust30": {
            "anchor": "first trading session on/after 2022-01-01, extended backward by exact 126-session steps for 2021 diagnostic",
            "horizon": H,
            "selected_blocks": int(len(selections)),
            "b10_reproduction_guard": bool(10 not in selections or tuple(selections[10]["members"]) == EXPECTED_B10),
        },
        "v1": {
            "rule": "ResistancePct252>=75 AND raw ScoreDelta_new<=0 veto pure rank switch",
            "profile_lookback": 120,
            "percentile_lookback": 252,
            "minimum_profile_history": 60,
            "profile_symbols": int(len(needed_symbols)),
            "veto_count_reported": int(events.loc[(events["execution_date"] >= START_EXEC) & (events["decision"] == "VETO_V1")].shape[0]) if len(events) else 0,
        },
        "full_period": full,
        "divergence": divergence_stats(rpt),
        "primary_cost_bp_per_side": 6,
        "annual_primary": annual[["year","sessions","baseline_return_6bp","v1_return_6bp","v1_minus_baseline_pp_6bp","baseline_mdd_6bp","v1_mdd_6bp","baseline_turnover_sides","v1_turnover_sides","v1_veto_count"]].to_dict("records"),
    }

    sel_df = pd.DataFrame(selection_rows)
    sel_df.to_csv(out / "stage7g_universe_selections.csv", index=False)
    annual.to_csv(out / "stage7g_annual.csv", index=False)
    rpt_out = rpt.copy()
    for c in ["signal_date","execution_date","return_end_date"]:
        rpt_out[c] = pd.to_datetime(rpt_out[c]).dt.strftime("%Y-%m-%d")
    rpt_out["members"] = rpt_out["members"].map(lambda x: ",".join(x) if isinstance(x, tuple) else str(x))
    rpt_out.to_csv(out / "stage7g_daily.csv", index=False)
    events.to_csv(out / "stage7g_v1_events.csv", index=False)
    (out / "stage7g_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
