#!/usr/bin/env python3
"""As-of historical percentile and price-path audit for ETF OLS Top1; research only."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
import audit_top1_extreme_quality_v1 as base

EXPECTED_SHA="7a218407280309b475998668ccd3d232cfc67efda307f97db3f76fef7324b644"
SEED=20261113

def features(d):
    d=d.sort_values(["symbol","date"]).copy()
    g=d.groupby("symbol",sort=False)
    for lag in (3,5,10):
        d[f"beta_delta{lag}"]=d.slope-g.slope.shift(lag)
    # Strictly prior observations: today is excluded from the reference distribution.
    def pct(x):
        a=x.to_numpy(float)
        out=np.full(len(a),np.nan)
        for i in range(126,len(a)):
            history=a[max(0,i-252):i]
            history=history[np.isfinite(history)]
            if len(history)>=126 and np.isfinite(a[i]):
                out[i]=100*(np.sum(history<a[i])+.5*np.sum(history==a[i]))/len(history)
        return pd.Series(out,index=x.index)
    d["beta_pct252"]=g.slope.transform(pct)
    d["beta_pct126"]=g.slope.transform(lambda x: x.shift(1).rolling(126,min_periods=126).apply(
        lambda a: np.nan,raw=True)) if False else np.nan
    return d

def add_prices(d,bars):
    b=bars[["symbol","date","close"]].copy()
    b.symbol=b.symbol.astype(str).str.zfill(6)
    b.date=pd.to_datetime(b.date).dt.normalize()
    b=b.sort_values(["symbol","date"])
    g=b.groupby("symbol",sort=False)
    for n in (5,10,26):
        b[f"ret{n}"]=b.close/g.close.shift(n)-1
    b["drawdown60"]=b.close/g.close.transform(lambda s:s.shift(1).rolling(60,min_periods=40).max())-1
    b["low60"]=g.close.transform(lambda s:s.shift(1).rolling(60,min_periods=40).min())
    b["rebound_from_low60"]=b.close/b.low60-1
    b["deviation26"]=b.close/g.close.transform(lambda s:s.rolling(26,min_periods=26).mean())-1
    cols=["symbol","date","ret5","ret10","ret26","drawdown60","rebound_from_low60","deviation26"]
    return d.merge(b[cols],on=["symbol","date"],how="left",validate="one_to_one")

def bootstrap_diff(x,flag):
    x=x.loc[x.net10.notna()&x[flag].notna()].copy()
    if x.empty:return {}
    a=x.loc[x[flag]].net10; b=x.loc[~x[flag]].net10
    if len(a)<5 or len(b)<5:return {"n_high":len(a),"n_low":len(b),"insufficient":True}
    x["month"]=x.date.dt.to_period("M")
    months=[z for _,z in x.groupby("month")]
    rng=np.random.default_rng(SEED)
    values=[]
    for _ in range(2000):
        sample=pd.concat([months[j] for j in rng.integers(0,len(months),len(months))])
        h=sample.loc[sample[flag]].net10;l=sample.loc[~sample[flag]].net10
        if len(h) and len(l):values.append(100*(h.mean()-l.mean()))
    return {"n_high":len(a),"n_low":len(b),"high_mean_pct":round(100*a.mean(),3),
      "low_mean_pct":round(100*b.mean(),3),"difference_pp":round(100*(a.mean()-b.mean()),3),
      "month_block_ci95_pp":[round(v,3) for v in np.quantile(values,[.025,.975])]}

def summarize(x):
    return {"n":len(x),"mean10_pct":round(100*x.net10.mean(),3),
            "p10_pct":round(100*x.net10.quantile(.1),3),
            "win_pct":round(100*(x.net10>0).mean(),2)}

def analyze(d):
    variants,_=base.pools(d)
    top=base.rank_top(variants["EXACT_PRE"])
    top=top.loc[(top.date>=pd.Timestamp("2021-01-01"))&top.net10.notna()].copy()
    top["pct95"]=top.beta_pct252>=95
    top["pct90"]=top.beta_pct252>=90
    top["burst5"]=top.ret5>=.10
    top["prior_deep"]=top.drawdown60<=-.15
    top["decelerating"]=top.beta_delta5<0
    top["high_and_burst"]=top.pct90&top.burst5
    top["high_and_decelerating"]=top.pct90&top.decelerating
    top["high_and_deep"]=top.pct90&top.prior_deep
    top["year"]=top.date.dt.year
    out={"contract":"ETF_TOP1_BETA_HISTORICAL_POSITION_V1",
      "notes":["Static 2026 taxonomy is NOT PIT","252 trailing observed beta values, current excluded; minimum 126","Returns are overlapping 10d event outcomes, not portfolio NAV","Signal date close; next open to day11 open; costs inherited from base","Predefined descriptive cuts are not optimized trading thresholds"],
      "sample":{"top1_dates":len(top),"with_percentile":int(top.beta_pct252.notna().sum()),"first_date":str(top.date.min().date()),"last_date":str(top.date.max().date())},
      "year":{str(y):{**summarize(z),"with_percentile":int(z.beta_pct252.notna().sum()),"unique_funds":int(z.symbol.nunique()),"unique_indices":int(z.exact_key.nunique())} for y,z in top.groupby("year")},
      "percentile_buckets":{},"conditional":{},"paired_filter":{}}
    valid=top.loc[top.beta_pct252.notna()].copy()
    valid["bucket"]=pd.cut(valid.beta_pct252,[-.001,50,80,90,95,100.001],labels=["0-50","50-80","80-90","90-95","95-100"])
    for (year,bucket),z in valid.groupby(["year","bucket"],observed=True):
        out["percentile_buckets"][f"{year}:{bucket}"]=summarize(z)
    for flag in ["pct95","pct90","burst5","prior_deep","decelerating","high_and_burst","high_and_decelerating","high_and_deep"]:
        out["conditional"][flag]=bootstrap_diff(valid,flag)
        out["conditional"][flag]["by_year"]={str(y):bootstrap_diff(z,flag) for y,z in valid.groupby("year")}
    # Actual same-day Top1 replacement, not a comparison of survivors alone.
    for flag in ["pct95","high_and_burst","high_and_decelerating","high_and_deep"]:
        banned=valid.loc[valid[flag],["date","symbol"]]
        candidate=variants["EXACT_PRE"].merge(banned.assign(ban=True),on=["date","symbol"],how="left")
        alt=base.rank_top(candidate.loc[candidate.ban!=True]).set_index("date")
        common=valid.set_index("date")[["symbol","net10"]].join(alt[["symbol","net10"]],rsuffix="_alt",how="inner").dropna()
        diff=100*(common.net10_alt-common.net10)
        out["paired_filter"][flag]={"matched_dates":len(common),
          "changed_dates":int((common.symbol!=common.symbol_alt).sum()),
          "mean_delta_pp":round(float(diff.mean()),3) if len(diff) else None,
          "warning":"Only high-percentile Top1 dates eligible for flag; all candidate rows retained otherwise; candidate ban applied per date"}
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--bars",type=Path)
    p.add_argument("--taxonomy",type=Path)
    p.add_argument("--output",type=Path,default=Path("research/taxonomy_v3/output_v32/beta_historical_position_v1.json"))
    a=p.parse_args()
    if a.self_test:
        q=pd.DataFrame({"symbol":["a"]*140,"date":pd.date_range("2020-01-01",periods=140),"slope":np.arange(140,dtype=float)})
        z=features(q)
        assert pd.isna(z.beta_pct252.iloc[125]) and z.beta_pct252.iloc[139]==100
        print("SELF_TEST_PASS");return
    sha=hashlib.sha256(a.bars.read_bytes()).hexdigest()
    if sha!=EXPECTED_SHA:raise RuntimeError(f"Archive SHA mismatch actual={sha} expected={EXPECTED_SHA}")
    bars=pd.read_parquet(a.bars,columns=["symbol","date","open","high","low","close","amount"])
    tax=pd.read_parquet(a.taxonomy)
    daily,_=base.qualified_daily(bars,tax)
    result=analyze(add_prices(features(daily),bars))
    result["source"]={"sha256":sha,"as_of":str(pd.to_datetime(bars.date).max().date()),"taxonomy_pit":False}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    report=a.output.with_suffix(".md")
    lines=["# β历史位置与价格路径：独立审计V1","","数据SHA: "+sha,"历史分类非PIT；后10日收益重叠，非实际组合回测。","","## 样本",json.dumps(result["sample"],ensure_ascii=False),"","## 全部年份Top1样本覆盖",json.dumps(result["year"],ensure_ascii=False,indent=2),"","## 分年历史β分位",json.dumps(result["percentile_buckets"],ensure_ascii=False,indent=2),"","## 价格路径条件和月份区块区间",json.dumps(result["conditional"],ensure_ascii=False,indent=2),"","## Top1候选更换",json.dumps(result["paired_filter"],ensure_ascii=False,indent=2)]
    report.write_text("\n".join(lines)+"\n")
    print("AUDIT_PASS",json.dumps(result["sample"]))
if __name__=="__main__":main()
