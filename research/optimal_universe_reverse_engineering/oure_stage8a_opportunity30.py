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
import optimal_universe_reverse_engineering.oure_stage7f_forward_monitor as s7f
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

H = 126
TRAIN_BLOCKS = 3
HIST_SESSIONS = H * TRAIN_BLOCKS
WINDOW = 21
K = 30
CASH = "511220"
START_EXEC = pd.Timestamp("2021-01-01")
COST = 0.0006
FIX15 = [
    "518880","159985","159825","161226","513100","159915","511220",
    "159509","513290","159529","159981","501018","513920","511380","164824",
]
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


def rank_pct(s: pd.Series) -> pd.Series:
    x = pd.Series(s, dtype=float)
    if x.notna().sum() <= 1:
        return pd.Series(np.where(x.notna(), 1.0, np.nan), index=x.index)
    return x.rank(method="average", pct=True)


def common_pool_for_block(bno, pos, starts_map, cal, close, meta):
    hs = [bno-3, bno-2, bno-1]
    if any(h not in starts_map for h in hs):
        raise RuntimeError(f"B{bno}: missing history blocks")
    pts = [starts_map[h] for h in hs] + [pos]
    pools = [set(s5.available_pool(close, meta, cal, int(p))) for p in pts]
    common = sorted(set.intersection(*pools))
    common = [s for s in common if s != CASH]
    if len(common) < K:
        raise RuntimeError(f"B{bno}: common pool {len(common)} < {K}")
    return common


def window_rank_matrix(score, gross, cal, hist_start, common):
    rows = []
    labels = []
    for w0 in range(hist_start, hist_start + HIST_SESSIONS, WINDOW):
        dates = pd.DatetimeIndex(cal[w0:w0+WINDOW])
        if len(dates) != WINDOW:
            raise RuntimeError("bad 21-session window")
        ev = s6c.Eval(score, gross, dates, common)
        vals = {s: float(ev.evaluate((s,))["log_growth"]) for s in common}
        r = rank_pct(pd.Series(vals))
        rows.append(r.reindex(common).to_numpy(float))
        labels.append(f"{dates[0].date()}_{dates[-1].date()}")
    arr = np.vstack(rows).T
    return arr, labels


def amount_quality_rank(amount_ratio, score, hist_dates, common):
    vals = {}
    for s in common:
        sr = score.loc[hist_dates, s]
        ar = amount_ratio.loc[hist_dates, s]
        mask = sr.notna() & ar.notna() & np.isfinite(ar) & (ar > 0)
        if int(mask.sum()) < 10:
            vals[s] = np.nan
        else:
            vals[s] = float(np.nanmedian(ar.loc[mask].to_numpy(float)))
    q = rank_pct(pd.Series(vals)).reindex(common)
    q = q.fillna(0.5)
    return q.to_numpy(float), vals


def top2_coverage(mat: np.ndarray, ids: list[int]) -> float:
    if not ids:
        return -np.inf
    v = mat[np.asarray(ids, dtype=int), :]
    if v.shape[0] == 1:
        return float(np.nanmean(v[0]))
    part = np.partition(v, kth=v.shape[0]-2, axis=0)[-2:, :]
    return float(np.nanmean(part))


def greedy_select(mat: np.ndarray, common: list[str]) -> tuple[str,...]:
    selected: list[int] = []
    remaining = set(range(len(common)))
    mean_r = np.nanmean(mat, axis=1)
    for _ in range(K):
        best = None
        best_key = None
        for j in remaining:
            sc = top2_coverage(mat, selected + [j])
            key = (sc, float(mean_r[j]), -j)
            if best_key is None or key > best_key:
                best_key = key; best = j
        if best is None:
            raise RuntimeError("greedy selection failed")
        selected.append(best); remaining.remove(best)
    return tuple(sorted(common[j] for j in selected))


def select_opportunity_block(bno, pos, starts_map, cal, score, gross, close, meta, amount_ratio):
    common = common_pool_for_block(bno, pos, starts_map, cal, close, meta)
    hist_start = pos - HIST_SESSIONS
    if hist_start < 0:
        raise RuntimeError(f"B{bno}: not enough 378-session history")
    hist_dates = pd.DatetimeIndex(cal[hist_start:pos])
    rank_mat, labels = window_rank_matrix(score, gross, cal, hist_start, common)
    members_plain = greedy_select(rank_mat, common)
    aq, raw_amount = amount_quality_rank(amount_ratio, score, hist_dates, common)
    rank_amount = 0.5 * rank_mat + 0.5 * aq[:, None]
    members_amount = greedy_select(rank_amount, common)
    idx = {s:i for i,s in enumerate(common)}
    def cov(members, mat):
        return top2_coverage(mat, [idx[s] for s in members])
    return {
        "block_no": int(bno),
        "decision_date": str(pd.Timestamp(cal[pos]).date()),
        "common_pool_n": int(len(common)),
        "window_n": int(rank_mat.shape[1]),
        "members_plain": members_plain,
        "members_amount": members_amount,
        "plain_coverage": cov(members_plain, rank_mat),
        "amount_coverage": cov(members_amount, rank_amount),
        "plain_raw_coverage": cov(members_plain, rank_mat),
        "amount_raw_coverage": cov(members_amount, rank_mat),
        "plain_amount_quality_mean": float(np.mean([aq[idx[s]] for s in members_plain])),
        "amount_amount_quality_mean": float(np.mean([aq[idx[s]] for s in members_amount])),
        "window_labels": labels,
    }


def choose_target(score, d, members):
    risk_members = [s for s in members if s != CASH and s in score.columns]
    vals = score.loc[d, risk_members].astype(float)
    vals = vals[np.isfinite(vals)]
    if vals.empty:
        return None
    risk = str(vals.idxmax()); riskv = float(vals.loc[risk])
    cashv = float(score.at[d, CASH]) if CASH in score.columns and pd.notna(score.at[d, CASH]) else -np.inf
    return risk if np.isfinite(riskv) and riskv > cashv else None


def build_variant_daily(name, universe_by_block, starts_map, cal, score, gross, first_signal, last_signal):
    rows = []
    prev = None
    for bno, pos in sorted(starts_map.items(), key=lambda kv: kv[1]):
        if bno not in universe_by_block:
            continue
        next_pos = starts_map.get(bno+1, len(cal))
        lo = max(pos, first_signal); hi = min(next_pos - 1, last_signal)
        if hi < lo:
            continue
        members = universe_by_block[bno]
        for i in range(lo, hi+1):
            d = pd.Timestamp(cal[i])
            target = choose_target(score, d, members)
            if target == prev:
                sides = 0
            elif target is None or prev is None:
                sides = 1
            else:
                sides = 2
            g = 0.0
            if target is not None:
                v = gross.at[d, target]
                g = float(v) if pd.notna(v) and np.isfinite(v) else 0.0
            net = (1.0 + g) * (1.0 - COST * sides) - 1.0
            rows.append({
                "variant": name,
                "signal_date": d,
                "execution_date": pd.Timestamp(cal[i+1]),
                "return_end_date": pd.Timestamp(cal[i+2]),
                "block_no": bno,
                "target": target,
                "sides": sides,
                "gross": g,
                "net": net,
            })
            prev = target
    return pd.DataFrame(rows)


def summarize(daily):
    rows = []
    for (variant, year), g in daily.groupby(["variant", daily["execution_date"].dt.year]):
        if year < 2021 or year > 2026:
            continue
        r = g["net"].to_numpy(float)
        eq = np.cumprod(1.0+r)
        peak = np.maximum.accumulate(np.r_[1.0, eq])[1:]
        mdd = float(np.min(eq/peak-1.0))
        rows.append({
            "variant": variant, "year": int(year), "sessions": int(len(g)),
            "return": float(np.prod(1.0+r)-1.0), "mdd": mdd,
            "turnover_sides": int(g["sides"].sum()),
        })
    ann = pd.DataFrame(rows)
    full = []
    for variant, g in daily.groupby("variant"):
        r = g["net"].to_numpy(float)
        eq = np.cumprod(1.0+r)
        peak = np.maximum.accumulate(np.r_[1.0, eq])[1:]
        full.append({
            "variant": variant,
            "total_return": float(np.prod(1.0+r)-1.0),
            "mdd": float(np.min(eq/peak-1.0)),
            "turnover_sides": int(g["sides"].sum()),
            "sessions": int(len(g)),
        })
    return ann, pd.DataFrame(full)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage8a-output")
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

    amount = bars.pivot(index="date", columns="symbol", values="amount").reindex(index=cal, columns=score.columns)
    amount_med60 = amount.rolling(60, min_periods=20).median().shift(1)
    amount_ratio = amount / amount_med60

    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    starts = extended_starts(cal, start0)
    starts_map = {b:p for b,p in starts}
    first_exec_pos = int(cal.searchsorted(START_EXEC, side="left"))
    first_signal = max(0, first_exec_pos - 1)
    last_signal = len(cal) - 3

    need = []
    for b,p in starts:
        next_p = starts_map.get(b+1, len(cal))
        if next_p <= first_signal or p > last_signal:
            continue
        if p - HIST_SESSIONS < 0:
            continue
        if all((b-j) in starts_map for j in (1,2,3)):
            need.append((b,p))
    if not need:
        raise RuntimeError("no blocks")

    sel_rows = []
    old_by = {}; opp_by = {}; amt_by = {}
    for bno,pos in need:
        old = s7f.select_universe(bno, pos, starts_map, cal, score, gross, close, meta)
        if bno == 10 and tuple(old["members"]) != EXPECTED_B10:
            raise RuntimeError("B10 old Robust30 reproduction failed")
        new = select_opportunity_block(bno, pos, starts_map, cal, score, gross, close, meta, amount_ratio)
        old_by[bno] = tuple(old["members"])
        opp_by[bno] = tuple(new["members_plain"])
        amt_by[bno] = tuple(new["members_amount"])
        sel_rows.append({
            "block_no": bno,
            "decision_date": new["decision_date"],
            "common_pool_n": new["common_pool_n"],
            "old_robust_members": ",".join(old_by[bno]),
            "opportunity30_members": ",".join(opp_by[bno]),
            "opportunity30_amount_members": ",".join(amt_by[bno]),
            "opportunity30_coverage": new["plain_coverage"],
            "opportunity30_amount_score_coverage": new["amount_coverage"],
            "opportunity30_amount_raw_coverage": new["amount_raw_coverage"],
            "opportunity30_amount_quality_mean": new["plain_amount_quality_mean"],
            "opportunity30_amount_variant_quality_mean": new["amount_amount_quality_mean"],
            "opp_overlap_fix15": len(set(opp_by[bno]) & set(FIX15)),
            "amt_overlap_fix15": len(set(amt_by[bno]) & set(FIX15)),
            "old_overlap_fix15": len(set(old_by[bno]) & set(FIX15)),
        })

    fix_by = {b: tuple(FIX15) for b,_ in need}
    dfs = [
        build_variant_daily("OLD_ROBUST30", old_by, starts_map, cal, score, gross, first_signal, last_signal),
        build_variant_daily("OPPORTUNITY30", opp_by, starts_map, cal, score, gross, first_signal, last_signal),
        build_variant_daily("OPPORTUNITY30_AMOUNT", amt_by, starts_map, cal, score, gross, first_signal, last_signal),
        build_variant_daily("FIX15_BENCHMARK", fix_by, starts_map, cal, score, gross, first_signal, last_signal),
    ]
    daily = pd.concat(dfs, ignore_index=True)
    daily = daily.loc[(daily["execution_date"] >= START_EXEC)].copy()
    ann, full = summarize(daily)

    pd.DataFrame(sel_rows).to_csv(out/"stage8a_selections.csv", index=False)
    daily.to_csv(out/"stage8a_daily.csv", index=False)
    ann.to_csv(out/"stage8a_annual.csv", index=False)
    full.to_csv(out/"stage8a_full.csv", index=False)

    current = pd.DataFrame(sel_rows).sort_values("block_no").iloc[-1].to_dict()
    summary = {
        "study": "OURE Stage8A opportunity-coverage universe with amount-aware variant",
        "status": "completed",
        "selection_uses_fix15": False,
        "history_sessions": HIST_SESSIONS,
        "subwindow_sessions": WINDOW,
        "subwindows": HIST_SESSIONS // WINDOW,
        "k": K,
        "coverage_definition": "mean across 21d windows of the average of the best two selected singleton OLS performance percentile ranks",
        "amount_definition": "median current amount / strictly-prior 60-session median amount on OLS-eligible days, cross-sectional percentile; amount-aware matrix = 0.5*opportunity rank + 0.5*amount-quality rank",
        "full_period": full.set_index("variant").to_dict(orient="index"),
        "current_selection": current,
    }
    (out/"stage8a_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print("\nANNUAL\n", ann.to_string(index=False))

if __name__ == "__main__":
    main()
