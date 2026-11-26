"""IV1.3: frozen protocol validation of historical training memory and annual refit cadence.
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
OUT=pathlib.Path("iv13_validation.json")
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
            if dt.date(2015,1,1)<=d<=dt.date(2026,11,25) and np.isfinite(v) and v>0: o[d]=v
        except (ValueError,TypeError): continue
    for y in range(2015,2027):
        n=sum(d.year==y for d in o)
        if n<(210 if y==2026 else 240): raise RuntimeError(f"OVX coverage {y}: {n}")
    pathlib.Path("iv13_ovx.csv").write_text("date,ovx\n"+"\n".join(f"{d},{o[d]}" for d in sorted(o))+"\n")
    return o
def load():
    data=list(csv.DictReader((ROOT/"audit/20261126_oil_inception_sessions_hfq.csv").open()))
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
        if d<dt.date(2017,1,1):continue
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
    # Primary model is the already specified linear B. No feature, hyperparameter, or label changes.
    # No model selection based on this audit. Annual and quarterly use expanding history.
    def pred(tr,te):
        model=make_pipeline(StandardScaler(),QuantileRegressor(quantile=.9,alpha=.005,solver="highs"))
        model.fit(np.array([r["B"] for r in tr]),np.log(np.array([r["y"] for r in tr])+EPS))
        return np.clip(np.exp(model.predict(np.array([r["B"] for r in te])))-EPS,0,1)
    def pool(start):
        ix=bisect.bisect_left(dates,start)
        return [r for r in rows if r["i"]<ix-10]
    def loss(te,p):
        e=np.array([r["y"] for r in te])-p
        return np.where(e>=0,.9*e,-.1*e)
    def stats(te,p):
        e=np.array([r["y"] for r in te])-p
        return {"n":len(te),"pinball":float(loss(te,p).mean()),"coverage":float(np.mean(e<=0)),"severe":int(np.sum(e>.03)),"mean_q":float(p.mean()),"excess":float(np.maximum(e,0).mean())}
    rng=np.random.default_rng(20261126)
    def ci(z):
        n=len(z);q=[]
        for _ in range(2000):
            ix=np.concatenate([(np.arange(20)+s)%n for s in rng.integers(0,n,size=math.ceil(n/20))])[:n]
            q.append(z[ix].mean())
        return {"delta":float(z.mean()),"ci95":[float(v) for v in np.quantile(q,[.025,.975])]}
    annual={};ablation={};predictions=[];delta_all=[];delta_pre=[];all_y=[];all_a=[];all_q=[]
    # Fixed candidate years, no parameter grid. Freeze each calendar year, 2019 as extra check.
    # Historical ablation uses annual freeze, only past years; 20 equal-size block-removal controls.
    # Random deletion starts from full pool, partition into consecutive 20-row blocks, last block truncated.
    def random_keep(n,k,rg):
        blocks=[np.arange(i,min(i+20,n)) for i in range(0,n,20)]
        order=rg.permutation(len(blocks));cut=[]
        remaining=k
        for j in order:
            if remaining<=0:break
            block=blocks[j]
            if len(block)>remaining:
                a=int(rg.integers(0,len(block)-remaining+1));block=block[a:a+remaining]
            cut.extend(block.tolist());remaining-=len(block)
        assert len(cut)==k
        drop=set(cut);return [i for i in range(n) if i not in drop]
    controls=20
    for year in range(2019,2027):
        start=dt.date(year,1,1)
        te=[r for r in rows if r["d"].year==year]
        tr=pool(start)
        if len(tr)<250 or not te:continue
        p=pred(tr,te)
        # Quarterly update; same test dates and model. No retuning.
        pq=np.full(len(te),np.nan)
        for m in (1,4,7,10):
            ix=[i for i,r in enumerate(te) if (r["d"].month-1)//3==(m-1)//3]
            if ix:pq[ix]=pred(pool(dt.date(year,m,1)),[te[i] for i in ix])
        assert np.all(np.isfinite(pq))
        z=loss(te,p)-loss(te,pq)
        top=[i for i,r in enumerate(te) if r["top"]]
        annual[str(year)]={"train_n":len(tr),"frozen":stats(te,p),"quarterly":stats(te,pq),"paired":ci(z),
            "top1":({"frozen":stats([te[i] for i in top],p[top]),"quarterly":stats([te[i] for i in top],pq[top])} if top else None)}
        delta_all.extend(z);all_y.extend(te);all_a.extend(p);all_q.extend(pq)
        if year<2026:delta_pre.extend(z)
        predictions.extend({"d":str(r["d"]),"y":r["y"],"annual":float(a),"quarterly":float(q),"top":r["top"]} for r,a,q in zip(te,p,pq))
        # Evaluate past event-year exclusion against both full training and random equal-size block deletions.
        eligible=[y for y in (2018,2020,2022) if y<year]
        specs=[(str(y),[y]) for y in eligible]
        if len(eligible)==3:specs.append(("all_three",eligible))
        ablation[str(year)]={}
        for name,ys in specs:
            keep=[r for r in tr if r["d"].year not in ys];k=len(tr)-len(keep)
            if k==0 or len(keep)<250:continue
            pa=pred(keep,te);za=loss(te,pa)-loss(te,p)
            ctrl=[];rg=np.random.default_rng(20261126+year*100+sum(ys))
            for _ in range(controls):
                keep_ix=random_keep(len(tr),k,rg)
                pr=pred([tr[i] for i in keep_ix],te)
                ctrl.append(stats(te,pr)["pinball"])
            actual=stats(te,pa)
            ablation[str(year)][name]={"removed":k,"remaining":len(keep),"full":stats(te,p),"ablation":actual,"paired_vs_full":ci(za),
                "random_controls":controls,"random_loss_mean":float(np.mean(ctrl)),"random_loss_median":float(np.median(ctrl)),
                "random_loss_range":[float(np.min(ctrl)),float(np.max(ctrl))],"random_losses":ctrl,
                "rank_fraction_random_no_worse":float(np.mean(np.array(ctrl)<=actual["pinball"]))}
        print("IV13_YEAR "+json.dumps({"year":year,"annual":annual[str(year)],"ablation":ablation[str(year)]},separators=(",",":")),flush=True)
    result={"coverage":{"rows":len(rows),"test":len(all_y),"first":str(all_y[0]["d"]),"last":str(all_y[-1]["d"]),"excluded":excluded},
        "annual":annual,"ablation":ablation,"aggregate":{"frozen":stats(all_y,np.array(all_a)),"quarterly":stats(all_y,np.array(all_q)),"paired_all":ci(np.array(delta_all)),"paired_pre2026":ci(np.array(delta_pre))},
        "protocol":{"model":"B linear, alpha=.005, q=.9, same IV1.2 data gates","ablation":"remove training rows by signal year; boundary features may still encode earlier history; random contiguous 20-row block deletion matched exact n, 20 draws","freeze":"annual expanding history versus quarterly expanding history, 10-session purge; features update daily","caution":"2026 research-exposed, exploratory contrasts, overlapping targets; no multiplicity adjustment"},"predictions":predictions}
    OUT.write_text(json.dumps(result,indent=2))
    print("IV13_SUMMARY "+json.dumps({k:result[k] for k in ("coverage","aggregate","protocol")},separators=(",",":")),flush=True)
if __name__=="__main__":main()
