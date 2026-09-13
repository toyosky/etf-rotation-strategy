#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe.oracle_replacement_v1 import CASH_SIGNAL

FEATURES = [
    "active_share_t",
    "score_iqr_t",
    "prior20_switch_rate_t",
    "prior20_top1_tenure_t",
    "mean_pairwise_corr120_t",
]
MIN_TRAIN_MONTHS = 24


def stage1_pool_score(features: pd.DataFrame) -> pd.DataFrame:
    f = features.copy()
    f["date"] = pd.to_datetime(f["date"])
    f["symbol"] = f["symbol"].astype(str)
    active = ((f["annual"] > 0) & (f["r2"] > 0) & (f["score"] > 0)
              & (~f["recent_drop3"].fillna(False)))
    f["pool_score"] = f["score"].where(active)
    return f


def run_lengths(vals: list[str | None]) -> float:
    vals = [x for x in vals if x is not None]
    if not vals:
        return np.nan
    runs=[]; cur=vals[0]; n=1
    for x in vals[1:]:
        if x == cur: n += 1
        else: runs.append(n); cur=x; n=1
    runs.append(n)
    return float(np.mean(runs))


def build_month_state(snap: pd.DataFrame, bars: pd.DataFrame, f: pd.DataFrame) -> pd.DataFrame:
    calendar = pd.Index(sorted(pd.to_datetime(bars["date"].unique())))
    score = f.pivot(index="date", columns="symbol", values="pool_score").reindex(calendar)
    close = bars.pivot(index="date", columns="symbol", values="close").reindex(calendar)
    ret = close.pct_change(fill_method=None)
    rows=[]
    for month,g in snap.groupby("month", sort=True):
        prev = pd.Timestamp(g["prev_date"].iloc[0])
        pool = sorted(set(g["symbol"].astype(str)))
        if prev not in calendar or not pool:
            continue
        present=[s for s in pool if s in score.columns]
        if not present:
            continue
        s0=score.loc[prev,present]
        active=s0.dropna()
        active_share=float(active.size/len(present))
        score_iqr=float(active.quantile(.75)-active.quantile(.25)) if len(active)>=2 else 0.0
        p=calendar.get_loc(prev)
        hist20=calendar[max(0,p-19):p+1]
        ss=score.loc[hist20,present]
        ranked=[]
        for _,row in ss.iterrows():
            x=row.dropna()
            ranked.append(None if x.empty else str(x.idxmax()))
        switches=0; prev_t=None; obs=0
        for x in ranked:
            if x is not None: obs+=1
            if x != prev_t: switches += 1
            prev_t=x
        switch_rate=float(switches/max(1,obs))
        tenure=run_lengths(ranked)
        hist120=calendar[max(0,p-119):p+1]
        r=ret.loc[hist120,present]
        c=r.corr(min_periods=60)
        arr=c.to_numpy(float)
        if arr.shape[0] >= 2:
            tri=arr[np.triu_indices(arr.shape[0],1)]
            tri=tri[np.isfinite(tri)]
            mean_corr=float(np.mean(tri)) if len(tri) else np.nan
        else:
            mean_corr=np.nan
        rows.append({"month":str(month),"active_share_t":active_share,"score_iqr_t":score_iqr,
                     "prior20_switch_rate_t":switch_rate,"prior20_top1_tenure_t":tenure,
                     "mean_pairwise_corr120_t":mean_corr})
    return pd.DataFrame(rows)


def metrics(y, p):
    y=np.asarray(y,int); p=np.asarray(p,float); pred=(p>=.5).astype(int)
    out={"n":int(len(y)),"sign_accuracy":float(np.mean(pred==y)),
         "balanced_accuracy":float(balanced_accuracy_score(y,pred)),
         "brier":float(brier_score_loss(y,p))}
    out["auc"]=float(roc_auc_score(y,p)) if len(np.unique(y))>1 else None
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--stage1-artifact-dir", required=True)
    ap.add_argument("--output-dir", default="stage3-conditional-size-direction-output")
    args=ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    a=Path(args.stage1_artifact_dir); out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    dist=pd.read_csv(a/"monthly_k_distribution.csv")
    snap=pd.read_csv(a/"monthly_parent_pool_snapshots.csv")
    k3=dist[dist.k==3][["month","return_mean"]].rename(columns={"return_mean":"r3"})
    k30=dist[dist.k==30][["month","return_mean"]].rename(columns={"return_mean":"r30"})
    target=k3.merge(k30,on="month",how="inner")
    target["size_contrast"]=target.r30-target.r3
    target["lean_larger"]=(target.size_contrast>0).astype(int)

    eng=create_engine(_db_url(args.database_url),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["date"]=pd.to_datetime(bars["date"]); bars["symbol"]=bars["symbol"].astype(str)
    f=stage1_pool_score(build_features(bars))
    state=build_month_state(snap,bars,f)
    df=target.merge(state,on="month",how="inner").sort_values("month").reset_index(drop=True)
    df["year"]=df.month.str[:4].astype(int)
    preds=[]
    for i in range(MIN_TRAIN_MONTHS,len(df)):
        tr=df.iloc[:i].dropna(subset=FEATURES)
        te=df.iloc[[i]].dropna(subset=FEATURES)
        if te.empty or len(tr)<MIN_TRAIN_MONTHS: continue
        y=tr.lean_larger.astype(int).to_numpy()
        if len(np.unique(y))<2:
            p=float(np.mean(y))
        else:
            model=make_pipeline(StandardScaler(),LogisticRegression(C=1.0,penalty="l2",solver="lbfgs",max_iter=2000))
            model.fit(tr[FEATURES],y); p=float(model.predict_proba(te[FEATURES])[:,1][0])
        prev_sign=int(df.iloc[i-1].lean_larger)
        maj=float(tr.lean_larger.mean()>=.5)
        preds.append({"month":df.iloc[i].month,"year":int(df.iloc[i].year),"y":int(df.iloc[i].lean_larger),
                      "size_contrast":float(df.iloc[i].size_contrast),"p_model":p,
                      "p_prev_sign":float(prev_sign),"p_majority":maj})
    P=pd.DataFrame(preds)
    P.to_csv(out/"stage3_expanding_predictions.csv",index=False)
    state_out=df[["month","size_contrast","lean_larger",*FEATURES]].copy()
    state_out.to_csv(out/"stage3_monthly_state.csv",index=False)
    report={"stage":"new_stage_3","name":"conditional_size_direction_identifiability",
            "target":"mean_return_K30_minus_K3_sign","features":FEATURES,"min_train_months":MIN_TRAIN_MONTHS,
            "model":"StandardScaler(train only)+LogisticRegression L2 C=1.0; no tuning",
            "months_total":int(len(df)),"oos_months":int(len(P)),"metrics":{},"feature_association":{}}
    if len(P):
        report["metrics"]["overall"]={"model":metrics(P.y,P.p_model),"prev_sign":metrics(P.y,P.p_prev_sign),"majority":metrics(P.y,P.p_majority)}
        for name,mask in {"2021-24":P.year<=2024,"2025-26":P.year>=2025}.items():
            q=P[mask]
            if len(q): report["metrics"][name]={"model":metrics(q.y,q.p_model),"prev_sign":metrics(q.y,q.p_prev_sign),"majority":metrics(q.y,q.p_majority)}
    for feat in FEATURES:
        x=df[[feat,"size_contrast"]].dropna()
        report["feature_association"][feat]={"spearman_with_contrast":float(x[feat].corr(x.size_contrast,method="spearman")) if len(x)>2 else None}
    (out/"stage3_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
