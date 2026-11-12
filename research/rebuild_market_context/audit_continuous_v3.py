#!/usr/bin/env python3
"""V3 research: continuous/dynamic ETF rebuild context validation.

The unit of independent market context is a trade date, not an ETF event.
All feature construction uses prior/current close; target is future next-open
to open 10-session return. Historical index classification not yet PIT.
Research-only: no live signal changes, no website updates.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

import compute_indicators_v1 as v1
import audit_diffusion_v2 as v2

ASOF_TRAIN_END = pd.Timestamp("2025-01-01")
FEATURES = (
    ("rebuild_diffusion5_pct",10),
    ("diffusion_lag1_pct",10),
    ("diffusion_delta5_pp",10),
    ("trend_breadth15_pct",10),
    ("breadth_delta5_pp",10),
    ("persistence_d5_pct",10),
    ("sector_rs10_pp",1),
)
BANDS = [0,10,20,30,40,50,101]
REPS = 1600
SEED = 20261112


def enrich(reps, events, daily, sector, bars):
    ev,check=v2.attach_features(reps,daily,events,bars)
    s=sector[["date","region","sector","sector_rs10_pp","sector_strength_valid"]]
    ev=ev.merge(s,on=["date","region","sector"],how="left",validate="many_to_one")
    ev["sector_rs10_pp"]=ev.sector_rs10_pp.where(ev.sector_strength_valid==True)
    d=daily[["date","trend_breadth15_pct"]].copy().sort_values("date")
    d["breadth_delta5_pp"]=d.trend_breadth15_pct.diff(5)
    ev=ev.merge(d[["date","breadth_delta5_pp"]],on="date",how="left",validate="many_to_one")
    return ev,check


def day_frame(events):
    # Day-equal: one observation per trading date, all ETFs on the date get
    # equal weight inside the daily portfolio. Not a funded equity curve.
    day=(events.groupby("date",as_index=False)
         .agg(n=("symbol","count"),
              net10=("net10","mean"),
              excess_region10=("excess_region10","mean"),
              rebuild_diffusion5_pct=("rebuild_diffusion5_pct","first"),
              diffusion_lag1_pct=("diffusion_lag1_pct","first"),
              diffusion_delta5_pp=("diffusion_delta5_pp","first"),
              trend_breadth15_pct=("trend_breadth15_pct","first"),
              breadth_delta5_pp=("breadth_delta5_pp","first"),
              persistence_d5_pct=("persistence_d5_pct","first"),
              sector_rs10_pp=("sector_rs10_pp","mean"),
              market_ret10_past=("market_ret10_past","first"),
              price_ret10=("price_ret10","mean"),
              slope_delta=("slope_delta","mean"),
              cn_share=("region",lambda r:float((r=="CN").mean())),
              hk_share=("region",lambda r:float((r=="HK").mean())),
              market_amount60=("amount60","mean")))
    day["year"]=day.date.dt.year
    day["month"]=day.date.dt.strftime("%Y-%m")
    # These are observation-date only. Later OOS model fills using TRAIN means.
    return day


def stats(x,col):
    x=x[col].dropna().to_numpy(float)
    return {"n":len(x),"mean_pct":round(float(x.mean()*100),4) if len(x) else None,
            "median_pct":round(float(np.median(x)*100),4) if len(x) else None,
            "win_pct":round(float(np.mean(x>0)*100),2) if len(x) else None}


def bands(train,test,raw_test):
    result=[]
    for l,r in zip(BANDS[:-1],BANDS[1:]):
        d=test.loc[(test.rebuild_diffusion5_pct>=l)&(test.rebuild_diffusion5_pct<r)]
        e=raw_test.loc[(raw_test.rebuild_diffusion5_pct>=l)&(raw_test.rebuild_diffusion5_pct<r)]
        t=train.loc[(train.rebuild_diffusion5_pct>=l)&(train.rebuild_diffusion5_pct<r)]
        result.append({
            "range_pct":f"[{l},{r if r!=101 else 100}{')' if r!=101 else ']'}",
            "training_days":int(len(t)),
            "validation_days":int(len(d)),
            "validation_events":int(len(e)),
            "validation_net10_day_equal":stats(d,"net10"),
            "validation_excess10_day_equal":stats(d,"excess_region10"),
            "validation_2025":stats(d.loc[d.year==2025],"excess_region10"),
            "validation_2026":stats(d.loc[d.year==2026],"excess_region10"),
        })
    return result


def standardized(df,col,standard,extra_square=False):
    lo,hi,mu,sd=standard[col]
    v=df[col].astype(float).fillna(mu).clip(lo,hi).to_numpy()
    return (v-mu)/sd


def fit_standard(train, features):
    out={}
    for col in features:
        x=train[col].dropna().to_numpy(float)
        if len(x)<30:raise RuntimeError(f"Training insufficient: {col}={len(x)}")
        lo,hi=np.quantile(x,[.01,.99])
        z=np.clip(x,lo,hi)
        mu=float(np.mean(z));sd=float(np.std(z)) or 1
        out[col]=(float(lo),float(hi),mu,sd)
    return out


def design(df,features,standard):
    parts=[np.ones(len(df))]
    for col in features:
        parts.append(standardized(df,col,standard))
    return np.column_stack(parts)


def train_model(train,test,cols,standard,lam=5):
    x=design(train,cols,standard)
    y=train.excess_region10.to_numpy(float)*100
    xv=design(test,cols,standard)
    z=test.excess_region10.to_numpy(float)*100
    penalty=np.eye(len(cols)+1)*lam
    penalty[0,0]=0
    weights=np.linalg.solve(x.T@x+penalty,x.T@y)
    predict=xv@weights
    base=float(np.mean(y))
    def measures(actual,pred):
        return {
            "rmse_pp":round(float(np.sqrt(np.mean((actual-pred)**2))),5),
            "mae_pp":round(float(np.mean(np.abs(actual-pred))),5),
            "correlation":round(float(np.corrcoef(actual,pred)[0,1]),5)
                if np.std(pred)>1e-12 and np.std(actual)>1e-12 else None,
            "oos_r2_vs_train_mean":round(float(1-np.sum((actual-pred)**2)/np.sum((actual-base)**2)),5),
        }
    # standard deviation model fit by training only; no validation-based selection
    return {"full":measures(z,predict),"2025":measures(z[test.year==2025],predict[test.year==2025]),
            "2026":measures(z[test.year==2026],predict[test.year==2026]),
            "train_n":len(train),"validation_n":len(test),
            "coefficients":{v:round(float(w),5) for v,w in zip(["intercept"]+cols,weights)}}


def quantized_linear_fit(df, f, y, scale=10, controls=()):
    # y in pct points, f in original units/scale. OLS coefficient = y pp per
    # scale unit (10 percentage points of breadth/diffusion).
    clean=df.dropna(subset=[f,y,*controls])
    if len(clean)<20:return None
    x=np.column_stack([np.ones(len(clean)),
                       clean[f].to_numpy(float)/scale]+[clean[c].to_numpy(float) for c in controls])
    yy=clean[y].to_numpy(float)*100
    if np.linalg.matrix_rank(x)<x.shape[1]:return None
    beta=np.linalg.lstsq(x,yy,rcond=None)[0]
    return {"n_days":len(clean),"slope_pp_per_unit":round(float(beta[1]),5),
            "mean_x":round(float(clean[f].mean()),4)}


def slope_bootstrap(df,feature,outcome,controls=(),scale=10,reps=REPS,seed=SEED):
    z=df.dropna(subset=[feature,outcome,*controls]).copy()
    if len(z)<25:return {"n_days":len(z),"ci95_pp":None}
    z["mon"]=z.date.dt.strftime("%Y-%m")
    months=sorted(z.mon.unique())
    # Sufficient statistics allow exact block OLS without resampling raw events:
    # each month contributes X'X and X'Y; preserves within-month dependencies.
    gram=[];cross=[]
    for month in months:
        k=z.loc[z.mon==month]
        X=np.column_stack([np.ones(len(k)),k[feature].to_numpy(float)/scale]+
            [k[col].to_numpy(float) for col in controls])
        Y=k[outcome].to_numpy(float)*100
        gram.append(X.T@X)
        cross.append(X.T@Y)
    gram=np.stack(gram)
    cross=np.stack(cross)
    rng=np.random.default_rng(seed)
    result=[]
    for _ in range(reps):
        drawn=rng.integers(0,len(months),len(months))
        xx=gram[drawn].sum(axis=0)
        xy=cross[drawn].sum(axis=0)
        if np.linalg.matrix_rank(xx)==len(xx):
            result.append(float(np.linalg.solve(xx,xy)[1]))
    if not result:return {"n_days":len(z),"ci95_pp":None}
    return {"n_days":len(z),"months":len(months),
            "ci95_pp":[round(float(x),5) for x in np.quantile(result,[.025,.975])],
            "p_nonpositive":round(float(np.mean(np.asarray(result)<=0)),4),
            "valid_draws":len(result)}


def continuous(ev,train,test):
    controls=("trend_breadth15_pct","market_ret10_past","price_ret10")
    output={}
    for f,scale in FEATURES:
        out={"scale":scale,"train_nonnull":int(train[f].notna().sum()),
             "test_nonnull":int(test[f].notna().sum()),
             "training_range":[round(float(v),4) for v in train[f].quantile([.05,.5,.95])],
             "validation_range":[round(float(v),4) for v in test[f].quantile([.05,.5,.95])],
             "train":{},"validation":{},"by_year":{}}
        for label,dd in [("train",train),("validation",test),("2025",test.loc[test.year==2025]),("2026",test.loc[test.year==2026])]:
            sub={
             "raw_univariate":quantized_linear_fit(dd,f,"net10",scale),
             "excess_univariate":quantized_linear_fit(dd,f,"excess_region10",scale),
             "excess_adjusted":quantized_linear_fit(dd,f,"excess_region10",scale,controls),
            }
            if label=="train":out["train"]=sub
            elif label=="validation":out["validation"]=sub
            else:out["by_year"][label]=sub
        out["month_bootstrap"]={
            "excess_univariate":slope_bootstrap(test,f,"excess_region10",scale=scale),
            "excess_adjusted":slope_bootstrap(test,f,"excess_region10",controls,scale)
        }
        output[f]=out
    return output


def compare_models(train,test):
    # Freeze all transforms on 2021-24 to prevent validating on a trained look.
    base=["trend_breadth15_pct","market_ret10_past","price_ret10",
          "slope_delta","persistence_d5_pct","cn_share","hk_share"]
    candidates={
       "00_baseline_constant":[],
       "01_market_price_controls":base,
       "02_plus_diffusion_level":base+["rebuild_diffusion5_pct"],
       "03_plus_diffusion_velocity":base+["diffusion_delta5_pp"],
       "04_plus_breadth_velocity":base+["breadth_delta5_pp"],
       "05_level_and_velocity":base+["rebuild_diffusion5_pct","diffusion_delta5_pp"],
       "06_lagged_diffusion_and_velocity":base+["diffusion_lag1_pct","diffusion_delta5_pp"],
       "07_all_context":base+["rebuild_diffusion5_pct","diffusion_delta5_pp","breadth_delta5_pp"],
    }
    standards=fit_standard(train,sorted(set(sum(candidates.values(),[]))))
    r={}
    for key,features in candidates.items():
        if not features:
            tr_mean=float(train.excess_region10.mean()*100)
            row={"train_n":len(train),"validation_n":len(test)}
            for label,dd in [("full",test),("2025",test.loc[test.year==2025]),("2026",test.loc[test.year==2026])]:
                zz=dd.excess_region10.to_numpy(float)*100
                mse=float(np.mean((zz-tr_mean)**2))
                row[label]={"rmse_pp":round(float(np.sqrt(mse)),5),
                            "mae_pp":round(float(np.mean(np.abs(zz-tr_mean))),5),
                            "oos_r2_vs_train_mean":0.0,"correlation":None}
            r[key]=row
        else:r[key]=train_model(train,test,features,standards)
    return r


def nonlinear(train,test):
    # Predefined quadratic term (no OOS knot tuning), standardized using TRAIN.
    base=["trend_breadth15_pct","market_ret10_past","price_ret10","slope_delta",
          "persistence_d5_pct","cn_share","hk_share"]
    f="rebuild_diffusion5_pct"
    std=fit_standard(train,base+[f])
    x=standardized(train,f,std)
    xt=standardized(test,f,std)
    mean_square=float(np.mean(x*x))
    tr=train.copy();te=test.copy()
    tr["diffusion_square"]=x*x-mean_square
    te["diffusion_square"]=xt*xt-mean_square
    std["diffusion_square"]=(-10000.,10000.,0.,1.)
    linear=train_model(tr,te,base+[f],std)
    quadratic=train_model(tr,te,base+[f,"diffusion_square"],std)
    return {"linear":linear,"quadratic":quadratic,
            "delta_rmse_pp":round(linear["full"]["rmse_pp"]-quadratic["full"]["rmse_pp"],5),
            "quadratic_coef":quadratic["coefficients"]["diffusion_square"],
            "basis":"(diffusion_standardized_on_train)**2 minus train mean squared; frozen before validation"}


def main():
    pa=argparse.ArgumentParser()
    pa.add_argument("--parquet",required=True)
    pa.add_argument("--output",default="research/rebuild_market_context/continuous_factor_audit_v3.json")
    pa.add_argument("--markdown",default="research/rebuild_market_context/continuous_factor_audit_v3.md")
    args=pa.parse_args()
    source=Path(args.parquet)
    metadata=v1.metadata(os.getenv("ETF_DAILY_BARS_DATABASE_URL",""))
    bars,source_info=v1.prepare(source,metadata)
    reps,events,quality=v1.build_representatives(bars,metadata)
    daily,sector=v1.context_daily(reps,events)
    ev,checks=enrich(reps,events,daily,sector,bars)
    d=day_frame(ev)
    train=d.loc[d.date<ASOF_TRAIN_END].copy()
    test=d.loc[d.date>=ASOF_TRAIN_END].copy()
    etest=ev.loc[ev.date>=ASOF_TRAIN_END]
    if len(ev)!=3511 or len(etest)!=1474:raise RuntimeError("V1 event cohort mismatch")
    output={
     "contract":"ETF_REBUILD_MARKET_CONTINUOUS_V3_RESEARCH_ONLY",
     "source":source_info,
     "quality":quality,
     "checks":checks,
     "date_counts":{"train_days":len(train),"train_events":int(train.n.sum()),
       "test_days":len(test),"test_events":int(test.n.sum()),
       "test_months":int(test.month.nunique()),
       "test_2025_days":int(sum(test.year==2025)),
       "test_2026_days":int(sum(test.year==2026))},
     "definitions":{
       "outcome_raw":"Mean next-open to 10-session open gross multiplied by 0.9994^2 per event, averaged equally per date",
       "outcome_excess":"Same event return less contemporaneous same-region representative ETF median net return; day-equal, post-hoc",
       "diffusion_level":"15-day qualified rebuilding themes in rolling 5 sessions as percent of currently eligible themes",
       "diffusion_delta5_pp":"Diffusion today minus diffusion 5 market sessions ago, in percentage points",
       "breadth_delta5_pp":"Positive 15-day OLS ratio today minus 5 market sessions ago, in percentage points",
       "unit":"Coefficient is future 10-session outcome in percentage points per given feature scale; controlled effect is association, not causal",
       "controls":"Trend breadth, same-day past 10-session market ETF median return, event own past 10-session return; time-split 2021-24 and 2025-26",
       "cluster":"Months resampled, preserving all signal-day correlated events and return overlap",
       "time_varying_universe":"Eligibility requires 200 prior prices, 60-session >=3m amount, no zero volume, current-taxonomy proxy grouping"
     },
     "bands_out_of_sample":bands(train,test,etest),
     "continuous_day_equal":continuous(ev,train,test),
     "out_of_sample_models":compare_models(train,test),
     "nonlinear_oos_check":nonlinear(train,test),
     "caveats":[
       "Current classifications underlie proxy grouping; 2021-2025 taxonomy not point-in-time; incomplete delisted instruments.",
       "Using a cross-sectional future median as a reference outcome is not a realistic investable strategy benchmark.",
       "Same-date events are correlated, and 10-session holding periods overlap; daily results have month-block bootstrap only.",
       "Continuous linear slopes can be misleading if dose response is nonlinear; bands and OOS quadratic sensitivity must be consulted.",
       "This is signal-event evaluation with next-session open, not a fully-funded portfolio. No historical QDII/LOF premium or intraday veto.",
       "Multiple features and variants tested retrospectively; select new rules only after a fresh walk-forward period."
     ]
    }
    # Simple quadratic sensitivity after linear factor check.
    # All hyperparameters frozen; validation results not used to tune them.
    # Will be added after computing the separately standardized test basis.
    pp=Path(args.output);pp.parent.mkdir(parents=True,exist_ok=True)
    pp.write_text(json.dumps(output,ensure_ascii=False,indent=2,default=str,allow_nan=False),encoding="utf-8")
    lines=["# 重建环境指标连续量化研究 V3","",
           f"来源：{source_info['as_of']}，全市场 {source_info['raw_symbols']} ETF/LOF 归档代码。",
           f"时间切分：训练期 {len(train)} 信号日、验证期 {len(test)} 信号日；后者含 {int(test.n.sum())} 次重建事件。",
           "",
           "## 完整固定区间的扩散率剂量响应（按信号交易日等权）","",
           "| 扩散率 | 验证天数 | 事件数 | 10日净收益 | 10日地区超额 | 2025超额 | 2026超额 |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for b in output["bands_out_of_sample"]:
        def fm(s):return "—" if s["mean_pct"] is None else f"{s['mean_pct']:+.3f}%"
        lines.append(f"| {b['range_pct']} | {b['validation_days']} | {b['validation_events']} | {fm(b['validation_net10_day_equal'])} | {fm(b['validation_excess10_day_equal'])} | {fm(b['validation_2025'])} | {fm(b['validation_2026'])} |")
    lines+=["","## 连续量回归：每单位变化，对10日地区超额收益的关联","",
            "| 因子 | 单位 | 训练原始 | 验证原始 | 验证控制后 | 验证控制后月度95%区间 |",
            "|---|---:|---:|---:|---:|---:|"]
    for f,scale in FEATURES:
        row=output["continuous_day_equal"][f]
        def val(x):return f"{x['slope_pp_per_unit']:+.4f}" if x else "—"
        rng=row["month_bootstrap"]["excess_adjusted"]["ci95_pp"]
        rng_str="—" if rng is None else f"[{rng[0]:+.3f}, {rng[1]:+.3f}]"
        lines.append(f"| {f} | {scale} | {val(row['train']['excess_univariate'])} | {val(row['validation']['excess_univariate'])} | {val(row['validation']['excess_adjusted'])} | {rng_str} |")
    lines+=["","## 冻结模型的 2025–2026 样本外均方根误差","",
            "| 模型 | RMSE pp | OOS R²（对训练均值） |",
            "|---|---:|---:|"]
    for name,row in output["out_of_sample_models"].items():
        lines.append(f"| {name} | {row['full']['rmse_pp']:.4f} | {row['full']['oos_r2_vs_train_mean']:+.4f} |")
    lines+=["","## 非线性（冻结二次项，训练后样本外）","",
      "线性模型 RMSE: "+str(output["nonlinear_oos_check"]["linear"]["full"]["rmse_pp"])+
      " pp；加入二次项: "+str(output["nonlinear_oos_check"]["quadratic"]["full"]["rmse_pp"])+" pp。",
      "","## 局限","",*["- "+x for x in output["caveats"]]]
    m=Path(args.markdown);m.parent.mkdir(parents=True,exist_ok=True);m.write_text("\n".join(lines),encoding="utf-8")
    primary={f:{"validation_univ":v["validation"]["excess_univariate"],
                 "validation_adjusted":v["validation"]["excess_adjusted"],
                 "bootstrap_adjusted":v["month_bootstrap"]["excess_adjusted"]}
              for f,v in output["continuous_day_equal"].items()}
    print("CONTINUOUS_V3_COMPLETE "+json.dumps({
      "dates":output["date_counts"],"bins":output["bands_out_of_sample"],
      "coefficients":primary,
      "models":{name:{"rmse":m["full"]["rmse_pp"],"oosr2":m["full"]["oos_r2_vs_train_mean"]}
                for name,m in output["out_of_sample_models"].items()}
    },ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
