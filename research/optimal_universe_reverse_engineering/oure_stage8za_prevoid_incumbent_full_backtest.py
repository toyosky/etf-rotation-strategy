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
import optimal_universe_reverse_engineering.oure_stage8y_full_routed_backtest as s8y

CASH='511220'
CARRIER='513500'
COST=0.0006
MIN_AGE=365
STREAKS=(1,2,3)


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


def build_prevoid_variant(base,map_panel,raw_score,feat_idx,mode,streak_need=2):
    """
    Entering Void freezes the ACTUAL PRE-VOID output target (previous signal day's routed target),
    not the base target newly produced on the Void-entry day.

    modes:
      BASE: untouched Stage8M V1.
      IMMEDIATE_CARRIER: Stage8Y immediate carrier benchmark.
      PREVOID_FREEZE_INVALID_CASH: freeze pre-Void incumbent; switch to cash only once incumbent score <= cash score.
      PREVOID_DEEPEN_INVALID_ROUTE: freeze pre-Void incumbent; route only when Breadth and Gap are both below
        their Void-entry values for streak_need consecutive Void signal days AND incumbent score <= cash score.
        Then choose 513500 if >=365d old and score > cash, else 511220; hold route until Void exit.
    """
    if mode=='BASE':
        z=base.copy(); z['route_decision']='BASE'; return z
    if mode=='IMMEDIATE_CARRIER':
        return s8y.routed_targets(base,map_panel,raw_score,feat_idx,'CARRIER')

    mp=map_panel.copy(); mp['signal_date']=pd.to_datetime(mp['signal_date']); mp=mp.set_index('signal_date')
    out=base.copy()
    targets=[]; decisions=[]
    in_void=False; incumbent=None; routed=False; route_target=None
    entry_b=np.nan; entry_g=np.nan; deep_streak=0; prev_output=None

    for r in out.itertuples(index=False):
        d=pd.Timestamp(r.signal_date)
        base_t=None if pd.isna(r.target) else str(r.target)
        quad=mp.at[d,'quadrant_511220'] if d in mp.index else None
        is_void=(quad=='DEFENSIVE_VOID')
        b=float(mp.at[d,'breadth_511220']) if d in mp.index and pd.notna(mp.at[d,'breadth_511220']) else np.nan
        g=float(mp.at[d,'gap_percentile']) if d in mp.index and pd.notna(mp.at[d,'gap_percentile']) else np.nan

        if not is_void:
            in_void=False; incumbent=None; routed=False; route_target=None; deep_streak=0
            t=base_t; dec='BASE'
        else:
            if not in_void:
                incumbent=prev_output if prev_output is not None else base_t
                entry_b=b; entry_g=g; deep_streak=0; routed=False; route_target=None; in_void=True
                t=incumbent; dec='VOID_ENTER_FREEZE_PREV'
            elif routed:
                t=route_target; dec='VOID_HOLD_ROUTED'
            else:
                if np.isfinite(b) and np.isfinite(g) and np.isfinite(entry_b) and np.isfinite(entry_g) and b<entry_b and g<entry_g:
                    deep_streak += 1
                else:
                    deep_streak = 0

                ks=score_at(raw_score,d,CASH)
                os=score_at(raw_score,d,incumbent) if incumbent is not None else np.nan
                incumbent_valid=(incumbent is not None and np.isfinite(os) and np.isfinite(ks) and os>ks)

                if mode=='PREVOID_FREEZE_INVALID_CASH':
                    if incumbent_valid:
                        t=incumbent; dec='VOID_FREEZE_VALID'
                    else:
                        routed=True; route_target=CASH; t=CASH; dec='VOID_INVALID_TO_CASH'
                else:
                    deepened=(deep_streak>=int(streak_need))
                    if incumbent_valid or not deepened:
                        t=incumbent
                        dec='VOID_FREEZE_VALID' if deepened else 'VOID_WAIT_DEEPEN'
                    else:
                        cs=score_at(raw_score,d,CARRIER)
                        carrier_ok=(age_ok(feat_idx,d,CARRIER) and np.isfinite(cs) and np.isfinite(ks) and cs>ks)
                        route_target=CARRIER if carrier_ok else CASH
                        routed=True; t=route_target
                        dec='VOID_DEEP_INVALID_TO_CARRIER' if carrier_ok else 'VOID_DEEP_INVALID_TO_CASH'
        targets.append(t); decisions.append(dec); prev_output=t

    out['target']=targets; out['route_decision']=decisions
    sides=[]; prev=None
    for t in targets:
        sides.append(side_count(prev,t)); prev=t
    out['sides']=sides
    return out


def calc_drawdowns(path,name):
    return s8m.drawdown_table(path,name,topn=10)


def main():
    db=os.getenv('ETF_DAILY_BARS_DATABASE_URL')
    if not db: raise SystemExit('Missing ETF_DAILY_BARS_DATABASE_URL')
    out=Path(os.getenv('OUTPUT_DIR','stage8za-output')); out.mkdir(parents=True,exist_ok=True)
    eng=create_engine(_db_url(db),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars['symbol']=bars['symbol'].astype(str).str.zfill(6); bars['date']=pd.to_datetime(bars['date'])
    feat=build_features(bars); feat['symbol']=feat['symbol'].astype(str).str.zfill(6); feat['date']=pd.to_datetime(feat['date'])
    feat_idx=feat.set_index(['date','symbol']).sort_index()
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    raw_score=s8m.raw_score_wide(feat,cal,list(score.columns.astype(str))); raw_delta=raw_score.diff()
    cash_ok=score[CASH].notna() & np.isfinite(score[CASH]) & (score.index>=s8m.START_FLOOR)
    first=pd.Timestamp(score.index[cash_ok][0]); start_i=int(cal.get_loc(first)); last_i=len(cal)-3
    raw=s8m.build_raw_targets(cal,score,s8m.MAIN_MEMBERS,start_i,last_i)
    prof=v1lib.build_needed_profiles(bars,set(s8m.MAIN_RISK)); pmap=prof.set_index(['date','symbol'])['resistance_pct252'].to_dict()
    v1,_=s8m.build_v1_targets(raw,score,raw_delta,pmap,s8m.MAIN_MEMBERS,s8m.MAIN_THRESHOLD)
    labels=s8q.fixed_strategy_labels(cal,score,gross,feat,bars); map_panel=s8q.build_map_panel(cal,score,feat,labels)

    specs=[
      ('ORIGINAL_V1','BASE',2),
      ('VOID_IMMEDIATE_US_CARRIER','IMMEDIATE_CARRIER',2),
      ('PREVOID_FREEZE_INVALID_CASH','PREVOID_FREEZE_INVALID_CASH',2),
    ] + [(f'PREVOID_DEEPEN{n}_INVALID_ROUTE','PREVOID_DEEPEN_INVALID_ROUTE',n) for n in STREAKS]

    paths={}; rows=[]; annuals=[]; periods=[]; routes=[]; dds=[]
    for name,mode,n in specs:
        p=build_prevoid_variant(v1,map_panel,raw_score,feat_idx,mode,n)
        q=s8m.attach_returns(p,gross,COST); q['variant']=name; paths[name]=p
        rows.append({'variant':name,'deep_streak_required':n if 'DEEPEN' in name else np.nan,**s8m.stats(q)})
        annuals.append(s8m.annual_table(q,None,name)); periods.append(s8m.period_table(q,name)); dds.append(calc_drawdowns(q,name))
        for k,v in q['route_decision'].value_counts(dropna=False).items(): routes.append({'variant':name,'decision':str(k),'days':int(v)})
        q.to_csv(out/f'{name.lower()}_daily.csv',index=False)

    summary=pd.DataFrame(rows); annual=pd.concat(annuals,ignore_index=True); periods=pd.concat(periods,ignore_index=True); route_df=pd.DataFrame(routes); dd=pd.concat(dds,ignore_index=True)
    summary.to_csv(out/'stage8za_full_summary.csv',index=False); annual.to_csv(out/'stage8za_annual.csv',index=False); periods.to_csv(out/'stage8za_periods.csv',index=False); route_df.to_csv(out/'stage8za_route_counts.csv',index=False); dd.to_csv(out/'stage8za_drawdowns.csv',index=False)

    stress=[]
    for c in (0.0006,0.0012,0.0020,0.0030):
        for name,p in paths.items():
            q=s8m.attach_returns(p,gross,c)
            stress.append({'variant':name,'cost_per_side':c,**s8m.stats(q)})
    stress=pd.DataFrame(stress); stress.to_csv(out/'stage8za_cost_stress.csv',index=False)

    md=['# Stage8ZA — Pre-Void incumbent freeze full backtest','',
        'Frozen base: Stage8M FixV2/V1(75), formal 26d weighted log-price OLS, half-life 10, 6bp per side.','',
        'Critical correction vs Stage8Z: on the first DEFENSIVE_VOID signal day, freeze the ACTUAL PRE-VOID output target from the prior signal day. The newly computed base target on the Void-entry day is not allowed to replace it.','',
        'Deepening: both Breadth and Gap percentile below their episode-entry values for N consecutive Void signal days. Route only if the frozen incumbent also no longer beats 511220. Then use 513500 only if >=365 days old and raw OLS score > 511220; otherwise 511220. Hold routed target until Void exit.','',
        'N=1/2/3 are shown as mechanism-neighborhood checks, not an ex-post optimization.','',
        '## Full summary','',summary.to_markdown(index=False),'','## Annual','',annual.to_markdown(index=False),'','## Periods','',periods.to_markdown(index=False),'','## Route counts','',route_df.to_markdown(index=False),'','## Major drawdowns','',dd.to_markdown(index=False),'','## Cost stress','',stress.to_markdown(index=False)]
    (out/'stage8za_summary.md').write_text('\n'.join(md),encoding='utf-8')
    (out/'stage8za_summary.json').write_text(json.dumps({'summary':summary.to_dict('records'),'annual':annual.to_dict('records'),'routes':route_df.to_dict('records')},ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print('\n'.join(md))

if __name__=='__main__': main()
