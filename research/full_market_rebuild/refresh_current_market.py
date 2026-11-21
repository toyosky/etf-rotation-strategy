#!/usr/bin/env python3
"""Research-only daily refresh of the whole exchange-listed ETF/LOF universe.

Rehydrates September 17 frozen Supabase Storage archive, discovers *current*
listed ETF/LOF metadata, refreshes Tencent HFQ bars through requested A-share
trade date, scans independent weighted-OLS26 rebuilding signals, and writes a
self-contained compressed Parquet snapshot for private GitHub Release.

Does NOT modify public.daily_bars, production strategies or live signals.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import random
import time
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from automation.build_fundamental_audit_trigger import calc_ols, db_url
from automation.tencent_daily_sync import run_westock, normalize
from research.full_market_rebuild.full_market_archive_study import read_snapshot

def symbol_to_tencent(s):
    if len(s) != 6 or not s.isdigit(): return None
    if s[0] in "56": return "sh"+s
    if s[0] == "1": return "sz"+s
    return None

def read_current_universe():
    raw = os.getenv("ETF_DAILY_BARS_DATABASE_URL", "").strip()
    if not raw:raise RuntimeError("Missing database URL needed ONLY to discover current ETF/LOF codes")
    eng=create_engine(db_url(raw),pool_pre_ping=True)
    with eng.connect() as conn:
        df=pd.read_sql_query(text("""
            SELECT DISTINCT symbol, product_type, name
            FROM public.instrument_metadata
            WHERE current_exchange_listed IS TRUE AND product_type IN ('ETF','LOF')
            ORDER BY symbol
        """), conn)
    df["symbol"]=df.symbol.astype(str).str.zfill(6)
    df["tencent_code"]=df.symbol.map(symbol_to_tencent)
    df=df.dropna(subset=["tencent_code"]).drop_duplicates("symbol")
    if len(df)<1200:raise RuntimeError("Current ETF/LOF metadata unexpectedly small")
    return df.reset_index(drop=True)

def refresh_batch(items,begin,end,attempts):
    # One bad code can cause the Tencent batched endpoint to return no data at
    # all. Recover with recursive halves and ultimately individual tickers.
    # Keep valid rows even if some symbols have no available quotes.
    def fetch(piece):
        codes=[symbol_to_tencent(sym) for sym in piece]
        types={sym:"ETF" for sym in piece}
        error=None
        for trial in range(attempts):
            try:
                response=run_westock(codes,begin,end,1)
                rows=normalize(response,codes,types,end)
                if rows:
                    got={r[0] for r in rows}
                    missed=[sym for sym in piece if sym not in got]
                    if missed and len(piece)>1:
                        recovered, errs=divide(missed)
                        rows.extend(recovered)
                        return rows,errs
                    return rows,[]
                error="Empty Tencent kline response"
            except Exception as ex:
                error=str(ex)[-240:]
            if trial+1<attempts:time.sleep(min(2**trial,3))
        if len(piece)>1:
            return divide(piece)
        return [],[{"symbols":piece,"error":error or "empty"}]
    def divide(piece):
        if len(piece)<=1:return fetch(piece)
        half=len(piece)//2
        left,e1=fetch(piece[:half])
        right,e2=fetch(piece[half:])
        return left+right,e1+e2
    rows,errs=fetch(items)
    return rows, errs

def fetch_updates(current, archive, as_of, workers=5, batch_size=12, attempts=2, max_symbols=0):
    old=set(archive.symbol.unique())
    selected=current
    if max_symbols:
        # Deterministic smoke test across archived, new and requested symbols.
        selected=current.iloc[:max_symbols].copy()
    grouped={"existing":[],"bootstrap":[]}
    for s in selected.symbol.astype(str):
        grouped["existing" if s in old else "bootstrap"].append(s)
    start_existing=as_of-timedelta(days=75)  # overlaps Sep17 snapshot
    start_bootstrap=as_of-timedelta(days=525)  # ~365 trading days for recent funds
    jobs=[]
    for key,start in (("existing",start_existing),("bootstrap",start_bootstrap)):
        sym=grouped[key]
        for i in range(0,len(sym),batch_size):jobs.append((sym[i:i+batch_size],start))
    print("REFRESH_PLAN "+json.dumps({"current_etf_lof":len(current),"selected":len(selected),
                                       "existing":len(grouped["existing"]),"bootstrap":len(grouped["bootstrap"]),
                                       "requests":len(jobs),"as_of":str(as_of)},ensure_ascii=False),flush=True)
    updates=[]
    errors=[]
    completed=set()
    with ThreadPoolExecutor(max_workers=workers) as exe:
        jobs_future={exe.submit(refresh_batch, symbols,start,as_of,attempts):(symbols,start) for symbols,start in jobs}
        for ix,future in enumerate(as_completed(jobs_future),1):
            codes,start=jobs_future[future]
            try:
                rows,error=future.result()
                updates.extend(rows)
                completed.update(r[0] for r in rows)
                if error:errors.extend(error)
            except Exception as e:
                errors.append({"symbols":codes,"error":repr(e)[:400]})
            if ix%20==0 or ix==len(jobs):
                print("REFRESH_PROGRESS "+json.dumps({"batch":ix,"total":len(jobs),"rows":len(updates),
                                                         "symbols_returned":len(completed),"errors":len(errors)}),flush=True)
    return updates, errors, selected, {"jobs":len(jobs),"existing":len(grouped["existing"]),"bootstrap":len(grouped["bootstrap"])}

def merge(base,updates):
    # Older frozen sample plus updated history; latest historical Tencent bars
    # supersede overlaps in order to keep adjustment vintage consistent.
    columns=["symbol","date","open","high","low","close","volume","amount","instrument_type","ingested_on"]
    if not updates:return base.copy(), []
    patch=pd.DataFrame(updates,columns=columns)
    patch["date"]=pd.to_datetime(patch.date)
    base=base.copy()
    base["date"]=pd.to_datetime(base.date)
    a=base.set_index(["symbol","date"])
    b=patch.set_index(["symbol","date"])
    both=a.join(b[["close"]],how="inner",rsuffix="_patch")
    price_ratio=both.close_patch/both.close
    overlap={"count":len(both),"median_abs_pct":float((price_ratio-1).abs().median()*100),
             "over_1pct":int(((price_ratio-1).abs()>0.01).sum()),
             "over_5pct":int(((price_ratio-1).abs()>0.05).sum())}
    # Existing source adjustment may rebase; report changed periods explicitly.
    merged=pd.concat([base,patch],ignore_index=True).drop_duplicates(["symbol","date"],keep="last")
    merged=merged.sort_values(["symbol","date"]).reset_index(drop=True)
    if merged.duplicated(["symbol","date"]).any():raise RuntimeError("Merge duplicate symbol-date")
    if (merged[["open","close"]]<=0).any().any():raise RuntimeError("Nonpositive merged price")
    return merged, overlap

def scan_one(g,as_of):
    g=g.sort_values("date").reset_index(drop=True)
    s=str(g.at[0,"symbol"])
    last=str(g.date.iloc[-1].date())
    result={"symbol":s,"name":str(g.at[0,"name"]) if "name" in g else "",
            "last_date":last,"history_bars":len(g),"stale":last!=str(as_of)}
    if len(g)<65 or result["stale"]:
        result["stage"]="DATA_STALE" if result["stale"] else "INSUFFICIENT_HISTORY"
        return result
    c=g.close.to_numpy(dtype=float)
    with np.errstate(divide="ignore",invalid="ignore",over="ignore"):
        annual,r2=calc_ols(c)
    if not np.isfinite(annual[-1]) or not np.isfinite(r2[-1]):
        result["stage"]="OLS_NONFINITE";return result
    latest=len(g)-1
    # Numerical tolerance avoids false annual crossings for fixed-price assets.
    threshold=1e-8
    crossings=np.flatnonzero((annual[1:]>threshold)&(annual[:-1]<=threshold))+1
    cross=next((int(i) for i in reversed(crossings) if latest-3<=i<=latest),None)
    age=latest-cross if cross is not None else None
    d1=float(r2[-1]-r2[-2])
    d3=float(r2[-1]-r2[-4])
    recent2=c[-1]/c[-3]-1
    dailies=c[-3:]/c[-4:-1]-1
    avg60=float(g.amount.iloc[-60:].mean())
    med60=float(g.amount.iloc[-60:].median())
    nonzero=float((g.volume.iloc[-60:]>0).mean())
    age_days=(g.date.iloc[-1]-g.date.iloc[0]).days
    strict=bool(len(g)>=200 and age_days>=365 and avg60>=2e7 and med60>=1e7 and nonzero>=.95)
    broad=bool(avg60>=3e6 and nonzero>=.90)
    status="NONE"
    if cross is not None:
        if age==0:status="CROSS_DETECTED"
        elif age in (1,2,3) and annual[-1]>threshold and d1>1e-12 and r2[-1]>r2[cross]+1e-12:
            status="REBUILDING_QUALIFIED"
        elif age in (1,2,3) and annual[-1]>threshold:status="REBUILD_WATCH"
    result.update({"annual":float(annual[-1]),"r2":float(r2[-1]),
                   "delta_r2_1":d1,"delta_r2_3":d3,
                   "cross_date":str(g.date.iloc[cross].date()) if cross is not None else None,
                   "cross_age_sessions":age,"r2_at_cross":float(r2[cross]) if cross is not None else None,
                   "stage":status,"strict_eligible":strict,"broad_eligible":broad,
                   "avg_amount60":avg60,"median_amount60":med60,
                   "ret2":float(recent2),"max_daily_ret3":float(dailies.max()),
                   "shock10_8":bool(recent2>=.10 or dailies.max()>=.08)})
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--as-of",type=date.fromisoformat,default=date(2026,10,20))
    p.add_argument("--max-symbols",type=int,default=0)
    p.add_argument("--resume-path",default="")
    p.add_argument("--workers",type=int,default=5)
    p.add_argument("--batch-size",type=int,default=12)
    p.add_argument("--out",default="research/full_market_rebuild/today_output")
    args=p.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    if args.resume_path and Path(args.resume_path).exists():
        data=pd.read_parquet(args.resume_path)
        data["symbol"]=data.symbol.astype(str).str.zfill(6)
        data["date"]=pd.to_datetime(data.date)
        print("RESUME_SNAPSHOT "+json.dumps({"rows":len(data),"symbols":int(data.symbol.nunique())}),flush=True)
    else:
        data,manifest,checks=read_snapshot(out/"base_frozen_archive.tar.gz")
    current=read_current_universe()
    already_current=set(data.loc[pd.to_datetime(data.date).dt.date==args.as_of,"symbol"].astype(str))
    missing_now=current[~current.symbol.isin(already_current)].copy()
    update,errors,requested,batch_stats=fetch_updates(missing_now,data,args.as_of,args.workers,args.batch_size,max_symbols=args.max_symbols)
    all_data,overlap=merge(data,update)
    # Store self-contained snapshot (parquet metadata remains separated).
    all_data.to_parquet(out/"refreshed_daily_bars.parquet",index=False,compression="zstd")
    current_names=dict(zip(current.symbol,current.name))
    actual = all_data[all_data.symbol.isin(current.symbol)].copy()
    actual["name"]=actual.symbol.map(current_names)
    results=[scan_one(g,args.as_of) for _,g in actual.groupby("symbol",sort=True)]
    found=set(actual.symbol.unique())
    for sym in current.symbol:
        if sym not in found:
            results.append({"symbol":sym,"name":str(current_names.get(sym,"")),"last_date":None,
                            "history_bars":0,"stale":True,"stage":"DATA_MISSING",
                            "strict_eligible":False,"broad_eligible":False})
    scan=pd.DataFrame(results).sort_values(["stage","symbol"])
    scan.to_csv(out/"today_signals.csv",index=False)
    stages={str(k):int(v) for k,v in scan.stage.value_counts().items()}
    eligible=scan[(scan.stage=="REBUILDING_QUALIFIED")&scan.strict_eligible]
    qualified=scan[scan.stage=="REBUILDING_QUALIFIED"]
    with_today=int((scan.last_date==str(args.as_of)).sum())
    coverage=with_today/len(current)
    report={"as_of":str(args.as_of),"source":"Tencent HFQ latest daily bar merged with frozen 2026-09-17 Supabase archive",
            "update_method":"research only, no live PostgreSQL writes","snapshot_symbols":int(all_data.symbol.nunique()),
            "snapshot_rows":len(all_data),"listed_requested":len(current),"requested_for_update":len(requested),
            "symbols_with_asof_close":with_today,"asof_coverage":coverage,
            "refresh_rows":len(update),"refresh_batches":batch_stats,
            "query_batch_errors":errors[:80],"query_error_count":len(errors),
            "overlap_revision":overlap,"stage_counts":stages,
            "raw_qualified":int(len(qualified)),"strict_qualified":int(len(eligible)),
            "raw_qualified_symbols":qualified.symbol.tolist(),
            "strict_qualified_symbols":eligible.symbol.tolist(),
            "data_quality_gate": "PASS" if coverage>=.90 and with_today>=1000 else "PARTIAL_OR_FAILED",
            "data_version":"2026-09-17 frozen plus Tencent incremental HFQ 2026-10-20",
            "limitation":"Not a full census of historical delisted ETFs; ETF NAV/premium as-of unavailable; current metadata can exclude newly launched symbols",
            "sha256_snapshot":hashlib.sha256((out/"refreshed_daily_bars.parquet").read_bytes()).hexdigest()}
    (out/"today_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf8")
    print("TODAY_REPORT "+json.dumps({k:report[k] for k in ("as_of","listed_requested","symbols_with_asof_close","asof_coverage",
           "refresh_rows","query_error_count","data_quality_gate","stage_counts","raw_qualified_symbols","strict_qualified_symbols")},ensure_ascii=False),flush=True)
    # Need a nonzero return for unusably low coverage, while still uploading report for diagnosis.
    if coverage<0.4:raise RuntimeError(f"Insufficient full-market update coverage {coverage:.1%}")

if __name__=="__main__":main()
