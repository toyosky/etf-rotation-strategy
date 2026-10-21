#!/usr/bin/env python3
"""10/20 snapshot-only forensic test of 40 ETF rebuilds, no trading changes.

Daily/weekly return correlations are PRICE proxies, NOT exact tracking index
identification or underlying price confirmation. Fields marked unknown stay unknown.
All prices used are at or before audit date. No lookahead.
"""
from __future__ import annotations
import argparse, json, math
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

# Certified as SAME tracking index by source published 2026-05-06.
# CSI 800 Free Cash Flow index 932368.
VERIFIED_INDEX = {
    s:"CSI_800_FREE_CASH_FLOW_932368"
    for s in ("159229","563580","563990","159119","516460","563680")
}
# Separate confirmed from public fund pages. No guessed index assignments.
VERIFIED_INDEX.update({
    "161725":"CSI_BAIJIU",
    "512690":"CSI_LIQUOR",
    "159520":"CSI_CONSUMER_LEADERS",
})

def nf(x,prec=4):
    try:
        return round(float(x),prec) if np.isfinite(x) else None
    except (TypeError,ValueError):
        return None

def corr_matrix(src,days,period=120,lag=1,min_overlap=40):
    closes=src.pivot_table(index="date",columns="symbol",values="close",aggfunc="last").sort_index()
    closes=closes.loc[closes.index<=pd.Timestamp(days)].tail(period+lag+3)
    # DO NOT forward fill; stale holidays remain flat actual onshore ETF price,
    # but no market-priced underlying index is imputed.
    returns=np.log(closes/closes.shift(lag)).tail(period)
    return returns.corr(min_periods=min_overlap), returns

def complete_link(corr, threshold):
    ids=list(corr.index)
    clusters=[[i] for i in ids]
    def merger(a,b):
        for u in a:
            for v in b:
                val=corr.loc[u,v]
                if not np.isfinite(val) or val<threshold:
                    return False
        return True
    while True:
        candidates=[(i,j) for i in range(len(clusters))
                    for j in range(i+1,len(clusters))
                    if merger(clusters[i],clusters[j])]
        if not candidates:
            break
        # Merge the pair with best WORST correlation; deterministic tie-breaks.
        i,j=max(candidates,key=lambda p:(min(float(corr.loc[a,b])
                     for a in clusters[p[0]] for b in clusters[p[1]]),-p[0],-p[1]))
        clusters[i]=sorted(clusters[i]+clusters[j])
        clusters.pop(j)
    return sorted(clusters,key=lambda a:(-len(a),a[0]))

def group_matrix(corr,items):
    out=pd.DataFrame(index=items,columns=items,dtype=float)
    for a in items:
        for b in items:
            if a in corr.index and b in corr.columns:
                out.loc[a,b]=corr.loc[a,b]
    return out

def daily_hist(data,symbol,day):
    x=data[(data.symbol==symbol)&(data.date.isin(pd.to_datetime(["2026-10-15","2026-10-16",
                           "2026-10-19","2026-10-20"])))]
    return {d.strftime("%Y-%m-%d"):nf(c,5) for d,c in zip(x.date,x.close)}

def ret_between(hist,start,end):
    a=hist.get(start);b=hist.get(end)
    return nf((b/a-1)*100,3) if a and b else None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--parquet",required=True)
    ap.add_argument("--market",default="data/full-market-rebuild-latest.json")
    ap.add_argument("--scope",default="data/audit-scope-latest.json")
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    market=json.loads(Path(args.market).read_text())
    scope=json.loads(Path(args.scope).read_text())
    day="2026-10-20"
    if market.get("as_of")!=day or scope.get("as_of")!=day or market.get("raw_qualified")!=40:
        raise RuntimeError("Expected 2026-10-20 validated 40 symbols")
    rows=market["qualified_candidates"]
    codes=sorted(set(str(x["symbol"]) for x in rows))
    if len(codes)!=40 or any(x["stage"]!="REBUILDING_QUALIFIED" for x in rows):
        raise RuntimeError("40 independent code labels required, duplicate or stale?")
    category={}
    for group in scope["categories"]:
        for member in group["members"]:
            if member["symbol"] in codes:
                category[member["symbol"]]=group["category_id"]
    if set(category)!=set(codes): raise RuntimeError("Missing classifications")
    data=pd.read_parquet(args.parquet,columns=["symbol","date","close","open","amount"])
    data=data.loc[data.symbol.astype(str).isin(codes)].copy()
    data["date"]=pd.to_datetime(data.date)
    data=data.loc[data.date<=pd.Timestamp(day)]
    data=data.sort_values(["symbol","date"]).drop_duplicates(["symbol","date"],keep="last")
    if not set(codes).issubset(set(data.symbol.astype(str).unique())): raise RuntimeError("Missing full-market price symbols")
    corr1,returns1=corr_matrix(data,day,120,1,45)
    corr5,returns5=corr_matrix(data,day,120,5,45)
    corr5_60,returns5_60=corr_matrix(data,day,60,5,30)
    grouped=defaultdict(list)
    for c in codes:grouped[category[c]].append(c)
    metas={str(x["symbol"]):x for x in rows}
    result={
        "as_of":day,"source":"private archived all-market Tencent HFQ parq release asof 2026-10-20",
        "qualified_etf_count":len(codes),
        "definition_note":"Intra-category clusters use 5-session log close returns, trailing 120 A-share sessions, minimum 45 overlapping returns, complete-link min pairwise correlations; thresholds are SENSITIVITY analyses not factually independent indexes.",
        "caution":["ETF prices are adjusted and may be rounded; correlation cannot prove tracking-index identity",
                   "Historical tracking-index IDs are unknown for most members; no exact total-index count asserted",
                   "Cross-border ETF price updates on China trading days even when Hong Kong underlying is closed",
                   "Correlation windows include pre-signal days but no post-2026-10-20 prices",
                   "Rolling 5-day returns overlap; correlated sampling noise; thresholds exploratory",
                   "No NAV/premium on 10/20; underlying-index truth test cannot yet be run"],
        "known_index_identifications":{c:VERIFIED_INDEX[c] for c in codes if c in VERIFIED_INDEX},
        "market_holidays":{"HK":["2026-10-19"]},
        "categories":{},
        "members":[],
        "pairwise_extremes":[],
    }
    for c in codes:
        p=data[data.symbol==c]
        hist=daily_hist(data,c,day)
        window=p[p.date>=pd.Timestamp("2026-06-01")]
        d_close=window.close.astype(float).to_numpy()
        same=np.mean(np.diff(d_close)==0) if len(d_close)>1 else None
        result["members"].append({"symbol":c,"name":metas[c].get("name"),
                "category":category[c],"first_qualified_date":metas[c].get("first_qualified_date"),
                "r2_asof":nf(metas[c].get("r2")),"avg_daily_amount60":nf(metas[c].get("avg_amount60"),1),
                "verified_underlying_index":VERIFIED_INDEX.get(c),
                "oct_prices":hist,
                "ret_16_to_19_pct":ret_between(hist,"2026-10-16","2026-10-19"),
                "ret_19_to_20_pct":ret_between(hist,"2026-10-19","2026-10-20"),
                "pct_same_close_days_since_june":nf(100*same,1) if same is not None else None,
                "holiday_mismatch":category[c] in {"HK_CONSUMER","CROSS_BORDER_CONSUMER"} and 
                                "2026-10-19" in hist})
    for k,ids in sorted(grouped.items()):
        stats={"n":len(ids),"members":sorted(ids),
               "onset_dates":{d:len([a for a in ids if metas[a].get("first_qualified_date")==d])
                    for d in ["2026-10-16","2026-10-19","2026-10-20"]},
               "verified_index_groups":{},
               "unverified_index_count":0,
               "price_clusters":{},
               "pair_correlation_summary":{}}
        groups=defaultdict(list)
        for symbol in ids:
            if symbol in VERIFIED_INDEX:
                groups[VERIFIED_INDEX[symbol]].append(symbol)
            else:
                stats["unverified_index_count"]+=1
        stats["verified_index_groups"]={key:sorted(v) for key,v in groups.items()}
        if len(ids)>1:
            for name,m in [("corr5_120",corr5),("corr1_120",corr1),("corr5_60",corr5_60)]:
                cm=group_matrix(m,ids)
                pairs=[nf(cm.loc[a,b],5) for i,a in enumerate(ids) for b in ids[i+1:]]
                pairs=[v for v in pairs if v is not None]
                stats["pair_correlation_summary"][name]={
                    "pairs":len(pairs),
                    "min":min(pairs) if pairs else None,
                    "median":nf(np.median(pairs),4) if pairs else None,
                    "max":max(pairs) if pairs else None,
                    "share_above_0_9":nf(np.mean(np.asarray(pairs)>=.9),3) if pairs else None}
            cm=group_matrix(corr5,ids)
            for threshold in (.75,.85,.9,.95):
                c=complete_link(cm,threshold)
                stats["price_clusters"][str(threshold)]={"n":len(c),"members":c}
        else:
            stats["price_clusters"]={"0.75":{"n":1,"members":[ids]},
                                     "0.85":{"n":1,"members":[ids]},
                                     "0.9":{"n":1,"members":[ids]},
                                     "0.95":{"n":1,"members":[ids]}}
        result["categories"][k]=stats
    for i,a in enumerate(codes):
        for b in codes[i+1:]:
            if category[a]!=category[b]:continue
            c1=nf(corr1.loc[a,b],5)
            c5=nf(corr5.loc[a,b],5)
            c60=nf(corr5_60.loc[a,b],5)
            if c5 is not None:
                result["pairwise_extremes"].append({
                    "a":a,"b":b,"category":category[a],"corr_1d_120":c1,
                    "corr_5d_120":c5,"corr_5d_60":c60,
                    "same_verified_index":(bool(VERIFIED_INDEX.get(a)) and
                                            VERIFIED_INDEX.get(a)==VERIFIED_INDEX.get(b))})
    result["pairwise_extremes"].sort(key=lambda a:a["corr_5d_120"],reverse=True)
    result["category_total"]=len(result["categories"])
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf8")
    print(json.dumps({"status":"ok","qualified":len(codes),
            "categories":{k:{"n":v["n"],
                "clusters":{m:s["n"] for m,s in v["price_clusters"].items()},
                "verified":v["verified_index_groups"],
                "unverified":v["unverified_index_count"],
                "corr":v["pair_correlation_summary"].get("corr5_120")}
                for k,v in result["categories"].items()}},ensure_ascii=False))

if __name__=="__main__":
    main()
