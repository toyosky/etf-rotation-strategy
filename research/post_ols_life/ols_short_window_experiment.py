#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
from sqlalchemy import create_engine
RESEARCH_DIR=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(RESEARCH_DIR))
import full_market_ols_storage as fm

WINDOWS=(5,10,15,20,26); BASE=26
FIXED15=["518880","159985","159825","161226","513100","159915","511220","159509","513290","159529","159981","501018","513920","511380","164824"]
START=pd.Timestamp("2021-01-01"); SPLIT=pd.Timestamp("2025-01-01")

def period(d): return "2021-2024" if d<SPLIT else "2025-2026"

def features_for(bars,w):
    old=fm.LOOKBACK
    try:
        fm.LOOKBACK=w
        return fm.build_features(bars)
    finally: fm.LOOKBACK=old

def leaders(f):
    f=f.copy(); f["symbol"]=f.symbol.astype(str).str.zfill(6)
    m=(f.date>=START)&f.symbol.isin(FIXED15)&(f.annual>0)&(f.r2>0)&(f.score>0)&(~f.recent_drop3.fillna(False))
    c=f.loc[m,["date","symbol","score"]].sort_values(["date","score","symbol"],ascending=[True,False,False])
    return c.groupby("date",as_index=False).first().rename(columns={"symbol":"leader","score":"leader_score"})

def run_stats(x,w):
    rows=[]
    for p,g in x.groupby("period"):
        g=g.sort_values("date"); s=g.leader.dropna()
        ch=(s!=s.shift()).sum(); runs=s.groupby((s!=s.shift()).cumsum()).size()
        rows.append(dict(window=w,period=p,leader_days=len(s),leader_runs=int(ch),mean_tenure=float(runs.mean()),median_tenure=float(runs.median()),change_rate=float((s!=s.shift()).iloc[1:].mean()) if len(s)>1 else np.nan))
    return rows

def main():
    url=os.getenv("ETF_DAILY_BARS_DATABASE_URL")
    if not url: raise SystemExit("missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(os.getenv("OUTPUT_DIR","ols-short-window-output")); out.mkdir(parents=True,exist_ok=True)
    bars=fm.load_daily_bars(create_engine(fm._db_url(url),pool_pre_ping=True))
    bars["symbol"]=bars.symbol.astype(str).str.zfill(6); bars["date"]=pd.to_datetime(bars.date)
    close=bars.pivot(index="date",columns="symbol",values="close").sort_index()
    allL={}; stats=[]
    dates=pd.DataFrame({"date":sorted(bars.loc[bars.date>=START,"date"].unique())})
    for w in WINDOWS:
        L=leaders(features_for(bars,w))
        d=dates.merge(L,on="date",how="left"); d["period"]=d.date.map(period)
        allL[w]=d; stats+=run_stats(d,w)
    base=allL[BASE][["date","leader"]].rename(columns={"leader":"base_leader"})
    event_rows=[]
    horizons=(1,3,5,10,20)
    for w in WINDOWS[:-1]:
        d=allL[w][["date","leader"]].merge(base,on="date")
        d=d[(d.leader.notna())&(d.base_leader.notna())&(d.leader!=d.base_leader)].copy()
        for r in d.itertuples(index=False):
            if r.date not in close.index or r.leader not in close.columns or r.base_leader not in close.columns: continue
            i=close.index.get_loc(r.date)
            row={"window":w,"date":r.date,"period":period(r.date),"short_leader":r.leader,"base_leader":r.base_leader}
            for h in horizons:
                if i+h>=len(close): row[f"rel_fwd{h}"]=np.nan; continue
                a=close.iloc[i+h][r.leader]/close.iloc[i][r.leader]-1
                b=close.iloc[i+h][r.base_leader]/close.iloc[i][r.base_leader]-1
                row[f"rel_fwd{h}"]=a-b
            event_rows.append(row)
    ev=pd.DataFrame(event_rows)
    summ=[]
    for (w,p),g in ev.groupby(["window","period"]):
        z={"window":w,"period":p,"disagreement_days":len(g)}
        for h in horizons:
            x=g[f"rel_fwd{h}"].dropna(); z[f"mean_rel{h}"]=float(x.mean()); z[f"win_rate{h}"]=float((x>0).mean())
        summ.append(z)
    pd.DataFrame(stats).to_csv(out/"tenure.csv",index=False)
    ev.to_csv(out/"disagreement_events.csv",index=False)
    pd.DataFrame(summ).to_csv(out/"relative_forward.csv",index=False)
    summary={"data_asof":str(bars.date.max().date()),"windows":WINDOWS,"tenure":stats,"relative_forward":summ}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    md=["# OLS short-window experiment","",f"Data as of: {summary['data_asof']}","","## Tenure","",pd.DataFrame(stats).to_markdown(index=False),"","## Short-window leader vs 26d leader","",pd.DataFrame(summ).to_markdown(index=False)]
    (out/"summary.md").write_text("\n".join(md),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
if __name__=="__main__": main()
