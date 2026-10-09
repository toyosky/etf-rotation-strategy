#!/usr/bin/env python3
"""Point-in-time Brazil ETF OLS/R2 study. Research only; no trading changes."""
from __future__ import annotations
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from automation.build_fundamental_audit_trigger import calc_ols, db_url, RISK_POOL

BRAZIL = ("520870", "159100")
OUT = Path("data/brazil-trend-research.json")

def main():
    engine = create_engine(db_url(os.environ["ETF_DAILY_BARS_DATABASE_URL"]))
    symbols = sorted(set(RISK_POOL + ["511220", "513500"]))
    with engine.connect() as conn:
        frame = pd.read_sql_query(
            text("select symbol,date,open,high,low,close,amount from public.daily_bars "
                 "where symbol = any(:symbols) order by symbol,date"),
            conn, params={"symbols": symbols}, parse_dates=["date"])
    frame["symbol"] = frame.symbol.astype(str).str.zfill(6)
    frame["close"] = pd.to_numeric(frame.close)
    frame["open"] = pd.to_numeric(frame.open)
    valid = {}
    for symbol,g in frame.groupby("symbol"):
        g=g.sort_values("date").copy().reset_index(drop=True)
        if len(g)<30: continue
        annual,r2=calc_ols(g.close.to_numpy(float))
        g["annual"]=annual;g["r2"]=r2
        g["score"]=np.where(annual>0,annual*r2,0.0)
        g["cross"]=(g.annual.shift(1)<=0)&(g.annual>0)
        g["dr2"]=g.r2.diff()
        valid[symbol]=g
    rows=[]
    for symbol in BRAZIL:
        if symbol not in valid:continue
        g=valid[symbol]
        for i in range(len(g)):
            crossing = [j for j in range(max(0,i-3),i+1) if bool(g.at[j,"cross"])]
            cross_i = crossing[-1] if crossing else None
            age = i-cross_i if cross_i is not None else None
            stage=None
            if age == 0:stage="CROSS_DETECTED"
            elif age is not None and 1<=age<=3 and g.at[i,"annual"]>0:
                if g.at[i,"dr2"]>0 and g.at[i,"r2"]>g.at[cross_i,"r2"]:
                    stage="REBUILDING_QUALIFIED"
                else:stage="REBUILD_WATCH"
            if not stage:continue
            date=g.at[i,"date"]; score=g.at[i,"score"]
            rivals=[]
            for other,otherg in valid.items():
                if other in BRAZIL:continue
                r=otherg[otherg.date==date]
                if not r.empty and pd.notna(r.iloc[0].score):
                    rivals.append((float(r.iloc[0].score),other))
            rivals.sort(reverse=True)
            record={"symbol":symbol,"date":date.strftime("%Y-%m-%d"),
                    "stage":stage,"annual":float(g.at[i,"annual"]),
                    "r2":float(g.at[i,"r2"]),"score":float(score),
                    "shadow_top1":bool(rivals and score>rivals[0][0]),
                    "best_other":rivals[0][1] if rivals else None,
                    "best_other_score":rivals[0][0] if rivals else None}
            for horizon in (5,10,20):
                end=i+horizon
                record[f"future_{horizon}d_close_return"]=(
                    float(g.at[end,"close"]/g.at[i,"close"]-1)
                    if end<len(g) else None)
                record[f"next_open_to_{horizon}d_close_return"]=(
                    float(g.at[end,"close"]/g.at[i+1,"open"]-1)
                    if end<len(g) and i+1<len(g) and g.at[i+1,"open"]>0 else None)
            rows.append(record)
    carriers=[]
    for symbol in BRAZIL:
        g=valid.get(symbol)
        carriers.append({"symbol":symbol,"bars":len(g) if g is not None else 0,
                         "first_date":g.date.min().strftime("%Y-%m-%d") if g is not None else None,
                         "last_date":g.date.max().strftime("%Y-%m-%d") if g is not None else None,
                         "latest_annual":float(g.annual.iloc[-1]) if g is not None else None,
                         "latest_r2":float(g.r2.iloc[-1]) if g is not None else None})
    result={"method":"26 day weighted OLS; preliminary shadow ranking, not state-map/FixV2 execution",
            "date_convention":"signal at close, next domestic trading session open for execution",
            "production_changed":False,"carriers":carriers,"events":rows,
            "note":"Research only. Shadow Top1 ignores FixV2 eligibility/state/route and costs; forward returns unadjusted for premium and spreads."}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"carriers":carriers,"events":len(rows),
                      "qualified":sum(r["stage"]=="REBUILDING_QUALIFIED" for r in rows)},
                     ensure_ascii=False))
if __name__=="__main__": main()
