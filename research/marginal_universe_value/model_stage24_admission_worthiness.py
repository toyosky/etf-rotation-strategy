#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,sys
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine
RESEARCH=Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path: sys.path.insert(0,str(RESEARCH))
from full_market_ols_storage import _db_url,build_features,load_daily_bars
from validate_fixed15_vs_full_market import FIXED15
FEATURES=["score","r2","score_delta","current_resid","efficiency20","dist_high20"]
CASH="511220"; TEST_START="2023-01"; OUT=Path("muv-stage24-admission-worthiness-report.json"); OUTM=Path("muv-stage24-admission-worthiness-months.csv")
def fwd20(f):
 p=[]
 for _,g0 in f.groupby("symbol",sort=False):
  g=g0.sort_values("date").copy(); c=g.close.astype(float).to_numpy(); v=np.full(len(g),np.nan)
  if len(g)>20:v[:-20]=c[20:]/c[:-20]-1
  g["fwd20_close"]=v;p.append(g)
 return pd.concat(p,ignore_index=True)
def pipe(): return Pipeline([("imputer",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler()),("model",LogisticRegression(C=1,class_weight="balanced",max_iter=2000))])
def summ(m,p):
 r=pd.to_numeric(m[p+"_rank"],errors="coerce");return {"n_months":int(len(m)),"hit_at_5":float((r<=5).mean()),"mrr":float((1/r).fillna(0).mean()),"median_first_positive_rank":float(r.median())}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--database-url",default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"));a=ap.parse_args()
 if not a.database_url:raise RuntimeError("ETF_DAILY_BARS_DATABASE_URL is required")
 f=fwd20(build_features(load_daily_bars(create_engine(_db_url(a.database_url),pool_pre_ping=True))));f.symbol=f.symbol.astype(str);f["month"]=pd.to_datetime(f.date).dt.to_period("M").astype(str)
 d=f[["date","month"]].drop_duplicates().groupby("month").date.max(); me=set(pd.to_datetime(d)); fixed=set(map(str,FIXED15))-{CASH}
 s=f[f.date.isin(me)&f.trend_eligible.fillna(False)&(f.symbol!=CASH)&f.fwd20_close.notna()][["date","month","symbol","fwd20_close",*FEATURES]].copy(); rows=[]
 for m,g in s.groupby("month"):
  gf=g[g.symbol.isin(fixed)];go=g[~g.symbol.isin(fixed)].copy()
  if gf.empty or go.empty:continue
  front=float(gf.fwd20_close.max());go["y"]=(go.fwd20_close>front).astype(int);rows.append(go)
 data=pd.concat(rows,ignore_index=True); out=[]
 for m in sorted(x for x in data.month.unique() if x>=TEST_START):
  tr=data[data.month<m];te=data[data.month==m].copy()
  if tr.month.nunique()<12 or tr.y.nunique()<2 or te.y.sum()<1:continue
  md=pipe();md.fit(tr[FEATURES],tr.y);te["p"]=md.predict_proba(te[FEATURES])[:,1];te["score_r"]=te.score.rank(method="min",ascending=False);te["state_r"]=te.p.rank(method="min",ascending=False)
  out.append({"month":m,"era":"2023-24" if int(m[:4])<2025 else "2025-26","candidate_count":len(te),"positive_count":int(te.y.sum()),"positive_share":float(te.y.mean()),"score_rank":float(te.loc[te.y==1,"score_r"].min()),"state_rank":float(te.loc[te.y==1,"state_r"].min())})
 M=pd.DataFrame(out);M.to_csv(OUTM,index=False);S=summ(M,"score");X=summ(M,"state");by={};ds=[]
 for e,g in M.groupby("era"):
  se=summ(g,"score");xe=summ(g,"state");dd={"hit_at_5":xe["hit_at_5"]-se["hit_at_5"],"mrr":xe["mrr"]-se["mrr"]};by[e]={"score_baseline":se,"low_dof_state":xe,"delta":dd};ds.append(dd)
 ok=X["hit_at_5"]>=S["hit_at_5"] and X["mrr"]>=S["mrr"] and all(z["hit_at_5"]>=0 and z["mrr"]>=0 for z in ds)
 R={"version":"muv_stage24_admission_worthiness_state_audit_20260913","design":{"target":"outsider fwd20 > contemporaneous Fixed15 oracle-best fwd20","features":FEATURES,"split":"strict monthly expanding OOS","feature_search":False,"hyperparameter_search":False,"topk_search":False,"policy_backtest":False},"coverage":{"oos_positive_months":len(M),"candidate_count_mean":float(M.candidate_count.mean()),"positive_count_mean":float(M.positive_count.mean()),"positive_share_mean":float(M.positive_share.mean())},"overall":{"score_baseline":S,"low_dof_state":X},"by_era":by,"predeclared_interpretation":{"low_dof_admission_state_supported":bool(ok),"rule":"Hit@5 and MRR must not deteriorate overall or in either era."}}
 OUT.write_text(json.dumps(R,ensure_ascii=False,indent=2));print(json.dumps(R,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
