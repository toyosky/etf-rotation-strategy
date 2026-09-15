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
CASH = s8a.CASH


def block_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for (variant,bno),g in df.groupby(["variant","block_no"]):
        rows.append({"variant":variant,"block_no":int(bno),**s8b.path_stats(g)})
    return pd.DataFrame(rows)


def breadth(full: pd.DataFrame, annual: pd.DataFrame, block: pd.DataFrame, refs: dict[str,str]) -> pd.DataFrame:
    rows=[]
    tol=1e-12
    for variant,ref in refs.items():
        if variant==ref: continue
        vfull=full.loc[full.variant==variant].iloc[0]
        rfull=full.loc[full.variant==ref].iloc[0]
        va=annual[annual.variant==variant][["year","return"]].rename(columns={"return":"v"})
        ra=annual[annual.variant==ref][["year","return"]].rename(columns={"return":"r"})
        ya=va.merge(ra,on="year",how="inner"); yd=ya.v-ya.r
        vb=block[block.variant==variant][["block_no","total_return"]].rename(columns={"total_return":"v"})
        rb=block[block.variant==ref][["block_no","total_return"]].rename(columns={"total_return":"r"})
        bb=vb.merge(rb,on="block_no",how="inner"); bd=bb.v-bb.r
        rows.append({
            "variant":variant,"reference":ref,
            "full_return_delta":float(vfull.total_return-rfull.total_return),
            "mdd_delta":float(vfull.mdd-rfull.mdd),
            "turnover_delta":int(vfull.turnover_sides-rfull.turnover_sides),
            "year_better":int((yd>tol).sum()),"year_worse":int((yd<-tol).sum()),"year_tied":int((yd.abs()<=tol).sum()),
            "block_better":int((bd>tol).sum()),"block_worse":int((bd<-tol).sum()),"block_tied":int((bd.abs()<=tol).sum()),
            "mean_block_delta":float(bd.mean()) if len(bd) else None,
        })
    return pd.DataFrame(rows).sort_values(["reference","full_return_delta"],ascending=[True,False])


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--database-url",default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir",default="oure-stage8i-output")
    args=ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)

    eng=create_engine(_db_url(args.database_url),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars["symbol"].astype(str).str.zfill(6); bars["date"]=pd.to_datetime(bars["date"])
    feat=build_features(bars); feat["symbol"]=feat["symbol"].astype(str).str.zfill(6)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    amount=s8e.build_amount_wide(bars,cal)
    meta=pd.read_sql_query(text("select symbol,name,asset_class,region_primary,exposure_level1,exposure_level2,underlying_key,risk_bucket,style_sector,is_qdii,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"),eng)
    meta["symbol"]=meta["symbol"].astype(str).str.zfill(6)
    mm=meta.set_index("symbol",drop=False)

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

    risk_fix=tuple(sorted(s for s in FIX15 if s!=CASH))
    base_by={b:FIX15 for b,_ in need}
    variants={"BASE_FIX15":base_by}
    refs={"BASE_FIX15":"BASE_FIX15"}

    # Leave-one-out exploratory pruning matrix.
    for sym in risk_fix:
        name=f"LOO_{sym}"
        members=tuple(sorted(s for s in FIX15 if s!=sym))
        variants[name]={b:members for b,_ in need}; refs[name]="BASE_FIX15"

    # Explicit focal deletion combinations.
    focal={
        "DROP_159825": {"159825"},
        "DROP_159985": {"159985"},
        "DROP_159981": {"159981"},
        "DROP_159825_159981": {"159825","159981"},
        "DROP_159825_159985": {"159825","159985"},
    }
    for name,rm in focal.items():
        members=tuple(sorted(s for s in FIX15 if s not in rm))
        variants[name]={b:members for b,_ in need}; refs[name]="BASE_FIX15"

    # Structural slot coverage of Fix15 after removing 159825. This uses metadata identity only.
    pruned_members=tuple(sorted(s for s in FIX15 if s!="159825"))
    covered=set()
    coverage_rows=[]
    for s in pruned_members:
        if s==CASH or s not in mm.index: continue
        slot=s8e.economic_slot(mm.at[s,"risk_bucket"])
        if slot: covered.add(slot)
        coverage_rows.append({"symbol":s,"name":mm.at[s,"name"] if s in mm.index else None,"risk_bucket":mm.at[s,"risk_bucket"] if s in mm.index else None,"economic_slot":slot})
    missing=[slot for slot in s8e.SLOT_ORDER if slot not in covered]

    # Precompute Stage8E point-in-time representative per slot/block.
    rep_by_block={}; rep_rows=[]
    for bno,pos in need:
        common=s8a.common_pool_for_block(bno,pos,starts_map,cal,close,meta)
        _,rows=s8e.select_economic(common,pos,cal,amount,meta)
        d={str(r["slot"]):str(r["symbol"]) for r in rows}
        rep_by_block[bno]=d
        for r in rows:
            rr=dict(r); rr.update({"block_no":int(bno),"decision_date":str(pd.Timestamp(cal[pos]).date())})
            rep_rows.append(rr)

    replacement_rows=[]
    for slot in missing:
        name=f"REPLACE_159825_WITH_{slot}"
        by={}
        for bno,_ in need:
            members=set(pruned_members)
            rep=rep_by_block.get(bno,{}).get(slot)
            if rep and rep not in members:
                members.add(rep)
                replacement_rows.append({"variant":name,"slot":slot,"block_no":int(bno),"symbol":rep,"added":True})
            else:
                replacement_rows.append({"variant":name,"slot":slot,"block_no":int(bno),"symbol":rep,"added":False})
            by[bno]=tuple(sorted(members))
        variants[name]=by; refs[name]="DROP_159825"

    parts=[]
    for name,by in variants.items():
        parts.append(s8a.build_variant_daily(name,by,starts_map,cal,score,gross,first_signal,last_signal))
    daily=pd.concat(parts,ignore_index=True)
    daily=daily.loc[daily["execution_date"]>=START_EXEC].copy()
    annual,_=s8a.summarize(daily)
    full=pd.DataFrame([{"variant":v,**s8b.path_stats(g)} for v,g in daily.groupby("variant")])
    block=block_stats(daily)
    breadth_df=breadth(full,annual,block,refs)

    # Annotate full table with reference deltas.
    ref_lookup={r.variant:r for r in full.itertuples()}
    frows=[]
    for r in full.itertuples():
        ref=refs.get(r.variant,"BASE_FIX15")
        rr=ref_lookup[ref]
        d=r._asdict(); d.update({"reference":ref,"return_delta_vs_ref":float(r.total_return-rr.total_return),"mdd_delta_vs_ref":float(r.mdd-rr.mdd),"turnover_delta_vs_ref":int(r.turnover_sides-rr.turnover_sides)})
        frows.append(d)
    full2=pd.DataFrame(frows)

    daily.to_csv(out/"stage8i_daily.csv",index=False)
    annual.to_csv(out/"stage8i_annual.csv",index=False)
    full2.to_csv(out/"stage8i_full.csv",index=False)
    block.to_csv(out/"stage8i_block.csv",index=False)
    breadth_df.to_csv(out/"stage8i_breadth.csv",index=False)
    pd.DataFrame(coverage_rows).to_csv(out/"stage8i_fix15_slot_coverage_after_drop159825.csv",index=False)
    pd.DataFrame(rep_rows).to_csv(out/"stage8i_stage8e_representatives.csv",index=False)
    pd.DataFrame(replacement_rows).to_csv(out/"stage8i_replacements.csv",index=False)

    summary={
        "study":"OURE Stage8I Fix15 pruning/replacement matrix","status":"completed","blocks":len(need),
        "fix15_risk_members":list(risk_fix),"covered_slots_after_drop159825":sorted(covered),"missing_slots_tested":missing,
        "variants":list(variants.keys()),"full":full2.to_dict(orient="records"),
    }
    (out/"stage8i_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print(full2.sort_values("total_return",ascending=False).to_string(index=False))
    print(breadth_df.to_string(index=False))

if __name__=="__main__": main()
