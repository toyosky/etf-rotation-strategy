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

import optimal_universe_reverse_engineering.oure_stage8a_opportunity30 as s8a
import optimal_universe_reverse_engineering.oure_stage8e_economic_coverage as s8e
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

START_EXEC = pd.Timestamp("2021-01-01")
HIST_SESSIONS = 378
NEAR_HIGH_TOL = 0.005
MIN_ALL = 10
MIN_RECENT2Y = 5
WARNING_WIN = 0.35
WATCH_WIN = 0.40


def summarize(g: pd.DataFrame) -> dict:
    if g.empty:
        return {"count":0,"fwd5_mean":np.nan,"fwd5_median":np.nan,"fwd5_win_rate":np.nan,
                "fwd10_mean":np.nan,"fwd10_median":np.nan,"fwd10_win_rate":np.nan}
    return {
        "count": int(len(g)),
        "fwd5_mean": float(g["fwd5"].mean()),
        "fwd5_median": float(g["fwd5"].median()),
        "fwd5_win_rate": float((g["fwd5"] > 0).mean()),
        "fwd10_mean": float(g["fwd10"].mean()),
        "fwd10_median": float(g["fwd10"].median()),
        "fwd10_win_rate": float((g["fwd10"] > 0).mean()),
    }


def classify(all_near: dict, recent_near: dict) -> tuple[str,str]:
    na = int(all_near["count"] or 0); nr = int(recent_near["count"] or 0)
    if na < MIN_ALL or nr < MIN_RECENT2Y:
        return "INSUFFICIENT_DATA", f"near-high samples insufficient: all={na}/{MIN_ALL}, recent_2y={nr}/{MIN_RECENT2Y}"
    am = float(all_near["fwd10_mean"]); rm = float(recent_near["fwd10_mean"])
    aw = float(all_near["fwd10_win_rate"]); rw = float(recent_near["fwd10_win_rate"])
    if am < 0 and rm < 0:
        if aw < WARNING_WIN and rw < WARNING_WIN:
            return "WARNING", "near-high Top1 continuation negative in full history and recent 2y; both 10d win rates <35%"
        return "WATCH", "near-high Top1 10d mean negative in full history and recent 2y"
    if rm < 0 and rw < WATCH_WIN:
        return "WATCH", "recent-2y near-high Top1 continuation negative with 10d win rate <40%"
    return "HEALTHY", "no frozen V1 deterioration condition triggered"


def build_economic_path(bars, feat, meta):
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)
    amount = s8e.build_amount_wide(bars, cal)
    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    starts = s8a.extended_starts(cal, start0); starts_map = {b:p for b,p in starts}
    first_exec_pos = int(cal.searchsorted(START_EXEC, side="left")); first_signal = max(0, first_exec_pos-1)
    last_signal = len(cal)-3
    need=[]
    for b,p in starts:
        next_p=starts_map.get(b+1,len(cal))
        if next_p<=first_signal or p>last_signal: continue
        if p-HIST_SESSIONS<0: continue
        if all((b-j) in starts_map for j in (1,2,3)): need.append((b,p))
    eco_by={}; selection_rows=[]
    for bno,pos in need:
        common=s8a.common_pool_for_block(bno,pos,starts_map,cal,close,meta)
        eco,rows=s8e.select_economic(common,pos,cal,amount,meta)
        eco_by[bno]=eco
        for r in rows:
            rr=dict(r); rr.update({"block_no":int(bno),"decision_date":str(pd.Timestamp(cal[pos]).date())})
            selection_rows.append(rr)
    daily=s8a.build_variant_daily("ECONOMIC_COVERAGE",eco_by,starts_map,cal,score,gross,first_signal,last_signal)
    daily=daily.loc[daily["execution_date"]>=START_EXEC].sort_values("signal_date").reset_index(drop=True)
    sel=pd.DataFrame(selection_rows)
    slot_lookup={(int(r.block_no),str(r.symbol)):str(r.slot) for r in sel.itertuples()}
    daily["slot"]=[slot_lookup.get((int(b),str(t))) if pd.notna(t) else None for b,t in zip(daily["block_no"],daily["target"])]
    daily["episode_start"]=daily["target"].astype(object).ne(daily["target"].astype(object).shift(1))
    return cal, score, r2, close, daily, sel


def build_events(bars: pd.DataFrame, daily: pd.DataFrame, score: pd.DataFrame, r2: pd.DataFrame) -> pd.DataFrame:
    bysym={}
    for sym,g in bars.groupby("symbol",sort=False):
        x=g.sort_values("date")[["date","close"]].copy().reset_index(drop=True)
        x["date"]=pd.to_datetime(x["date"]); bysym[str(sym)]=x
    rows=[]
    for rec in daily.itertuples():
        if pd.isna(rec.target) or not rec.slot: continue
        sym=str(rec.target); d=pd.Timestamp(rec.signal_date)
        g=bysym.get(sym)
        if g is None: continue
        hits=np.flatnonzero(g["date"].to_numpy()==np.datetime64(d))
        if len(hits)!=1: continue
        i=int(hits[0])
        if i<19 or i+10>=len(g): continue
        c0=float(g.at[i,"close"]); h20=float(g.loc[i-19:i,"close"].max())
        f5=float(g.at[i+5,"close"])/c0-1.0; f10=float(g.at[i+10,"close"])/c0-1.0
        rows.append({
            "signal_date":d,"block_no":int(rec.block_no),"slot":str(rec.slot),"symbol":sym,
            "episode_start":bool(rec.episode_start),"near_high":bool(c0>=h20*(1-NEAR_HIGH_TOL)),
            "fwd5":f5,"fwd10":f10,
            "score":float(score.at[d,sym]) if d in score.index and sym in score.columns and pd.notna(score.at[d,sym]) else np.nan,
            "r2":float(r2.at[d,sym]) if d in r2.index and sym in r2.columns and pd.notna(r2.at[d,sym]) else np.nan,
        })
    return pd.DataFrame(rows)


def entity_summary(events: pd.DataFrame, key: str, recent_start: pd.Timestamp) -> pd.DataFrame:
    vals=[]
    entities = sorted(events[key].dropna().astype(str).unique())
    for ent in entities:
        g=events[events[key].astype(str)==ent]
        near=g[g["near_high"]]
        near_recent=near[near["signal_date"]>=recent_start]
        ep=g[g["episode_start"]]
        ep_near=ep[ep["near_high"]]
        a=summarize(g); n=summarize(near); nr=summarize(near_recent); e=summarize(ep); en=summarize(ep_near)
        status,reason=classify(n,nr)
        row={key:ent,"status":status,"reason":reason}
        for prefix,sm in [("top1",a),("near_high",n),("recent2y_near_high",nr),("episode",e),("episode_near_high",en)]:
            for k,v in sm.items(): row[f"{prefix}_{k}"]=v
        vals.append(row)
    out=pd.DataFrame(vals)
    if not out.empty:
        rank_order={"WARNING":0,"WATCH":1,"HEALTHY":2,"INSUFFICIENT_DATA":3}
        out["status_order"]=out["status"].map(rank_order).fillna(9)
        out=out.sort_values(["status_order","near_high_fwd10_mean","top1_fwd10_mean"],ascending=[True,True,True]).drop(columns="status_order")
    return out


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--database-url",default=os.getenv("ETF_DAILY_BARS_DATABASE_URL")); ap.add_argument("--output-dir",default="oure-stage8g-output")
    args=ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    eng=create_engine(_db_url(args.database_url),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars["symbol"].astype(str).str.zfill(6); bars["date"]=pd.to_datetime(bars["date"])
    feat=build_features(bars); feat["symbol"]=feat["symbol"].astype(str).str.zfill(6)
    meta=pd.read_sql_query(text("select symbol,name,risk_bucket,underlying_key,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"),eng)
    meta["symbol"]=meta["symbol"].astype(str).str.zfill(6)
    cal,score,r2,close,daily,sel=build_economic_path(bars,feat,meta)
    events=build_events(bars,daily,score,r2)
    if events.empty: raise RuntimeError("no mature Economic Coverage Top1 events")
    cutoff=pd.Timestamp(events["signal_date"].max()); recent_start=cutoff-pd.Timedelta(days=730)
    slot=entity_summary(events,"slot",recent_start)
    symbol=entity_summary(events,"symbol",recent_start)
    ep=events[events["episode_start"]].copy()
    # Compact episode-first robustness by slot without applying a new classification.
    ep_slot=[]
    for s,g in ep.groupby("slot"):
        sm=summarize(g); nm=summarize(g[g["near_high"]])
        ep_slot.append({"slot":s,**{f"episode_{k}":v for k,v in sm.items()},**{f"episode_near_high_{k}":v for k,v in nm.items()}})
    ep_slot=pd.DataFrame(ep_slot).sort_values("episode_fwd10_mean") if ep_slot else pd.DataFrame()
    events.to_csv(out/"stage8g_events.csv",index=False)
    slot.to_csv(out/"stage8g_slot_health.csv",index=False)
    symbol.to_csv(out/"stage8g_symbol_health.csv",index=False)
    ep_slot.to_csv(out/"stage8g_episode_slot_robustness.csv",index=False)
    sel.to_csv(out/"stage8g_stage8e_selections.csv",index=False)
    summary={
        "study":"OURE Stage8G economic asset health","status":"completed","event_count":int(len(events)),"episode_count":int(ep.shape[0]),
        "mature_cutoff":str(cutoff.date()),"recent2y_start":str(recent_start.date()),
        "slot_status_counts":slot["status"].value_counts(dropna=False).to_dict(),
        "warning_slots":slot.loc[slot["status"]=="WARNING","slot"].tolist(),
        "watch_slots":slot.loc[slot["status"]=="WATCH","slot"].tolist(),
    }
    (out/"stage8g_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    print(slot.to_string(index=False))

if __name__=="__main__": main()
