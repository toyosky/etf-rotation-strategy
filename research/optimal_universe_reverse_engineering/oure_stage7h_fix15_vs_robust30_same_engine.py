#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, os, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage7g_robust30_v1_annual as s7g
import optimal_universe_reverse_engineering.oure_stage7f_forward_monitor as s7f
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

FIX15 = (
    "518880","159985","159825","161226","513100","159915","511220",
    "159509","513290","159529","159981","501018","513920","511380","164824",
)
FIX15_RISK = tuple(x for x in FIX15 if x != s7g.CASH)
COSTS = s7g.COSTS
START_EXEC = s7g.START_EXEC
H = s7g.H


def sides(cur, prev):
    if cur == prev: return 0
    if cur is None or prev is None: return 1
    return 2


def build_variant(rows, score, gross, members_by_signal, name):
    targets=[]; sidev=[]; prev=None
    out=[]
    for i,d,ed,retd in rows:
        members = members_by_signal(i)
        cur = s7g.choose_raw_target(score, d, members)
        sd = sides(cur, prev); prev = cur
        g = 0.0
        if cur is not None:
            v = gross.at[d, cur] if cur in gross.columns else np.nan
            g = float(v) if pd.notna(v) and np.isfinite(v) else 0.0
        rec={"signal_pos":i,"signal_date":d,"execution_date":ed,"return_end_date":retd,
             f"{name}_target":cur,f"{name}_sides":sd,f"{name}_gross":g}
        for c in COSTS:
            bp=int(round(c*10000))
            rec[f"{name}_net_{bp}bp"]=(1.0+g)*(1.0-c*sd)-1.0
        out.append(rec)
    return pd.DataFrame(out)


def mdd(x):
    return s7g.annual_mdd(np.asarray(x,float))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--database-url",default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir",default="oure-stage7h-output")
    args=ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)

    eng=create_engine(_db_url(args.database_url),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars["symbol"].astype(str)
    feat=build_features(bars); feat["symbol"]=feat["symbol"].astype(str)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    meta=pd.read_sql_query(text("select symbol,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"),eng)
    meta["symbol"]=meta["symbol"].astype(str)

    missing=[s for s in FIX15 if s not in score.columns]
    if missing: raise RuntimeError(f"Fix15 missing: {missing}")
    last_signal_pos=len(cal)-3
    last_exec_date=pd.Timestamp(cal[last_signal_pos+1])
    first_exec_pos=int(cal.searchsorted(START_EXEC,side="left"))
    first_signal_needed=max(0,first_exec_pos-1)

    start0=int(cal.searchsorted(pd.Timestamp("2022-01-01"),side="left"))
    starts=s7g.extended_starts(cal,start0); starts_map={b:p for b,p in starts}
    active_candidates=[(b,p) for b,p in starts if p<=first_signal_needed]
    warm_bno,warm_pos=max(active_candidates,key=lambda x:x[1])
    needed=[]
    for b,p in starts:
        np_=starts_map.get(b+1,len(cal))
        if np_<=warm_pos or p>last_signal_pos: continue
        if all(x in starts_map for x in (b-3,b-2,b-1)): needed.append((b,p))
    if not needed or needed[0][0]!=warm_bno: raise RuntimeError("Robust30 warm-up history unavailable")

    selections={}
    for b,p in needed:
        selections[b]=s7f.select_universe(b,p,starts_map,cal,score,gross,close,meta)
    if 10 in selections and tuple(selections[10]["members"])!=s7g.EXPECTED_B10:
        raise RuntimeError("B10 reproduction guard failed")

    # Map every signal to its contemporaneous frozen Robust30.
    block_intervals=[]
    for b,p in needed:
        block_intervals.append((p,min(starts_map.get(b+1,len(cal))-1,last_signal_pos),b))
    def robust_members(i):
        for a,z,b in block_intervals:
            if a<=i<=z: return tuple(selections[b]["members"])
        raise RuntimeError(f"no Robust30 block for signal {i}")

    rows=[]
    for i in range(warm_pos,last_signal_pos+1):
        rows.append((i,pd.Timestamp(cal[i]),pd.Timestamp(cal[i+1]),pd.Timestamp(cal[i+2])))
    robust=build_variant(rows,score,gross,robust_members,"robust30")
    fix15=build_variant(rows,score,gross,lambda i:FIX15_RISK,"fix15")
    daily=robust.merge(fix15,on=["signal_pos","signal_date","execution_date","return_end_date"],how="inner",validate="one_to_one")
    rpt=daily[(daily.execution_date>=START_EXEC)&(daily.execution_date<=last_exec_date)].copy()

    annual=[]
    for y in range(2021,2027):
        g=rpt[rpt.execution_date.dt.year==y]
        if g.empty: continue
        rec={"year":y,"sessions":len(g),"start":str(g.execution_date.iloc[0].date()),"end":str(g.execution_date.iloc[-1].date()),
             "robust30_turnover_sides":int(g.robust30_sides.sum()),"fix15_turnover_sides":int(g.fix15_sides.sum())}
        for c in COSTS:
            bp=int(round(c*10000))
            rr=np.asarray(g[f"robust30_net_{bp}bp"],float); rf=np.asarray(g[f"fix15_net_{bp}bp"],float)
            rret=float(np.prod(1+rr)-1); fret=float(np.prod(1+rf)-1)
            rec[f"robust30_return_{bp}bp"]=rret; rec[f"fix15_return_{bp}bp"]=fret; rec[f"robust_minus_fix15_{bp}bp_pp"]=(rret-fret)*100
            if bp==6:
                rec["robust30_mdd_6bp"]=mdd(rr); rec["fix15_mdd_6bp"]=mdd(rf)
        annual.append(rec)
    adf=pd.DataFrame(annual); adf.to_csv(out/"stage7h_annual.csv",index=False)
    rpt.to_csv(out/"stage7h_daily.csv",index=False)

    summary={"study":"OURE Stage7H Fix15 vs dynamic Robust30 same-engine","window_start":str(rpt.execution_date.iloc[0].date()),"window_end":str(rpt.execution_date.iloc[-1].date()),"years":{}}
    for _,r in adf.iterrows(): summary["years"][str(int(r.year))]={k:(float(v) if isinstance(v,(np.floating,float)) else int(v) if isinstance(v,(np.integer,int)) else v) for k,v in r.items() if k!="year"}
    full={}
    for c in COSTS:
        bp=int(round(c*10000))
        rr=np.asarray(rpt[f"robust30_net_{bp}bp"],float); rf=np.asarray(rpt[f"fix15_net_{bp}bp"],float)
        full[f"robust30_return_{bp}bp"]=float(np.prod(1+rr)-1); full[f"fix15_return_{bp}bp"]=float(np.prod(1+rf)-1); full[f"robust_minus_fix15_{bp}bp_pp"]=(full[f"robust30_return_{bp}bp"]-full[f"fix15_return_{bp}bp"])*100
        if bp==6:
            full["robust30_mdd_6bp"]=mdd(rr); full["fix15_mdd_6bp"]=mdd(rf)
    full["robust30_turnover_sides"]=int(rpt.robust30_sides.sum()); full["fix15_turnover_sides"]=int(rpt.fix15_sides.sum())
    summary["full_period"]=full; summary["fix15_members"]=list(FIX15)
    (out/"stage7h_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))

if __name__=="__main__": main()
