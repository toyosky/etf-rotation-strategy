#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import date, datetime, time
from pathlib import Path

import psycopg2

ROOT=Path(__file__).resolve().parents[1]
START=date(2026,9,14)
COST=0.0006
DROP_FILTER=0.97
DRAWDOWN_FILTER=-0.02
OUT=ROOT/'data'/'minute-live.json'
SRC=ROOT/'data'/'live-forward.json'
VARIANTS=('baseline','original','freeze_cash')
LABELS={'baseline':'Frozen Baseline v1','original':'Original V1','freeze_cash':'Freeze → Cash'}

def dburl():
    x=os.environ.get('ETF_DAILY_BARS_DATABASE_URL','').strip()
    if not x: raise RuntimeError('ETF_DAILY_BARS_DATABASE_URL is not set')
    return x

def target_map(events,dates):
    ev=sorted(events,key=lambda x:x['signal_date'])
    cur=None; out={}; i=0
    for d in dates:
        ds=d.isoformat()
        while i<len(ev) and ev[i]['signal_date']<=ds:
            cur=ev[i].get('to'); i+=1
        out[d]=cur
    return out

def main():
    live=json.loads(SRC.read_text(encoding='utf-8'))
    with psycopg2.connect(dburl(),connect_timeout=30,application_name='minute_execution_forward') as conn:
        with conn.cursor() as cur:
            cur.execute("select distinct trade_date from public.minute_bars where trade_date >= %s order by trade_date",(START,))
            dates=[r[0] for r in cur.fetchall()]
            cur.execute("select trade_date,symbol,bar_time::time,close from public.minute_bars where trade_date >= %s and ((bar_time::time between time '09:30' and time '11:30') or (bar_time::time between time '13:00' and time '15:00')) order by trade_date,symbol,bar_time",(START,))
            rows=cur.fetchall()
    by={}
    for d,s,t,p in rows:
        by.setdefault((d,s),[]).append((t,float(p)))
    def px(d,s,hhmm):
        arr=by.get((d,s),[])
        for t,p in arr:
            if t==hhmm:return p
        return None
    def last_px(d,s):
        a=by.get((d,s),[]); return a[-1][1] if a else None
    def max_to(d,s,hhmm):
        a=[p for t,p in by.get((d,s),[]) if t<=hhmm]
        return max(a) if a else None
    complete=[d for d in dates if sum(1 for v in {s for dd,s in by if dd==d} if px(d,v,time(15,0)) is not None)>=10]
    settled_through=max(complete) if complete else None
    results={}
    for key in VARIANTS:
        tm=target_map(live['events'][key],dates)
        nav=1.0; holding=None; prev_close=None; series=[]; trades=[]
        for idx,d in enumerate(dates):
            desired=tm[d]
            is_complete=d in complete
            if idx==0:
                holding=desired
                startp=px(d,holding,time(9,31)) if holding else None
                endp=px(d,holding,time(15,0)) if holding and is_complete else (last_px(d,holding) if holding else None)
                if holding and startp and endp:
                    r=endp/startp-1
                    nav*=1+r
                else:r=0.0
                series.append({'date':d.isoformat(),'nav':nav,'return':r,'holding':holding,'status':'settled' if is_complete else 'mark_to_market','note':'inherited_start'})
                if is_complete and holding: prev_close=px(d,holding,time(15,0))
                continue
            if not is_complete:
                # latest partial-day mark-to-market from prior close with no irreversible execution booking
                mtm=nav
                if holding and prev_close:
                    lp=last_px(d,holding)
                    if lp: mtm*=lp/prev_close
                series.append({'date':d.isoformat(),'nav':mtm,'return':mtm/nav-1,'holding':holding,'status':'mark_to_market','note':'partial_day'})
                continue
            before=nav
            if desired==holding:
                if holding and prev_close:
                    cp=px(d,holding,time(15,0))
                    if cp: nav*=cp/prev_close
                series.append({'date':d.isoformat(),'nav':nav,'return':nav/before-1,'holding':holding,'status':'settled','note':'hold'})
            else:
                sellp=px(d,holding,time(14,0)) if holding else None
                if holding and prev_close and sellp:
                    nav*=sellp/prev_close
                    nav*=1-COST
                old=holding
                holding=None
                blocked=None
                if desired:
                    p0931=px(d,desired,time(9,31)); prev_desired=px(dates[idx-1],desired,time(15,0)) if idx>0 else None
                    p1405=px(d,desired,time(14,5)); hi=max_to(d,desired,time(14,5))
                    if p0931 and prev_desired and p0931/prev_desired < DROP_FILTER:
                        blocked='09:31_DROP'
                    elif p1405 and hi and p1405/hi-1 <= DRAWDOWN_FILTER:
                        blocked='14:05_DRAWDOWN'
                    elif p1405:
                        nav*=1-COST
                        holding=desired
                if holding:
                    cp=px(d,holding,time(15,0)); bp=px(d,holding,time(14,5))
                    if cp and bp: nav*=cp/bp
                trades.append({'date':d.isoformat(),'from':old,'desired':desired,'actual':holding,'sell_1400':sellp,'buy_1405':px(d,desired,time(14,5)) if desired else None,'blocked':blocked})
                series.append({'date':d.isoformat(),'nav':nav,'return':nav/before-1,'holding':holding,'status':'settled','note':'switch' if not blocked else blocked})
            prev_close=px(d,holding,time(15,0)) if holding else None
        results[key]={'label':LABELS[key],'series':series,'trades':trades,'settled_return':next((x['nav'] for x in reversed(series) if x['status']=='settled'),1.0)-1,'latest_nav':series[-1]['nav'] if series else 1.0,'latest_holding':holding}
    payload={'tracking_start':START.isoformat(),'settled_through':settled_through.isoformat() if settled_through else None,'cost_per_side':COST,'execution_rules':{'09:31_drop_ratio':DROP_FILTER,'sell':'14:00 minute close','buy':'14:05 minute close','14:05_drawdown':DRAWDOWN_FILTER},'variants':results,'note':'Minute forward execution model. Tencent five-day timeline is used only to bridge the 2026-09-14 start; canonical m1 is used when available. No data before 2026-09-14.'}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'settled_through':payload['settled_through'],'returns':{k:v['settled_return'] for k,v in results.items()},'holdings':{k:v['latest_holding'] for k,v in results.items()}},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
