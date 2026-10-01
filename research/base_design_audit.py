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

import cluster90_resistance_score_v1_test as v1lib
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
import optimal_universe_reverse_engineering.oure_stage8m_fixv2_v1_long_horizon as s8m
import optimal_universe_reverse_engineering.oure_stage8q_map_comparator_robustness as s8q
import optimal_universe_reverse_engineering.oure_stage8za_prevoid_incumbent_full_backtest as s8za
from base_plus_ols_allocation_backtest import perf_stats, monthly_stats, combine_band

COST = 0.0006
CASH = "511220"
RISK = ["513500", "159934"]
TARGET_OLS = 0.70
BAND = 0.05

VARIANTS = [
    {"name":"BOND30_IV60","cash":0.30,"mode":"iv","lookback":60},
    {"name":"NO_BOND_IV60","cash":0.00,"mode":"iv","lookback":60},
    {"name":"NO_BOND_IV90","cash":0.00,"mode":"iv","lookback":90},
    {"name":"NO_BOND_EQUAL","cash":0.00,"mode":"equal","lookback":60},
    {"name":"BOND15_IV60","cash":0.15,"mode":"iv","lookback":60},
]


def build_base_variant(bars, calendar, signal_dates, execution_dates, spec):
    syms = ([CASH] if spec["cash"] > 0 else []) + RISK
    b = bars[bars["symbol"].isin(syms)].copy()
    close = b.pivot(index="date", columns="symbol", values="close").sort_index().reindex(calendar)
    op = b.pivot(index="date", columns="symbol", values="open").sort_index().reindex(calendar)
    o2o = op.shift(-1) / op - 1.0
    vol = close[RISK].pct_change().rolling(spec["lookback"], min_periods=spec["lookback"]).std()

    sig = pd.to_datetime(signal_dates).reset_index(drop=True)
    exe = pd.to_datetime(execution_dates).reset_index(drop=True)
    rows, active_w, prev_w = [], None, None

    for i,(sd,ed) in enumerate(zip(sig,exe)):
        month_end = (i == len(sig)-1) or (exe.iloc[i].month != sd.month) or (i+1 < len(sig) and sig.iloc[i+1].month != sd.month)
        turnover = 0.0
        if active_w is None or month_end:
            risk_total = 1.0 - spec["cash"]
            if spec["mode"] == "equal":
                rw = pd.Series({s:risk_total/len(RISK) for s in RISK})
                ok = True
            else:
                vv = vol.loc[sd,RISK] if sd in vol.index else pd.Series(index=RISK,dtype=float)
                ok = vv.notna().all() and (vv>0).all()
                if ok:
                    inv = 1.0/vv
                    rw = risk_total * inv/inv.sum()
            if ok:
                nw = {s:float(rw[s]) for s in RISK}
                if spec["cash"] > 0:
                    nw[CASH] = float(spec["cash"])
                turnover = 0.0 if prev_w is None else sum(abs(nw.get(k,0)-prev_w.get(k,0)) for k in set(nw)|set(prev_w))
                active_w, prev_w = nw, nw.copy()

        gross = 0.0
        if active_w is not None and ed in o2o.index:
            for s,w in active_w.items():
                rr = o2o.at[ed,s] if s in o2o.columns else np.nan
                if pd.notna(rr) and np.isfinite(rr):
                    gross += w*float(rr)
        net = (1.0+gross)*(1.0-COST*turnover)-1.0
        rows.append({"signal_date":sd,"execution_date":ed,"base_net_ret":net,"base_turnover_sides":turnover})
    return pd.DataFrame(rows)


def main():
    db=os.getenv("ETF_DAILY_BARS_DATABASE_URL")
    if not db: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(os.getenv("OUTPUT_DIR","base-design-audit-output")); out.mkdir(parents=True,exist_ok=True)
    eng=create_engine(_db_url(db),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars["symbol"].astype(str).str.zfill(6); bars["date"]=pd.to_datetime(bars["date"])
    feat=build_features(bars); feat["symbol"]=feat["symbol"].astype(str).str.zfill(6); feat["date"]=pd.to_datetime(feat["date"])
    feat_idx=feat.set_index(["date","symbol"]).sort_index()
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    raw_score=s8m.raw_score_wide(feat,cal,list(score.columns.astype(str))); raw_delta=raw_score.diff()
    cash_ok=score[CASH].notna() & np.isfinite(score[CASH]) & (score.index>=s8m.START_FLOOR)
    first=pd.Timestamp(score.index[cash_ok][0]); start_i=int(cal.get_loc(first)); last_i=len(cal)-3
    raw=s8m.build_raw_targets(cal,score,s8m.MAIN_MEMBERS,start_i,last_i)
    prof=v1lib.build_needed_profiles(bars,set(s8m.MAIN_RISK)); pmap=prof.set_index(["date","symbol"])["resistance_pct252"].to_dict()
    v1,_=s8m.build_v1_targets(raw,score,raw_delta,pmap,s8m.MAIN_MEMBERS,s8m.MAIN_THRESHOLD)
    labels=s8q.fixed_strategy_labels(cal,score,gross,feat,bars); map_panel=s8q.build_map_panel(cal,score,feat,labels)
    ols_path=s8za.build_prevoid_variant(v1,map_panel,raw_score,feat_idx,"PREVOID_DEEPEN_INVALID_ROUTE",streak_need=1)
    ols=s8m.attach_returns(ols_path,gross,COST).copy()
    mp=map_panel[["signal_date","quadrant_511220"]].copy(); mp["signal_date"]=pd.to_datetime(mp["signal_date"])

    summaries=[]; annuals=[]; voids=[]; base_summaries=[]
    common_start=None
    built={}
    for spec in VARIANTS:
        b=build_base_variant(bars,cal,ols["signal_date"],ols["execution_date"],spec)
        z=ols[["signal_date","execution_date","net_ret"]].rename(columns={"net_ret":"ols_net_ret"}).merge(b,on=["signal_date","execution_date"],how="left")
        # initialized base: nonzero return history is not reliable flag, use date after lookback availability
        first_valid = z["execution_date"].iloc[max(spec["lookback"],0)] if len(z)>spec["lookback"] else z["execution_date"].iloc[0]
        z=z[z["execution_date"]>=first_valid].reset_index(drop=True)
        built[spec["name"]]=(z,spec)
        common_start = first_valid if common_start is None else max(common_start,first_valid)

    for name,(z,spec) in built.items():
        z=z[z["execution_date"]>=common_start].reset_index(drop=True)
        z=z.merge(mp,on="signal_date",how="left")
        c=combine_band(z["ols_net_ret"],z["base_net_ret"],z["execution_date"],TARGET_OLS)
        c["signal_date"]=z["signal_date"].values; c["quadrant_511220"]=z["quadrant_511220"].values
        c["variant"]=name
        st=perf_stats(c["net_ret"]); st.update(monthly_stats(c,"net_ret"))
        st.update({"variant":name,"cash_weight":spec["cash"],"mode":spec["mode"],"lookback":spec["lookback"],"allocation_rebalances":int(c["rebalance"].sum()),"avg_ols_weight":float(c["ols_weight_start"].mean())})
        summaries.append(st)
        bs=perf_stats(z["base_net_ret"]); bs.update(monthly_stats(z.rename(columns={"base_net_ret":"tmp"}),"tmp")); bs["variant"]=name
        base_summaries.append(bs)
        c["year"]=c["execution_date"].dt.year
        for y,g in c.groupby("year"):
            annuals.append({"variant":name,"year":int(y),**perf_stats(g["net_ret"])})
        vg=c[c["quadrant_511220"]=="DEFENSIVE_VOID"]
        if len(vg): voids.append({"variant":name,**perf_stats(vg["net_ret"])})
        c.to_csv(out/f"{name.lower()}_daily.csv",index=False)

    summary=pd.DataFrame(summaries); annual=pd.DataFrame(annuals); void=pd.DataFrame(voids); base_summary=pd.DataFrame(base_summaries)
    summary.to_csv(out/"base_design_summary.csv",index=False)
    annual.to_csv(out/"base_design_annual.csv",index=False)
    void.to_csv(out/"base_design_void.csv",index=False)
    base_summary.to_csv(out/"base_only_summary.csv",index=False)
    md=["# Base design audit","",
        f"Frozen total allocation: 70% OLS / 30% base, monthly +/-5pct band. Common start: {common_start.date()}.",
        "Only base composition / weighting changes. OLS engine is frozen Stage8ZA PREVOID_DEEPEN1.",
        "","## 70/30 portfolio","",summary.to_markdown(index=False),
        "","## Base sleeve only","",base_summary.to_markdown(index=False),
        "","## DEFENSIVE_VOID","",void.to_markdown(index=False),
        "","## Annual","",annual.to_markdown(index=False)]
    (out/"summary.md").write_text("\n".join(md),encoding="utf-8")
    (out/"summary.json").write_text(json.dumps({"summary":summary.to_dict("records"),"base_only":base_summary.to_dict("records"),"void":void.to_dict("records"),"annual":annual.to_dict("records")},ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print("\n".join(md))

if __name__=="__main__": main()
