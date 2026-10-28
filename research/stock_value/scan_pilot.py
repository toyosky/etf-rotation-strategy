#!/usr/bin/env python3
"""Independent A-share value-drawdown pilot, no Supabase writes.

Tencent Westock kline -> gzipped CSV per stock -> dated screening JSON.
Only past data as of --as-of. Raw files are small 7-stock pilot archives.
"""
import argparse, csv, gzip, io, json, shutil, subprocess, sys, tempfile
from datetime import date
from pathlib import Path

PACKAGE="westock-data-skillhub@1.0.5"
STOCKS={"002353":"杰瑞股份","688059":"华锐精密","300308":"中际旭创","300502":"新易盛","300394":"天孚通信","603986":"兆易创新","001309":"德明利"}
ROOT=Path("research/stock_value")
ARCHIVE=ROOT/"data"/"daily"
RESULTS=ROOT/"results"

def fetch(code,start,end):
    prefix="sh" if code.startswith(("6","9")) else "sz"
    p=subprocess.run(["npx","-y",PACKAGE,"kline",prefix+code,"--period","day","--start",start,"--end",end,"--fq","none","--raw"],
                     text=True,capture_output=True,timeout=180)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout)[-500:])
    d=json.loads(p.stdout)
    if isinstance(d,dict) and d.get("success") is False: raise RuntimeError(str(d.get("error")))
    if isinstance(d,dict): d=d.get("data",[])
    if not isinstance(d,list): raise ValueError("Unexpected response shape")
    out={}
    for r in d:
        try:
            day=str(r["date"])[:10];o=float(r["open"]);h=float(r["high"]);l=float(r["low"]);c=float(r.get("last",r.get("close")))
            v=float(r["volume"]);a=float(r["amount"])
            if not(day>=start and day<=end and min(o,h,l,c)>0 and h>=max(o,c,l) and l<=min(o,c,h) and v>=0 and a>=0):continue
            out[day]=[day,o,h,l,c,v*100,a]
        except (KeyError,ValueError,TypeError):continue
    return [out[k] for k in sorted(out)]

def archive(code,rows):
    ARCHIVE.mkdir(parents=True,exist_ok=True)
    path=ARCHIVE/(code+".csv.gz")
    buffer=io.StringIO();w=csv.writer(buffer,lineterminator="\n")
    w.writerow(["date","open","high","low","close","volume_shares","turnover_cny"])
    w.writerows(rows)
    # Deterministic gzip bytes to avoid spurious git changes.
    raw=buffer.getvalue().encode()
    with path.open("wb") as f:
        with gzip.GzipFile(fileobj=f,mode="wb",filename="",mtime=0,compresslevel=9) as g:g.write(raw)
    if path.stat().st_size>4_000_000:raise ValueError("Single ticker file exceeds 4 MB limit")
    return path

def screen(code,rows,as_of):
    if not rows:return {"symbol":code,"name":STOCKS[code],"status":"NO_DATA"}
    bars=[r for r in rows if r[0]<=as_of]
    if not bars:return {"symbol":code,"name":STOCKS[code],"status":"NO_ASOF_DATA"}
    latest=bars[-1]
    september=[r for r in bars if "2026-09-01"<=r[0]<=as_of]
    if not september:return {"symbol":code,"name":STOCKS[code],"status":"NO_SEPT_DATA"}
    peak=max(september,key=lambda r:r[2])
    low=min(september,key=lambda r:r[3])
    if latest[0]<as_of:status="STALE"
    else:status="OK"
    return {"symbol":code,"name":STOCKS[code],"status":status,"as_of_bar":latest[0],
            "close":latest[4],"sept_oct_peak_high":peak[2],"peak_date":peak[0],
            "drawdown_from_peak_pct":round((latest[4]/peak[2]-1)*100,2),
            "window_low":low[3],"low_date":low[0],"bars":len(bars),
            "price_basis":"unadjusted","financial_review":"NOT_VERIFIED"}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--as-of",default="2026-10-28")
    ap.add_argument("--start",default="2026-08-01")
    args=ap.parse_args();date.fromisoformat(args.as_of);date.fromisoformat(args.start)
    results=[];failures=[]
    for code in STOCKS:
        try:
            rows=fetch(code,args.start,args.as_of)
            if len(rows)<15:raise ValueError("Insufficient bars: "+str(len(rows)))
            archive(code,rows);results.append(screen(code,rows,args.as_of))
        except Exception as ex:
            failures.append({"symbol":code,"error":str(ex)[:300]})
    RESULTS.mkdir(parents=True,exist_ok=True)
    payload={"as_of":args.as_of,"source":"Tencent Westock","financial_data_status":"not_collected",
             "universe":"7-stock exploratory pilot; not whole A-share market",
             "drawdown_method":"window peak intraday high / as-of unadjusted close - 1",
             "candidates":sorted(results,key=lambda x:x.get("drawdown_from_peak_pct",0)),
             "failures":failures}
    out=RESULTS/"latest.json";out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"success":len(results),"failed":len(failures),"summary":str(out)},ensure_ascii=False))
    return 0 if not failures else 1
if __name__=="__main__":sys.exit(main())
