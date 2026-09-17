#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, date
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import execute_values

START=date(2026,9,14)
SH=ZoneInfo('Asia/Shanghai')
SOURCE='tencent_mkline_m1'
SYMBOLS=(
 '159934','159985','161226','513100','159957','159509','513290','159529',
 '159981','501018','513530','511380','164824','511220','513500'
)

def txcode(s:str)->str:
    return ('sh' if s.startswith(('5','6','9')) else 'sz')+s

def get_json(url:str):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.qq.com/','Accept':'application/json,text/plain,*/*'})
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read().decode('utf-8','replace').strip()
    if '=' in raw and not raw.lstrip().startswith('{'):
        raw=raw.split('=',1)[1].strip().rstrip(';')
    return json.loads(raw)

def parse_mkline(symbol:str,count:int=1200):
    code=txcode(symbol)
    url='https://ifzq.gtimg.cn/appstock/app/kline/mkline?'+urllib.parse.urlencode({'param':f'{code},m1,,{count}'})
    obj=get_json(url)
    node=((obj.get('data') or {}).get(code) or {})
    arr=node.get('m1') or []
    out=[]
    for row in arr:
        if not isinstance(row,list) or len(row)<6: continue
        try:
            ts=datetime.strptime(str(row[0]),'%Y%m%d%H%M')
            if ts.date()<START: continue
            o,c,h,l=(float(row[i]) for i in (1,2,3,4))
            vol=int(round(float(row[5])*100))
        except Exception:
            continue
        if min(o,c,h,l)<=0 or h<max(o,c,l) or l>min(o,c,h): continue
        out.append((symbol,ts,1,o,h,l,c,vol,SOURCE))
    return out, len(arr)

def database_url():
    v=os.environ.get('ETF_DAILY_BARS_DATABASE_URL','').strip()
    if not v: raise RuntimeError('ETF_DAILY_BARS_DATABASE_URL is not set')
    return v

def upsert(conn,rows):
    sql='''
    insert into public.minute_bars
      (symbol,bar_time,interval_min,open,high,low,close,volume_shares,source)
    values %s
    on conflict(symbol,bar_time,interval_min) do update set
      open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,
      volume_shares=excluded.volume_shares,source=excluded.source,ingested_at=now()
    '''
    with conn.cursor() as cur:
        execute_values(cur,sql,rows,page_size=2000)

def main():
    all_rows=[]; raw_counts={}; errors={}
    for s in SYMBOLS:
        try:
            rows,n=parse_mkline(s)
            raw_counts[s]=n; all_rows.extend(rows)
            print(f'{s}: raw={n} kept={len(rows)}',flush=True)
        except Exception as e:
            errors[s]=repr(e)
        time.sleep(.08)
    if not all_rows:
        raise RuntimeError(f'No minute rows returned: {errors}')
    all_rows=list({(r[0],r[1],r[2]):r for r in all_rows}.values())
    with psycopg2.connect(database_url(),connect_timeout=30,application_name='github_tencent_minute_forward') as conn:
        upsert(conn,all_rows)
        with conn.cursor() as cur:
            cur.execute("select min(trade_date),max(trade_date),count(*),count(distinct symbol) from public.minute_bars where trade_date >= %s",(START,))
            span=cur.fetchone()
            cur.execute("select trade_date,count(*),count(distinct symbol) from public.minute_bars where trade_date >= %s group by trade_date order by trade_date",(START,))
            daily=cur.fetchall()
    summary={'status':'PASS','tracking_start':START.isoformat(),'run_at':datetime.now(SH).isoformat(),'rows_upserted':len(all_rows),'raw_counts':raw_counts,'errors':errors,'stored_span':[str(span[0]),str(span[1])],'stored_rows':span[2],'stored_symbols':span[3],'by_date':[{'date':str(d),'rows':n,'symbols':k} for d,n,k in daily]}
    open('tencent-minute-forward-summary.json','w',encoding='utf-8').write(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
