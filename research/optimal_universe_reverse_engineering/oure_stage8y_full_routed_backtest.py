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

CASH='511220'
CARRIER='513500'
SUBS=('513100','159509','513290','159529')
COST=0.0006
MIN_AGE=365
SEED=4


def side_count(a,b):
    if a==b:return 0
    if a is None or b is None:return 1
    return 2


def age_ok(feat_idx,d,s):
    try:
        r=feat_idx.loc[(pd.Timestamp(d),str(s))]
        if isinstance(r,pd.DataFrame): r=r.iloc[-1]
        return float(r['listing_age_days'])>=MIN_AGE
    except Exception:
        return False


def score_at(raw_score,d,s):
    try:
        x=raw_score.at[pd.Timestamp(d),s]
        return float(x) if pd.notna(x) and np.isfinite(x) else np.nan
    except Exception:
        return np.nan


def ret3_at(feat_idx,d,s):
    try:
        r=feat_idx.loc[(pd.Timestamp(d),str(s))]
        if isinstance(r,pd.DataFrame): r=r.iloc[-1]
        x=r['ret3']; return float(x) if pd.notna(x) and np.isfinite(x) else np.nan
    except Exception:
        return np.nan


def routed_targets(base, map_panel, raw_score, feat_idx, mode):
    out=base.copy()
    q=map_panel.set_index('signal_date')['quadrant_511220'].to_dict()
    past_active_ret3=[]
    in_void=False
    episode_target=None
    prev_out=None
    targets=[]
    decisions=[]

    for r in out.itertuples(index=False):
        d=pd.Timestamp(r.signal_date)
        quad=q.get(d,None)
        is_void=(quad=='DEFENSIVE_VOID')
        base_t=None if pd.isna(r.target) else str(r.target)
        decision='BASE'
        t=base_t

        if is_void:
            if not in_void:
                cs=score_at(raw_score,d,CARRIER)
                ks=score_at(raw_score,d,CASH)
                us_healthy=(age_ok(feat_idx,d,CARRIER) and np.isfinite(cs) and np.isfinite(ks) and cs>ks)
                if mode=='CASH' or not us_healthy:
                    episode_target=CASH
                    decision='VOID_CASH'
                elif mode=='CARRIER':
                    episode_target=CARRIER
                    decision='VOID_CARRIER'
                else:
                    # Default carrier; selectively enhance.
                    episode_target=CARRIER
                    best=None; best_score=-np.inf
                    for s in SUBS:
                        ss=score_at(raw_score,d,s)
                        if age_ok(feat_idx,d,s) and np.isfinite(ss) and ss>ks and ss>best_score:
                            best=s; best_score=ss
                    if best is not None:
                        rr=ret3_at(feat_idx,d,best)
                        if np.isfinite(rr):
                            if len(past_active_ret3)>=SEED:
                                thr=float(np.median(past_active_ret3))
                                if rr<=thr:
                                    episode_target=best
                                    decision='VOID_ENHANCER'
                                else:
                                    decision='VOID_CARRIER_REJECT_ENH'
                            else:
                                decision='VOID_CARRIER_SEED'
                            # only past episode entries determine future threshold
                            past_active_ret3.append(rr)
                in_void=True
            t=episode_target
        else:
            in_void=False
            episode_target=None
            t=base_t

        targets.append(t)
        decisions.append(decision)

    out['target']=targets
    out['route_decision']=decisions
    # recompute side counts after routing
    sides=[]
    prev=None
    for t in targets:
        sides.append(side_count(prev,t)); prev=t
    out['sides']=sides
    return out


def annual(path,name):
    a=s8m.annual_table(path,None,name)
    keep=['variant','year','total_return','cagr','mdd','ann_vol','sharpe_0rf','calmar','turnover_sides','switches','start','end']
    return a[[c for c in keep if c in a.columns]]


def main():
    db=os.getenv('ETF_DAILY_BARS_DATABASE_URL')
    if not db: raise SystemExit('Missing ETF_DAILY_BARS_DATABASE_URL')
    out=Path(os.getenv('OUTPUT_DIR','stage8y-full-routed-output')); out.mkdir(parents=True,exist_ok=True)
    eng=create_engine(_db_url(db),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars['symbol']=bars['symbol'].astype(str).str.zfill(6); bars['date']=pd.to_datetime(bars['date'])
    feat=build_features(bars); feat['symbol']=feat['symbol'].astype(str).str.zfill(6); feat['date']=pd.to_datetime(feat['date'])
    feat_idx=feat.set_index(['date','symbol']).sort_index()
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    raw_score=s8m.raw_score_wide(feat,cal,list(score.columns.astype(str)))
    raw_delta=raw_score.diff()

    cash_ok=score[CASH].notna() & np.isfinite(score[CASH]) & (score.index>=s8m.START_FLOOR)
    first=pd.Timestamp(score.index[cash_ok][0]); start_i=int(cal.get_loc(first)); last_i=len(cal)-3
    raw=s8m.build_raw_targets(cal,score,s8m.MAIN_MEMBERS,start_i,last_i)
    prof=v1lib.build_needed_profiles(bars,set(s8m.MAIN_RISK))
    pmap=prof.set_index(['date','symbol'])['resistance_pct252'].to_dict()
    v1,events=s8m.build_v1_targets(raw,score,raw_delta,pmap,s8m.MAIN_MEMBERS,s8m.MAIN_THRESHOLD)

    labels=s8q.fixed_strategy_labels(cal,score,gross,feat,bars)
    map_panel=s8q.build_map_panel(cal,score,feat,labels)

    variants={
      'VOID_CASH': routed_targets(v1,map_panel,raw_score,feat_idx,'CASH'),
      'VOID_US_CARRIER': routed_targets(v1,map_panel,raw_score,feat_idx,'CARRIER'),
      'VOID_US_CARRIER_ENHANCER': routed_targets(v1,map_panel,raw_score,feat_idx,'ENHANCER'),
    }
    detailed={}
    summary=[]; annuals=[]; periods=[]; dds=[]
    for name,p in variants.items():
        q=s8m.attach_returns(p,gross,COST); q['variant']=name; detailed[name]=q
        summary.append({'variant':name,**s8m.stats(q)})
        annuals.append(annual(q,name))
        periods.append(s8m.period_table(q,name))
        dds.append(s8m.drawdown_table(q,name,topn=8))
        q.to_csv(out/f'{name.lower()}_daily.csv',index=False)

    summary=pd.DataFrame(summary)
    annual_df=pd.concat(annuals,ignore_index=True)
    period_df=pd.concat(periods,ignore_index=True)
    dd_df=pd.concat(dds,ignore_index=True)
    summary.to_csv(out/'stage8y_full_summary.csv',index=False)
    annual_df.to_csv(out/'stage8y_annual.csv',index=False)
    period_df.to_csv(out/'stage8y_periods.csv',index=False)
    dd_df.to_csv(out/'stage8y_drawdowns.csv',index=False)

    # Additional-cost stress only on days entering/exiting US-routed positions is conservatively
    # approximated by raising per-side global cost for routed variants; this is deliberately harsh.
    stress=[]
    for c in (0.0006,0.0010,0.0015,0.0020,0.0030):
        for name,p in variants.items():
            q=s8m.attach_returns(p,gross,c)
            stress.append({'variant':name,'cost_per_side':c,**s8m.stats(q)})
    pd.DataFrame(stress).to_csv(out/'stage8y_cost_stress.csv',index=False)

    route_rows=[]
    for name,q in detailed.items():
        if 'route_decision' in q.columns:
            vc=q['route_decision'].value_counts(dropna=False)
            for k,v in vc.items(): route_rows.append({'variant':name,'decision':str(k),'days':int(v)})
    pd.DataFrame(route_rows).to_csv(out/'stage8y_route_counts.csv',index=False)

    md=['# Stage8Y — Full FixV2/V1 routed portfolio backtest','',
        'Frozen base: Stage8M FixV2/V1(75), 26d weighted log-price OLS, half-life 10, 6bp per side.','',
        'Only DEFENSIVE_VOID handling differs across variants. Routing is frozen once at each Void episode entry and held until the episode exits.','',
        '## Full summary','',summary.to_markdown(index=False),'','## Annual', '',annual_df.to_markdown(index=False),'',
        '## Periods','',period_df.to_markdown(index=False),'','## Major drawdowns','',dd_df.to_markdown(index=False),'',
        'Enhancer rule: if US carrier 513500 beats 511220 and is >=365 days old, default to 513500. The highest historically-available US sub-exposure among 513100/159509/513290/159529 may replace the carrier only if it beats 511220 and its ret3 is <= the expanding median ret3 of prior active Void episode candidates after four seed events. No future event is used in the threshold.']
    (out/'stage8y_summary.md').write_text('\n'.join(md),encoding='utf-8')
    (out/'stage8y_summary.json').write_text(json.dumps({'summary':summary.to_dict('records'),'annual':annual_df.to_dict('records')},ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print('\n'.join(md))

if __name__=='__main__': main()
