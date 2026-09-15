#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage8a_opportunity30 as s8a
import optimal_universe_reverse_engineering.oure_stage8b_opportunity_k_frontier as s8b
import optimal_universe_reverse_engineering.oure_stage8c_marginal_opportunity_capture as s8c
import optimal_universe_reverse_engineering.oure_stage8e_economic_coverage as s8e
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

CASH = s8a.CASH
COST = s8a.COST
START_EXEC = pd.Timestamp("2021-01-01")
HIST_SESSIONS = 378
HORIZONS = (1, 3, 5, 10)
FEATURES = (
    "score_gap","gap_delta","challenger_score_delta","persistence",
    "challenger_r2","challenger_slope","amount_ratio","core_r2","core_slope",
)


def safe_float(x, default=np.nan):
    try:
        v = float(x)
        return v if np.isfinite(v) else default
    except Exception:
        return default


def best_risk(score: pd.DataFrame, d, members):
    cols = [s for s in members if s != CASH and s in score.columns]
    if not cols:
        return None, -np.inf
    x = pd.to_numeric(score.loc[d, cols], errors="coerce").replace([np.inf,-np.inf], np.nan).dropna()
    if x.empty:
        return None, -np.inf
    s = str(x.idxmax())
    return s, float(x.loc[s])


def gross_at(gross: pd.DataFrame, d, s):
    if s is None or s not in gross.columns:
        return 0.0
    return safe_float(gross.at[d, s], 0.0)


def fwd_hold(gross: pd.DataFrame, cal: pd.DatetimeIndex, i: int, s: str | None, h: int):
    if s is None or s not in gross.columns or i + h - 1 >= len(cal) - 2:
        return np.nan
    vals=[]
    for j in range(h):
        v=safe_float(gross.at[cal[i+j],s],np.nan)
        if not np.isfinite(v): return np.nan
        vals.append(v)
    return float(np.prod(1.0+np.asarray(vals,float))-1.0)


def amount_ratio(amount: pd.DataFrame, cal: pd.DatetimeIndex, i: int, s: str):
    if s not in amount.columns or i <= 0: return np.nan
    hist = amount.loc[cal[max(0,i-60):i-1], s]
    med = float(np.nanmedian(pd.to_numeric(hist,errors="coerce").to_numpy(float))) if len(hist) else np.nan
    cur = safe_float(amount.at[cal[i],s],np.nan)
    return float(cur/med) if np.isfinite(cur) and np.isfinite(med) and med>0 else np.nan


def auc_rank(x: pd.Series, y: pd.Series):
    z=pd.DataFrame({"x":pd.to_numeric(x,errors="coerce"),"y":pd.to_numeric(y,errors="coerce")}).dropna()
    if z.empty: return np.nan
    z["y"]=(z["y"]>0).astype(int)
    n1=int(z["y"].sum()); n0=int(len(z)-n1)
    if n1==0 or n0==0: return np.nan
    r=z["x"].rank(method="average")
    u=float(r[z["y"]==1].sum()-n1*(n1+1)/2)
    return u/(n1*n0)


def path_stats_df(daily: pd.DataFrame):
    out=[]
    for v,g in daily.groupby("variant"):
        out.append({"variant":v,**s8b.path_stats(g)})
    return pd.DataFrame(out)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage8f-output")
    args=ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)

    eng=create_engine(_db_url(args.database_url),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars["symbol"].astype(str); bars["date"]=pd.to_datetime(bars["date"])
    feat=build_features(bars); feat["symbol"]=feat["symbol"].astype(str)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    amount=s8e.build_amount_wide(bars,cal)
    meta=pd.read_sql_query(text("""select symbol,name,asset_class,region_primary,exposure_level1,exposure_level2,underlying_key,risk_bucket,style_sector,is_qdii,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"""),eng)
    meta["symbol"]=meta["symbol"].astype(str).str.zfill(6)

    start0=int(cal.searchsorted(pd.Timestamp("2022-01-01"),side="left"))
    starts=s8a.extended_starts(cal,start0); starts_map={b:p for b,p in starts}
    first_exec_pos=int(cal.searchsorted(START_EXEC,side="left")); first_signal=max(0,first_exec_pos-1); last_signal=len(cal)-3
    need=[]
    for b,p in starts:
        nxt=starts_map.get(b+1,len(cal))
        if nxt<=first_signal or p>last_signal: continue
        if p-HIST_SESSIONS<0: continue
        if all((b-j) in starts_map for j in (1,2,3)): need.append((b,p))
    if not need: raise RuntimeError("no blocks")

    core_by={}; eco_by={}; slot_map={}; sel_rows=[]
    for bno,pos in need:
        common=s8a.common_pool_for_block(bno,pos,starts_map,cal,close,meta)
        order,_,_=s8c.old_order_point_in_time(score,gross,cal,pos,common,30)
        core=tuple(sorted(common[j] for j in order[:15]))
        eco,rows=s8e.select_economic(common,pos,cal,amount,meta)
        core_by[bno]=core; eco_by[bno]=eco
        for rr in rows:
            slot_map[(bno,str(rr["symbol"]))]=str(rr["slot"])
            sel_rows.append({**rr,"block_no":bno,"decision_date":str(pd.Timestamp(cal[pos]).date()),"core15":",".join(core),"economic_k":len(eco)})

    core_daily=s8a.build_variant_daily("CORE15",core_by,starts_map,cal,score,gross,first_signal,last_signal)
    core_daily=core_daily.loc[core_daily["execution_date"]>=START_EXEC].copy()

    event_rows=[]; oracle_rows=[]; prev_oracle=None; prev_ch=None; persist=0
    for bno,pos in sorted(need,key=lambda z:z[1]):
        next_pos=starts_map.get(bno+1,len(cal))
        lo=max(pos,first_signal); hi=min(next_pos-1,last_signal)
        core=core_by[bno]; eco=eco_by[bno]
        outsiders=[s for s in eco if s not in core and s!=CASH]
        for i in range(lo,hi+1):
            d=pd.Timestamp(cal[i])
            core_leader,core_score=best_risk(score,d,core)
            cash_score=safe_float(score.at[d,CASH],-np.inf) if CASH in score.columns else -np.inf
            core_target=s8a.choose_target(score,d,core)
            ch,ch_score=best_risk(score,d,outsiders)
            executable=bool(ch is not None and np.isfinite(ch_score) and ch_score>core_score and ch_score>cash_score)
            if executable and ch==prev_ch: persist+=1
            elif executable: persist=1
            else: persist=0

            oracle_target=core_target
            core_g=gross_at(gross,d,core_target)
            ch_g=gross_at(gross,d,ch) if executable else -np.inf
            if executable and ch_g>core_g: oracle_target=ch
            if oracle_target==prev_oracle: sides=0
            elif oracle_target is None or prev_oracle is None: sides=1
            else: sides=2
            og=gross_at(gross,d,oracle_target)
            net=(1.0+og)*(1.0-COST*sides)-1.0
            oracle_rows.append({"variant":"NARROW_ORACLE","signal_date":d,"execution_date":pd.Timestamp(cal[i+1]),"return_end_date":pd.Timestamp(cal[i+2]),"block_no":bno,"target":oracle_target,"sides":sides,"gross":og,"net":net,"core_target":core_target,"challenger":ch if executable else None,"oracle_used_challenger":bool(executable and oracle_target==ch)})
            prev_oracle=oracle_target

            if executable:
                prev_i=i-1
                prev_core_score=-np.inf
                if prev_i>=0:
                    _,prev_core_score=best_risk(score,cal[prev_i],core)
                prev_ch_score=safe_float(score.at[cal[prev_i],ch],np.nan) if prev_i>=0 and ch in score.columns else np.nan
                gap=ch_score-core_score
                prev_gap=prev_ch_score-prev_core_score if np.isfinite(prev_ch_score) and np.isfinite(prev_core_score) else np.nan
                rr={
                    "signal_date":d,"execution_date":pd.Timestamp(cal[i+1]),"year":int(d.year),"era":"2021_2024" if d.year<=2024 else "2025_2026",
                    "block_no":bno,"core_leader":core_leader,"core_target":core_target,"challenger":ch,"challenger_slot":slot_map.get((bno,ch)),
                    "score_gap":gap,"gap_delta":gap-prev_gap if np.isfinite(prev_gap) else np.nan,
                    "challenger_score_delta":ch_score-prev_ch_score if np.isfinite(prev_ch_score) else np.nan,"persistence":persist,
                    "challenger_score":ch_score,"core_score":core_score,"cash_score":cash_score,
                    "challenger_r2":safe_float(r2.at[d,ch],np.nan),"challenger_slope":safe_float(slope.at[d,ch],np.nan),
                    "core_r2":safe_float(r2.at[d,core_leader],np.nan) if core_leader else np.nan,"core_slope":safe_float(slope.at[d,core_leader],np.nan) if core_leader else np.nan,
                    "amount_ratio":amount_ratio(amount,cal,i,ch),"episode_start":bool(persist==1),
                    "next_gross_challenger":gross_at(gross,d,ch),"next_gross_core_target":core_g,
                }
                for h in HORIZONS:
                    cr=fwd_hold(gross,cal,i,ch,h); br=fwd_hold(gross,cal,i,core_leader,h)
                    alpha=cr-br if np.isfinite(cr) and np.isfinite(br) else np.nan
                    rr[f"challenger_ret_{h}"]=cr; rr[f"core_leader_ret_{h}"]=br; rr[f"alpha_{h}"]=alpha; rr[f"useful_{h}"]=bool(alpha>0) if np.isfinite(alpha) else np.nan
                event_rows.append(rr)
            prev_ch=ch if executable else None

    events=pd.DataFrame(event_rows)
    oracle=pd.DataFrame(oracle_rows)
    oracle=oracle.loc[oracle["execution_date"]>=START_EXEC].copy()
    daily=pd.concat([core_daily,oracle],ignore_index=True,sort=False)
    ann,_=s8a.summarize(daily)
    full=path_stats_df(daily)

    # Oracle opportunity diagnostics.
    core_map=core_daily.set_index("signal_date")["target"]
    od=oracle.copy(); od["core_target_lookup"]=od["signal_date"].map(core_map)
    oracle_change_days=int((od["target"].fillna("CASH")!=od["core_target_lookup"].fillna("CASH")).sum())
    oracle_used=int(od["oracle_used_challenger"].sum())

    auc_rows=[]; group_rows=[]
    for sample_name,df0 in [("daily",events),("episode_start",events[events["episode_start"]==True])]:
        for era_name,df1 in [("ALL",df0),("2021_2024",df0[df0["era"]=="2021_2024"]),("2025_2026",df0[df0["era"]=="2025_2026"])]:
            for h in HORIZONS:
                lab=f"useful_{h}"
                if lab not in df1.columns: continue
                for f in FEATURES:
                    auc=auc_rank(df1[f],df1[lab])
                    auc_rows.append({"sample":sample_name,"era":era_name,"horizon":h,"feature":f,"n":int(pd.DataFrame({"x":df1[f],"y":df1[lab]}).dropna().shape[0]),"auc_higher_is_useful":auc,"auc_separation":max(auc,1-auc) if np.isfinite(auc) else np.nan})
                for useful_val in (False,True):
                    z=df1[df1[lab]==useful_val]
                    row={"sample":sample_name,"era":era_name,"horizon":h,"useful":useful_val,"n":len(z)}
                    for f in FEATURES:
                        row[f"{f}_mean"]=float(pd.to_numeric(z[f],errors="coerce").mean()) if len(z) else np.nan
                        row[f"{f}_median"]=float(pd.to_numeric(z[f],errors="coerce").median()) if len(z) else np.nan
                    group_rows.append(row)
    aucs=pd.DataFrame(auc_rows); groups=pd.DataFrame(group_rows)

    alpha_rows=[]
    for sample_name,df0 in [("daily",events),("episode_start",events[events["episode_start"]==True])]:
        for era_name,df1 in [("ALL",df0),("2021_2024",df0[df0["era"]=="2021_2024"]),("2025_2026",df0[df0["era"]=="2025_2026"])]:
            for h in HORIZONS:
                a=pd.to_numeric(df1[f"alpha_{h}"],errors="coerce").dropna()
                alpha_rows.append({"sample":sample_name,"era":era_name,"horizon":h,"n":len(a),"mean_alpha":float(a.mean()) if len(a) else np.nan,"median_alpha":float(a.median()) if len(a) else np.nan,"positive_share":float((a>0).mean()) if len(a) else np.nan,"q25":float(a.quantile(.25)) if len(a) else np.nan,"q75":float(a.quantile(.75)) if len(a) else np.nan})
    alpha_summary=pd.DataFrame(alpha_rows)

    slot_summary=(events.groupby("challenger_slot",dropna=False).agg(challenge_days=("signal_date","size"),episodes=("episode_start","sum"),mean_alpha1=("alpha_1","mean"),mean_alpha5=("alpha_5","mean"),useful1_share=("useful_1","mean"),useful5_share=("useful_5","mean")).reset_index().sort_values("challenge_days",ascending=False)) if len(events) else pd.DataFrame()

    summary={
        "study":"OURE Stage8F challenger oracle + event study","status":"completed","blocks":len(need),
        "sessions":int(len(core_daily)),"challenge_days":int(len(events)),"challenge_day_share":float(len(events)/len(core_daily)) if len(core_daily) else np.nan,
        "challenge_episodes":int(events["episode_start"].sum()) if len(events) else 0,
        "oracle_used_challenger_days":oracle_used,"oracle_changed_vs_core_days":oracle_change_days,
        "full":full.to_dict(orient="records"),
    }

    pd.DataFrame(sel_rows).to_csv(out/"stage8f_block_structures.csv",index=False)
    events.to_csv(out/"stage8f_challenge_events.csv",index=False)
    events[events["episode_start"]==True].to_csv(out/"stage8f_challenge_episodes.csv",index=False)
    daily.to_csv(out/"stage8f_daily_paths.csv",index=False)
    ann.to_csv(out/"stage8f_annual.csv",index=False)
    full.to_csv(out/"stage8f_full.csv",index=False)
    aucs.to_csv(out/"stage8f_feature_auc.csv",index=False)
    groups.to_csv(out/"stage8f_feature_groups.csv",index=False)
    alpha_summary.to_csv(out/"stage8f_alpha_summary.csv",index=False)
    slot_summary.to_csv(out/"stage8f_slot_summary.csv",index=False)
    (out/"stage8f_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")

    print(full.to_string(index=False))
    print(json.dumps({k:v for k,v in summary.items() if k!="full"},indent=2,ensure_ascii=False,default=str))
    print(alpha_summary.to_string(index=False))
    if len(aucs):
        print(aucs.sort_values(["sample","era","horizon","auc_separation"],ascending=[True,True,True,False]).groupby(["sample","era","horizon"]).head(3).to_string(index=False))

if __name__=="__main__":
    main()
