#!/usr/bin/env python3
"""New Stage 1: monthly Oracle Universe-size Monte Carlo.

Hindsight mechanism study only. The primary evidence is the distribution of
Frozen-OLS one-month results by Universe size K, not the best subset.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from walk_forward_candidate_pool import SIDE_COST
from walk_forward_dedup import monthly_representatives
from universe.oracle_replacement_v1 import CASH_SIGNAL

START_MONTH = pd.Period("2021-01", freq="M")
DEFAULT_SEED = 20260914
DEFAULT_SAMPLES = 120
DEFAULT_PATHS = 24
PRIMARY_DEDUP = 0.95
MIN_K = 3
MAX_K = 30
NESTED_START_K = 15


def stable_seed(base: int, *parts) -> int:
    b = "|".join([str(base), *map(str, parts)]).encode()
    return int.from_bytes(hashlib.blake2b(b, digest_size=8).digest(), "little") & 0x7FFFFFFF


def month_frames(calendar: pd.Index):
    grouped = [(p, pd.Index(s.values)) for p, s in pd.Series(calendar, index=calendar).groupby(calendar.to_period("M"))]
    for i in range(1, len(grouped) - 1):
        p, dates = grouped[i]
        np_, ndates = grouped[i + 1]
        if p < START_MONTH or np_ != p + 1:
            continue
        first = pd.Timestamp(dates[0]); nxt = pd.Timestamp(ndates[0])
        ip = calendar.get_loc(first); jp = calendar.get_loc(nxt)
        if ip == 0 or jp - ip < 2:
            continue
        prev = pd.Timestamp(calendar[ip - 1])
        # signal(prev month last day) -> hold from first monthly open; final
        # included exec day is last trading day of the month.
        signals = calendar[ip - 1:jp - 1]
        yield p, first, nxt, prev, signals


def build_wides(bars: pd.DataFrame, features: pd.DataFrame):
    cal = pd.Index(sorted(pd.to_datetime(bars["date"].unique())), name="date")
    syms = sorted(bars["symbol"].astype(str).unique())
    f = features.copy(); f["symbol"] = f["symbol"].astype(str)
    trend = ((f["annual"] > 0) & (f["r2"] > 0) & (f["score"] > 0)
             & (~f["recent_drop3"].fillna(False)))
    f["pool_score"] = f["score"].where(trend)
    f["pool_r2"] = f["r2"].where(trend)
    f["pool_slope"] = f["slope"].where(trend)
    def piv(col):
        return f.pivot(index="date", columns="symbol", values=col).reindex(index=cal, columns=syms)
    score, r2, slope = piv("pool_score"), piv("pool_r2"), piv("pool_slope")
    close = bars.pivot(index="date", columns="symbol", values="close").reindex(index=cal, columns=syms)
    op = bars.pivot(index="date", columns="symbol", values="open").reindex(index=cal, columns=syms)
    gross = op.shift(-2) / op.shift(-1) - 1.0
    ret = close.pct_change(fill_method=None)
    return cal, score, r2, slope, close, op, gross, ret


def sample_combos(items: list[str], choose_n: int, n: int, seed: int):
    total = math.comb(len(items), choose_n)
    if total <= n:
        return list(itertools.combinations(items, choose_n)), True, total
    rng = random.Random(seed); out = set()
    while len(out) < n:
        out.add(tuple(sorted(rng.sample(items, choose_n))))
    return sorted(out), False, total


def corr_metrics(ret: pd.DataFrame, hist_dates: pd.Index, pool: list[str]):
    c = ret.loc[hist_dates, pool].corr(min_periods=60).to_numpy(float)
    if c.size == 0:
        return np.nan, np.nan
    c = np.where(np.isfinite(c), c, 0.0); c = (c + c.T) / 2; np.fill_diagonal(c, 1.0)
    tri = c[np.triu_indices(len(pool), 1)]
    mean_corr = float(np.mean(tri)) if len(tri) else np.nan
    fro2 = float(np.square(c).sum())
    effective_n = len(pool) ** 2 / fro2 if fro2 > 0 else np.nan
    return mean_corr, effective_n


def winners(op: pd.DataFrame, first: pd.Timestamp, nxt: pd.Timestamp, parent: list[str]):
    r = (op.loc[nxt, parent] / op.loc[first, parent] - 1).replace([np.inf, -np.inf], np.nan).dropna()
    if r.empty:
        return set()
    q = r.quantile(.90)
    return set(r.index[r >= q].astype(str))


def evaluate(pool: list[str], signals: pd.Index, score: pd.DataFrame, r2: pd.DataFrame,
             slope: pd.DataFrame, gross: pd.DataFrame, close: pd.DataFrame,
             winner_set: set[str], mean_corr: float, effective_n: float,
             month: str, uid: str, source: str, path_id=None):
    ss = score.loc[signals, pool]
    ranked = ss.idxmax(axis=1, skipna=True)
    ranked[ss.notna().sum(axis=1) == 0] = None
    counts = ss.notna().sum(axis=1)
    prev = None; nets = []; switches = 0; sides_sum = 0; events = []
    ranked_list = []
    for i, d in enumerate(signals):
        sym = ranked.iloc[i]
        sym = str(sym) if sym is not None and pd.notna(sym) else None
        ranked_list.append(sym)
        target = None if sym in (None, CASH_SIGNAL) else sym
        if target == prev: sides = 0
        elif prev is None or target is None: sides = 1
        else: sides = 2
        if target != prev: switches += 1
        sides_sum += sides
        g = 0.0
        if target is not None:
            v = gross.at[d, target]
            g = float(v) if pd.notna(v) and np.isfinite(v) else 0.0
        nets.append((1 + g) * (1 - SIDE_COST * sides) - 1)
        changed_rank = sym is not None and (i == 0 or sym != ranked_list[i-1])
        if changed_rank:
            row = ss.iloc[i].dropna().sort_values(ascending=False)
            gap = float(row.iloc[0] - row.iloc[1]) if len(row) >= 2 else np.nan
            ev = {"month": month, "k": len(pool), "universe_id": uid, "source": source,
                  "path_id": path_id, "symbol": sym, "admission_signal_date": pd.Timestamp(d),
                  "score": float(score.at[d, sym]), "r2": float(r2.at[d, sym]),
                  "slope": float(slope.at[d, sym]), "top1_minus_top2_gap": gap}
            pos = close.index.get_loc(d); p0 = close.at[d, sym]
            for h in (1, 3, 5, 10, 20):
                ev[f"fwd{h}"] = (float(close.iloc[pos+h][sym] / p0 - 1)
                                  if pos + h < len(close) and pd.notna(p0) and pd.notna(close.iloc[pos+h][sym]) else np.nan)
            events.append(ev)
        prev = target
    for i, ev in enumerate(events):
        ev["observed_replacement_signal_date"] = events[i+1]["admission_signal_date"] if i+1 < len(events) else None
    eq = np.cumprod(1 + np.asarray(nets, float)); dd = eq / np.maximum.accumulate(eq) - 1
    vals = [x for x in ranked_list if x is not None]
    runs = []
    if vals:
        cur = vals[0]; n = 1
        for x in vals[1:]:
            if x == cur: n += 1
            else: runs.append(n); cur = x; n = 1
        runs.append(n)
    unique = set(vals)
    return ({"month": month, "k": len(pool), "universe_id": uid, "source": source, "path_id": path_id,
             "members": ",".join(sorted(pool)), "total_return": float(eq[-1]-1),
             "max_drawdown": float(dd.min()), "switches": switches, "turnover_sides": sides_sum,
             "candidate_mean": float(counts.mean()), "mean_top1_tenure": float(np.mean(runs)) if runs else np.nan,
             "winner_coverage": len(set(pool)&winner_set)/len(winner_set) if winner_set else np.nan,
             "dormant_member_share": 1-len(unique&set(pool))/len(pool),
             "mean_pairwise_corr": mean_corr, "effective_n": effective_n}, events)


def aggregate(detail: pd.DataFrame):
    mc = detail[detail.source == "same_k_mc"].copy()
    thresholds = mc.groupby("month").total_return.quantile(.90).to_dict()
    mc["month_top_decile"] = [r >= thresholds[m] for m, r in zip(mc.month, mc.total_return)]
    return mc.groupby(["month","k"], as_index=False).agg(
        n=("total_return","size"), return_mean=("total_return","mean"),
        return_p10=("total_return",lambda s:s.quantile(.10)), return_p25=("total_return",lambda s:s.quantile(.25)),
        return_median=("total_return","median"), return_p75=("total_return",lambda s:s.quantile(.75)),
        return_p90=("total_return",lambda s:s.quantile(.90)), return_best=("total_return","max"),
        return_worst=("total_return","min"), top_decile_probability=("month_top_decile","mean"),
        mdd_median=("max_drawdown","median"), switches_median=("switches","median"),
        tenure_median=("mean_top1_tenure","median"), winner_coverage_median=("winner_coverage","median"),
        dormant_share_median=("dormant_member_share","median"), effective_n_median=("effective_n","median"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--samples-per-k", type=int, default=DEFAULT_SAMPLES)
    ap.add_argument("--nested-paths", type=int, default=DEFAULT_PATHS)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--corr-threshold", type=float, default=PRIMARY_DEDUP)
    ap.add_argument("--output-dir", default="stage1-size-mc-output")
    args = ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine); bars["symbol"] = bars["symbol"].astype(str)
    features = build_features(bars); features["symbol"] = features["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, features)
    by_date, rep_stats = monthly_representatives(bars, features, args.corr_threshold)
    snapshots=[]; details=[]; events=[]
    for p, first, nxt, prev, signals in month_frames(cal):
        parent = sorted((set(by_date.get(first,set())) & set(score.columns)) | {CASH_SIGNAL})
        if len(parent) < MIN_K: continue
        snapshots += [{"month":str(p),"first_date":first,"prev_date":prev,"symbol":s,"corr_threshold":args.corr_threshold} for s in parent]
        noncash=[s for s in parent if s != CASH_SIGNAL]; win=winners(op, first, nxt, parent)
        pos=cal.get_loc(prev); hist=cal[max(0,pos-119):pos+1]
        maxk=min(MAX_K,len(parent))
        for k in range(MIN_K,maxk+1):
            combos, exhaustive, space = sample_combos(noncash,k-1,args.samples_per_k,stable_seed(args.seed,p,k,"mc"))
            for j,c in enumerate(combos):
                pool=[CASH_SIGNAL,*c]; cm,en=corr_metrics(ret,hist,pool)
                rec,ev=evaluate(pool,signals,score,r2,slope,gross,close,win,cm,en,str(p),f"{p}-k{k}-mc{j:04d}","same_k_mc")
                rec.update({"sampling_exhaustive":exhaustive,"combination_space":space}); details.append(rec); events+=ev
        startk=min(NESTED_START_K,maxk); rng=random.Random(stable_seed(args.seed,p,"nested"))
        for path in range(args.nested_paths):
            current=set(rng.sample(noncash,startk-1))|{CASH_SIGNAL}
            for k in range(startk,MIN_K-1,-1):
                pool=sorted(current); cm,en=corr_metrics(ret,hist,pool)
                rec,ev=evaluate(pool,signals,score,r2,slope,gross,close,win,cm,en,str(p),f"{p}-path{path:03d}-k{k}","nested_random_delete",path)
                details.append(rec); events+=ev
                if k>MIN_K: current.remove(rng.choice(sorted(current-{CASH_SIGNAL})))
    d=pd.DataFrame(details); e=pd.DataFrame(events); s=aggregate(d)
    pd.DataFrame(snapshots).to_csv(out/"monthly_parent_pool_snapshots.csv",index=False)
    d.to_parquet(out/"sampled_universe_detail.parquet",index=False,compression="zstd")
    e.to_parquet(out/"top1_admission_events.parquet",index=False,compression="zstd")
    s.to_csv(out/"monthly_k_distribution.csv",index=False)
    nested=d[d.source=="nested_random_delete"].copy(); rows=[]
    for (m,path),g in nested.groupby(["month","path_id"]):
        rr=dict(zip(g.k.astype(int),g.total_return.astype(float)))
        for k in range(NESTED_START_K,MIN_K,-1):
            if k in rr and k-1 in rr: rows.append({"month":m,"path_id":path,"k_from":k,"k_to":k-1,"delta":rr[k-1]-rr[k]})
    pd.DataFrame(rows).to_csv(out/"nested_15_to_3_deltas.csv",index=False)
    summary={"study":"New Stage 1 Oracle Universe Size Monte Carlo","lookahead":True,
             "status":"first_batch_completed","months":int(s.month.nunique()),"sampled_universes":int(len(d)),
             "top1_admission_events":int(len(e)),"config":{"samples_per_k":args.samples_per_k,"nested_paths":args.nested_paths,
             "seed":args.seed,"corr_threshold":args.corr_threshold,"k_min":MIN_K,"k_max":MAX_K,"nested_start_k":NESTED_START_K,
             "cash_signal":CASH_SIGNAL,"side_cost":SIDE_COST},"representative_pool_stats":rep_stats,
             "next_checks":["alternative seed convergence","corr_threshold=0.90 sensitivity","month-cluster bootstrap","Stage2 remaining-life definition"]}
    (out/"stage1_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))

if __name__ == "__main__":
    main()
