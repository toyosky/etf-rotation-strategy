#!/usr/bin/env python3
from __future__ import annotations

import os, sys
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

COST=0.0006


def year_block(q, start, end):
    z=q[(q['signal_date']>=pd.Timestamp(start))&(q['signal_date']<=pd.Timestamp(end))].copy()
    return s8m.stats(z) if len(z) else {}


def main():
    db=os.getenv('ETF_DAILY_BARS_DATABASE_URL')
    if not db: raise SystemExit('Missing ETF_DAILY_BARS_DATABASE_URL')
    out=Path(os.getenv('OUTPUT_DIR','stage8zb-output')); out.mkdir(parents=True,exist_ok=True)
    eng=create_engine(_db_url(db),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars['symbol']=bars['symbol'].astype(str).str.zfill(6); bars['date']=pd.to_datetime(bars['date'])
    feat=build_features(bars); feat['symbol']=feat['symbol'].astype(str).str.zfill(6); feat['date']=pd.to_datetime(feat['date'])
    feat_idx=feat.set_index(['date','symbol']).sort_index()
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    raw_score=s8m.raw_score_wide(feat,cal,list(score.columns.astype(str))); raw_delta=raw_score.diff()
    cash_ok=score['511220'].notna() & np.isfinite(score['511220']) & (score.index>=s8m.START_FLOOR)
    first=pd.Timestamp(score.index[cash_ok][0]); start_i=int(cal.get_loc(first)); last_i=len(cal)-3
    raw=s8m.build_raw_targets(cal,score,s8m.MAIN_MEMBERS,start_i,last_i)
    prof=v1lib.build_needed_profiles(bars,set(s8m.MAIN_RISK)); pmap=prof.set_index(['date','symbol'])['resistance_pct252'].to_dict()
    v1,_=s8m.build_v1_targets(raw,score,raw_delta,pmap,s8m.MAIN_MEMBERS,s8m.MAIN_THRESHOLD)
    labels=s8q.fixed_strategy_labels(cal,score,gross,feat,bars); map_panel=s8q.build_map_panel(cal,score,feat,labels)

    variants={'ORIGINAL_V1':('BASE',None),'FREEZE_INVALID_CASH':('FREEZE',None)}
    for n in (1,2,3): variants[f'DEEPEN{n}_ROUTE']=('DEEPEN',n)

    built={}
    for name,(mode,n) in variants.items():
        if mode=='BASE':
            p=v1.copy(); p['route_decision']='BASE'
        elif mode=='FREEZE':
            p=s8za.build_prevoid_variant(v1,map_panel,raw_score,feat_idx,'PREVOID_FREEZE_INVALID_CASH')
        else:
            p=s8za.build_prevoid_variant(v1,map_panel,raw_score,feat_idx,'PREVOID_DEEPEN_INVALID_ROUTE',streak_need=n)
        built[name]=s8m.attach_returns(p,gross,COST)

    windows=[
      ('2015_2022','2015-01-01','2022-12-31'),
      ('2023_2026','2023-01-01','2026-12-31'),
      ('2015_2018','2015-01-01','2018-12-31'),
      ('2019_2022','2019-01-01','2022-12-31'),
      ('2023_2024','2023-01-01','2024-12-31'),
      ('2025_2026','2025-01-01','2026-12-31'),
    ]
    rows=[]
    for name,q in built.items():
        for w,a,b in windows:
            st=year_block(q,a,b); rows.append({'variant':name,'window':w,**st})
    sub=pd.DataFrame(rows)
    sub.to_csv(out/'stage8zb_subperiods.csv',index=False)

    annual_rows=[]
    for name,q in built.items():
        for y in range(2016,2027):
            st=year_block(q,f'{y}-01-01',f'{y}-12-31'); annual_rows.append({'variant':name,'year':y,**st})
    annual=pd.DataFrame(annual_rows); annual.to_csv(out/'stage8zb_annual_oos.csv',index=False)

    rel=[]
    base=sub[sub.variant=='ORIGINAL_V1'].set_index('window')
    for name in [x for x in variants if x!='ORIGINAL_V1']:
        z=sub[sub.variant==name].set_index('window')
        for w in base.index:
            if w in z.index:
                rel.append({'variant':name,'window':w,
                            'delta_cagr':z.at[w,'cagr']-base.at[w,'cagr'],
                            'delta_mdd_abs':abs(base.at[w,'mdd'])-abs(z.at[w,'mdd']),
                            'delta_sharpe':z.at[w,'sharpe_0rf']-base.at[w,'sharpe_0rf'],
                            'delta_switches':z.at[w,'switches']-base.at[w,'switches']})
    rel=pd.DataFrame(rel); rel.to_csv(out/'stage8zb_relative.csv',index=False)

    md=['# Stage8ZB — Walk-forward / subperiod robustness audit','',
        'Mechanism is frozen ex ante: pre-Void incumbent freeze; route only when incumbent no longer beats 511220 and Void deepens. N=1/2/3 are robustness neighbors, not optimized inside evaluation windows.','',
        '## Relative vs ORIGINAL_V1','',rel.to_markdown(index=False),'','## Subperiod raw stats','',sub.to_markdown(index=False),'','## Annual pseudo-OOS','',annual.to_markdown(index=False)]
    (out/'stage8zb_summary.md').write_text('\n'.join(md),encoding='utf-8')
    print('\n'.join(md))

if __name__=='__main__': main()
