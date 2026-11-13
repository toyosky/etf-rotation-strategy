#!/usr/bin/env python3
"""Research-only 2021+ comparison: daily cross-sectional middle 40% vs own-history beta middle 40%."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
import audit_beta_historical_position_v1 as hist
import audit_top1_extreme_quality_v1 as base
SHA=hist.EXPECTED_SHA
def summary(g):
    if len(g)==0:return {"n":0}
    v=g.net10.dropna()
    return {"n":int(len(v)),"mean10_pct":round(100*float(v.mean()),3) if len(v) else None,"median10_pct":round(100*float(v.median()),3) if len(v) else None,"p10_pct":round(100*float(v.quantile(.1)),3) if len(v) else None,"win_pct":round(100*float((v>0).mean()),2) if len(v) else None,"funds":int(g.symbol.nunique())}
def pick(g):return base.rank_top(g)
def evaluate(d):
    pool,_=base.pools(d)
    p=pool["EXACT_PRE"].copy()
    p=p.loc[(p.date>=pd.Timestamp("2021-01-01"))&p.net10.notna()].copy()
    p["cross_pct"]=p.groupby("date").slope.rank(pct=True,method="average")*100
    p["cross_n"]=p.groupby("date").symbol.transform("size")
    # Historical position based only on previous observations for that symbol.
    groups={"original_top1":p,"cross_section_middle40":p.loc[(p.cross_n>=5)&p.cross_pct.ge(30)&p.cross_pct.le(70)],"historical_middle40":p.loc[p.beta_pct252.ge(30)&p.beta_pct252.le(70)]}
    selected={k:pick(v) for k,v in groups.items()}
    result={"contract":"ETF_MIDDLE40_TWO_DEFINITIONS_V1","source_sha":SHA,
      "caveats":["Retrospective 2026 taxonomy not historical PIT","10d overlapping event outcomes not investable NAV","Cross-sectional rank among same-day eligible deduplicated candidates, min 5","Historical percentile from previous 126-252 observed betas, today excluded","Middle40=30th through 70th percentile inclusive","Selection within middle40 uses highest beta; signal close then next open, exit 11th open, 6bp each side","Missing eligible middle40 dates are not zero-return days; paired dates reported"],
      "universe":{"days":int(p.date.nunique()),"symbols":int(p.symbol.nunique()),"daily_candidates_mean":round(float(p.groupby("date").size().mean()),2)},
      "strategies":{},"paired_vs_top1":{}}
    orig=selected["original_top1"].set_index("date")
    for name,s in selected.items():
        result["strategies"][name]={"all":summary(s),"by_year":{str(y):summary(z) for y,z in s.groupby(s.date.dt.year)}}
        if name=="original_top1":continue
        joined=orig[["symbol","net10"]].join(s.set_index("date")[["symbol","net10"]],how="inner",rsuffix="_alternative").dropna()
        diff=100*(joined.net10_alternative-joined.net10)
        month=diff.groupby(diff.index.to_period("M"))
        sums=month.sum().to_numpy(float);ns=month.size().to_numpy(int)
        if len(sums):
            rng=np.random.default_rng(20261113)
            ix=rng.integers(0,len(sums),size=(2000,len(sums)))
            ci=np.quantile(sums[ix].sum(axis=1)/ns[ix].sum(axis=1),[.025,.975])
        else:ci=[float("nan")]*2
        result["paired_vs_top1"][name]={"matched_days":len(joined),"changed_days":int((joined.symbol!=joined.symbol_alternative).sum()),"delta_pp":round(float(diff.mean()),3) if len(diff) else None,"month_block_ci95_pp":[round(float(x),3) for x in ci],"by_year":{str(y):{"n":len(z),"delta_pp":round(float((z.net10_alternative-z.net10).mean()*100),3)} for y,z in joined.groupby(joined.index.year)}}
    return result
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--self-test",action="store_true")
    ap.add_argument("--bars",type=Path)
    ap.add_argument("--taxonomy",type=Path)
    ap.add_argument("--output",type=Path,default=Path("research/taxonomy_v3/output_v32/middle40_two_definitions_v1.json"))
    a=ap.parse_args()
    if a.self_test:
        q=pd.DataFrame({"date":pd.to_datetime(["2021-01-01"]*5),"symbol":list("abcde"),"slope":[1,2,3,4,5],"net10":[0,.01,.02,.03,.04],"beta_pct252":[40]*5,"r2":[.6]*5,"prior_amount":[2e7]*5})
        q["cross_pct"]=q.groupby("date").slope.rank(pct=True)*100
        assert q.loc[q.cross_pct.between(30,70)].symbol.tolist()==["b","c"]
        print("SELF_TEST_PASS");return
    sha=hashlib.sha256(a.bars.read_bytes()).hexdigest()
    if sha!=SHA:raise RuntimeError("Archive hash mismatch "+sha)
    bars=pd.read_parquet(a.bars,columns=["symbol","date","open","high","low","close","amount"])
    tax=pd.read_parquet(a.taxonomy)
    daily,_=base.qualified_daily(bars,tax)
    daily=hist.features(daily)
    res=evaluate(daily)
    res["as_of"]=str(pd.to_datetime(bars.date).max().date())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(res,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    a.output.with_suffix(".md").write_text("# 2021—2026 β中间40%两种定义回测\n\n研究用途，非PIT或完整资金净值回测。\n\n"+json.dumps(res,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(res,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
