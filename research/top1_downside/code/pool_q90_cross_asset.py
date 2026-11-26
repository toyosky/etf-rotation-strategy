"""POOL-Q1-Q4: fixed IV1.3 B linear quantile model; all current risk assets.
No parameter tuning; only training population/window changes.
Calendar = union of observed China trading dates across frozen 14 assets.
All rows and labels strictly dated; no fill of prices; same daily B features.
"""
import csv, datetime as dt, pathlib, json, math, bisect
from collections import defaultdict
import numpy as np
from scipy.optimize import linprog
from sklearn.linear_model import QuantileRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

ROOT=pathlib.Path(__file__).resolve().parents[1]
SYMS=["159934","159985","161226","513100","159957","159509","513290","159529","159981","501018","513530","511380","164824","512800"]
EPS=.002
ALPHA=.005
Q=.9
def load():
    raw=defaultdict(dict)
    for p in range(4):
        with (ROOT/f"audit/20261126_pool_bars_part{p}.csv").open() as f:
            for r in csv.DictReader(f):
                d=dt.date.fromisoformat(r["date"]);s=r["symbol"]
                assert d not in raw[s]
                raw[s][d]=[float(r[k]) if r[k] else np.nan for k in ("open","high","low","close","amount")]
    assert set(raw)==set(SYMS) and sum(map(len,raw.values()))==26704
    dates=sorted(set().union(*(set(x) for x in raw.values())))
    orig={}
    with (ROOT/"audit/20261120_prob_opportunity_oos_predictions.csv").open() as f:
        for r in csv.DictReader(f):
            if r["s"] in SYMS:
                orig[(r["s"],dt.datetime.strptime(r["d"],"%Y%m%d").date())]=(float(r["D"]),float(r["loss"]))
    rows=[];audit={}
    for s in SYMS:
        first=bisect.bisect_left(dates,min(raw[s]))
        op,hi,lo,cl,amt=np.array([raw[s].get(d,[np.nan]*5) for d in dates]).T
        good=np.isfinite(op+hi+lo+cl)&(np.minimum.reduce([op,hi,lo,cl])>0)&(hi>=np.maximum(op,cl)-1e-8)&(lo<=np.minimum(op,cl)+1e-8)&(hi>=lo)
        L=np.full(len(dates),np.nan)
        for i in range(first,len(dates)-5):
            if np.all(good[i:i+6]):L[i]=max(0,1-np.min(lo[i+1:i+6])/op[i+1])
        exclusions=defaultdict(int);n=0;missing_amt=0
        for i in range(first+60,len(dates)):
            d=dates[i];g=good[i-60:i+1];pair=g[1:]&g[:-1]
            if not g[-1] or not g[-6] or not g[-21] or pair.sum()<55 or pair[-20:].sum()<18 or pair[-5:].sum()<4 or pair[-25:-5].sum()<18:
                exclusions["history"]+=1;continue
            if not np.isfinite(L[i]):exclusions["label"]+=1;continue
            past=L[max(first,i-129):i-9];past=past[np.isfinite(past)]
            if len(past)<100:exclusions["warmup"]+=1;continue
            A=float(np.quantile(past,Q,method="higher"))
            r=np.diff(np.log(np.where(g,cl[i-60:i+1],np.nan)))
            rv=lambda n:float(np.nanstd(r[-n:],ddof=1)*np.sqrt(252))
            rv5,rv20,rv60=rv(5),rv(20),rv(60)
            down=float(np.sqrt(np.nanmean(np.minimum(r[-20:],0)**2))*np.sqrt(252))
            ret5,ret20=float(np.log(cl[i]/cl[i-5])),float(np.log(cl[i]/cl[i-20]))
            draw=float(cl[i]/np.nanmax(np.where(good[i-20:i+1],cl[i-20:i+1],np.nan))-1)
            intr=float(np.nanmean(np.where(good[i-4:i+1],np.log(hi[i-4:i+1]/lo[i-4:i+1]),np.nan)))
            gap=float(np.nanmean(np.where(good[i-4:i+1]&good[i-5:i],np.abs(np.log(op[i-4:i+1]/cl[i-5:i])),np.nan)))
            histamt=amt[i-20:i+1];validamt=bool(np.all(np.isfinite(histamt)) and np.all(histamt>0))
            av=float(np.log(np.mean(histamt[-5:])/np.mean(histamt))) if validamt else 0.
            b=[math.log(A+EPS),math.log(rv5+EPS),math.log(rv20+EPS),math.log(rv60+EPS),math.log(down+EPS),ret5,ret20,draw,intr,gap,av,float(not validamt)]
            assert np.all(np.isfinite(b))
            old=orig.get((s,d))
            # Compare archived Q90 only when original realized loss agrees with current L5 (tolerance 1e-8).
            rows.append({"s":s,"d":d,"i":i,"y":float(L[i]),"A":A,"B":b,"oldQ":old[0] if old else None,"old_loss":old[1] if old else None,"top":old is not None})
            n+=1;missing_amt+=not validamt
        audit[s]={"raw":len(raw[s]),"features":n,"missing_amount":missing_amt,"exclusions":dict(exclusions),"first":str(min(raw[s]))}
    return dates,rows,audit
def matrix(rs):
    return np.array([r["B"] for r in rs]),np.log(np.array([r["y"] for r in rs])+EPS)
def objective(y,p,b):
    e=y-p
    return float(np.mean(np.where(e>=0,Q*e,(Q-1)*e))+ALPHA*np.abs(b).sum())
def fit(tr,te,verify=False):
    x,y=matrix(tr); scaler=StandardScaler().fit(x);z=scaler.transform(x);xt=scaler.transform(np.array([r["B"] for r in te]))
    n,k=z.shape
    # Exact dual of sklearn's L1-penalized quantile LP. Few constraints, faster for pooled data.
    result=linprog(-y,A_ub=np.vstack((z.T,-z.T)),b_ub=np.full(2*k,n*ALPHA),A_eq=np.ones((1,n)),b_eq=[0],bounds=(Q-1,Q),method="highs")
    if not result.success:raise RuntimeError(result.message)
    beta=-result.ineqlin.marginals[:k]+result.ineqlin.marginals[k:]
    intercept=-result.eqlin.marginals[0]
    ob=objective(y,z@beta+intercept,beta)
    assert abs(ob+result.fun/n)<1e-7,(ob,result.fun/n)
    if verify:
        m=QuantileRegressor(quantile=Q,alpha=ALPHA,solver="highs").fit(z,y)
        ref=objective(y,m.predict(z),m.coef_)
        assert abs(ref-ob)<1e-7,(ref,ob)
    return np.clip(np.exp(xt@beta+intercept)-EPS,0,1)
def loss(rs,key):
    e=np.array([r["y"]-r[key] for r in rs])
    return np.where(e>=0,Q*e,(Q-1)*e)
def metric(rs,key):
    if not rs:return None
    e=np.array([r["y"]-r[key] for r in rs])
    return {"n":len(rs),"pinball":float(loss(rs,key).mean()),"coverage":float(np.mean(e<=0)),"severe":int(np.sum(e>.03)),"excess":float(np.maximum(e,0).mean()),"mean_q":float(np.mean([r[key] for r in rs]))}
def metrics(rs,keys):
    return {k:metric(rs,k) for k in keys}
def paired(rs,a,b,seed=20261126):
    if not rs:return None
    # Sample calendar blocks jointly across all assets to retain shared market shocks.
    dates=sorted(set(r["i"] for r in rs));idx={d:i for i,d in enumerate(dates)}
    totals=np.zeros(len(dates));counts=np.zeros(len(dates))
    for r,v in zip(rs,loss(rs,b)-loss(rs,a)):
        j=idx[r["i"]];totals[j]+=v;counts[j]+=1
    rng=np.random.default_rng(seed);n=len(dates);v=[]
    for _ in range(2000):
        ix=np.concatenate([(np.arange(20)+s)%n for s in rng.integers(0,n,size=math.ceil(n/20))])[:n]
        v.append(totals[ix].sum()/counts[ix].sum())
    return {"delta":float(totals.sum()/counts.sum()),"ci95":[float(x) for x in np.quantile(v,[.025,.975])],"dates":n}
def main():
    dates,rows,audit=load()
    # All models identical test sample: minimum 250 eligible own-history rows in 3y window.
    tested=[];folds=[];loo_cold=[]
    for y in range(2019,2027):
        for m in (1,4,7,10):
            start=dt.date(y,m,1);end=dt.date(y+int(m==10),1 if m==10 else m+3,1)
            ix=bisect.bisect_left(dates,start)
            alltr=[r for r in rows if r["i"]<ix-10]
            short=[r for r in alltr if r["d"]>=start-dt.timedelta(days=1096)]
            candidates=[r for r in rows if start<=r["d"]<end]
            eligible=[s for s in SYMS if sum(r["s"]==s for r in short)>=250]
            te=[r for r in candidates if r["s"] in eligible]
            if not te:continue
            for k,p in zip(te,fit(alltr,te,verify=not tested)):k["P_all"]=float(p)
            for k,p in zip(te,fit(short,te)):k["P_3"]=float(p)
            for s in SYMS:
                st=[r for r in te if r["s"]==s]
                if st:
                    for k,p in zip(st,fit([r for r in alltr if r["s"]==s],st,verify=not tested)):k["I_all"]=float(p)
                    for k,p in zip(st,fit([r for r in short if r["s"]==s],st)):k["I_3"]=float(p)
                # Held-out asset never contributes any model training row; its own past raw features allowed.
                ct=[r for r in candidates if r["s"]==s]
                if ct:
                    lt=[r for r in alltr if r["s"]!=s]
                    if len(lt)>=250:
                        for k,p in zip(ct,fit(lt,ct)):k["LOO"]=float(p)
                        loo_cold.extend([r for r in ct if s not in eligible])
            assert all(all(k in r for k in ("I_all","I_3","P_all","P_3","LOO")) for r in te)
            tested.extend(te);folds.append({"fold":f"{y}Q{(m+2)//3}","train_all":len(alltr),"train_3":len(short),"eligible":eligible,"test":len(te)})
            print("POOL_PROGRESS "+json.dumps(folds[-1]),flush=True)
    keys=["A","I_3","I_all","P_3","P_all","LOO"]
    top=[r for r in tested if r["top"] and abs(r["old_loss"]-r["y"])<1e-8]
    top_all=[r for r in tested if r["top"]]
    segs={"all":tested,"pre2026":[r for r in tested if r["d"].year<2026],"2026":[r for r in tested if r["d"].year==2026],"no_oil":[r for r in tested if r["s"]!="501018"],"top1":top,"top1_2026":[r for r in top if r["d"].year==2026]}
    comparisons=[("I_3","I_all"),("P_3","P_all"),("I_all","P_all"),("P_all","LOO"),("A","P_all")]
    per_asset={s:metrics([r for r in tested if r["s"]==s],keys) for s in SYMS}
    out={"coverage":{"calendar":len(dates),"raw":sum(a["raw"] for a in audit.values()),"feature_rows":len(rows),"test":len(tested),"dates":len(set(r["i"] for r in tested)),"first":str(min(r["d"] for r in tested)),"last":str(max(r["d"] for r in tested)),"top_archive_matched":len(top),"top_archive_loss_mismatch":len(top_all)-len(top),"cold_start":len(loo_cold)},
        "data_audit":audit,"folds":folds,"metrics":{k:metrics(v,keys+(["oldQ"] if k.startswith("top1") else [])) for k,v in segs.items()},
        "per_asset":per_asset,"by_year":{str(y):metrics([r for r in tested if r["d"].year==y],keys) for y in range(2019,2027)},
        "paired":{k:{b+"-"+a:paired(v,a,b) for a,b in comparisons} for k,v in segs.items() if k in ("all","pre2026","2026","no_oil")},
        "top_paired":{b+"-"+a:paired(top,a,b) for a,b in [("oldQ","I_all"),("oldQ","P_all"),("oldQ","LOO")]},
        "cold_loo":metrics(loo_cold,["A","LOO"]),"per_asset_2026":{s:metrics([r for r in tested if r["s"]==s and r["d"].year==2026],keys) for s in SYMS}}
    # Equal asset weight macro mean; not tune on the result.
    out["macro"]={k:float(np.mean([v[k]["pinball"] for v in per_asset.values() if v[k] is not None])) for k in keys}
    out["predictions"]=[{k:(str(v) if k=="d" else v) for k,v in r.items() if k!="B"} for r in tested]
    pathlib.Path("pool_q90_results.json").write_text(json.dumps(out,indent=2))
    for k in ("coverage","metrics","per_asset","by_year","paired","top_paired","cold_loo","macro","per_asset_2026","data_audit"):
        print("POOL_"+k.upper()+" "+json.dumps(out[k],separators=(",",":")),flush=True)
if __name__=="__main__":main()
