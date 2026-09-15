#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
import optimal_universe_reverse_engineering.oure_stage8a_opportunity30 as s8a

COST = 0.0006
CASH = "511220"
FIX15 = tuple(sorted(s8a.FIX15))
FIX13 = tuple(sorted(s for s in FIX15 if s not in {"159825", "159981"}))
FIX13_HK_DIV = tuple(sorted((set(FIX13) - {"513920"}) | {"513530"}))
VARIANTS = {
    "BASE_FIX15": FIX15,
    "FIX13_PRUNED": FIX13,
    "FIX13_HK_DIV": FIX13_HK_DIV,
}
MIN_START = pd.Timestamp("2015-01-01")


def choose_target(score: pd.DataFrame, d: pd.Timestamp, members: tuple[str, ...]):
    risk = [s for s in members if s != CASH and s in score.columns]
    vals = score.loc[d, risk].astype(float)
    vals = vals[np.isfinite(vals)]
    if vals.empty:
        return None
    sym = str(vals.idxmax()); rv = float(vals.loc[sym])
    cv = float(score.at[d, CASH]) if CASH in score.columns and pd.notna(score.at[d, CASH]) else -np.inf
    return sym if np.isfinite(rv) and rv > cv else None


def path_stats(g: pd.DataFrame) -> dict:
    r = g["net"].to_numpy(float)
    if len(r) == 0:
        return {"sessions":0,"total_return":np.nan,"mdd":np.nan,"turnover_sides":0,"switches":0,"mean_top1_tenure":np.nan}
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.r_[1.0, eq])[1:]
    targets = g["target"].fillna("__CASH__").astype(str).tolist()
    switches = int(sum(a != b for a,b in zip(targets[1:],targets[:-1])))
    runs=[]
    if targets:
        cur=targets[0]; n=1
        for x in targets[1:]:
            if x==cur: n+=1
            else: runs.append(n); cur=x; n=1
        runs.append(n)
    return {
        "sessions":int(len(g)),"total_return":float(eq[-1]-1.0),"mdd":float(np.min(eq/peak-1.0)),
        "turnover_sides":int(g["sides"].sum()),"switches":switches,
        "mean_top1_tenure":float(np.mean(runs)) if runs else np.nan,
    }


def build_path(name: str, members: tuple[str,...], cal, score, gross, start_i: int, last_i: int):
    rows=[]; prev=None
    for i in range(start_i,last_i+1):
        d=pd.Timestamp(cal[i]); target=choose_target(score,d,members)
        if target==prev: sides=0
        elif target is None or prev is None: sides=1
        else: sides=2
        g=0.0
        if target is not None:
            v=gross.at[d,target]
            g=float(v) if pd.notna(v) and np.isfinite(v) else 0.0
        net=(1.0+g)*(1.0-COST*sides)-1.0
        avail=sum(1 for s in members if s in score.columns and pd.notna(score.at[d,s]) and np.isfinite(score.at[d,s]))
        rows.append({
            "variant":name,"signal_date":d,"execution_date":pd.Timestamp(cal[i+1]),"return_end_date":pd.Timestamp(cal[i+2]),
            "target":target,"sides":sides,"gross":g,"net":net,"finite_score_members":int(avail),
        })
        prev=target
    return pd.DataFrame(rows)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--database-url",default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir",default="oure-stage8k-output")
    args=ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)

    eng=create_engine(_db_url(args.database_url),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars["symbol"].astype(str).str.zfill(6); bars["date"]=pd.to_datetime(bars["date"])
    feat=build_features(bars); feat["symbol"]=feat["symbol"].astype(str).str.zfill(6)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)

    cash_ok=score[CASH].notna() & np.isfinite(score[CASH]) & (score.index>=MIN_START)
    if not cash_ok.any(): raise RuntimeError("cash comparator never becomes valid")
    first_signal_date=pd.Timestamp(score.index[cash_ok][0])
    start_i=int(cal.get_loc(first_signal_date)); last_i=len(cal)-3

    parts=[build_path(n,m,cal,score,gross,start_i,last_i) for n,m in VARIANTS.items()]
    daily=pd.concat(parts,ignore_index=True)

    annual_rows=[]
    for (v,y),g in daily.groupby(["variant",daily["execution_date"].dt.year]):
        annual_rows.append({"variant":v,"year":int(y),**path_stats(g),
                            "avg_finite_members":float(g["finite_score_members"].mean()),
                            "min_finite_members":int(g["finite_score_members"].min()),
                            "max_finite_members":int(g["finite_score_members"].max())})
    annual=pd.DataFrame(annual_rows)

    period_rows=[]
    periods={
        "PRE2021":(None,pd.Timestamp("2020-12-31")),
        "POST2021":(pd.Timestamp("2021-01-01"),None),
        "FULL":(None,None),
    }
    for v,g0 in daily.groupby("variant"):
        for pname,(lo,hi) in periods.items():
            g=g0
            if lo is not None: g=g[g["execution_date"]>=lo]
            if hi is not None: g=g[g["execution_date"]<=hi]
            rec={"variant":v,"period":pname,**path_stats(g)}
            if len(g): rec.update({"start":str(g.execution_date.min().date()),"end":str(g.execution_date.max().date())})
            period_rows.append(rec)
    periods_df=pd.DataFrame(period_rows)

    member_rows=[]
    for v,members in VARIANTS.items():
        for s in members:
            gb=bars[bars.symbol==s]
            first_bar=pd.Timestamp(gb.date.min()).date() if len(gb) else None
            if s in score.columns:
                z=score[s].notna() & np.isfinite(score[s])
                first_score=pd.Timestamp(score.index[z][0]).date() if z.any() else None
            else: first_score=None
            member_rows.append({"variant":v,"symbol":s,"first_bar":str(first_bar) if first_bar else None,"first_finite_score":str(first_score) if first_score else None})
    member=pd.DataFrame(member_rows)

    daily.to_csv(out/"stage8k_daily.csv",index=False)
    annual.to_csv(out/"stage8k_annual.csv",index=False)
    periods_df.to_csv(out/"stage8k_periods.csv",index=False)
    member.to_csv(out/"stage8k_member_availability.csv",index=False)

    summary={
        "study":"OURE Stage8K pre-2021 extension","status":"completed","first_valid_signal":str(first_signal_date.date()),
        "first_execution":str(pd.Timestamp(cal[start_i+1]).date()),"last_execution":str(pd.Timestamp(cal[last_i+1]).date()),
        "universes":{k:list(v) for k,v in VARIANTS.items()},
        "periods":periods_df.to_dict(orient="records"),
    }
    (out/"stage8k_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    print(annual.to_string(index=False))
    print(member.to_string(index=False))

if __name__=="__main__": main()
