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

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

COST = 0.0006
CASH = "511220"
MIN_BARS = 500
OLS_READY_BARS = 26
BLOCK = 126

BASE_A = tuple(sorted([
    "518880","159985","161226","513100","159915",CASH,
    "159509","513290","159529","501018","511380","164824","513530",
]))
BASE_B = tuple(sorted(set(BASE_A) | {"159981"}))
BASES = {
    "BASE_FIX13_HKDIV": BASE_A,
    "BASE_FIX14_HKDIV_ENCHEM": BASE_B,
}

INCUMBENTS = {
    "GOLD_SPOT": "518880",
    "NASDAQ100": "513100",
    "CHINEXT_STANDARD": "159915",
    "HK_DIVIDEND_ROLE": "513530",
    "US_BIOTECH_ROLE": "513290",
}
STRICT_SLOTS = {"GOLD_SPOT","NASDAQ100","CHINEXT_STANDARD"}
EXCLUDE_CHINEXT = ("50","200","综","成长","价值","科技","软件","新能源","人工智能","医药","大盘","增强")


def path_stats(g: pd.DataFrame) -> dict:
    if g.empty:
        return {"total_return":np.nan,"mdd":np.nan,"turnover_sides":0,"switches":0,"mean_top1_tenure":np.nan,"sessions":0}
    r=g["net"].to_numpy(float)
    eq=np.cumprod(1+r)
    peak=np.maximum.accumulate(np.r_[1.0,eq])[1:]
    vals=g["target"].astype(object).tolist()
    switches=0; runs=[]
    if vals:
        cur=vals[0]; n=1
        for x in vals[1:]:
            same=(x==cur) or (pd.isna(x) and pd.isna(cur))
            if same: n+=1
            else: runs.append(n); cur=x; n=1; switches+=1
        runs.append(n)
    return {
        "total_return":float(np.prod(1+r)-1),
        "mdd":float(np.min(eq/peak-1)),
        "turnover_sides":int(g["sides"].sum()),
        "switches":int(switches),
        "mean_top1_tenure":float(np.mean(runs)) if runs else np.nan,
        "sessions":int(len(g)),
    }


def choose_target(score: pd.DataFrame, d: pd.Timestamp, members: tuple[str,...]) -> str|None:
    risk=[s for s in members if s!=CASH and s in score.columns]
    vals=score.loc[d,risk].astype(float)
    vals=vals[np.isfinite(vals)]
    if vals.empty: return None
    sym=str(vals.idxmax()); rv=float(vals.loc[sym])
    cv=float(score.at[d,CASH]) if CASH in score.columns and pd.notna(score.at[d,CASH]) else -np.inf
    return sym if np.isfinite(rv) and rv>cv else None


def run_path(name: str, members: tuple[str,...], cal: pd.DatetimeIndex, score: pd.DataFrame, gross: pd.DataFrame,
             start_signal: pd.Timestamp, last_signal_pos: int) -> pd.DataFrame:
    start_pos=int(cal.searchsorted(pd.Timestamp(start_signal),side="left"))
    start_pos=max(0,start_pos)
    rows=[]; prev=None
    for i in range(start_pos,last_signal_pos+1):
        d=pd.Timestamp(cal[i]); target=choose_target(score,d,members)
        if target==prev: sides=0
        elif target is None or prev is None: sides=1
        else: sides=2
        gr=0.0
        if target is not None:
            v=gross.at[d,target]
            gr=float(v) if pd.notna(v) and np.isfinite(v) else 0.0
        net=(1+gr)*(1-COST*sides)-1
        rows.append({"variant":name,"signal_date":d,"execution_date":pd.Timestamp(cal[i+1]),
                     "return_end_date":pd.Timestamp(cal[i+2]),"target":target,"sides":sides,"gross":gr,"net":net})
        prev=target
    return pd.DataFrame(rows)


def candidate_slot(row) -> str|None:
    uk=str(row.underlying_key) if pd.notna(row.underlying_key) else ""
    rb=str(row.risk_bucket) if pd.notna(row.risk_bucket) else ""
    name=str(row.name)
    if uk=="GOLD_SPOT": return "GOLD_SPOT"
    if uk=="NASDAQ100": return "NASDAQ100"
    if rb=="CHINA_GROWTH_CHINEXT" and "创业板ETF" in name and not any(t in name for t in EXCLUDE_CHINEXT):
        return "CHINEXT_STANDARD"
    if rb=="HK_DIVIDEND": return "HK_DIVIDEND_ROLE"
    if rb=="US_BIOTECH": return "US_BIOTECH_ROLE"
    return None


def breadth_compare(base: pd.DataFrame, cand: pd.DataFrame) -> dict:
    # Both paths are reset from the same start and therefore should align by execution date.
    x=base[["execution_date","net"]].rename(columns={"net":"b"}).merge(
        cand[["execution_date","net"]].rename(columns={"net":"c"}),on="execution_date",how="inner")
    if x.empty:
        return {"year_better":0,"year_worse":0,"year_tied":0,"block_better":0,"block_worse":0,"block_tied":0,"mean_block_delta":np.nan}
    x["year"]=x.execution_date.dt.year
    yr=[]
    for y,g in x.groupby("year"):
        yr.append((y,float(np.prod(1+g.c)-1),float(np.prod(1+g.b)-1)))
    tol=1e-12
    yd=np.array([c-b for _,c,b in yr],float)
    block_rows=[]
    for j in range(0,len(x),BLOCK):
        g=x.iloc[j:j+BLOCK]
        if len(g)<30: continue
        cr=float(np.prod(1+g.c)-1); br=float(np.prod(1+g.b)-1)
        block_rows.append(cr-br)
    bd=np.array(block_rows,float)
    return {
        "year_better":int((yd>tol).sum()),"year_worse":int((yd<-tol).sum()),"year_tied":int((np.abs(yd)<=tol).sum()),
        "block_better":int((bd>tol).sum()),"block_worse":int((bd<-tol).sum()),"block_tied":int((np.abs(bd)<=tol).sum()),
        "mean_block_delta":float(np.mean(bd)) if len(bd) else np.nan,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--database-url",default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir",default="oure-stage8l-output")
    args=ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)

    eng=create_engine(_db_url(args.database_url),pool_pre_ping=True)
    meta=pd.read_sql_query(text("""
        select symbol,name,asset_class,region_primary,risk_bucket,underlying_key,
               has_daily_bars,leveraged_flag,inverse_flag
        from public.instrument_metadata_current
    """),eng)
    meta["symbol"]=meta.symbol.astype(str).str.zfill(6)

    bars=load_daily_bars(eng); bars["symbol"]=bars.symbol.astype(str).str.zfill(6); bars["date"]=pd.to_datetime(bars.date)
    counts=bars.groupby("symbol").agg(first_date=("date","min"),last_date=("date","max"),n=("date","size")).reset_index()
    inv=meta.merge(counts,on="symbol",how="inner")
    inv=inv[(inv.has_daily_bars==True) & (~inv.leveraged_flag.fillna(False)) & (~inv.inverse_flag.fillna(False)) & (inv.n>=MIN_BARS)].copy()
    inv["slot"]=[candidate_slot(r) for r in inv.itertuples()]
    inv=inv[inv.slot.notna()].copy()
    # Ensure incumbents are present even if metadata quirks would otherwise exclude them.
    incumbent_set=set(INCUMBENTS.values())
    miss=meta[meta.symbol.isin(incumbent_set-set(inv.symbol))].merge(counts,on="symbol",how="inner")
    if not miss.empty:
        miss["slot"]=[next((k for k,v in INCUMBENTS.items() if v==s),None) for s in miss.symbol]
        inv=pd.concat([inv,miss],ignore_index=True)
    inv=inv.drop_duplicates("symbol").sort_values(["slot","first_date","symbol"]).reset_index(drop=True)
    inv["incumbent"]=[INCUMBENTS[str(s)] for s in inv.slot]
    inv["strict_same_exposure"]=inv.slot.isin(STRICT_SLOTS)

    all_syms=set().union(*[set(v) for v in BASES.values()]) | set(inv.symbol)
    bars2=bars[bars.symbol.isin(all_syms)].copy()
    feat=build_features(bars2); feat["symbol"]=feat.symbol.astype(str).str.zfill(6)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars2,feat); cal=pd.DatetimeIndex(cal)
    if CASH not in score.columns: raise RuntimeError("cash comparator missing")
    cash_valid=score[CASH].dropna()
    if cash_valid.empty: raise RuntimeError("cash has no finite OLS score")
    global_start=pd.Timestamp(cash_valid.index[0]); last_signal_pos=len(cal)-3

    # 26th real trading bar = product's OLS-ready date, regardless of whether the trend is positive then.
    ready={}
    for s,g in bars2.groupby("symbol"):
        ds=pd.DatetimeIndex(g.sort_values("date").date)
        ready[s]=pd.Timestamp(ds[min(OLS_READY_BARS-1,len(ds)-1)])
    inv["ols_ready_date"]=[ready.get(s,pd.NaT) for s in inv.symbol]
    inv.to_csv(out/"stage8l_candidates.csv",index=False)

    # Full-history paths for bases and every one-at-a-time replacement.
    full_paths={}
    full_rows=[]
    for bname,bmembers in BASES.items():
        bp=run_path(bname,bmembers,cal,score,gross,global_start,last_signal_pos); full_paths[bname]=bp
        full_rows.append({"base":bname,"slot":"BASE","candidate":"BASE","incumbent":"BASE","variant":bname,**path_stats(bp)})
        for r in inv.itertuples():
            slot=str(r.slot); cand=str(r.symbol); inc=INCUMBENTS[slot]
            if cand==inc: continue
            members=tuple(sorted((set(bmembers)-{inc})|{cand}))
            vname=f"{bname}__{slot}__{cand}"
            p=run_path(vname,members,cal,score,gross,global_start,last_signal_pos); full_paths[vname]=p
            st=path_stats(p); bst=path_stats(bp)
            full_rows.append({"base":bname,"slot":slot,"candidate":cand,"incumbent":inc,"variant":vname,**st,
                              "return_delta_vs_base":float(st["total_return"]-bst["total_return"]),
                              "mdd_delta_vs_base":float(st["mdd"]-bst["mdd"]),
                              "turnover_delta_vs_base":int(st["turnover_sides"]-bst["turnover_sides"])})
    pd.DataFrame(full_rows).to_csv(out/"stage8l_full_history_metrics.csv",index=False)

    # Matched-availability tests, resetting base and replacement from candidate OLS-ready date.
    matched_rows=[]; annual_rows=[]; block_rows=[]
    for bname,bmembers in BASES.items():
        for r in inv.itertuples():
            slot=str(r.slot); cand=str(r.symbol); inc=INCUMBENTS[slot]
            if cand==inc: continue
            start=max(global_start,pd.Timestamp(r.ols_ready_date))
            base_p=run_path(f"MATCH_BASE__{bname}__{slot}__{cand}",bmembers,cal,score,gross,start,last_signal_pos)
            members=tuple(sorted((set(bmembers)-{inc})|{cand}))
            cand_p=run_path(f"MATCH_CAND__{bname}__{slot}__{cand}",members,cal,score,gross,start,last_signal_pos)
            bs=path_stats(base_p); cs=path_stats(cand_p); br=breadth_compare(base_p,cand_p)
            row={"base":bname,"slot":slot,"candidate":cand,"incumbent":inc,"candidate_name":str(r.name),
                 "strict_same_exposure":bool(r.strict_same_exposure),"matched_start_signal":str(start.date()),
                 **{f"base_{k}":v for k,v in bs.items()},**{f"candidate_{k}":v for k,v in cs.items()},**br}
            row.update({"matched_return_delta":float(cs["total_return"]-bs["total_return"]),
                        "matched_log_wealth_adv":float(math.log1p(cs["total_return"])-math.log1p(bs["total_return"])),
                        "matched_mdd_delta":float(cs["mdd"]-bs["mdd"]),
                        "matched_turnover_delta":int(cs["turnover_sides"]-bs["turnover_sides"])})
            matched_rows.append(row)
            # detailed annual deltas
            xb=base_p.copy(); xc=cand_p.copy(); xb["year"]=xb.execution_date.dt.year; xc["year"]=xc.execution_date.dt.year
            by={y:float(np.prod(1+g.net)-1) for y,g in xb.groupby("year")}; cy={y:float(np.prod(1+g.net)-1) for y,g in xc.groupby("year")}
            for y in sorted(set(by)&set(cy)):
                annual_rows.append({"base":bname,"slot":slot,"candidate":cand,"year":int(y),"base_return":by[y],"candidate_return":cy[y],"delta":cy[y]-by[y]})
            # detailed 126-session matched blocks
            x=base_p[["execution_date","net"]].rename(columns={"net":"b"}).merge(cand_p[["execution_date","net"]].rename(columns={"net":"c"}),on="execution_date")
            for j in range(0,len(x),BLOCK):
                g=x.iloc[j:j+BLOCK]
                if len(g)<30: continue
                brt=float(np.prod(1+g.b)-1); crt=float(np.prod(1+g.c)-1)
                block_rows.append({"base":bname,"slot":slot,"candidate":cand,"block":j//BLOCK,
                                   "start":str(g.execution_date.iloc[0].date()),"end":str(g.execution_date.iloc[-1].date()),
                                   "base_return":brt,"candidate_return":crt,"delta":crt-brt})

    matched=pd.DataFrame(matched_rows)
    matched.to_csv(out/"stage8l_matched_metrics.csv",index=False)
    pd.DataFrame(annual_rows).to_csv(out/"stage8l_matched_annual.csv",index=False)
    pd.DataFrame(block_rows).to_csv(out/"stage8l_matched_blocks.csv",index=False)

    # Frozen robust-dominance rule across BOTH base compositions.
    summary_rows=[]
    for (slot,cand),g in matched.groupby(["slot","candidate"]):
        if len(g)!=len(BASES): continue
        cond_return=bool((g.matched_return_delta>0).all())
        cond_blocks=bool((g.block_better>=g.block_worse).all())
        cond_mdd=bool((g.matched_mdd_delta>=-0.02).all())
        robust=cond_return and cond_blocks and cond_mdd
        meta_row=inv.loc[inv.symbol==cand].iloc[0]
        summary_rows.append({
            "slot":slot,"candidate":cand,"candidate_name":meta_row["name"],"incumbent":INCUMBENTS[slot],
            "strict_same_exposure":bool(slot in STRICT_SLOTS),"robust_status":"ROBUST_DOMINATES" if robust else "NO_ROBUST_DOMINANCE",
            "return_positive_both":cond_return,"blocks_nonnegative_both":cond_blocks,"mdd_guardrail_both":cond_mdd,
            "mean_matched_log_wealth_adv":float(g.matched_log_wealth_adv.mean()),
            "min_matched_return_delta":float(g.matched_return_delta.min()),"max_matched_return_delta":float(g.matched_return_delta.max()),
            "worst_mdd_delta":float(g.matched_mdd_delta.min()),
            "total_block_better":int(g.block_better.sum()),"total_block_worse":int(g.block_worse.sum()),"total_block_tied":int(g.block_tied.sum()),
            "total_year_better":int(g.year_better.sum()),"total_year_worse":int(g.year_worse.sum()),"total_year_tied":int(g.year_tied.sum()),
            "ols_ready_date":str(pd.Timestamp(meta_row["ols_ready_date"]).date()),
        })
    summ=pd.DataFrame(summary_rows)
    if not summ.empty:
        summ=summ.sort_values(["slot","robust_status","mean_matched_log_wealth_adv"],ascending=[True,True,False])
    summ.to_csv(out/"stage8l_slot_summary.csv",index=False)

    result={
        "study":"OURE Stage8L within-exposure ETF carrier audit","status":"completed",
        "global_start_signal":str(global_start.date()),"candidate_count":int(len(inv)),
        "slot_candidate_counts":inv.groupby("slot").size().to_dict(),
        "robust_dominators":summ.loc[summ.robust_status=="ROBUST_DOMINATES",["slot","candidate","candidate_name","mean_matched_log_wealth_adv"]].to_dict(orient="records") if not summ.empty else [],
    }
    (out/"stage8l_summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    if not summ.empty: print(summ.to_string(index=False))

if __name__=="__main__": main()
