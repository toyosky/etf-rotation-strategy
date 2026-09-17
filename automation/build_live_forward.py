#!/usr/bin/env python3
from __future__ import annotations

import json, os, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

ROOT=Path(__file__).resolve().parents[1]
RESEARCH=ROOT/'research'
if str(RESEARCH) not in sys.path: sys.path.insert(0,str(RESEARCH))

import cluster90_resistance_score_v1_test as v1lib
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
import optimal_universe_reverse_engineering.oure_stage8m_fixv2_v1_long_horizon as s8m
import optimal_universe_reverse_engineering.oure_stage8q_map_comparator_robustness as s8q
import optimal_universe_reverse_engineering.oure_stage8za_prevoid_incumbent_full_backtest as s8za

START=pd.Timestamp('2026-09-14')
COST=0.0006
OUT=ROOT/'data'/'live-forward.json'
CASH='511220'; CARRIER='513500'
NAMES={'159934':'黄金','159985':'豆粕','161226':'白银','513100':'纳指100','159957':'创业板','159509':'纳指科技','513290':'纳指生物','159529':'标普消费','159981':'能源化工','501018':'原油','513530':'港股红利','511380':'可转债','164824':'印度','511220':'城投债/现金','513500':'标普500 Carrier'}
BACKTEST_REFERENCE={
  'period':'2015-01-26 → 2026-09-15',
  'baseline':{'cagr':0.4453,'mdd':-0.3130,'sharpe':1.249,'switches':298},
  'original':{'cagr':0.4058,'mdd':-0.3859,'sharpe':1.167,'switches':408},
  'freeze_cash':{'cagr':0.4443,'mdd':-0.3220,'sharpe':1.257,'switches':319}
}

def clean(v):
    if isinstance(v,(np.floating,float)):
        return None if not np.isfinite(v) else float(v)
    if isinstance(v,(np.integer,int)): return int(v)
    if isinstance(v,pd.Timestamp): return v.strftime('%Y-%m-%d')
    return v

def raw_all(cal,score):
    rows=[]; prev=None
    for i,d in enumerate(cal):
        d=pd.Timestamp(d); cur=s8m.choose_target(score,d,s8m.MAIN_MEMBERS)
        ex=pd.Timestamp(cal[i+1]) if i+1<len(cal) else pd.NaT
        end=pd.Timestamp(cal[i+2]) if i+2<len(cal) else pd.NaT
        rows.append({'signal_pos':i,'signal_date':d,'execution_date':ex,'return_end_date':end,'target':cur,'sides':s8m.side_count(prev,cur)})
        prev=cur
    return pd.DataFrame(rows)

def score(raw,d,s):
    try:
        x=raw.at[pd.Timestamp(d),s]
        return None if pd.isna(x) or not np.isfinite(x) else float(x)
    except Exception:return None

def variants(v1,map_panel,raw_score,feat_idx):
    return {
      'baseline':s8za.build_prevoid_variant(v1,map_panel,raw_score,feat_idx,'PREVOID_DEEPEN_INVALID_ROUTE',1),
      'original':s8za.build_prevoid_variant(v1,map_panel,raw_score,feat_idx,'BASE',1),
      'freeze_cash':s8za.build_prevoid_variant(v1,map_panel,raw_score,feat_idx,'PREVOID_FREEZE_INVALID_CASH',1),
    }

def fmt_exec(v,last):
    return v.strftime('%Y-%m-%d') if pd.notna(v) and pd.Timestamp(v)<=last else 'next trading day'

def intraday_mtm(path, latest_d, op, close, official_nav):
    rows=path[(pd.to_datetime(path.execution_date)==latest_d)&(pd.to_datetime(path.signal_date)>=START)]
    if rows.empty:
        return {'valuation_date':latest_d.strftime('%Y-%m-%d'),'available':False,'official_nav':float(official_nav),'mtm_nav':float(official_nav),'provisional_return':0.0}
    r=rows.iloc[-1]
    target=None if pd.isna(r.target) else str(r.target)
    sides=int(getattr(r,'sides',0) or 0)
    gross_ret=0.0; open_px=None; close_px=None
    if target is not None and target in op.columns and target in close.columns:
        a=op.at[latest_d,target]; b=close.at[latest_d,target]
        if pd.notna(a) and pd.notna(b) and np.isfinite(a) and np.isfinite(b) and float(a)>0:
            open_px=float(a); close_px=float(b); gross_ret=float(b/a-1.0)
    net_ret=(1.0+gross_ret)*(1.0-COST*sides)-1.0
    return {
      'valuation_date':latest_d.strftime('%Y-%m-%d'),'available':True,
      'signal_date':pd.Timestamp(r.signal_date).strftime('%Y-%m-%d'),
      'execution_date':latest_d.strftime('%Y-%m-%d'),'target':target,
      'target_name':NAMES.get(target,'现金') if target else '现金',
      'decision':str(getattr(r,'route_decision','BASE')),
      'sides':sides,'open':open_px,'close':close_px,
      'gross_return':gross_ret,'provisional_return':net_ret,
      'official_nav':float(official_nav),'mtm_nav':float(official_nav*(1.0+net_ret)),
      'mtm_total_return':float(official_nav*(1.0+net_ret)-1.0)
    }

def main():
    db=os.getenv('ETF_DAILY_BARS_DATABASE_URL')
    if not db: raise SystemExit('Missing ETF_DAILY_BARS_DATABASE_URL')
    eng=create_engine(_db_url(db),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars['symbol']=bars['symbol'].astype(str).str.zfill(6); bars['date']=pd.to_datetime(bars['date'])
    feat=build_features(bars); feat['symbol']=feat['symbol'].astype(str).str.zfill(6); feat['date']=pd.to_datetime(feat['date'])
    feat_idx=feat.set_index(['date','symbol']).sort_index()
    cal,score_w,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    raw_score=s8m.raw_score_wide(feat,cal,list(score_w.columns.astype(str))); raw_delta=raw_score.diff()
    raw=raw_all(cal,score_w)
    profiles=v1lib.build_needed_profiles(bars,set(s8m.MAIN_RISK)); pmap=profiles.set_index(['date','symbol'])['resistance_pct252'].to_dict()
    v1,_=s8m.build_v1_targets(raw,score_w,raw_delta,pmap,s8m.MAIN_MEMBERS,s8m.MAIN_THRESHOLD)
    labels=s8q.fixed_strategy_labels(cal,score_w,gross,feat,bars); mp=s8q.build_map_panel(cal,score_w,feat,labels)
    vs=variants(v1,mp,raw_score,feat_idx)

    latest_d=pd.Timestamp(cal[-1])
    completed_signal_max=pd.Timestamp(cal[-3]) if len(cal)>=3 else pd.Timestamp.min
    series={}; summaries={}; events={}; mark_to_market={}
    for key,p in vs.items():
        q=s8m.attach_returns(p,gross,COST)
        q=q[(q.signal_date>=START)&(q.signal_date<=completed_signal_max)].copy()
        eq=(1+q.net_ret).cumprod() if len(q) else pd.Series(dtype=float)
        peak=np.maximum.accumulate(eq.to_numpy()) if len(q) else np.array([])
        dd=eq.to_numpy()/peak-1 if len(q) else np.array([])
        series[key]=[{'signal_date':r.signal_date.strftime('%Y-%m-%d'),'execution_date':r.execution_date.strftime('%Y-%m-%d'),'valuation_date':r.return_end_date.strftime('%Y-%m-%d'),'target':None if pd.isna(r.target) else str(r.target),'target_name':NAMES.get(str(r.target),'') if pd.notna(r.target) else '现金','daily_return':float(r.net_ret),'nav':float(eq.iloc[i]),'drawdown':float(dd[i]),'status':'settled'} for i,r in enumerate(q.itertuples(index=False))]
        targets=q.target.where(q.target.notna(),'__CASH__').astype(str).tolist()
        switches=sum(a!=b for a,b in zip(targets[1:],targets[:-1]))
        official_nav=float(eq.iloc[-1]) if len(eq) else 1.0
        summaries[key]={'total_return':official_nav-1.0,'mdd':float(dd.min()) if len(dd) else 0.0,'sessions':int(len(q)),'switches':int(switches),'turnover_sides':int(q.sides.sum()) if len(q) else 0}
        mark_to_market[key]=intraday_mtm(p,latest_d,op,close,official_nav)
        pf=p[p.signal_date>=START].copy(); ev=[]; prev=None
        for r in pf.itertuples(index=False):
            t=None if pd.isna(r.target) else str(r.target)
            if t!=prev:
                ev.append({'signal_date':r.signal_date.strftime('%Y-%m-%d'),'execution_date':fmt_exec(r.execution_date,latest_d),'from':prev,'to':t,'to_name':NAMES.get(t,'现金') if t else '现金','decision':getattr(r,'route_decision','BASE')})
            prev=t
        events[key]=ev

    base=vs['baseline']; lr=base[base.signal_date==latest_d].iloc[-1] if (base.signal_date==latest_d).any() else base.iloc[-1]
    mp2=mp.copy(); mp2['signal_date']=pd.to_datetime(mp2['signal_date']); mrow=mp2[mp2.signal_date==latest_d].iloc[-1] if (mp2.signal_date==latest_d).any() else mp2.iloc[-1]
    target=None if pd.isna(lr.target) else str(lr.target)
    latest={'date':latest_d.strftime('%Y-%m-%d'),'target':target,'target_name':NAMES.get(target,'现金') if target else '现金','decision':str(getattr(lr,'route_decision','BASE')),'quadrant':str(mrow.get('quadrant_511220','')),'breadth_pct':float(mrow.get('breadth_511220',np.nan))*100 if pd.notna(mrow.get('breadth_511220',np.nan)) and float(mrow.get('breadth_511220'))<=1.0 else clean(mrow.get('breadth_511220')),'gap_percentile':clean(mrow.get('gap_percentile')),'target_score':score(raw_score,latest_d,target) if target else None,'cash_score':score(raw_score,latest_d,CASH),'carrier_score':score(raw_score,latest_d,CARRIER),'completed_through':latest_d.strftime('%Y-%m-%d'),'performance_signal_through':completed_signal_max.strftime('%Y-%m-%d')}

    payload={'version':'Void Route Baseline v1','tracking_start':'2026-09-14','pricing':'Tencent HFQ daily bars','cost_per_side':COST,'execution_model':'signal at close; execute next trading-day open; settled return measured to following trading-day open; latest execution day also marked to latest close','generated_from_market_data_through':latest_d.strftime('%Y-%m-%d'),'backtest_reference':BACKTEST_REFERENCE,'latest':latest,'summary':summaries,'mark_to_market':mark_to_market,'series':series,'events':events,'notes':['Forward model tracking, not broker-confirmed fills.','Settled NAV preserves the frozen backtest open-to-open convention; mark_to_market adds the latest observable execution-day open-to-close move without rewriting settled history.','Tracking inherits the strategy state existing at the start date; no artificial re-entry cost is charged solely because the dashboard starts on 2026-09-14.','Frozen baseline: pre-Void incumbent freeze; Deepen1 + incumbent invalidation; healthy 513500 else 511220.','Original V1 and Freeze→Cash remain shadow controls.']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'latest':latest,'summary':summaries,'mark_to_market':mark_to_market},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
