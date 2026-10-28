#!/usr/bin/env python3
"""Apply the frozen ETF OLS26 rebuilding contract to the 7-stock pilot.

Point-in-time rules:
- 26-session weighted log-price OLS, half-life 10, effective weights q^2
- annual crosses <=0 -> >0
- first qualified observation 1-3 sessions later when annual>0,
  1d R2 delta>0, and R2 > cross-day R2
- signal at close, hypothetical entry at next session open
No look-ahead selection among multiple qualified dates in one episode.
"""
import csv,gzip,json,math
from pathlib import Path
import numpy as np

ROOT=Path("research/stock_value")
DATA=ROOT/"data"/"daily"
OUT=ROOT/"results"/"rebuild-signals.json"
STOCKS={"002353":"杰瑞股份","688059":"华锐精密","300308":"中际旭创","300502":"新易盛","300394":"天孚通信","603986":"兆易创新","001309":"德明利"}
LOOKBACK=26; HALF_LIFE=10.0; ANNUALIZATION=250.0

def load(code):
    p=DATA/(code+".csv.gz")
    rows=[]
    with gzip.open(p,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            rows.append({"date":r["date"],"open":float(r["open"]),"close":float(r["close"])})
    return rows

def calc(closes):
    n=len(closes); annual=np.full(n,np.nan); r2o=np.full(n,np.nan)
    if n<LOOKBACK:return annual,r2o
    y=np.log(np.asarray(closes,float)); x=np.arange(LOOKBACK,dtype=float)
    q=np.power(.5,(LOOKBACK-1-x)/HALF_LIFE); w=q*q
    sw=w.sum(); swx=(w*x).sum(); swxx=(w*x*x).sum(); den=sw*swxx-swx*swx
    for i in range(LOOKBACK-1,n):
        yy=y[i-LOOKBACK+1:i+1]
        wy=(w*yy).sum(); wxy=(w*x*yy).sum()
        slope=(sw*wxy-swx*wy)/den; intercept=(wy-slope*swx)/sw
        fit=intercept+slope*x; resid=yy-fit
        sse=(w*resid*resid).sum(); ybar=wy/sw; sst=(w*(yy-ybar)**2).sum()
        r2=0.0 if sst<=0 else max(0.0,min(1.0,1-sse/sst))
        annual[i]=math.exp(slope*ANNUALIZATION)-1; r2o[i]=r2
    return annual,r2o

def events(rows):
    annual,r2=calc([r["close"] for r in rows])
    cross=[False]*len(rows)
    for i in range(1,len(rows)):
        if np.isfinite(annual[i-1]) and np.isfinite(annual[i]):
            cross[i]=annual[i-1]<=0 and annual[i]>0
    out=[]; i=0
    while i<len(rows):
        if not cross[i]: i+=1; continue
        qidx=None
        for j in range(i+1,min(i+4,len(rows))):
            if annual[j]>0 and r2[j]-r2[j-1]>0 and r2[j]>r2[i]:
                qidx=j; break
        rec={"cross_idx":i,"cross_date":rows[i]["date"],"cross_annual":float(annual[i]),"cross_r2":float(r2[i])}
        if qidx is not None:
            rec.update({"qualified_idx":qidx,"qualified_date":rows[qidx]["date"],
                        "annual":float(annual[qidx]),"r2":float(r2[qidx]),
                        "delta_r2_1":float(r2[qidx]-r2[qidx-1])})
            if qidx+1<len(rows):
                entry=rows[qidx+1]
                rec["entry_date"]=entry["date"]; rec["entry_open"]=entry["open"]
                rec["return_to_asof_close_pct"]=round((rows[-1]["close"]/entry["open"]-1)*100,2)
                # structural failure after entry
                fail=None
                for k in range(qidx+1,len(rows)):
                    if np.isfinite(annual[k]) and annual[k]<=0:
                        fail=k; break
                rec["first_annual_failure_date"]=rows[fail]["date"] if fail is not None else None
                rec["alive_through_asof"]=fail is None
        out.append(rec)
        i=(qidx+1) if qidx is not None else i+1
    return out

def main():
    items=[]
    for code,name in STOCKS.items():
        rows=load(code); ev=events(rows)
        qualified=[e for e in ev if "qualified_date" in e and e["qualified_date"]>="2026-09-01"]
        # first signal in the post-drawdown Sep-Oct window; no ex-post "best" date
        first=qualified[0] if qualified else None
        prev_close=rows[-2]["close"] if len(rows)>1 else None
        today_ret=round((rows[-1]["close"]/prev_close-1)*100,2) if prev_close else None
        items.append({"symbol":code,"name":name,"as_of":rows[-1]["date"],"as_of_close":rows[-1]["close"],
                      "as_of_day_return_pct":today_ret,"first_sep_oct_rebuild":first,
                      "all_sep_oct_qualified":qualified})
    payload={"as_of":"2026-10-28","signal_contract":"frozen ETF weighted OLS26 / HL10 / annual cross + R2 rebuild",
             "execution":"signal at close; hypothetical buy next session open","items":items}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"stocks":len(items),"with_sep_oct_rebuild":sum(bool(x["first_sep_oct_rebuild"]) for x in items)},ensure_ascii=False))
if __name__=="__main__":main()
