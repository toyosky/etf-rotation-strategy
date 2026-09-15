#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage8a_opportunity30 as s8a
import optimal_universe_reverse_engineering.oure_stage8b_opportunity_k_frontier as s8b
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

START_EXEC = pd.Timestamp("2021-01-01")
HIST_SESSIONS = 378
FIX15 = tuple(s8a.FIX15)
FIX13 = tuple(sorted(s for s in FIX15 if s not in {"159825","159981"}))

REPLACEMENTS = {
    "REPLACE_513920_510880": "510880",
    "REPLACE_513920_515080": "515080",
    "REPLACE_513920_512890": "512890",
    "REPLACE_513920_513530": "513530",
}


def block_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for (variant,bno),g in df.groupby(["variant","block_no"]):
        rows.append({"variant":variant,"block_no":int(bno),**s8b.path_stats(g)})
    return pd.DataFrame(rows)


def breadth(full: pd.DataFrame, annual: pd.DataFrame, block: pd.DataFrame, reference: str) -> pd.DataFrame:
    rows=[]; tol=1e-12
    rf=full.loc[full.variant==reference].iloc[0]
    ra=annual[annual.variant==reference][["year","return"]].rename(columns={"return":"r"})
    rb=block[block.variant==reference][["block_no","total_return"]].rename(columns={"total_return":"r"})
    for variant in sorted(v for v in full.variant.unique() if v!=reference):
        vf=full.loc[full.variant==variant].iloc[0]
        va=annual[annual.variant==variant][["year","return"]].rename(columns={"return":"v"})
        vb=block[block.variant==variant][["block_no","total_return"]].rename(columns={"total_return":"v"})
        ya=va.merge(ra,on="year",how="inner"); yd=ya.v-ya.r
        bb=vb.merge(rb,on="block_no",how="inner"); bd=bb.v-bb.r
        rows.append({
            "variant":variant,"reference":reference,
            "full_return_delta":float(vf.total_return-rf.total_return),
            "mdd_delta":float(vf.mdd-rf.mdd),
            "turnover_delta":int(vf.turnover_sides-rf.turnover_sides),
            "year_better":int((yd>tol).sum()),"year_worse":int((yd<-tol).sum()),"year_tied":int((yd.abs()<=tol).sum()),
            "block_better":int((bd>tol).sum()),"block_worse":int((bd<-tol).sum()),"block_tied":int((bd.abs()<=tol).sum()),
            "mean_block_delta":float(bd.mean()) if len(bd) else None,
        })
    return pd.DataFrame(rows).sort_values("full_return_delta",ascending=False)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--database-url",default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir",default="oure-stage8j-output")
    args=ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)

    eng=create_engine(_db_url(args.database_url),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars["symbol"].astype(str).str.zfill(6); bars["date"]=pd.to_datetime(bars["date"])
    feat=build_features(bars); feat["symbol"]=feat["symbol"].astype(str).str.zfill(6)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)

    start0=int(cal.searchsorted(pd.Timestamp("2022-01-01"),side="left"))
    starts=s8a.extended_starts(cal,start0); starts_map={b:p for b,p in starts}
    first_exec_pos=int(cal.searchsorted(START_EXEC,side="left")); first_signal=max(0,first_exec_pos-1); last_signal=len(cal)-3
    need=[]
    for b,p in starts:
        next_p=starts_map.get(b+1,len(cal))
        if next_p<=first_signal or p>last_signal: continue
        if p-HIST_SESSIONS<0: continue
        if all((b-j) in starts_map for j in (1,2,3)): need.append((b,p))
    if not need: raise RuntimeError("no blocks")

    base_fix13=tuple(sorted(FIX13))
    drop_513920=tuple(sorted(s for s in FIX13 if s!="513920"))
    variants={
        "BASE_FIX13": {b:base_fix13 for b,_ in need},
        "DROP_513920": {b:drop_513920 for b,_ in need},
        "BASE_FIX15": {b:tuple(sorted(FIX15)) for b,_ in need},
    }
    for name,sym in REPLACEMENTS.items():
        members=tuple(sorted(set(drop_513920)|{sym}))
        variants[name]={b:members for b,_ in need}

    parts=[]
    for name,by in variants.items():
        parts.append(s8a.build_variant_daily(name,by,starts_map,cal,score,gross,first_signal,last_signal))
    daily=pd.concat(parts,ignore_index=True)
    daily=daily.loc[daily["execution_date"]>=START_EXEC].copy()
    annual,_=s8a.summarize(daily)
    full=pd.DataFrame([{"variant":v,**s8b.path_stats(g)} for v,g in daily.groupby("variant")])
    block=block_stats(daily)
    breadth_df=breadth(full,annual,block,"BASE_FIX13")

    daily.to_csv(out/"stage8j_daily.csv",index=False)
    annual.to_csv(out/"stage8j_annual.csv",index=False)
    full.to_csv(out/"stage8j_full.csv",index=False)
    block.to_csv(out/"stage8j_block.csv",index=False)
    breadth_df.to_csv(out/"stage8j_breadth.csv",index=False)

    summary={
        "study":"OURE Stage8J dividend role replacement","status":"completed","blocks":len(need),
        "fix13":list(base_fix13),"replacements":REPLACEMENTS,"full":full.to_dict(orient="records"),
    }
    (out/"stage8j_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print(full.sort_values("total_return",ascending=False).to_string(index=False))
    print(breadth_df.to_string(index=False))
    print(annual.to_string(index=False))

if __name__=="__main__": main()
