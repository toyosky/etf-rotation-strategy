#!/usr/bin/env python3
"""Full A-share oversold/value/reversal/OLS research V1.

Research-only. No Supabase writes and no production strategy changes.

Past-only backtest contract
---------------------------
Universe: current exchange-listed A shares from Eastmoney list API (SH/SZ/BJ),
excluding ST/*ST/退 names from signal eligibility.
Price source: Tencent Westock qfq (split/dividend adjusted) daily bars; Eastmoney is used only for universe
and current valuation snapshot. Backtest starts 2025-01-01, bootstrap history
starts 2024-07-01.
Financial source: Tencent Westock finance --num 8 --raw, fetched only for stocks
that ever satisfy the price drawdown screen. A report becomes usable only from
InfoPublDate onward.

VALUE_OVERSOLD episode starts when:
- trailing 60-session peak-high to close drawdown <= -20%;
- latest published deducted net profit > 0;
- same-period deducted-profit YoY >= -20% when comparable prior period exists;
- not ST/*ST/退.

EARLY_REVERSAL: first close within 40 sessions after episode start with:
- 5-session log-price OLS slope > 0;
- 3-session close return > 0;
- close > 5-session average close;
- close > trailing 10-session minimum close.
This is intentionally simple and frozen before the run; no parameter search.

OLS_REBUILD: existing frozen ETF contract:
26-session weighted log-price OLS, half-life 10 (q^2 effective weights);
annual crosses <=0 -> >0; first observation 1-3 sessions later with annual>0,
1d R2 improving, and R2 > cross-day R2.

All signals form at close and hypothetical entry is next session open.
Evaluation is fixed-horizon 1/5/10/20/40 session close return plus 20-session MDD.
"""
from __future__ import annotations
import argparse,csv,gzip,json,math,os,subprocess,sys,time,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd

PACKAGE="westock-data-skillhub@1.0.5"
ROOT=Path("research/stock_value/full_market_v1")
OUT=ROOT/"output"
RESULTS=Path("research/stock_value/results")
CACHE=ROOT/"cache"
BACKTEST_START=pd.Timestamp("2025-01-01")
BOOTSTRAP_START="2024-07-01"
DD_THRESHOLD=-0.20
PROFIT_YOY_FLOOR=-20.0
WATCH_SESSIONS=40
LOOKBACK=26
HALF_LIFE=10.0
ANNUALIZATION=250.0

def http_json(url,params,attempts=4):
    q=url+"?"+urllib.parse.urlencode(params)
    err=""
    for i in range(attempts):
        try:
            req=urllib.request.Request(q,headers={"User-Agent":"Mozilla/5.0","Referer":"https://quote.eastmoney.com/"})
            with urllib.request.urlopen(req,timeout=25) as r:
                return json.loads(r.read().decode("utf-8","replace"))
        except Exception as ex:
            err=str(ex)
            time.sleep(min(2**i,8))
    raise RuntimeError(err)

def sina_list_page(node,page):
    params={"page":page,"num":100,"sort":"symbol","asc":1,"node":node,"_s_r_a":"page"}
    url="https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    q=url+"?"+urllib.parse.urlencode(params)
    err=""
    for i in range(4):
        try:
            req=urllib.request.Request(q,headers={"User-Agent":"Mozilla/5.0","Referer":"https://vip.stock.finance.sina.com.cn/"})
            with urllib.request.urlopen(req,timeout=25) as r:
                raw=r.read().decode("utf-8","replace")
            data=json.loads(raw)
            return data if isinstance(data,list) else []
        except Exception as ex:
            err=str(ex);time.sleep(min(1.5*(i+1),5))
    raise RuntimeError(f"Sina list failed node={node} page={page}: {err}")

def collect_sina_node(node,max_pages=100):
    rows=[]
    for page in range(1,max_pages+1):
        part=sina_list_page(node,page)
        if not part: break
        rows.extend(part)
        if len(part)<100: break
        time.sleep(0.12)
    return rows

def universe():
    raw=collect_sina_node("hs_a",80)
    if len(raw)<5000:
        raise RuntimeError(f"Sina hs_a universe unexpectedly small: {len(raw)}")
    # BSE node names are not documented consistently; probe a short allowlist.
    bse=[]
    for node in ("bj_a","bjs","bj"):
        try:
            test=collect_sina_node(node,10)
        except Exception:
            continue
        keep=[x for x in test if str(x.get("symbol") or "").lower().startswith("bj")
              or str(x.get("code") or "").startswith(("4","8","92"))]
        if len(keep)>len(bse): bse=keep
    merged=raw+bse
    rows=[]
    for x in merged:
        code=str(x.get("code") or "")[-6:].zfill(6)
        sym=str(x.get("symbol") or "").lower()
        name=str(x.get("name") or "")
        if len(code)!=6 or not code.isdigit() or not name: continue
        if sym.startswith(("sh","sz","bj")): tc=sym[:2]+code
        elif code.startswith(("4","8","92")): tc="bj"+code
        elif code.startswith(("5","6","9")): tc="sh"+code
        else: tc="sz"+code
        def fnum(key):
            try:return float(x.get(key))
            except:return None
        mcap=fnum("mktcap")
        rows.append({"symbol":code,"name":name,"tencent_code":tc,
                     "current_pe":fnum("per"),"current_pb":fnum("pb"),
                     "current_market_cap":None if mcap is None else mcap*10000.0,
                     "list_date":None,
                     "signal_eligible":not any(t in name.upper() for t in ("ST","退")),
                     "exchange":"BJ" if tc.startswith("bj") else ("SH" if tc.startswith("sh") else "SZ")})
    df=pd.DataFrame(rows).drop_duplicates("symbol").sort_values("symbol")
    if len(df)<5000: raise RuntimeError(f"A-share universe unexpectedly small after Sina parse: {len(df)}")
    return df.reset_index(drop=True)

def run(cmd,timeout=240):
    p=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout)[-800:])
    try: return json.loads(p.stdout)
    except Exception as ex: raise RuntimeError(f"invalid JSON: {ex}; tail={p.stdout[-300:]}")

def extract_kline(payload,requested):
    data=payload.get("data",payload) if isinstance(payload,dict) else payload
    if not isinstance(data,list): return []
    if len(requested)==1:
        for r in data:
            if isinstance(r,dict): r.setdefault("symbol",requested[0])
    out=[]
    for r in data:
        if not isinstance(r,dict): continue
        sym=str(r.get("symbol") or "")[-6:]
        if sym not in requested: continue
        try:
            d=str(r["date"])[:10]; o=float(r["open"]); h=float(r["high"]); l=float(r["low"])
            c=float(r.get("last",r.get("close"))); v=float(r["volume"])*100.0; a=float(r["amount"])
            if min(o,h,l,c)<=0 or v<0 or a<0: continue
            out.append((sym,d,o,h,l,c,v,a))
        except Exception: continue
    return out

def fetch_kline_piece(symbols,code_map,start,end,attempts=3):
    tcodes=[code_map[c] for c in symbols]
    err=""
    for i in range(attempts):
        try:
            p=run(["npx","-y",PACKAGE,"kline",",".join(tcodes),"--period","day",
                   "--start",start,"--end",end,"--fq","qfq","--raw"],300)
            rows=extract_kline(p,set(symbols))
            got={r[0] for r in rows}
            if rows and (got or len(symbols)==1):
                missing=[c for c in symbols if c not in got]
                return rows,missing
            err="empty"
        except Exception as ex: err=str(ex)
        time.sleep(min(2**i,5))
    return [],list(symbols)

def fetch_all_bars(uni,start,end,workers=6,batch=15):
    code_map=dict(zip(uni.symbol,uni.tencent_code))
    symbols=list(uni.symbol)
    # Tencent/Westock truncates long single requests (~200-250 daily rows).
    # Freeze three non-overlapping calendar segments, each below that practical cap.
    segments=[
        ("2024-07-01","2025-04-30"),
        ("2025-05-01","2026-02-28"),
        ("2026-03-01",end),
    ]
    chunks=[symbols[i:i+batch] for i in range(0,len(symbols),batch)]
    jobs=[(ch,seg_start,seg_end) for seg_start,seg_end in segments for ch in chunks]
    rows=[]; segment_seen={s:set() for s in symbols}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut={ex.submit(fetch_kline_piece,ch,code_map,seg_start,seg_end,2):(ch,seg_start,seg_end)
             for ch,seg_start,seg_end in jobs}
        for n,f in enumerate(as_completed(fut),1):
            ch,seg_start,seg_end=fut[f]
            try:
                rr,mm=f.result(); rows.extend(rr)
                for r in rr: segment_seen[r[0]].add(seg_start)
            except Exception:
                pass
            if n%80==0 or n==len(fut):
                got=sum(bool(v) for v in segment_seen.values())
                print("KLINE_PROGRESS",json.dumps({"jobs":n,"total":len(fut),"rows":len(rows),"symbols_any_data":got}),flush=True)
    # Individual segmented recovery only for symbols with zero data; this avoids
    # thousands of pointless retries while still rescuing batch endpoint misses.
    zero=[s for s,v in segment_seen.items() if not v]
    recovered=set()
    for n,code in enumerate(zero,1):
        for seg_start,seg_end in segments:
            rr,mm=fetch_kline_piece([code],code_map,seg_start,seg_end,2)
            if rr:
                rows.extend(rr); recovered.add(code)
        if n%100==0 or n==len(zero):
            print("RECOVERY_PROGRESS",json.dumps({"done":n,"total":len(zero),"recovered":len(recovered)}),flush=True)
    bars=pd.DataFrame(rows,columns=["symbol","date","open","high","low","close","volume","amount"])
    if bars.empty:
        return bars,sorted(set(symbols)-recovered)
    bars["date"]=pd.to_datetime(bars.date)
    bars=bars.sort_values(["symbol","date"]).drop_duplicates(["symbol","date"],keep="last")
    missing=sorted(set(symbols)-set(bars.symbol.astype(str)))
    coverage=bars.groupby("symbol").date.agg(["min","max","count"]).reset_index()
    thin=coverage[coverage["count"]<80]
    print("KLINE_COVERAGE",json.dumps({"symbols":int(bars.symbol.nunique()),"rows":len(bars),
                                        "missing":len(missing),"under_80_bars":len(thin)}),flush=True)
    return bars,missing

def price_features(g):
    g=g.sort_values("date").copy().reset_index(drop=True)
    g["peak60"]=g.high.rolling(60,min_periods=40).max()
    g["drawdown60"]=g.close/g.peak60-1
    g["ret3"]=g.close/g.close.shift(3)-1
    g["ma5"]=g.close.rolling(5).mean()
    g["min10"]=g.close.rolling(10).min()
    y=np.log(g.close.to_numpy(float)); slope5=np.full(len(g),np.nan)
    x=np.arange(5,dtype=float); den=((x-x.mean())**2).sum()
    for i in range(4,len(g)):
        yy=y[i-4:i+1]; slope5[i]=((x-x.mean())*(yy-yy.mean())).sum()/den
    g["slope5"]=slope5
    annual,r2=calc_ols(g.close.to_numpy(float));g["annual"]=annual;g["r2"]=r2
    g["dr2"]=g.r2.diff();g["cross"]=(g.annual.shift(1)<=0)&(g.annual>0)
    return g

def calc_ols(close):
    n=len(close); annual=np.full(n,np.nan); r2o=np.full(n,np.nan)
    if n<LOOKBACK:return annual,r2o
    y=np.log(np.asarray(close,float));x=np.arange(LOOKBACK,dtype=float)
    q=np.power(.5,(LOOKBACK-1-x)/HALF_LIFE);w=q*q
    sw=w.sum();swx=(w*x).sum();swxx=(w*x*x).sum();den=sw*swxx-swx*swx
    for i in range(LOOKBACK-1,n):
        yy=y[i-LOOKBACK+1:i+1];wy=(w*yy).sum();wxy=(w*x*yy).sum()
        slope=(sw*wxy-swx*wy)/den;inter=(wy-slope*swx)/sw
        fit=inter+slope*x;res=yy-fit;sse=(w*res*res).sum();yb=wy/sw;sst=(w*(yy-yb)**2).sum()
        r2=0 if sst<=0 else max(0,min(1,1-sse/sst))
        annual[i]=math.exp(slope*ANNUALIZATION)-1;r2o[i]=r2
    return annual,r2o

def finance_one(tcode,code):
    p=run(["npx","-y",PACKAGE,"finance",tcode,"--num","8","--raw"],240)
    groups=p.get("sections") if isinstance(p,dict) else None
    if not isinstance(groups,list) or len(groups)<3: raise ValueError("missing finance sections")
    idx=[{str(r.get("EndDate",r.get("date"))):r for r in group if isinstance(r,dict)} for group in groups]
    periods=sorted(set(idx[0])&set(idx[1])&set(idx[2]))
    out=[]
    for period in periods:
        a,b,c=(z[period] for z in idx)
        pubs=[str(z.get("InfoPublDate",""))[:10] for z in (a,b,c)]
        if not all(pubs): continue
        def num(obj,key):
            v=obj.get(key)
            try:return float(v)
            except:return None
        out.append({"symbol":code,"period_end":period,"publication_date":max(pubs),
                    "deducted_profit":num(b,"NPDeductNonRecurringPL"),
                    "net_profit_parent":num(a,"NPParentCompanyOwners"),
                    "operating_cash_flow":num(c,"NetOperateCashFlow")})
    return out

def fetch_financials(uni,codes,workers=6):
    cmap=dict(zip(uni.symbol,uni.tencent_code));rows=[];fails=[]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut={ex.submit(finance_one,cmap[c],c):c for c in codes}
        for n,f in enumerate(as_completed(fut),1):
            c=fut[f]
            try: rows.extend(f.result())
            except Exception as e:fails.append({"symbol":c,"error":str(e)[:250]})
            if n%100==0 or n==len(fut):
                print("FIN_PROGRESS",json.dumps({"done":n,"total":len(fut),"rows":len(rows),"fails":len(fails)}),flush=True)
    return pd.DataFrame(rows),fails

def fin_state(fin,date_):
    x=fin[fin.publication_date<=date_]
    if x.empty:return None
    cur=x.sort_values(["period_end","publication_date"]).iloc[-1]
    prior_period=str(int(cur.period_end[:4])-1)+cur.period_end[4:]
    prev=x[x.period_end==prior_period]
    yoy=None
    if not prev.empty:
        pv=prev.iloc[-1].deducted_profit;cv=cur.deducted_profit
        if pd.notna(pv) and pv>0 and pd.notna(cv):yoy=(cv/pv-1)*100
    return cur,yoy

def horizon_eval(g,signal_i):
    if signal_i is None or signal_i+1>=len(g):return None
    entry_i=signal_i+1;entry=float(g.at[entry_i,"open"])
    z={"signal_date":str(g.at[signal_i,"date"].date()),"entry_date":str(g.at[entry_i,"date"].date()),"entry_open":entry}
    for h in (1,5,10,20,40):
        j=min(entry_i+h-1,len(g)-1)
        if j-entry_i+1<h:z[f"ret{h}_pct"]=None
        else:z[f"ret{h}_pct"]=round((float(g.at[j,"close"])/entry-1)*100,3)
    # Peak-to-trough drawdown over a *complete* 20-session holding window.
    # Compare each session's low to prior peaks; do not assume its high
    # preceded its low intraday. Include entry open as the initial peak.
    if entry_i+19>=len(g):
        z["mdd20_pct"]=None
    else:
        peak=entry;worst=0.0
        for k in range(entry_i,entry_i+20):
            low=float(g.at[k,"low"]);high=float(g.at[k,"high"])
            worst=min(worst,low/peak-1.0)
            peak=max(peak,high)
        z["mdd20_pct"]=round(worst*100,3)
    return z

def process_stock(meta,g,fin):
    g=price_features(g)
    g=g[g.date>=pd.Timestamp(BOOTSTRAP_START)].reset_index(drop=True)
    eligible=bool(meta.signal_eligible)
    value=np.zeros(len(g),dtype=bool);fin_quality=[None]*len(g)
    for i,row in g.iterrows():
        if row.date<BACKTEST_START or not eligible or not np.isfinite(row.drawdown60) or row.drawdown60>DD_THRESHOLD: continue
        fs=fin_state(fin,str(row.date.date())) if fin is not None and not fin.empty else None
        if fs is None:continue
        cur,yoy=fs;dp=cur.deducted_profit
        ok=pd.notna(dp) and dp>0 and (yoy is None or yoy>=PROFIT_YOY_FLOOR)
        if ok:
            value[i]=True
            cfo=cur.operating_cash_flow;np_=cur.net_profit_parent
            ratio=(cfo/np_) if pd.notna(cfo) and pd.notna(np_) and np_>0 else None
            fin_quality[i]={"period":cur.period_end,"publication_date":cur.publication_date,
                            "deducted_profit_yoy_pct":None if yoy is None else round(yoy,2),
                            "cash_conversion":None if ratio is None else round(float(ratio),3)}
    starts=[i for i in range(len(g)) if value[i] and (i==0 or not value[i-1])]
    events=[]
    last_used=-999
    for start in starts:
        if start-last_used<10:continue
        end=min(len(g)-1,start+WATCH_SESSIONS)
        early=None
        for j in range(start,end+1):
            if j>=9 and np.isfinite(g.at[j,"slope5"]) and g.at[j,"slope5"]>0 and g.at[j,"ret3"]>0 and g.at[j,"close"]>g.at[j,"ma5"] and g.at[j,"close"]>g.at[j,"min10"]:
                early=j;break
        ols=None
        for cross in range(start,end+1):
            if not bool(g.at[cross,"cross"]):continue
            for j in range(cross+1,min(cross+4,end+1)):
                if g.at[j,"annual"]>0 and g.at[j,"dr2"]>0 and g.at[j,"r2"]>g.at[cross,"r2"]:
                    ols=j;break
            if ols is not None:break
        rec={"symbol":meta.symbol,"name":meta["name"],"value_start_date":str(g.at[start,"date"].date()),
             "drawdown_at_value_pct":round(float(g.at[start,"drawdown60"])*100,2),
             "financial":fin_quality[start],
             "VALUE_OVERSOLD":horizon_eval(g,start),
             "EARLY_REVERSAL":horizon_eval(g,early) if early is not None else None,
             "OLS_REBUILD":horizon_eval(g,ols) if ols is not None else None}
        events.append(rec);last_used=start
    return events,g

def summarize(events,key):
    arr=[e[key] for e in events if e.get(key)]
    out={"events":len(arr)}
    for metric in ("ret1_pct","ret5_pct","ret10_pct","ret20_pct","ret40_pct","mdd20_pct"):
        vals=[x[metric] for x in arr if x.get(metric) is not None]
        if vals:
            a=np.asarray(vals,float);out[metric]={"mean":round(float(a.mean()),3),"median":round(float(np.median(a)),3),
                                                "win_rate":round(float((a>0).mean()),3) if metric.startswith("ret") else None,
                                                "p10":round(float(np.quantile(a,.1)),3)}
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument("--as-of",default="2026-10-28");p.add_argument("--workers",type=int,default=6);p.add_argument("--max-symbols",type=int,default=0)
    args=p.parse_args();date.fromisoformat(args.as_of);OUT.mkdir(parents=True,exist_ok=True);RESULTS.mkdir(parents=True,exist_ok=True)
    uni=universe()
    if args.max_symbols:uni=uni.head(args.max_symbols).copy()
    print("UNIVERSE",json.dumps({"stocks":len(uni),"eligible":int(uni.signal_eligible.sum()),"bse":int((uni.exchange=="BJ").sum())}),flush=True)
    bars,missing=fetch_all_bars(uni,BOOTSTRAP_START,args.as_of,args.workers)
    # Never report an empty or severely incomplete backtest as success.
    coverage=int(bars.symbol.nunique())
    required=math.ceil(len(uni)*(0.8 if not args.max_symbols else 0.5))
    if coverage<required:
        raise RuntimeError(f"PRICE_QUALITY_GATE: {coverage}/{len(uni)} symbols with bars; minimum={required}; missing={len(missing)}")
    # Price candidates: ever 20% below 60d high during test period.
    pc=[]
    for s,g in bars.groupby("symbol"):
        gg=price_features(g)
        if ((gg.date>=BACKTEST_START)&(gg.drawdown60<=DD_THRESHOLD)).any():pc.append(s)
    print("PRICE_CANDIDATES",json.dumps({"count":len(pc),"missing_price":len(missing)}),flush=True)
    fin,fails=fetch_financials(uni,pc,args.workers)
    if pc and fin.empty:
        raise RuntimeError(f"FINANCE_QUALITY_GATE: {len(pc)} price candidates, zero usable finance rows; failures={len(fails)}")
    if len(pc)>=50 and len(fails)>len(pc)*0.4:
        raise RuntimeError(f"FINANCE_QUALITY_GATE: {len(fails)}/{len(pc)} finance requests failed")
    if not fin.empty:
        fin["publication_date"]=fin.publication_date.astype(str);fin["period_end"]=fin.period_end.astype(str)
    events=[];today=[]
    fin_group={s:g.copy() for s,g in fin.groupby("symbol")} if not fin.empty else {}
    meta=uni.set_index("symbol")
    for n,(s,g0) in enumerate(bars.groupby("symbol"),1):
        if s not in meta.index:continue
        ev,g=process_stock(meta.loc[s],g0,fin_group.get(s,pd.DataFrame()))
        events.extend(ev)
        if len(g)>=2:
            yday=str(g.iloc[-2].date.date());today_date=str(g.iloc[-1].date.date())
            if today_date==args.as_of and (args.as_of!="2026-10-28" or yday=="2026-10-27"):
                for e in ev:
                    for kind in ("VALUE_OVERSOLD","EARLY_REVERSAL","OLS_REBUILD"):
                        er=e.get(kind)
                        if er and er["signal_date"]==yday and er["entry_date"]==today_date:
                            today.append({"symbol":s,"name":meta.loc[s,"name"],"signal":kind,
                                          "entry_open":er["entry_open"],"ret1_pct":er["ret1_pct"],
                                          "drawdown_at_value_pct":e["drawdown_at_value_pct"]})
    summary={k:summarize(events,k) for k in ("VALUE_OVERSOLD","EARLY_REVERSAL","OLS_REBUILD")}
    result={"version":"full-a-share-value-reversal-ols-v1","as_of":args.as_of,"backtest_start":"2025-01-01",
            "universe_count":len(uni),"bse_count":int((uni.exchange=="BJ").sum()),"coverage_scope":"SH_SZ_BJ" if int((uni.exchange=="BJ").sum())>0 else "SH_SZ_ONLY_BSE_PENDING","price_symbols":int(bars.symbol.nunique()),"price_missing":missing,
            "price_oversold_symbols":len(pc),"finance_failures":fails,
            "price_basis":"qfq_adjusted","quality_gate":{"minimum_price_symbols":required,"price_coverage_pct":round(coverage/len(uni)*100,2)},
            "limitations":["Current listed universe and current ST name status cause survivorship bias; not a historical point-in-time universe","Financial source contains latest available 8 reports only; historical report coverage may be incomplete"],
            "rules":{"drawdown60_max":DD_THRESHOLD,"deducted_profit_positive":True,"deducted_profit_yoy_floor_pct":PROFIT_YOY_FLOOR,
                     "watch_sessions":WATCH_SESSIONS,"early_reversal":"slope5>0 & ret3>0 & close>MA5 & close>min10",
                     "ols_rebuild":"frozen ETF OLS26/HL10 cross + R2 rebuild"},
            "summary":summary,"today_capture_from_prior_close_signal":today,
            "events":events}
    (OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    uni.to_csv(OUT/"universe.csv",index=False)
    pd.DataFrame(events).drop(columns=[],errors="ignore").to_json(OUT/"events.jsonl",orient="records",lines=True,force_ascii=False)
    # Large raw bars remain artifact-only.
    bars.to_parquet(OUT/"daily_bars.parquet",index=False,compression="zstd")
    if not fin.empty:fin.to_parquet(OUT/"financials.parquet",index=False,compression="zstd")
    compact={k:v for k,v in result.items() if k!="events"}
    (RESULTS/"full-market-v1-latest.json").write_text(json.dumps(compact,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DONE",json.dumps({"events":len(events),"today_capture":len(today),"summary":summary},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
