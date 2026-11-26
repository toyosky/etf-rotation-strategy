"""IV1 preregistered paired oil Q90 calibration, research only.
Input: archived OOS oil Top1 predictions, Cboe/FRED daily closes.
No strategy changes; no deployment; no forward label within 21 calendar days of test quarter.
"""
import csv, json, math, datetime as dt, io, urllib.request, pathlib, statistics
import numpy as np
from scipy.optimize import linprog
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=pathlib.Path("iv1_oil_results.json")
START=dt.date(2019,1,1); END=dt.date(2026,11,25)
SOURCES={"CBOE":"https://cdn.cboe.com/api/global/us_indices/daily_prices/OVX_History.csv","FRED":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=OVXCLS&cosd=2019-01-01&coed=2026-11-25"}
def download(name,url):
    import re
    from concurrent.futures import ThreadPoolExecutor
    def get(u):
        req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"text/csv,text/html,*/*"})
        with urllib.request.urlopen(req,timeout=50) as f: return f.read().decode("utf-8-sig")
    def parse(data):
        out={}
        # Cboe OVX may use a single value column rather than CLOSE.
        for row in csv.DictReader(io.StringIO(data)):
            r={k.strip().upper():v for k,v in row.items() if k}
            date=r.get("DATE") or r.get("OBSERVATION_DATE") or r.get("TRADE DATE")
            val=next((r[k] for k in ("CLOSE","OVX","OVXCLS","VALUE","INDEX VALUE") if r.get(k)),None)
            if not val and len(r)==2: val=list(r.values())[-1]
            if not date or not val: continue
            try:
                d=dt.date.fromisoformat(date.strip()[:10]) if "-" in date else dt.datetime.strptime(date.strip().split()[0],"%m/%d/%Y").date()
                v=float(val)
                if START<=d<=END and math.isfinite(v) and v>0: out[d]=v
            except (ValueError,TypeError): continue
        # FRED's public HTML table is plain text in <pre> on some versions.
        if not out:
            plain=re.sub(r"<[^>]+>"," ",data)
            for d,v in re.findall(r"(\d{4}-\d{2}-\d{2})\s+([0-9]+\.[0-9]+)",plain):
                day=dt.date.fromisoformat(d); val=float(v)
                if START<=day<=END and val>0: out[day]=val
        return out
    urls=[url] if name=="CBOE" else ["https://fred.stlouisfed.org/data/OVXCLS.txt"]+[f"https://fred.stlouisfed.org/graph/fredgraph.csv?id=OVXCLS&cosd={y}-01-01&coed={y}-12-31" for y in range(2019,2027)]
    def one(u):
        try:
            data=get(u); result=parse(data)
            print("FEED",name,u,"rows",len(result),"header",repr(data.splitlines()[0][:180]) if data else "empty",flush=True)
            return result
        except Exception as e:
            print("FEED_ERROR",name,u,str(e),flush=True);return {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        out={}
        for part in pool.map(one,urls): out.update(part)
    if len(out)<1400 or min(out)>dt.date(2020,1,1) or max(out)<dt.date(2026,11,4):
        raise ValueError(f"incomplete series {name}: {len(out)} {min(out,default=None)} {max(out,default=None)}")
    # Coverage gate relative to expected US weekdays, excluding holidays roughly.
    for year in range(2019,2027):
        count=sum(d.year==year for d in out)
        if count<(210 if year==2026 else 240): raise ValueError(f"insufficient year {year}: {count}")
    return out
def fit(x,y,penalty=.05):
    # quantile regression in log ratio, fixed L1 on standardized coefficients only.
    # intercept free, slopes represented positive and negative; residual +/-.
    n,p=x.shape
    a=np.column_stack([np.ones(n),x,-x,np.eye(n),-np.eye(n)])
    cost=np.r_[0,np.full(2*p,penalty),np.full(n,.9/n),np.full(n,.1/n)]
    res=linprog(cost,A_eq=a,b_eq=y,bounds=[(None,None)]+[(0,None)]*(2*p+2*n),method="highs")
    if not res.success: raise RuntimeError(res.message)
    return res.x[0],res.x[1:1+p]-res.x[1+p:1+2*p]
def summary(rows,k):
    y=np.array([r["loss"] for r in rows]);p=np.array([r[k] for r in rows]);e=y-p
    return {"n":len(rows),"pinball":float(np.mean(np.where(e>=0,.9*e,-.1*e))),"coverage":float(np.mean(e<=0)),"mean_q":float(np.mean(p)),"mean_excess":float(np.mean(np.maximum(e,0))),"severe_miss_gt_3pp":int(np.sum(e>.03))}
def main():
    feeds={};errors={}
    for name,url in SOURCES.items():
        try: feeds[name]=download(name,url)
        except Exception as e: errors[name]=str(e)
    if not feeds: raise RuntimeError(str(errors))
    source="CBOE" if "CBOE" in feeds else "FRED"; data=feeds[source]; dates=sorted(data)
    cross={}
    if len(feeds)==2:
        common=sorted(set(feeds["CBOE"])&set(feeds["FRED"]))
        delta=[abs(feeds["CBOE"][d]-feeds["FRED"][d]) for d in common]
        cross={"n":len(common),"max_abs_diff":max(delta),"n_diff_gt_0_05":sum(v>.05 for v in delta)}
        if cross["n_diff_gt_0_05"]>max(5,.01*len(common)): raise RuntimeError(f"source discrepancy {cross}")
    import bisect
    rows=[];missing=[]
    with (ROOT/"audit/20261120_prob_opportunity_oos_predictions.csv").open() as f:
        for r in csv.DictReader(f):
            if r["s"]!="501018": continue
            d=dt.datetime.strptime(r["d"],"%Y%m%d").date()
            i=bisect.bisect_left(dates,d)-1
            if i<252 or (d-dates[i]).days>4: missing.append(r["d"]);continue
            iv=data[dates[i]]; hist=[data[t] for t in dates[i-251:i+1]]
            q=float(r["D"]); loss=float(r["loss"])
            if q<=0 or not (0<=loss<=1): raise ValueError("bad label")
            rows.append({"d":d,"us":dates[i].isoformat(),"iv":iv,"percentile":sum(v<=iv for v in hist)/252,"chg5":math.log(iv/data[dates[i-5]]),"D":q,"loss":loss,"base":float(r["Dbase"])})
    rows.sort(key=lambda r:r["d"]); tested=[]; folds=[]
    for year in range(2021,2027):
        for m in [1,4,7,10]:
            start=dt.date(year,m,1);end=dt.date(year+int(m==10),1 if m==10 else m+3,1)
            train=[r for r in rows if r["d"]<start-dt.timedelta(days=21)]
            test=[r for r in rows if start<=r["d"]<end]
            if len(train)<40 or not test: continue
            y=np.array([math.log((r["loss"]+.001)/(r["D"]+.001)) for r in train])
            intercept=float(np.quantile(y,.9,method="higher"))
            X=lambda rs: np.array([[math.log(r["iv"]),r["percentile"],r["chg5"]] for r in rs])
            x=X(train); mu=x.mean(axis=0); sd=np.maximum(x.std(axis=0),1e-8)
            a,b=fit((x-mu)/sd,y)
            for r in test:
                z=(X([r])[0]-mu)/sd
                r["cal"]=float(max(0,(r["D"]+.001)*math.exp(intercept)-.001))
                r["iv1"]=float(max(0,(r["D"]+.001)*math.exp(a+z@b)-.001))
                tested.append(r)
            folds.append({"quarter":f"{year}Q{(m+2)//3}","train":len(train),"test":len(test),"intercept":a,"coef":b.tolist()})
    if not tested: raise RuntimeError("no test rows")
    # dependence diagnostic: greedy nonoverlap >= 10 calendar days, no retuning.
    thin=[]
    for r in tested:
        if not thin or (r["d"]-thin[-1]["d"]).days>=10: thin.append(r)
    keys=["D","cal","iv1"]; met=lambda rs:{k:summary(rs,k) for k in keys}
    result={"source":source,"source_errors":errors,"source_counts":{k:len(v) for k,v in feeds.items()},"crosscheck":cross,"iv_range":[str(dates[0]),str(dates[-1])],"oil_rows":len(rows),"missing":missing,"folds":folds,"metrics":met(tested),"thin_metrics":met(thin),"by_year":{str(y):met(rs) for y in range(2021,2027) if (rs:=[r for r in tested if r["d"].year==y])},"oct_cases":[{**r,"d":str(r["d"])} for r in tested if dt.date(2026,10,16)<=r["d"]<=dt.date(2026,11,5)],"tested":[{**r,"d":str(r["d"])} for r in tested]}
    OUT.write_text(json.dumps(result,indent=2))
    pathlib.Path("iv1_ovx_source.csv").write_text("date,ovx\n"+"\n".join(f"{d},{data[d]}" for d in dates)+"\n")
    print("IV1_RESULT "+json.dumps({k:v for k,v in result.items() if k not in ["tested","folds"]},separators=(",",":")))
if __name__=="__main__":main()
