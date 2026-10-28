#!/usr/bin/env python3
"""Isolated 7-stock A-share price pilot: Tencent + independent Eastmoney verification."""
import argparse,csv,gzip,io,json,subprocess,sys,time,urllib.parse,urllib.request
from datetime import date
from pathlib import Path

PACKAGE="westock-data-skillhub@1.0.5"
STOCKS={"002353":"杰瑞股份","688059":"华锐精密","300308":"中际旭创","300502":"新易盛","300394":"天孚通信","603986":"兆易创新","001309":"德明利"}
ROOT=Path("research/stock_value")
ARCHIVE=ROOT/"data"/"daily"
RESULTS=ROOT/"results"
HEADERS={"User-Agent":"Mozilla/5.0","Referer":"https://finance.qq.com/"}

def http_json(url,params,referer=None):
    url=url+"?"+urllib.parse.urlencode(params)
    headers=dict(HEADERS)
    if referer:headers["Referer"]=referer
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers=headers)
            with urllib.request.urlopen(req,timeout=18) as r:
                raw=r.read().decode("utf-8-sig")
            if raw.lstrip().startswith("var ") or (not raw.lstrip().startswith("{") and "=" in raw):
                raw=raw.split("=",1)[1].strip().rstrip(";")
            return json.loads(raw)
        except Exception as exc:
            last=exc
            if attempt<2:time.sleep(2**attempt)
    raise RuntimeError(str(last)[:200])

def normalize_rows(items,start,end):
    out={}
    for r in items:
        try:
            d=str(r[0])[:10];o,h,l,c=(float(r[i]) for i in (1,2,3,4))
            v=float(r[5]);a=float(r[6])
            if not(start<=d<=end and min(o,h,l,c)>0 and h>=max(o,l,c) and l<=min(o,h,c) and v>=0 and a>=0):continue
            out[d]=[d,o,h,l,c,v,a]
        except (IndexError,TypeError,ValueError):continue
    return [out[k] for k in sorted(out)]

def westock(code,start,end):
    symbol=("sh" if code.startswith(("6","9")) else "sz")+code
    cmd=["npx","-y",PACKAGE,"kline",symbol,"--period","day","--start",start,"--end",end,"--fq","qfq","--raw"]
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=90)
    if p.returncode:raise RuntimeError((p.stderr or p.stdout)[-250:])
    data=json.loads(p.stdout)
    if isinstance(data,dict) and data.get("success") is False:raise RuntimeError(str(data.get("error"))[:200])
    if isinstance(data,dict):data=data.get("data",[])
    if not isinstance(data,list):raise ValueError("Unexpected Westock schema")
    return normalize_rows([[r["date"],r["open"],r["high"],r["low"],r.get("last",r.get("close")),float(r["volume"])*100,r.get("amount",0)] for r in data],start,end)

def tencent_direct(code,start,end):
    symbol=("sh" if code.startswith(("6","9")) else "sz")+code
    data=http_json("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                   {"_var":"kline_dayqfq","param":f"{symbol},day,{start},{end},200,qfq"})
    stock=data.get("data",{}).get(symbol,{})
    items=stock.get("qfqday") or stock.get("day") or []
    # Tencent rows: date, open, close, high, low, volume (lots), optional turnover.
    rows=[[r[0],r[1],r[3],r[4],r[2],float(r[5])*100,0] for r in items if len(r)>=6]
    return normalize_rows(rows,start,end)

def eastmoney(code,start,end):
    secid=("1." if code.startswith(("6","9")) else "0.")+code
    data=http_json("https://push2his.eastmoney.com/api/qt/stock/kline/get",
        {"secid":secid,"fields1":"f1,f2,f3,f4,f5,f6","fields2":"f51,f52,f53,f54,f55,f56,f57",
         "klt":101,"fqt":1,"beg":start.replace("-",""),"end":end.replace("-",""),"lmt":200},
        "https://quote.eastmoney.com/")
    items=(data.get("data") or {}).get("klines") or []
    rows=[]
    for item in items:
        f=item.split(",")
        if len(f)>=7:rows.append([f[0],f[1],f[3],f[4],f[2],float(f[5])*100,f[6]])
    return normalize_rows(rows,start,end)

def sina(code,start,end):
    symbol=("sh" if code.startswith(("6","9")) else "sz")+code
    data=http_json("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData",
                   {"symbol":symbol,"scale":240,"ma":"no","datalen":120},
                   "https://finance.sina.com.cn/")
    if not isinstance(data,list):raise ValueError("Unexpected Sina response")
    rows=[[r["day"],r["open"],r["high"],r["low"],r["close"],r.get("volume",0),0] for r in data]
    return normalize_rows(rows,start,end)

def get_data(code,start,end):
    errors=[];primary=[];provider=None
    for label,func in (("Tencent Westock",westock),("Tencent direct",tencent_direct)):
        try:
            primary=func(code,start,end)
            if len(primary)>=15:
                provider=label;break
            errors.append(label+": insufficient rows "+str(len(primary)))
        except Exception as exc:errors.append(label+": "+str(exc)[:200])
    secondary_provider="Eastmoney"
    try:secondary=eastmoney(code,start,end)
    except Exception as exc:
        secondary=[];errors.append("Eastmoney: "+str(exc)[:200])
    if not secondary:
        secondary_provider="Sina"
        try:secondary=sina(code,start,end)
        except Exception as exc:
            secondary=[];errors.append("Sina: "+str(exc)[:200])
    if not primary and secondary:
        return secondary,secondary_provider+" ONLY","NONE","TENCENT_UNAVAILABLE",errors
    if not primary:
        raise RuntimeError("; ".join(errors)[:600])
    if not secondary:return primary,provider,"NONE","SECONDARY_UNAVAILABLE",errors
    p={r[0]:r for r in primary};s={r[0]:r for r in secondary}
    dates=sorted(set(p)&set(s))[-10:]
    if len(dates)<5:return primary,provider,secondary_provider,"INSUFFICIENT_OVERLAP",errors
    deviations=[abs(p[d][4]-s[d][4])/max(s[d][4],0.01) for d in dates]
    window=[r for r in primary if "2026-09-01"<=r[0]<=end]
    peak=max(window,key=lambda r:r[2])
    peak_date=peak[0]
    if peak_date not in s:
        status="PEAK_DATE_UNAVAILABLE"
        errors.append("Secondary source has no peak date "+peak_date)
    else:
        peak_gap=abs(p[peak_date][2]-s[peak_date][2])/max(s[peak_date][2],0.01)
        status="PASS" if max(deviations)<=0.015 and peak_gap<=0.015 else "PRICE_MISMATCH"
        if peak_gap>0.015:
            errors.append("Peak-date high discrepancy "+peak_date+": "+str(round(peak_gap*100,3))+"%")
    if max(deviations)>0.015:
        errors.append("Maximum 10-day close discrepancy: "+str(round(max(deviations)*100,3))+"%")
    return primary,provider,secondary_provider,status,errors

def archive(code,rows):
    ARCHIVE.mkdir(parents=True,exist_ok=True)
    path=ARCHIVE/(code+".csv.gz")
    buf=io.StringIO();w=csv.writer(buf,lineterminator="\n")
    w.writerow(["date","open","high","low","close","volume_shares","turnover_cny"])
    w.writerows(rows)
    with path.open("wb") as f:
        with gzip.GzipFile(fileobj=f,mode="wb",filename="",mtime=0,compresslevel=9) as g:g.write(buf.getvalue().encode())
    if path.stat().st_size>4_000_000:raise ValueError("Archive size cap exceeded")
    return path

def screen(code,rows,as_of,provider,secondary_provider,verification,errors):
    latest=rows[-1]
    period=[r for r in rows if "2026-09-01"<=r[0]<=as_of]
    if not period:raise ValueError("No September/October rows")
    peak=max(period,key=lambda r:r[2]);low=min(period,key=lambda r:r[3])
    return {"symbol":code,"name":STOCKS[code],"status":"OK" if latest[0]==as_of else "STALE",
            "as_of_bar":latest[0],"close":latest[4],"sept_oct_peak_high":peak[2],
            "peak_date":peak[0],"drawdown_from_peak_pct":round((latest[4]/peak[2]-1)*100,2),
            "window_low":low[3],"low_date":low[0],"bars":len(rows),
            "price_basis":"qfq (forward-adjusted)","primary_source":provider,
            "secondary_source":secondary_provider,"secondary_verification":verification,
            "warnings":errors,"financial_review":"NOT_VERIFIED"}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--as-of",default="2026-10-28")
    ap.add_argument("--start",default="2026-08-01")
    args=ap.parse_args();date.fromisoformat(args.as_of);date.fromisoformat(args.start)
    results=[];failures=[]
    for code in STOCKS:
        try:
            rows,provider,secondary_provider,verification,errors=get_data(code,args.start,args.as_of)
            if len(rows)<15:raise ValueError("Insufficient bars: "+str(len(rows)))
            archive(code,rows);results.append(screen(code,rows,args.as_of,provider,secondary_provider,verification,errors))
            print(code,provider,verification,len(rows),flush=True)
        except Exception as exc:
            failures.append({"symbol":code,"error":str(exc)[:600]})
            print(code,"FAILED",str(exc)[:180],flush=True)
        time.sleep(1)
    RESULTS.mkdir(parents=True,exist_ok=True)
    payload={"as_of":args.as_of,"source":"Tencent Westock/direct with Eastmoney/Sina independent check",
             "financial_data_status":"not_collected",
             "universe":"7-stock exploratory pilot; not whole A-share market",
             "drawdown_method":"Sep 1–as-of maximum qfq intraday high / as-of qfq close - 1",
             "candidates":sorted(results,key=lambda x:x["drawdown_from_peak_pct"]),
             "failures":failures,
             "price_full_acceptance":len(results)==7 and not failures and all(x["status"]=="OK" and x["secondary_verification"]=="PASS" and x["primary_source"]!="Eastmoney ONLY" for x in results)}
    payload["full_acceptance"]=False  # financial validation step must explicitly promote acceptance
    out=RESULTS/"latest.json";out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"success":len(results),"failed":len(failures),"fully_price_verified":payload["price_full_acceptance"]},ensure_ascii=False))
    return 0 if len(results)==7 and not failures else 1
if __name__=="__main__":sys.exit(main())
