#!/usr/bin/env python3
"""Dual-engine, research-only Top1 plus R2 trend rebuilding sleeve backtest.

Reads Supabase production bars and isolated sector candidate bars. Does not change
any trading rule, production symbol registry or notification.
"""
from __future__ import annotations
import json
import math
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research"))
from full_market_ols_storage import build_features, _db_url
from walk_forward_candidate_pool import build_daily_targets, backtest_open_to_open
from sector_exposure_increment_v1.run import BASE, SECTORS

OUT = ROOT / "data" / "sector-dual-engine-backtest-20261018.json"
SIDE_COST = 0.0006
BEGIN = pd.Timestamp("2021-01-01")
DISCOVERY_END = pd.Timestamp("2024-12-31")
REBUILD_MAX_AGE = 20
VARIANTS = {
 "BASE": BASE,
 "ADD_BANK": BASE+["512800"],
 "ADD_AGRI_FUGUO": BASE+["159825"],
 "ADD_AGRI_JIASHI": BASE+["516550"],
 "ADD_DEFENSE": BASE+["512660"],
 "ADD_ALL": BASE+["512800","159825","512660"],
}

@dataclass
class Event:
    symbol:str
    signal_date:pd.Timestamp
    start:int
    end:int
    stage2:int
    stage3:int
    score:float

def num(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError):
        return None

def events_from_features(f, calendar):
    idx={pd.Timestamp(d):i for i,d in enumerate(calendar)}
    result=[]
    totals=Counter()
    passcounts=Counter()
    for symbol,g0 in f.groupby("symbol",sort=False):
        g=g0.sort_values("date").reset_index(drop=True)
        dates=g.date.tolist()
        annual=g.annual.to_numpy(float)
        r2=g.r2.to_numpy(float)
        score=g.score.to_numpy(float)
        cross=(np.roll(annual,1)<=0) & (annual>0)
        cross[0]=False
        for i in np.flatnonzero(cross):
            q=None
            for j in range(i+1,min(i+4,len(g))):
                if annual[j]>0 and r2[j]>r2[i] and r2[j]>r2[j-1]:
                    q=j
                    break
            if q is None or pd.Timestamp(dates[q])<pd.Timestamp("2020-12-01"):
                continue
            totals[symbol]+=1
            if not bool(g.at[q,"trend_eligible"]):
                continue
            passcounts[symbol]+=1
            qday=pd.Timestamp(dates[q])
            if qday not in idx or idx[qday]+1>=len(calendar):
                continue
            start=idx[qday]+1
            end=min(idx[pd.Timestamp(dates[min(q+REBUILD_MAX_AGE,len(g)-1)])]+1,len(calendar))
            s2=len(calendar)+1
            s3=len(calendar)+1
            streak=0
            confirmed=False
            for j in range(q+1,min(q+REBUILD_MAX_AGE+1,len(g))):
                if annual[j]<=0:
                    end=min(end,idx[pd.Timestamp(dates[j])]+1)
                    break
                good=annual[j]>0 and r2[j]>r2[q] and score[j]>score[q]
                streak=streak+1 if good else 0
                if not confirmed and streak>=2:
                    s2=idx[pd.Timestamp(dates[j])]+1
                    confirmed=True
                if confirmed and s3>len(calendar) and r2[j]>=0.50 and score[j]>score[q]:
                    s3=idx[pd.Timestamp(dates[j])]+1
            if end<=start: continue
            result.append(Event(symbol,qday,start,end,s2,s3,float(score[q])))
    return result,dict(totals),dict(passcounts)

def simulate_rebuild(events, symbols, calendar, open_wide, capacity):
    per_start={}
    for ev in events:
        if ev.symbol in symbols:
            per_start.setdefault(ev.start,[]).append(ev)
    for candidates in per_start.values():
        candidates.sort(key=lambda e:(-e.score,e.symbol))
    cash=1.0
    shares={}
    active={}
    last_price={}
    entries=Counter()
    fill_count=Counter()
    nav_rows=[]
    missing=0
    net_turnover=0.0
    for i in range(len(calendar)-1):
        today=pd.Timestamp(calendar[i])
        following=pd.Timestamp(calendar[i+1])
        def open_price(symbol,day_i):
            try:
                v=float(open_wide.at[calendar[day_i],symbol])
                return v if math.isfinite(v) and v>0 else None
            except (KeyError,ValueError,TypeError):
                return None
        def value(symbol,day_i):
            px=open_price(symbol,day_i)
            if px is not None:
                last_price[symbol]=px
                return px
            return last_price.get(symbol)
        for s in set(shares)|set(active):
            value(s,i)
        if any(s not in last_price for s in shares):
            raise RuntimeError("Missing market price for held ETF")
        nav_before=cash+sum(v*last_price[s] for s,v in shares.items())
        if nav_before<=0: raise RuntimeError("Bankrupt sleeve")

        # Decisions use observations no later than the previous day's close.
        for sym,ev in list(active.items()):
            if i>=ev.end:
                px=open_price(sym,i)
                if px is None:
                    missing+=1
                    continue
                quantity=shares.pop(sym,0.0)
                cash+=quantity*px*(1-SIDE_COST)
                net_turnover+=quantity*px/nav_before
                del active[sym]

        for ev in per_start.get(i,[]):
            if len(active)>=capacity: break
            if ev.symbol in active: continue
            if open_price(ev.symbol,i) is None:
                missing+=1
                continue
            active[ev.symbol]=ev
            setattr(ev,"_bought_fraction",0.0)
            entries[ev.symbol]+=1

        # Each episode has an equal RESERVED slot. Buy only when stage advances.
        # No hidden daily forced rebalance or price look-ahead.
        for sym,ev in list(active.items()):
            px=open_price(sym,i)
            if px is None:
                missing+=1
                continue
            target_step=0.2
            if i>=ev.stage2: target_step=0.5
            if i>=ev.stage3: target_step=1.0
            # Book cumulative funded fraction per event rather than resetting
            # to target weights daily. Tracks staged allocations explicitly.
            bought=getattr(ev,"_bought_fraction",0.0)
            delta=max(0.0,target_step-bought)
            if delta>0:
                # slot notional allocated relative to NAV at each stage
                qty_cost=min(cash/(1+SIDE_COST),delta*nav_before/capacity)
                if qty_cost>0:
                    cash-=qty_cost*(1+SIDE_COST)
                    shares[sym]=shares.get(sym,0.0)+qty_cost/px
                    net_turnover+=qty_cost/nav_before
                    fill_count[sym]+=1
                    setattr(ev,"_bought_fraction",bought+delta)
        nav_after=cash
        stale_here=0
        for sym,qty in shares.items():
            px=value(sym,i+1)
            if px is None: raise RuntimeError("Missing future and stale price for "+sym)
            if open_price(sym,i+1) is None: stale_here+=1
            nav_after+=qty*px
        missing+=stale_here
        nav_rows.append({"date":today,"ret":nav_after/nav_before-1,
                         "active_symbols":sorted(active),"active_slots":len(active),
                         "invested_fraction":sum(shares[s]*last_price[s] for s in shares)/nav_after
                         if nav_after>0 else 0})
    df=pd.DataFrame(nav_rows)
    return df,{"accepted_events":dict(entries),"accepted_event_count":int(sum(entries.values())),
                "fill_count":int(sum(fill_count.values())),"missing_quote_marks":missing,
                "turnover_notional_units":net_turnover,
                "avg_active_slots":float(df.loc[df.date>=BEGIN,"active_slots"].mean()),
                "avg_invested_fraction":float(df.loc[df.date>=BEGIN,"invested_fraction"].mean())}

def max_drawdown(a):
    v=(1+a).cumprod()
    return float((v/v.cummax()-1).min())

def period(df,start,end=None):
    g=df.loc[df.date>=pd.Timestamp(start)].copy()
    if end is not None: g=g.loc[g.date<=pd.Timestamp(end)]
    if g.empty:return {}
    v=(1+g.net_ret).cumprod()
    total=float(v.iloc[-1]-1)
    duration=max(1,(g.date.iloc[-1]-g.date.iloc[0]).days)
    return {
      "days":len(g),
      "total_return":total,
      "cagr":float((1+total)**(365.25/duration)-1) if total>-1 else -1,
      "max_drawdown":max_drawdown(g.net_ret),
      "daily_vol_annual":float(g.net_ret.std()*np.sqrt(250)),
      "positive_day_ratio":float((g.net_ret>0).mean()),
    }

def main():
    db=os.environ["ETF_DAILY_BARS_DATABASE_URL"]
    engine=create_engine(_db_url(db),pool_pre_ping=True)
    with engine.connect() as c:
        mainbar=pd.read_sql_query(text("""select symbol,date,open,high,low,close,volume,amount
        from public.daily_bars where symbol=any(:s) order by symbol,date"""),
        c,params={"s":BASE},parse_dates=["date"])
        add=pd.read_sql_query(text("""select symbol,date,open,high,low,close,volume,amount
        from research.sector_candidate_bars where symbol=any(:s) order by symbol,date"""),
        c,params={"s":list(SECTORS)},parse_dates=["date"])
    bars=pd.concat([mainbar,add],ignore_index=True)
    expected=set(BASE)|set(SECTORS)
    if set(bars.symbol.astype(str))!=expected:
        raise RuntimeError("Missing sector or baseline bars")
    features=build_features(bars)
    # Full calendar uses baseline market open dates only; do not create artificial
    # tradable intervals on non-A-share market dates.
    calendar=pd.Index(sorted(mainbar.date.unique()))
    open_wide=bars.pivot(index="date",columns="symbol",values="open").reindex(calendar)
    events,generated,eligible=events_from_features(features,calendar)
    result={"version":"dual_ols_rebuild_sector_v1",
            "data_end":str(pd.Timestamp(calendar[-1]).date()),
            "interpretation":"Fixed-weight daily combining independently simulated sleeves, no top-level rebalancing fee; research approximation",
            "r2_rebuild":"26-bar HL10, first qualified 1-3 days after annual cross, liquidity and D2 admission at qualification; chosen historical 20/30/50 R2>=0.5 staged additions, max20 sessions, exit annual<=0",
            "cost_per_trade_side":SIDE_COST,
            "tests":{}, "generated_events_by_symbol":generated,
            "eligible_events_by_symbol":eligible,
            "production_changed":False}

    for label,symbols in VARIANTS.items():
        mask=features.symbol.isin(symbols)
        ff=features.loc[mask]
        targets,counts=build_daily_targets(ff,"baseline")
        top_pnl=backtest_open_to_open(bars.loc[bars.symbol.isin(symbols)],targets)
        top_pnl=top_pnl[["date","net_ret","missing_quote"]].copy().rename(
          columns={"net_ret":"top1_ret"})
        # Explicitly keep original Top1 series, without retuning to rebuild.
        entry={"top1_only":{
          "discovery":period(top_pnl.rename(columns={"top1_ret":"net_ret"}),"2021-01-01","2024-12-31"),
          "validation":period(top_pnl.rename(columns={"top1_ret":"net_ret"}),"2025-01-01")},
          "missing_top1_quote_days":int(top_pnl.loc[top_pnl.date>=BEGIN,"missing_quote"].sum())}
        for max_slots in (1,3):
            r2_daily,diagnostics=simulate_rebuild(events,set(symbols),calendar,open_wide,max_slots)
            # R2 returns at open date i; top1 date i means holding from open(i)
            # to open(i+1) with the prior close's target.
            merged=top_pnl.merge(r2_daily[["date","ret","active_slots","invested_fraction"]],
                                 on="date",how="inner").rename(columns={"ret":"rebuild_ret"})
            entry[f"rebuild_{max_slots}_slot"]={
             "discovery":period(merged[["date","rebuild_ret"]].rename(columns={"rebuild_ret":"net_ret"}),"2021-01-01","2024-12-31"),
             "validation":period(merged[["date","rebuild_ret"]].rename(columns={"rebuild_ret":"net_ret"}),"2025-01-01"),
             "diagnostics":diagnostics}
            for top_weight in (0.5,0.7):
                mixture=merged[["date"]].copy()
                mixture["net_ret"]=top_weight*merged.top1_ret+(1-top_weight)*merged.rebuild_ret
                entry[f"mix_{int(top_weight*100)}_{int((1-top_weight)*100)}_{max_slots}_slot"]={
                 "discovery":period(mixture,"2021-01-01","2024-12-31"),
                 "validation":period(mixture,"2025-01-01")}
        result["tests"][label]=entry

    # Use the identical daily calendar and signal rule in every counterfactual.
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    summary={"status":"PASS","data_end":result["data_end"],"assets":len(expected)}
    for k,v in result["tests"].items():
        summary[k]={key:{"discovery":round(r["discovery"]["total_return"],4),
                          "validation":round(r["validation"]["total_return"],4),
                          "validation_mdd":round(r["validation"]["max_drawdown"],4)}
                    for key,r in v.items() if key.startswith("mix_")}
    print(json.dumps(summary,ensure_ascii=False))

if __name__=="__main__":
    main()
