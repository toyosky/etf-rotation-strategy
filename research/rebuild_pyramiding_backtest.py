#!/usr/bin/env python3
"""Walk-forward audit of staged position sizing for R2 rebuilding signals.

Frozen signal:
- 26-session weighted OLS, half-life 10
- annual crosses <=0 -> >0
- first REBUILDING_QUALIFIED observation within 1-3 sessions:
  annual > 0, 1d delta R2 > 0, current R2 > R2 at cross

Execution:
- decisions at close, trades at next domestic session open
- maximum episode horizon 20 sessions after initial qualified signal
- if annual <= 0 after entry: liquidate at next open
- otherwise unconfirmed positions keep their existing bottom position; no forced
  reduction merely because R2 softens

Sizing families are pre-declared and evaluated on 2021-2024 discovery, then
reported unchanged on 2025-2026 validation.
"""
from __future__ import annotations
import json, math, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from automation.build_fundamental_audit_trigger import calc_ols, db_url, RISK_POOL
OUT=ROOT/"data/rebuild-pyramiding-backtest.json"
COST=0.0006
MAX_H=20
ASSETS=sorted(set(RISK_POOL))  # includes Brazil research carriers in current repo

# stage 2 = persistence confirmation: two consecutive closes with annual>0,
# R2 above entry R2, and score above entry score.
# stage 3 = established trend: additionally reaches an absolute R2 threshold.
SCHEMES=[
 {"name":"FULL_100","alloc":[1.0,0.0,0.0],"r2_full":None},
 {"name":"TWO_30_70","alloc":[0.30,0.70,0.0],"r2_full":None},
 {"name":"TWO_50_50","alloc":[0.50,0.50,0.0],"r2_full":None},
]
for a in ((0.20,0.30,0.50),(0.30,0.30,0.40),(0.40,0.30,0.30),(0.50,0.25,0.25)):
    for t in (0.30,0.40,0.50):
        SCHEMES.append({"name":f"THREE_{int(a[0]*100)}_{int(a[1]*100)}_{int(a[2]*100)}_R2_{int(t*100)}",
                        "alloc":list(a),"r2_full":t})

def prepare(g):
    g=g.sort_values("date").copy().reset_index(drop=True)
    annual,r2=calc_ols(g.close.to_numpy(float))
    g["annual"]=annual; g["r2"]=r2
    g["score"]=np.where(g.annual>0,g.annual*g.r2,0.0)
    g["dr2_1"]=g.r2.diff()
    g["cross"]=(g.annual.shift(1)<=0)&(g.annual>0)
    return g

def first_qualified_events(g):
    events=[]
    i=0
    while i<len(g):
        if not bool(g.at[i,"cross"]):
            i+=1; continue
        cross=i; q=None
        for j in range(i+1,min(i+4,len(g))):
            if (g.at[j,"annual"]>0 and g.at[j,"dr2_1"]>0 and
                g.at[j,"r2"]>g.at[cross,"r2"]):
                q=j; break
        if q is not None and q+1<len(g):
            events.append((cross,q))
        i=max(i+1,(q+1 if q is not None else i+1))
    return events

def next_open(g, signal_i):
    j=signal_i+1
    return (j,float(g.at[j,"open"])) if j<len(g) and g.at[j,"open"]>0 else (None,None)

def simulate(g,q,scheme):
    entry_i,entry_px=next_open(g,q)
    if entry_i is None:return None
    alloc=scheme["alloc"]
    fills=[(entry_i,alloc[0],entry_px)] if alloc[0]>0 else []
    invested=alloc[0]
    entry_r2=float(g.at[q,"r2"]); entry_score=float(g.at[q,"score"])
    stage2=False; stage3=False
    pos_streak=0
    exit_i=min(q+MAX_H,len(g)-1)
    for t in range(q+1,min(q+MAX_H+1,len(g)-1)):
        # sell next open after structural failure
        if pd.notna(g.at[t,"annual"]) and g.at[t,"annual"]<=0:
            exit_i=t+1
            break
        good=(g.at[t,"annual"]>0 and g.at[t,"r2"]>entry_r2 and g.at[t,"score"]>entry_score)
        pos_streak=pos_streak+1 if good else 0
        if (not stage2) and pos_streak>=2 and alloc[1]>0:
            j,px=next_open(g,t)
            if j is not None:
                fills.append((j,alloc[1],px)); invested+=alloc[1]; stage2=True
        if stage2 and (not stage3) and alloc[2]>0:
            thr=scheme["r2_full"]
            if thr is not None and g.at[t,"annual"]>0 and g.at[t,"r2"]>=thr and g.at[t,"score"]>entry_score:
                j,px=next_open(g,t)
                if j is not None:
                    fills.append((j,alloc[2],px)); invested+=alloc[2]; stage3=True
    # exit at close for time-cap; next-open on failure
    if exit_i<=q+MAX_H and exit_i<len(g) and g.at[exit_i,"annual"]<=0:
        exit_px=float(g.at[exit_i,"open"]); exit_date=g.at[exit_i,"date"]
    else:
        exit_i=min(q+MAX_H,len(g)-1); exit_px=float(g.at[exit_i,"close"]); exit_date=g.at[exit_i,"date"]
    pnl=0.0
    curve=[]
    for fi,w,px in fills:
        pnl += w*((exit_px/px)-1) - w*(2*COST)
    # cash fraction has 0 return. Approximate event MDD on marked positions.
    for t in range(entry_i,exit_i+1):
        v=1.0-invested
        for fi,w,px in fills:
            if fi<=t:
                v += w*(float(g.at[t,"close"])/px)
            else:
                v += w
        curve.append(v)
    mdd=0.0
    if curve:
        a=np.asarray(curve); peak=np.maximum.accumulate(a); mdd=float(np.min(a/peak-1))
    return {"ret":float(pnl),"mdd":mdd,"invested":float(invested),
            "fills":len(fills),"stage2":stage2,"stage3":stage3,
            "exit_date":pd.Timestamp(exit_date).strftime("%Y-%m-%d")}

def stats(x):
    if not x:return {}
    r=np.array([z["ret"] for z in x]); d=np.array([z["mdd"] for z in x]); inv=np.array([z["invested"] for z in x])
    return {"n":len(x),"mean_return":float(r.mean()),"median_return":float(np.median(r)),
            "win_rate":float((r>0).mean()),"mean_mdd":float(d.mean()),
            "p10_return":float(np.quantile(r,.10)),"mean_invested":float(inv.mean()),
            "full_invest_rate":float((inv>=.999).mean())}

def main():
    eng=create_engine(db_url(os.environ["ETF_DAILY_BARS_DATABASE_URL"]))
    with eng.connect() as conn:
        bars=pd.read_sql_query(text("select symbol,date,open,close from public.daily_bars where symbol=any(:s) order by symbol,date"),
                               conn,params={"s":ASSETS},parse_dates=["date"])
    bars["symbol"]=bars.symbol.astype(str).str.zfill(6)
    allrows=[]
    asset_events={}
    for s,g0 in bars.groupby("symbol"):
        g=prepare(g0)
        ev=first_qualified_events(g); asset_events[s]=len(ev)
        for cross,q in ev:
            yr=int(g.at[q,"date"].year)
            if yr<2021:continue
            for scheme in SCHEMES:
                z=simulate(g,q,scheme)
                if z:
                    z.update({"symbol":s,"signal_date":g.at[q,"date"].strftime("%Y-%m-%d"),
                              "cross_date":g.at[cross,"date"].strftime("%Y-%m-%d"),
                              "year":yr,"scheme":scheme["name"]})
                    allrows.append(z)
    df=pd.DataFrame(allrows)
    summaries=[]
    for scheme in [s["name"] for s in SCHEMES]:
        sx=df[df.scheme==scheme]
        for seg,mask in [("DISCOVERY_2021_2024",sx.year.between(2021,2024)),
                         ("VALIDATION_2025_2026",sx.year.between(2025,2026)),
                         ("FULL_2021_2026",sx.year.between(2021,2026))]:
            st=stats(sx[mask].to_dict("records")); st.update({"scheme":scheme,"segment":seg}); summaries.append(st)
    sm=pd.DataFrame(summaries)
    disc=sm[sm.segment=="DISCOVERY_2021_2024"].copy()
    # Simple predeclared utility: reward return, penalize drawdown and low-tail loss.
    disc["utility"]=disc.mean_return + 0.5*disc.mean_mdd + 0.25*disc.p10_return
    best=disc.sort_values("utility",ascending=False).iloc[0]["scheme"]
    result={"version":"rebuild-pyramiding-v1","cost_per_side":COST,"max_horizon_sessions":MAX_H,
            "stage2":"two consecutive post-entry closes: annual>0, R2>entry R2, score>entry score",
            "stage3":"stage2 reached + absolute R2 threshold (0.30/0.40/0.50 depending scheme)",
            "failure_exit":"annual<=0 -> next-session open; R2 softening alone only freezes additions",
            "selection":"best scheme selected ONLY on 2021-2024 utility = mean_return + 0.5*mean_mdd + 0.25*p10_return",
            "selected_scheme":best,
            "selected_discovery":sm[(sm.scheme==best)&(sm.segment=="DISCOVERY_2021_2024")].to_dict("records")[0],
            "selected_validation":sm[(sm.scheme==best)&(sm.segment=="VALIDATION_2025_2026")].to_dict("records")[0],
            "baseline_discovery":sm[(sm.scheme=="FULL_100")&(sm.segment=="DISCOVERY_2021_2024")].to_dict("records")[0],
            "baseline_validation":sm[(sm.scheme=="FULL_100")&(sm.segment=="VALIDATION_2025_2026")].to_dict("records")[0],
            "summaries":summaries,"asset_event_counts":asset_events}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("selected_scheme","selected_discovery","selected_validation","baseline_validation")},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
