#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage8a_opportunity30 as s8a
import optimal_universe_reverse_engineering.oure_stage8b_opportunity_k_frontier as s8b
import optimal_universe_reverse_engineering.oure_stage8e_economic_coverage as s8e
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

START_EXEC = pd.Timestamp("2021-01-01")
HIST_SESSIONS = 378
FIX15 = tuple(s8a.FIX15)

DROP_MAP = {
    "DROP_CN_FINANCIALS": {"CN_FINANCIALS"},
    "DROP_CN_HEALTHCARE": {"CN_HEALTHCARE"},
    "DROP_CN_VALUE_DEFENSIVE": {"CN_VALUE_DEFENSIVE"},
    "DROP_CN_CONSUMER": {"CN_CONSUMER"},
    "DROP_TOP3_BAD_SLOTS": {"CN_FINANCIALS","CN_HEALTHCARE","CN_VALUE_DEFENSIVE"},
    "DROP_TOP4_BAD_SLOTS": {"CN_FINANCIALS","CN_HEALTHCARE","CN_VALUE_DEFENSIVE","CN_CONSUMER"},
}


def block_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for (variant,bno),g in df.groupby(["variant","block_no"]):
        st=s8b.path_stats(g)
        rows.append({"variant":variant,"block_no":int(bno),**st})
    return pd.DataFrame(rows)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage8h-output")
    args=ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)

    eng=create_engine(_db_url(args.database_url),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars["symbol"].astype(str).str.zfill(6); bars["date"]=pd.to_datetime(bars["date"])
    feat=build_features(bars); feat["symbol"]=feat["symbol"].astype(str).str.zfill(6)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    amount=s8e.build_amount_wide(bars,cal)
    meta=pd.read_sql_query(text("select symbol,name,asset_class,region_primary,exposure_level1,exposure_level2,underlying_key,risk_bucket,style_sector,is_qdii,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"),eng)
    meta["symbol"]=meta["symbol"].astype(str).str.zfill(6)

    start0=int(cal.searchsorted(pd.Timestamp("2022-01-01"),side="left"))
    starts=s8a.extended_starts(cal,start0); starts_map={b:p for b,p in starts}
    first_exec_pos=int(cal.searchsorted(START_EXEC,side="left")); first_signal=max(0,first_exec_pos-1); last_signal=len(cal)-3
    need=[]
    for b,p in starts:
        next_p=starts_map.get(b+1,len(cal))
        if next_p<=first_signal or p>last_signal: continue
        if p-HIST_SESSIONS<0: continue
        if all((b-j) in starts_map for j in (1,2,3)):
            need.append((b,p))
    if not need: raise RuntimeError("no blocks")

    base_by={}; slot_rows=[]
    for bno,pos in need:
        common=s8a.common_pool_for_block(bno,pos,starts_map,cal,close,meta)
        eco,rows=s8e.select_economic(common,pos,cal,amount,meta)
        base_by[bno]=tuple(sorted(eco))
        for r in rows:
            rr=dict(r); rr.update({"block_no":int(bno),"decision_date":str(pd.Timestamp(cal[pos]).date())})
            slot_rows.append(rr)
    sel=pd.DataFrame(slot_rows)

    variants={"BASE_ECONOMIC":base_by}
    removed=[]
    for name,slots in DROP_MAP.items():
        vb={}
        for bno,_ in need:
            members=set(base_by[bno])
            rows=sel[sel["block_no"]==bno]
            rm=rows[rows["slot"].isin(slots)][["slot","symbol"]]
            for rec in rm.itertuples():
                members.discard(str(rec.symbol))
                removed.append({"variant":name,"block_no":int(bno),"slot":str(rec.slot),"symbol":str(rec.symbol)})
            vb[bno]=tuple(sorted(members))
        variants[name]=vb

    # Representative-level deletion only: if 562500 is selected in industrial slot, leave that slot empty for the block.
    vb={}
    for bno,_ in need:
        members=set(base_by[bno])
        if "562500" in members:
            members.remove("562500")
            removed.append({"variant":"DROP_562500_ONLY","block_no":int(bno),"slot":"CN_INDUSTRIAL_DEFENSE","symbol":"562500"})
        vb[bno]=tuple(sorted(members))
    variants["DROP_562500_ONLY"]=vb
    variants["FIX15_BENCHMARK"]={b:FIX15 for b,_ in need}

    parts=[]
    for name,by in variants.items():
        parts.append(s8a.build_variant_daily(name,by,starts_map,cal,score,gross,first_signal,last_signal))
    daily=pd.concat(parts,ignore_index=True)
    daily=daily.loc[daily["execution_date"]>=START_EXEC].copy()

    ann,_=s8a.summarize(daily)
    full=[]
    for variant,g in daily.groupby("variant"):
        full.append({"variant":variant,**s8b.path_stats(g)})
    full=pd.DataFrame(full)
    blk=block_stats(daily)

    base_row=full[full["variant"]=="BASE_ECONOMIC"].iloc[0]
    if "total_return" in full.columns:
        full["delta_vs_base"] = full["total_return"] - float(base_row["total_return"])
    elif "return" in full.columns:
        full["delta_vs_base"] = full["return"] - float(base_row["return"])

    daily.to_csv(out/"stage8h_daily.csv",index=False)
    ann.to_csv(out/"stage8h_annual.csv",index=False)
    full.to_csv(out/"stage8h_full.csv",index=False)
    blk.to_csv(out/"stage8h_block.csv",index=False)
    sel.to_csv(out/"stage8h_base_selections.csv",index=False)
    pd.DataFrame(removed).to_csv(out/"stage8h_removed.csv",index=False)

    summary={
        "study":"OURE Stage8H bad-slot deletion counterfactual",
        "status":"completed",
        "blocks":len(need),
        "variants":list(variants.keys()),
        "full":full.to_dict(orient="records"),
    }
    (out/"stage8h_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print(full.to_string(index=False))
    print(ann.to_string(index=False))

if __name__=="__main__":
    main()
