#!/usr/bin/env python3
"""Audit whether ETF rebuild diffusion predicts tradable returns beyond regime.

Research-only. Reuses frozen V1 events, and never changes production signals.
Core independent units: DAY/MONTH (diffusion is shared by same-day events).
2021-2024 training cutoffs; 2025-2026 validation. Historical taxonomy not PIT.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

import compute_indicators_v1 as base

START_TEST = pd.Timestamp("2025-01-01")
SPLICE_A = pd.Timestamp("2026-06-01")
SPLICE_B = pd.Timestamp("2026-09-01")
RNG_SEED = 20261112
BOOT_REPS = 2500
FEATURES = (
    "rebuild_diffusion5_pct",
    "diffusion_lag1_pct",
    "diffusion_peer_ex_sector_pct",
)
OUTCOMES = ("net10", "excess_region10")


def stats(x:pd.DataFrame,outcome:str="net10",mode:str="event") -> dict:
    if x.empty:return {"n":0, "days":0}
    a=x.groupby("date")[outcome].mean() if mode=="day" else x[outcome]
    a=a.dropna()
    if a.empty:return {"n":len(x),"days":x.date.nunique(),"mean_pct":None}
    return {
      "n":int(len(x)), "days":int(x.date.nunique()),
      "mean_pct":round(float(a.mean()*100),4),
      "median_pct":round(float(a.median()*100),4),
      "win_pct":round(float((a>0).mean()*100),2)
    }


def delta(x:pd.DataFrame,feature:str,lo:float,hi:float,
          outcome:str="net10",mode:str="event") -> dict:
    high=x.loc[x[feature]>=hi]
    low=x.loc[x[feature]<=lo]
    H=stats(high,outcome,mode)
    L=stats(low,outcome,mode)
    gap=(H.get("mean_pct")-L.get("mean_pct")) if H.get("mean_pct") is not None and L.get("mean_pct") is not None else None
    return {"high":H, "low":L, "diff_pp":round(gap,4) if gap is not None else None}


def bootstrap_months(x:pd.DataFrame,feature:str,lo:float,hi:float,outcome:str,mode:str,seed:int=RNG_SEED) -> dict:
    # Resample entire calendar months; each observation in the same month stays together.
    y=x.loc[(x[feature]>=hi)|(x[feature]<=lo)].copy()
    y["band"]=np.where(y[feature]>=hi,"high","low")
    if mode=="day":
        y=(y.groupby(["date","band"],as_index=False)[outcome].mean())
    if y.empty:return {"months":0,"valid_replicates":0}
    y["month"]=y.date.dt.strftime("%Y-%m")
    months=sorted(y.month.unique())
    lookup=y.groupby(["month","band"])[outcome].agg(["sum","count"])
    agg=np.zeros((len(months),2,2))
    for idx,m in enumerate(months):
        for j,band in enumerate(("high","low")):
            if (m,band) in lookup.index:
                row=lookup.loc[(m,band)]
                agg[idx,j]=[float(row["sum"]),float(row["count"])]
    rng=np.random.default_rng(seed)
    draws=rng.integers(0,len(months),(BOOT_REPS,len(months)))
    sampled=agg[draws].sum(axis=1)
    good=(sampled[:,0,1]>0)&(sampled[:,1,1]>0)
    dif=100*(sampled[good,0,0]/sampled[good,0,1]-sampled[good,1,0]/sampled[good,1,1])
    return {
       "months":len(months),"replicates":BOOT_REPS,
       "valid_replicates":len(dif),
       "ci95_diff_pp":[round(float(v),4) for v in np.quantile(dif,[.025,.975])] if len(dif) else None,
       "p_boot_diff_nonpositive":round(float((dif<=0).mean()),4) if len(dif) else None
    }


def add_market_adjusted_returns(bars:pd.DataFrame,reps:pd.DataFrame,ev:pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    # All price targets are for identical future open-to-open holding periods.
    # Cross-sectional regional median is a post-hoc explanatory benchmark,
    # not a fully investable rebalanced portfolio.
    b=bars.sort_values(["symbol","date"])[["symbol","date","open"]].copy()
    b["next_open"]=b.groupby("symbol").open.shift(-1)
    b["exit_open"]=b.groupby("symbol").open.shift(-11)
    b["fwd10_gross"]=b.exit_open/b.next_open-1
    b=b[["symbol","date","fwd10_gross"]]
    rs=reps[["date","region","key","symbol"]].merge(b,on=["date","symbol"],how="left",validate="one_to_one")
    regional=(rs.groupby(["date","region"],as_index=False)
               .agg(region_forward10_gross=("fwd10_gross","median"),
                    region_proxy_count=("fwd10_gross","count")))
    regional["region_forward10_net"]=regional.region_forward10_gross-(2*base.COST_SIDE)
    e=ev.merge(regional,on=["date","region"],how="left",validate="many_to_one")
    e["excess_region10"]=e.net10-e.region_forward10_net
    e["region_market10_past"]=e.merge(reps.groupby(["date","region"],as_index=False)
                         .ret10.median().rename(columns={"ret10":"reg_past"}),on=["date","region"],how="left")["reg_past"].to_numpy()
    return e,regional


def attach_features(reps:pd.DataFrame,daily:pd.DataFrame,events:pd.DataFrame,bars:pd.DataFrame) -> tuple[pd.DataFrame,dict]:
    d=daily.copy().sort_values("date")
    d["diffusion_lag1_pct"]=d.rebuild_diffusion5_pct.shift(1)
    d["market_ret10_past"]=d.date.map(reps.groupby("date").ret10.median())
    d["diffusion_delta5_pp"]=d.rebuild_diffusion5_pct-d.rebuild_diffusion5_pct.shift(5)
    # Reconstruct V1 rolling signal states once, to exclude entire target SECTOR
    # from the diffusion numerator/denominator. Also guard against self-inclusion.
    market_days=pd.DatetimeIndex(sorted(reps.date.unique()),name="date")
    eligible=reps[["date","key","sector"]].drop_duplicates(["date","key"])
    signal=events[["date","key"]].assign(new=1).pivot(index="date",columns="key",values="new")
    signal=signal.reindex(index=market_days,columns=sorted(reps.key.unique())).fillna(0)
    recent5=(signal.rolling(5,min_periods=1).max()
                 .stack().rename("recent5").reset_index())
    recent5.columns=["date","key","recent5"]
    z=eligible.merge(recent5,on=["date","key"],how="left",validate="one_to_one")
    s=(z.groupby(["date","sector"],as_index=False)
       .agg(sector_active=("key","size"),sector_recent5=("recent5","sum")))
    e=events.loc[events.net10.notna()].merge(
          d[["date","active_proxies","new_rebuild_5d","rebuild_diffusion5_pct",
             "diffusion_lag1_pct","trend_breadth15_pct","persistence_d5_pct",
             "market_ret10_past","diffusion_delta5_pp"]],on="date",how="left",validate="many_to_one")
    e=e.merge(s,on=["date","sector"],how="left",validate="many_to_one")
    denom=e.active_proxies-e.sector_active
    e["diffusion_peer_ex_sector_pct"]=np.where(denom>0,
         100*(e.new_rebuild_5d-e.sector_recent5)/denom,np.nan)
    e,regional=add_market_adjusted_returns(bars,reps,e)
    # Baseline same-day numbers must be identical to original V1.
    assert len(e)==3511,f"Original V1 cohort changed: {len(e)} != 3511"
    baseline=base.evaluate(daily,base.context_daily(reps,events)[1],events)["feature_tests"]["rebuild_diffusion5_pct"]
    assert abs(baseline["high_minus_low_net10_pp"]-1.8109)<1e-3
    assert e.diffusion_peer_ex_sector_pct.between(0,100).all()
    assert e.date.le(e.entry_date).all()
    assert e.date.lt(e.exit_date).all()
    return e,{"regional_benchmark_rows":len(regional),
              "regional_benchmark_missing":int(e.region_forward10_net.isna().sum()),
              "v1_reconciled_high_low_diff_pp":baseline["high_minus_low_net10_pp"],
              "peer_diffusion_definition":"Excludes ALL current-taxonomy groups in target sector, not only target ETF."}


def ridge_out_of_sample(ev:pd.DataFrame) -> dict:
    # Frozen prior feature list and ridge constant. No validation-set tuning.
    base_cols=["trend_breadth15_pct","market_ret10_past","region_market10_past",
               "price_ret10","slope_delta"]
    trial_cols=base_cols+["rebuild_diffusion5_pct"]
    train=ev.loc[ev.date<START_TEST].copy()
    test=ev.loc[ev.date>=START_TEST].copy()
    all_features=trial_cols
    transforms={}
    for f in all_features:
        s=train[f].dropna().astype(float)
        if len(s)<50:raise RuntimeError("Insufficient training observations "+f)
        lo,hi=s.quantile([.01,.99])
        y=s.clip(lo,hi)
        transforms[f]=(float(lo),float(hi),float(y.mean()),float(y.std(ddof=0)) or 1.)
    def design(x,features):
        n=len(x)
        cols=[np.ones(n)]
        for f in features:
            lo,hi,mu,sd=transforms[f]
            v=x[f].astype(float).fillna(mu).clip(lo,hi).to_numpy()
            cols.append((v-mu)/sd)
        # Region categorical controls are frozen, not fit after 2024.
        for region in ("CN","HK","US"):
            cols.append((x.region==region).astype(float).to_numpy())
        return np.column_stack(cols)
    out={}
    for label,features in [("without_diffusion",base_cols),("with_diffusion",trial_cols)]:
        X=design(train,features);Y=train.net10.to_numpy()*100
        xt=design(test,features);yt=test.net10.to_numpy()*100
        reg=np.eye(X.shape[1])*25
        reg[0,0]=0
        weights=np.linalg.solve(X.T@X+reg,X.T@Y)
        pred=xt@weights
        base_pred=np.full(len(yt),Y.mean())
        by_year={}
        for y,group in test.groupby(test.date.dt.year):
            ind=test.date.dt.year==y
            by_year[str(y)]={"n":int(ind.sum()),"rmse_pct":round(float(np.sqrt(np.mean((yt[ind]-pred[ind])**2))),4)}
        out[label]={
         "n_train":len(train),"n_test":len(test),
         "rmse_pct":round(float(np.sqrt(np.mean((yt-pred)**2))),4),
         "mae_pct":round(float(np.abs(yt-pred).mean()),4),
         "prediction_corr":round(float(np.corrcoef(pred,yt)[0,1]),4),
         "baseline_mean_prediction_rmse_pct":round(float(np.sqrt(np.mean((yt-base_pred)**2))),4),
         "year":by_year,
         "diffusion_coef_pp_per_train_sd":round(float(weights[features.index("rebuild_diffusion5_pct")+1]),4) if "rebuild_diffusion5_pct" in features else None
        }
    out["rmse_gain_pct"]=round(out["without_diffusion"]["rmse_pct"]-out["with_diffusion"]["rmse_pct"],5)
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--parquet",required=True)
    parser.add_argument("--out",default="research/rebuild_market_context/diffusion_deep_audit_v2.json")
    parser.add_argument("--md",default="research/rebuild_market_context/diffusion_deep_audit_v2.md")
    args=parser.parse_args()
    md=base.metadata(os.getenv("ETF_DAILY_BARS_DATABASE_URL",""))
    bars,source=base.prepare(Path(args.parquet),md)
    reps,events,qual=base.build_representatives(bars,md)
    daily,sector=base.context_daily(reps,events)
    ev,diagnostics=attach_features(reps,daily,events,bars)
    train=ev.loc[ev.date<START_TEST];test=ev.loc[ev.date>=START_TEST]
    results={}
    for f in FEATURES:
        lo,hi=train[f].quantile([.25,.75])
        if pd.isna(lo) or pd.isna(hi):raise RuntimeError("No train thresholds for "+f)
        feat={
          "train_q25":round(float(lo),5),"train_q75":round(float(hi),5),
          "train_nonnull":int(train[f].notna().sum()),
          "validation_nonnull":int(test[f].notna().sum()),
          "discovery_net10":delta(train,f,lo,hi),
          "validation_event_net10":delta(test,f,lo,hi),
          "validation_equal_day_net10":delta(test,f,lo,hi,mode="day"),
          "validation_excess_region":delta(test,f,lo,hi,outcome="excess_region10"),
          "validation_excess_equal_day":delta(test,f,lo,hi,outcome="excess_region10",mode="day"),
          "by_year":{},
          "by_region":{},
          "by_market_strata":{}
        }
        for year,t in test.groupby(test.date.dt.year):
            feat["by_year"][str(year)]={
             "event_net10":delta(t,f,lo,hi),
             "equal_day_net10":delta(t,f,lo,hi,mode="day"),
             "excess_region_net10":delta(t,f,lo,hi,outcome="excess_region10")
            }
        for region,t in test.groupby("region"):
            if len(t)>=50:
                feat["by_region"][region]={
                 "event_net10":delta(t,f,lo,hi),
                 "excess_region_net10":delta(t,f,lo,hi,outcome="excess_region10")
                }
        for control in ("trend_breadth15_pct","market_ret10_past","price_ret10"):
            cutoff=float(train[control].median())
            feat["by_market_strata"][control]={
             "frozen_train_median":round(cutoff,6),
             "lower":delta(test.loc[test[control]<cutoff],f,lo,hi),
             "upper":delta(test.loc[test[control]>=cutoff],f,lo,hi)
            }
        feat["exclude_2026_source_splice"]=delta(test.loc[(test.date<SPLICE_A)|(test.date>SPLICE_B)],f,lo,hi)
        feat["bootstrap_months"]={
           "raw_event_net10":bootstrap_months(test,f,lo,hi,"net10","event"),
           "equal_day_net10":bootstrap_months(test,f,lo,hi,"net10","day"),
           "raw_event_excess":bootstrap_months(test,f,lo,hi,"excess_region10","event"),
           "equal_day_excess":bootstrap_months(test,f,lo,hi,"excess_region10","day")
        }
        if f=="rebuild_diffusion5_pct":
            # Extra safety: verify train calibration appears in both years.
            ntest=feat["validation_event_net10"]
            assert ntest["high"]["n"]==396 and ntest["low"]["n"]==421,ntest
        results[f]=feat
    fit=ridge_out_of_sample(ev)
    # Price-relevant group target: compare high/low on each individual calendar month,
    # not count 396 events as statistically independent.
    monthly=(test.groupby("date",as_index=False)
        .agg(net10=("net10","mean"),
             diffusion=("rebuild_diffusion5_pct","first"),
             breadth=("trend_breadth15_pct","first"),
             n=("symbol","count")))
    monthly["month"]=monthly.date.dt.to_period("M").astype(str)
    date_table=monthly.groupby("month",as_index=False).agg(
        days=("date","count"),events=("n","sum"),
        mean_net10_pct=("net10",lambda x:float(x.mean()*100)),
        mean_diffusion_pct=("diffusion","mean"),
        mean_breadth_pct=("breadth","mean"))
    details={
      "contract":"DIFFUSION_DEEP_AUDIT_V2_RESEARCH_ONLY",
      "source":source,"cohort":qual,"diagnostics":diagnostics,
      "asof":source["as_of"],"train_n":len(train),"validation_n":len(test),
      "data_cut":"2021-2024 frozen thresholds / 2025-2026 out-of-sample",
      "features":results,
      "ridge_regional_market_controls":fit,
      "validation_monthly_day_equal":json.loads(date_table.to_json(orient="records",double_precision=6)),
      "limitations":[
       "Current (2026) taxonomy is not historical point-in-time: all proxy-level event counts are retrospective.",
       "ETF archive omits historical delisted/closed funds; 200-bar and 3M amount filters bias cohorts.",
       "Signals share a MARKET date: effective N is dates/months rather than 1,474 independent ETF events.",
       "Market-relative benchmark is post-hoc contemporaneous median of observed regional proxy carriers, not an investable index.",
       "No historical premium series or intraday next-open veto; open-to-open fixed 10 session period only.",
       "Multiplicative testing of 3 related features, control strata and periods means a few positive cells could be chance.",
       "Current-date new signal contributes to 5-day diffusion; lag-one-day and sector-excluded diffusion are separate sensitivity tests."
      ],
      "decision":"keep as research-only; do not feed into live purchases before stable economic alpha and PIT taxonomy."
    }
    p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(details,ensure_ascii=False,indent=2,allow_nan=False,default=str),encoding="utf8")
    doc=["# 重建扩散率：增量收益与稳健性审计 V2","",
         f"快照 {source['as_of']}；研究期事件 {len(train)}，验证期事件 {len(test)}。",
         "研究目的：检验扩散率是否提供超越市场涨跌和重建自身动量的未来净收益。",
         "",
         "## 时间样本外检验（2025–2026）","",
         "| 变量 | 验证原始高-低 pp | 日期等权高-低 pp | 地区相对收益高-低 pp | 地区超额日等权 pp |",
         "|---|---:|---:|---:|---:|"]
    for f,x in results.items():
        vals=[x[y]["diff_pp"] for y in ("validation_event_net10","validation_equal_day_net10","validation_excess_region","validation_excess_equal_day")]
        doc.append("| "+f+" | "+" | ".join("—" if v is None else f"{v:+.3f}" for v in vals)+" |")
    doc+=["","## 重建扩散率详情",""]
    f=results["rebuild_diffusion5_pct"]
    doc.append(f"训练阈值：P25={f['train_q25']}%，P75={f['train_q75']}%。")
    for yr,item in f["by_year"].items():
        doc.append(f"- {yr}: 事件平均高-低 {item['event_net10']['diff_pp']} pp；地区超额 {item['excess_region_net10']['diff_pp']} pp。")
    doc+=["","## 区块重抽样（同一个月视为整体）",""]
    for k,x in f["bootstrap_months"].items():
        doc.append(f"- {k}: {x.get('ci95_diff_pp')} pp；有效复制 {x.get('valid_replicates')}。")
    doc+=["","## 控制过去价格与市场宽度的 OOS 岭回归",""]
    doc.append(json.dumps(fit,ensure_ascii=False,indent=2))
    doc+=["","## 稳健性与边界","",*["- "+x for x in details["limitations"]]]
    m=Path(args.md);m.parent.mkdir(parents=True,exist_ok=True);m.write_text("\n".join(doc),encoding="utf8")
    print("DIFFUSION_V2_COMPLETE "+json.dumps({
      "asof":source["as_of"],"events":len(ev),"val_n":len(test),
      "primary":{k:{"validation":v["validation_event_net10"],"equal_day":v["validation_equal_day_net10"],
                    "excess":v["validation_excess_region"],"ci":v["bootstrap_months"]["equal_day_excess"]}
                 for k,v in results.items()},
      "ridge":fit,
      "file":str(p)
    },ensure_ascii=False,default=str),flush=True)


if __name__=="__main__":
    main()
