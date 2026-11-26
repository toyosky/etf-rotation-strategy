"""IV1.1: all-session oil downside forecasting, fixed paired walk-forward protocol.
No selection by Top1, no live strategy modifications. Data snapshot uses China calendar 511220.
"""
import pathlib, csv, io, urllib.request, json, datetime as dt, bisect, math, os
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import QuantileRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

ROOT=pathlib.Path(__file__).resolve().parents[1]
TOLERANT=True # separate sensitivity; no missing-price fill
OUT=pathlib.Path("iv11_oil_results.json")
EPS=.002
def ovx():
    url="https://cdn.cboe.com/api/global/us_indices/daily_prices/OVX_History.csv"
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=45) as f: raw=f.read().decode("utf-8-sig")
    o={}
    for r in csv.DictReader(io.StringIO(raw)):
        r={k.upper().strip():v for k,v in r.items()}
        try:
            d=dt.date.fromisoformat(r["DATE"]) if "-" in r["DATE"] else dt.datetime.strptime(r["DATE"],"%m/%d/%Y").date()
            v=float(r.get("OVX") or r.get("CLOSE"))
            if dt.date(2016,1,1)<=d<=dt.date(2026,11,25) and np.isfinite(v) and v>0: o[d]=v
        except (ValueError,TypeError): continue
    for y in range(2016,2027):
        n=sum(d.year==y for d in o)
        if n<(210 if y==2026 else 240): raise RuntimeError(f"OVX coverage {y}: {n}")
    pathlib.Path("iv11_ovx.csv").write_text("date,ovx\n"+"\n".join(f"{d},{o[d]}" for d in sorted(o))+"\n")
    return o
def load():
    data=list(csv.DictReader((ROOT/"audit/20261126_oil_all_sessions_hfq.csv").open()))
    dates=[dt.date.fromisoformat(r["date"]) for r in data]
    vals=lambda k:np.array([float(r[k]) if r[k] else np.nan for r in data])
    op,hi,lo,cl,vol,amt=map(vals,["open","high","low","close","volume","amount"])
    good=np.isfinite(op+hi+lo+cl)&(np.minimum.reduce([op,hi,lo,cl])>0)&(hi>=np.maximum(op,cl)-1e-8)&(lo<=np.minimum(op,cl)+1e-8)&(hi>=lo)
    L=np.full(len(dates),np.nan)
    for i in range(len(dates)-5):
        if np.all(good[i:i+6]): L[i]=max(0,1-np.min(lo[i+1:i+6])/op[i+1])
    return dates,op,hi,lo,cl,vol,amt,good,L
def metrics(rows,keys):
    if not rows:return {}
    y=np.array([r["y"] for r in rows])
    out={}
    for k in keys:
        p=np.array([r[k] for r in rows]); e=y-p
        out[k]={"n":len(y),"pinball":float(np.mean(np.where(e>=0,.9*e,-.1*e))),"coverage":float(np.mean(e<=0)),"mean_q":float(p.mean()),"excess":float(np.maximum(e,0).mean()),"severe":int(np.sum(e>.03))}
    return out
def main():
    o=ovx(); od=sorted(o); ov=np.array([o[d] for d in od])
    dates,op,hi,lo,cl,vol,amt,good,L=load()
    # Archived Top1 labels are for subgroup evaluation only, never features or selection.
    orig={dt.datetime.strptime(r["d"],"%Y%m%d").date():float(r["D"]) for r in csv.DictReader((ROOT/"audit/20261120_prob_opportunity_oos_predictions.csv").open()) if r["s"]=="501018"}
    rows=[]; excluded={"history_or_bad_bar":0,"iv_missing":0,"label_missing":0,"mature_history":0}
    for i in range(60,len(dates)):
        d=dates[i]
        if d<dt.date(2018,1,1):continue
        if TOLERANT:
            g=good[i-60:i+1]
            pair=g[1:]&g[:-1]
            if not g[-1] or not g[-6] or not g[-21] or pair.sum()<55 or pair[-20:].sum()<18 or pair[-5:].sum()<4 or pair[-25:-5].sum()<18:
                excluded["history_or_bad_bar"]+=1;continue
        elif not np.all(good[i-60:i+1]):excluded["history_or_bad_bar"]+=1;continue
        if not np.isfinite(L[i]):excluded["label_missing"]+=1;continue
        j=bisect.bisect_left(od,d)-1
        if j<251 or (d-od[j]).days>4:excluded["iv_missing"]+=1;continue
        # Each historical label must already mature; 10 China sessions safety buffer.
        past=L[max(0,i-129):i-9];past=past[np.isfinite(past)]
        if len(past)<100:excluded["mature_history"]+=1;continue
        A=float(np.quantile(past,.9,method="higher"))
        r=np.diff(np.log(np.where(good[i-60:i+1],cl[i-60:i+1],np.nan)))
        rv=lambda n:float(np.nanstd(r[-n:],ddof=1)*np.sqrt(252))
        rv5,rv20,rv60=rv(5),rv(20),rv(60)
        iv=ov[j]/100
        down=float(np.sqrt(np.nanmean(np.minimum(r[-20:],0)**2))*np.sqrt(252))
        ret5,ret20=float(np.log(cl[i]/cl[i-5])),float(np.log(cl[i]/cl[i-20]))
        draw=float(cl[i]/np.nanmax(np.where(good[i-20:i+1],cl[i-20:i+1],np.nan))-1)
        intr=float(np.nanmean(np.where(good[i-4:i+1],np.log(hi[i-4:i+1]/lo[i-4:i+1]),np.nan)))
        gap=float(np.nanmean(np.where(good[i-4:i+1]&good[i-5:i],np.abs(np.log(op[i-4:i+1]/cl[i-5:i])),np.nan)))
        # Amount ratio is relative, zero/unknown does not become a fake turnover observation.
        histamt=amt[i-20:i+1];validamt=bool(np.all(np.isfinite(histamt)) and np.all(histamt>0))
        av=float(np.log(np.mean(histamt[-5:])/np.mean(histamt))) if validamt else 0.
        b=[math.log(A+EPS),math.log(rv5+EPS),math.log(rv20+EPS),math.log(rv60+EPS),math.log(down+EPS),ret5,ret20,draw,intr,gap,av,float(not validamt)]
        c=b+[math.log(iv),float(np.mean(ov[j-251:j+1]<=ov[j])),float(np.log(ov[j]/ov[j-5]))]
        # IV/RV is a cross-market divergence, not same-underlying variance risk premium.
        rv20prev=float(np.nanstd(r[-25:-5],ddof=1)*np.sqrt(252))
        df=c+[math.log(iv/(rv20+EPS)),float(np.log(ov[j]/ov[j-5])-np.log((rv20+EPS)/(rv20prev+EPS)))]
        rows.append({"i":i,"d":d,"us":str(od[j]),"y":float(L[i]),"A":A,"rv20":rv20,"iv":iv,"ratio":iv/(rv20+EPS),"ret20":ret20,"B":b,"C":c,"D":df,"top":d in orig,"oldQ":orig.get(d),"valid_amount":validamt})
    tested=[];folds=[]
    for y in range(2021,2027):
        for m in (1,4,7,10):
            start=dt.date(y,m,1);end=dt.date(y+int(m==10),1 if m==10 else m+3,1)
            start_i=bisect.bisect_left(dates,start)
            # Last three years, fixed calendar window; training labels 10 sessions away.
            tr=[r for r in rows if r["i"]<start_i-10 and r["d"]>=start-dt.timedelta(days=1096)]
            te=[r for r in rows if start<=r["d"]<end]
            if len(tr)<250 or not te:continue
            yy=np.log(np.array([r["y"] for r in tr])+EPS)
            for name in ("B","C","D"):
                xx=np.array([r[name] for r in tr]);xt=np.array([r[name] for r in te])
                models={"lin":make_pipeline(StandardScaler(),QuantileRegressor(quantile=.9,alpha=.005,solver="highs")),
                        "tree":HistGradientBoostingRegressor(loss="quantile",quantile=.9,max_iter=100,learning_rate=.05,max_depth=2,min_samples_leaf=30,l2_regularization=1,early_stopping=False,random_state=42)}
                for kind,model in models.items():
                    model.fit(xx,yy)
                    p=np.clip(np.exp(model.predict(xt))-EPS,0,1)
                    for r,v in zip(te,p):r[kind+name]=float(v)
            tested+=te;folds.append({"q":f"{y}Q{(m+2)//3}","train":len(tr),"test":len(te)})
    keys=["A","linB","linC","linD","treeB","treeC","treeD"]
    if not tested:raise RuntimeError("no test")
    top=[r for r in tested if r["top"]]
    # Fixed 20-session moving-block paired bootstrap, preserves overlapping labels locally.
    rng=np.random.default_rng(20261126)
    def paired(rs,a,b):
        yy=np.array([r["y"] for r in rs])
        def loss(k):
            e=yy-np.array([r[k] for r in rs]);return np.where(e>=0,.9*e,-.1*e)
        z=loss(b)-loss(a);n=len(z)
        if n<20:return {"delta":float(z.mean()),"ci95":None}
        q=[]
        for _ in range(1000):
            ix=np.concatenate([(np.arange(20)+s)%n for s in rng.integers(0,n,size=math.ceil(n/20))])[:n]
            q.append(z[ix].mean())
        return {"delta":float(z.mean()),"ci95":[float(v) for v in np.quantile(q,[.025,.975])]}
    segs={"all":tested,"pre2026":[r for r in tested if r["d"].year<2026],"2026":[r for r in tested if r["d"].year==2026],"uptrend":[r for r in tested if r["ret20"]>0],"downtrend":[r for r in tested if r["ret20"]<=0],"top1":top,"top1_2026":[r for r in top if r["d"].year==2026]}
    out={"coverage":{"gap_tolerant":TOLERANT,"calendar":len(dates),"valid_bars":int(good.sum()),"bad_dates":[str(d) for d,g in zip(dates,good) if not g],"ovx":len(o),"rows":len(rows),"test":len(tested),"excluded":excluded,"volume_missing":sum(not r["valid_amount"] for r in tested),"test_first":str(tested[0]["d"]),"test_last":str(tested[-1]["d"])},
        "folds":folds,"metrics":{k:metrics(v,keys+(["oldQ"] if k.startswith("top1") else [])) for k,v in segs.items()},
        "by_year":{str(y):metrics([r for r in tested if r["d"].year==y],keys) for y in range(2021,2027)},
        "paired":{k:paired(tested,a,b) for k,a,b in [("linC-B","linB","linC"),("linD-B","linB","linD"),("treeC-B","treeB","treeC"),("treeD-B","treeB","treeD")]},
        "thin":{str(i):metrics([r for r in tested if r["i"]%5==i],keys) for i in range(5)},
        "oct_cases":[{k:(str(v) if k=="d" else v) for k,v in r.items() if k not in ("B","C","D")} for r in tested if dt.date(2026,10,16)<=r["d"]<=dt.date(2026,11,5)],
        "july_cases":[{k:(str(v) if k=="d" else v) for k,v in r.items() if k not in ("B","C","D")} for r in tested if dt.date(2026,7,20)<=r["d"]<=dt.date(2026,7,24)]}
    out["predictions"]=[{k:(str(v) if k=="d" else v) for k,v in r.items() if k not in ("B","C","D")} for r in tested]
    OUT.write_text(json.dumps(out,indent=2))
    for k in ("coverage","metrics","by_year","paired","thin","oct_cases","july_cases"):
        print("IV11_"+k.upper()+" "+json.dumps(out[k],separators=(",",":")),flush=True)
if __name__=="__main__":main()
