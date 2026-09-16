#!/usr/bin/env python3
from __future__ import annotations

import json, os, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
import optimal_universe_reverse_engineering.oure_stage8m_fixv2_v1_long_horizon as s8m
import optimal_universe_reverse_engineering.oure_stage8n_internal_regime_diagnostic as s8n
import optimal_universe_reverse_engineering.oure_stage8q_map_comparator_robustness as s8q
import cluster90_resistance_score_v1_test as v1lib

BASELINE = "511220"
RISK = tuple(s8m.MAIN_RISK)
HORIZONS = (5,10,20)
COST = 0.0006


def fixed_strategy_labels(cal, score, gross, feat, bars):
    cash_ok = score[BASELINE].notna() & np.isfinite(score[BASELINE]) & (score.index >= s8m.START_FLOOR)
    first = pd.Timestamp(score.index[cash_ok][0])
    start_i = int(cal.get_loc(first)); last_i = len(cal)-3
    raw = s8m.build_raw_targets(cal, score, s8m.MAIN_MEMBERS, start_i, last_i)
    raw_score = s8m.raw_score_wide(feat, cal, list(score.columns.astype(str)))
    raw_delta = raw_score.diff()
    needed = set(raw["target"].dropna().astype(str).unique())
    profiles_df = v1lib.build_needed_profiles(bars, needed)
    profiles = profiles_df.set_index(["date","symbol"])["resistance_pct252"].to_dict()
    v1,_ = s8m.build_v1_targets(raw, score, raw_delta, profiles, s8m.MAIN_MEMBERS, s8m.MAIN_THRESHOLD)
    v1 = s8m.attach_returns(v1, gross, COST)
    z = raw[["signal_date","execution_date","return_end_date"]].copy()
    z["v1_net_ret"] = v1["net_ret"].to_numpy(float)
    return s8n.add_forward_labels(z)


def rank_pct_prior(s: pd.Series, lookback=252, min_hist=60):
    x = pd.to_numeric(s, errors="coerce").to_numpy(float)
    out=np.full(len(x), np.nan)
    for i,v in enumerate(x):
        if not np.isfinite(v): continue
        hist=x[max(0,i-lookback):i]; hist=hist[np.isfinite(hist)]
        if len(hist)>=min_hist:
            out[i]=100.0*np.mean(hist<=v)
    return pd.Series(out,index=s.index,dtype=float)


def build_panel(cal, feat, labels):
    raw_score = s8m.raw_score_wide(feat, cal, sorted(feat.symbol.astype(str).unique()))
    rows=[]
    for d in cal:
        d=pd.Timestamp(d)
        if BASELINE not in raw_score.columns: continue
        cv=raw_score.at[d,BASELINE]
        vals=raw_score.loc[d,[s for s in RISK if s in raw_score.columns]].astype(float)
        valid=vals[np.isfinite(vals)]
        if len(valid)<2 or pd.isna(cv) or not np.isfinite(cv): continue
        internal_count=int((valid>0).sum())
        riskdef_count=int((valid>float(cv)).sum())
        internal=100.0*internal_count/len(RISK)
        riskdef=100.0*riskdef_count/len(RISK)
        rows.append({"signal_date":d,"internal_breadth":internal,"risk_over_defense_breadth":riskdef,
                     "breadth_divergence":internal-riskdef,"internal_count":internal_count,
                     "risk_over_defense_count":riskdef_count,"cash_score":float(cv)})
    z=pd.DataFrame(rows).merge(labels,on="signal_date",how="left")
    for c in ["internal_breadth","risk_over_defense_breadth","breadth_divergence"]:
        z[c+"_pct252"]=rank_pct_prior(z[c])
    return z


def corr_table(z):
    rows=[]
    segments={"FULL":pd.Series(True,index=z.index),"PRE2021":z.signal_date<pd.Timestamp("2021-01-01"),"POST2021":z.signal_date>=pd.Timestamp("2021-01-01"),"POST2023":z.signal_date>=pd.Timestamp("2023-01-01")}
    for seg,mask in segments.items():
        g=z.loc[mask]
        for f in ["internal_breadth","risk_over_defense_breadth","breadth_divergence"]:
            for h in HORIZONS:
                x=g[[f,f"fwd_return_{h}",f"fwd_mdd_{h}"]].dropna()
                rows.append({"segment":seg,"feature":f,"horizon":h,"n":len(x),
                             "spearman_future_return":float(x[f].corr(x[f"fwd_return_{h}"],method="spearman")) if len(x)>=10 else np.nan,
                             "spearman_future_mdd":float(x[f].corr(x[f"fwd_mdd_{h}"],method="spearman")) if len(x)>=10 else np.nan})
    return pd.DataFrame(rows)


def quintiles(z):
    rows=[]
    for f in ["internal_breadth","risk_over_defense_breadth","breadth_divergence"]:
        p=f+"_pct252"; g=z.dropna(subset=[p]).copy();
        if g.empty: continue
        g["quintile"]=np.clip(np.floor(g[p]/20).astype(int)+1,1,5)
        for h in HORIZONS:
            for q,x in g.groupby("quintile"):
                r=x[f"fwd_return_{h}"].dropna(); m=x[f"fwd_mdd_{h}"].dropna()
                rows.append({"feature":f,"horizon":h,"quintile":int(q),"n":int(r.notna().sum()),
                             "mean_return":float(r.mean()) if len(r) else np.nan,
                             "median_return":float(r.median()) if len(r) else np.nan,
                             "win_rate":float((r>0).mean()) if len(r) else np.nan,
                             "mean_mdd":float(m.mean()) if len(m) else np.nan})
    return pd.DataFrame(rows)


def disagreement_states(z):
    g=z.dropna(subset=["internal_breadth_pct252","risk_over_defense_breadth_pct252"]).copy()
    g["state"]="BALANCED"
    g.loc[(g.internal_breadth_pct252>=80)&(g.risk_over_defense_breadth_pct252<=20),"state"]="HIGH_INTERNAL_LOW_RISKDEF"
    g.loc[(g.internal_breadth_pct252<=20)&(g.risk_over_defense_breadth_pct252>=80),"state"]="LOW_INTERNAL_HIGH_RISKDEF"
    g.loc[g.breadth_divergence_pct252>=80,"state"]="HIGH_DIVERGENCE"
    g.loc[g.breadth_divergence_pct252<=20,"state"]="LOW_DIVERGENCE"
    rows=[]
    for h in HORIZONS:
        for state,x in g.groupby("state"):
            r=x[f"fwd_return_{h}"].dropna(); m=x[f"fwd_mdd_{h}"].dropna()
            rows.append({"state":state,"horizon":h,"n":len(r),"mean_return":float(r.mean()) if len(r) else np.nan,
                         "median_return":float(r.median()) if len(r) else np.nan,"win_rate":float((r>0).mean()) if len(r) else np.nan,
                         "mean_mdd":float(m.mean()) if len(m) else np.nan})
    return pd.DataFrame(rows)


def latest(z):
    r=z.dropna(subset=["internal_breadth","risk_over_defense_breadth","breadth_divergence"]).iloc[-1]
    return {k:(str(pd.Timestamp(r[k]).date()) if k=="signal_date" else float(r[k])) for k in ["signal_date","internal_breadth","risk_over_defense_breadth","breadth_divergence","internal_breadth_pct252","risk_over_defense_breadth_pct252","breadth_divergence_pct252"]}


def main():
    db=os.getenv("ETF_DAILY_BARS_DATABASE_URL")
    if not db: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(os.getenv("OUTPUT_DIR","stage8r-breadth-divergence-output")); out.mkdir(parents=True,exist_ok=True)
    eng=create_engine(_db_url(db),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars.symbol.astype(str).str.zfill(6); bars["date"]=pd.to_datetime(bars.date)
    feat=build_features(bars); feat["symbol"]=feat.symbol.astype(str).str.zfill(6); feat["date"]=pd.to_datetime(feat.date)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    labels=fixed_strategy_labels(cal,score,gross,feat,bars)
    z=build_panel(cal,feat,labels)
    corr=corr_table(z); q=quintiles(z); ds=disagreement_states(z); lat=latest(z)
    z.to_csv(out/"stage8r_daily.csv",index=False); corr.to_csv(out/"stage8r_correlations.csv",index=False); q.to_csv(out/"stage8r_quintiles.csv",index=False); ds.to_csv(out/"stage8r_disagreement_states.csv",index=False)
    summary={"study":"OURE Stage8R breadth divergence diagnostic","definitions":{
        "internal_breadth":"fixed-13 share of raw risky OLS scores > 0",
        "risk_over_defense_breadth":"fixed-13 share of raw risky OLS scores > raw 511220 OLS score",
        "breadth_divergence":"internal_breadth - risk_over_defense_breadth"},"latest":lat,
        "interpretation":"Diagnostic only. Add to website only if divergence contributes stable incremental information."}
    (out/"stage8r_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# Stage8R — Breadth Divergence Diagnostic","",f"Latest: `{lat}`","","## Correlations","",corr.to_markdown(index=False),"","## Divergence / disagreement states","",ds.to_markdown(index=False)]
    (out/"stage8r_summary.md").write_text("\n".join(md),encoding="utf-8")
    print("\n".join(md))

if __name__=="__main__": main()
