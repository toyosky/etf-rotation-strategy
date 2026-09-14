#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import stage1_oracle_size_mc as s1
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from validate_fixed15_vs_full_market import FIXED15
from walk_forward_dedup import monthly_representatives
from universe.oracle_replacement_v1 import CASH_SIGNAL

K = 15
BOOT_SEED = 20260914
BOOT_N = 20000


def stage1_active(f: pd.DataFrame) -> pd.Series:
    return ((f['annual'] > 0) & (f['r2'] > 0) & (f['score'] > 0)
            & (~f['recent_drop3'].fillna(False)))


def rule_a_order(features: pd.DataFrame, prev: pd.Timestamp, parent: list[str]) -> list[str]:
    q = features.loc[(features.date == prev) & features.symbol.astype(str).isin(parent),
                     ['symbol','score','annual','r2','recent_drop3','avg_amount60']].copy()
    q['symbol'] = q.symbol.astype(str)
    q['active'] = stage1_active(q)
    q['pool_score'] = q['score'].where(q.active)
    active = q[q.pool_score.notna()].sort_values(['pool_score','avg_amount60','symbol'], ascending=[False,False,True])
    inactive = q[~q.symbol.isin(active.symbol)].sort_values(['avg_amount60','symbol'], ascending=[False,True])
    return active.symbol.tolist() + inactive.symbol.tolist()


def choose_rule_a(features, prev, parent):
    noncash = [s for s in parent if s != CASH_SIGNAL]
    order = rule_a_order(features, prev, noncash)
    return [CASH_SIGNAL] + order[:K-1]


def choose_rule_b(features, prev, parent, previous_effect: pd.DataFrame | None):
    noncash = [s for s in parent if s != CASH_SIGNAL]
    fallback = rule_a_order(features, prev, noncash)
    if previous_effect is None or previous_effect.empty:
        return None
    state = features.loc[(features.date == prev) & features.symbol.astype(str).isin(noncash),
                         ['symbol','score','annual','r2','recent_drop3','avg_amount60']].copy()
    state['symbol'] = state.symbol.astype(str)
    state['active'] = stage1_active(state)
    state['pool_score'] = state['score'].where(state.active)
    z = previous_effect[['symbol','inclusion_contrast']].copy()
    z['symbol'] = z.symbol.astype(str)
    z = z[z.symbol.isin(noncash)].merge(state[['symbol','pool_score','avg_amount60']], on='symbol', how='left')
    z = z.sort_values(['inclusion_contrast','pool_score','avg_amount60','symbol'], ascending=[False,False,False,True], na_position='last')
    chosen = z.symbol.tolist()[:K-1]
    for s in fallback:
        if s not in chosen:
            chosen.append(s)
        if len(chosen) >= K-1:
            break
    return [CASH_SIGNAL] + chosen[:K-1]


def eval_pool(pool, month, uid, signals, score, r2, slope, gross, close, ret, hist, win):
    pool = [s for s in pool if s in score.columns]
    if CASH_SIGNAL not in pool and CASH_SIGNAL in score.columns:
        pool = [CASH_SIGNAL] + pool
    pool = list(dict.fromkeys(pool))
    cm, en = s1.corr_metrics(ret, hist, pool)
    rec, _ = s1.evaluate(pool, signals, score, r2, slope, gross, close, win, cm, en, month, uid, 'stage5_simple')
    return rec


def boot_mean_ci(x: np.ndarray):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if not len(x): return [np.nan, np.nan]
    rng = np.random.default_rng(BOOT_SEED)
    vals = np.empty(BOOT_N)
    for i in range(BOOT_N): vals[i] = rng.choice(x, size=len(x), replace=True).mean()
    return [float(np.quantile(vals,.025)), float(np.quantile(vals,.975))]


def summarize(df: pd.DataFrame, rule: str):
    g = df[df.rule == rule].copy()
    if g.empty: return {}
    out = {'months':int(len(g)), 'return_mean':float(g.total_return.mean()),
           'minus_random_mean':float(g.delta_random_mean.mean()),
           'minus_random_median':float(g.delta_random_median.mean()),
           'paired_bootstrap95_minus_random_mean':boot_mean_ci(g.delta_random_mean.to_numpy()),
           'above_random_p90_share':float(g.above_random_p90.mean()),
           'random_percentile_mean':float(g.random_percentile.mean()),
           'mdd_mean':float(g.max_drawdown.mean()), 'switches_mean':float(g.switches.mean()),
           'tenure_mean':float(g.mean_top1_tenure.mean())}
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--database-url', default=os.getenv('ETF_DAILY_BARS_DATABASE_URL'))
    ap.add_argument('--stage1-dir', required=True)
    ap.add_argument('--stage4-dir', required=True)
    ap.add_argument('--output-dir', default='stage5-output')
    args=ap.parse_args()
    if not args.database_url: raise SystemExit('Missing ETF_DAILY_BARS_DATABASE_URL')
    out=Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    s1dir=Path(args.stage1_dir); s4dir=Path(args.stage4_dir)

    dist=pd.read_csv(s1dir/'monthly_k_distribution.csv')
    dist=dist[dist.k==K].copy(); dist['month']=dist.month.astype(str)
    detail=pd.read_parquet(s1dir/'sampled_universe_detail.parquet')
    detail=detail[(detail.source=='same_k_mc')&(detail.k==K)].copy(); detail['month']=detail.month.astype(str)
    effects=pd.read_csv(s4dir/'stage4_monthly_symbol_inclusion_contrasts.csv'); effects['month']=effects.month.astype(str)

    engine=create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars=load_daily_bars(engine); bars['symbol']=bars.symbol.astype(str)
    features=build_features(bars); features['symbol']=features.symbol.astype(str); features['date']=pd.to_datetime(features.date)
    cal, score, r2, slope, close, op, gross, ret=s1.build_wides(bars, features)
    by_date,_=monthly_representatives(bars, features, 0.95)

    rows=[]
    fixed15=[str(x) for x in FIXED15]
    for p, first, nxt, prev, signals in s1.month_frames(cal):
        month=str(p)
        parent=sorted((set(by_date.get(first,set())) & set(score.columns)) | {CASH_SIGNAL})
        if len(parent)<K: continue
        pos=cal.get_loc(prev); hist=cal[max(0,pos-119):pos+1]
        win=s1.winners(op, first, nxt, parent)
        drow=dist[dist.month==month]
        if drow.empty: continue
        random_mean=float(drow.iloc[0].return_mean); random_med=float(drow.iloc[0].return_median); random_p90=float(drow.iloc[0].return_p90)
        rand_returns=detail.loc[detail.month==month,'total_return'].astype(float).to_numpy()
        prev_month=str(p-1)
        prev_eff=effects[effects.month==prev_month] if prev_month in set(effects.month) else None
        pools={
          'current_score_top14':choose_rule_a(features,prev,parent),
          'lagged_inclusion_top14':choose_rule_b(features,prev,parent,prev_eff),
          'fix15':fixed15,
        }
        elig=features.loc[(features.date==prev)&features.universe_eligible.fillna(False),'symbol'].astype(str).tolist()
        pools['full_market']=sorted(set(elig)|{CASH_SIGNAL})
        for rule,pool in pools.items():
            if pool is None: continue
            rec=eval_pool(pool,month,f'{month}-{rule}',signals,score,r2,slope,gross,close,ret,hist,win)
            tr=float(rec['total_return'])
            rows.append({'month':month,'year':int(month[:4]),'rule':rule,'n_members':len(pool),'total_return':tr,
                         'max_drawdown':rec['max_drawdown'],'switches':rec['switches'],'mean_top1_tenure':rec['mean_top1_tenure'],
                         'random_mean':random_mean,'random_median':random_med,'random_p90':random_p90,
                         'delta_random_mean':tr-random_mean,'delta_random_median':tr-random_med,
                         'above_random_p90':tr>=random_p90,'random_percentile':float(np.mean(rand_returns<=tr))})
    R=pd.DataFrame(rows); R['era']=np.where(R.year<=2024,'2021-24','2025-26')
    report={'stage':'new_stage_5','name':'conservative_fixed_k15_executable_composition_audit','k':K,'bootstrap_seed':BOOT_SEED,'bootstrap_n':BOOT_N,'overall':{},'by_era':{}}
    for rule in R.rule.unique(): report['overall'][rule]=summarize(R,rule)
    for er,g in R.groupby('era'):
        report['by_era'][er]={rule:summarize(g,rule) for rule in g.rule.unique()}
    R.to_csv(out/'stage5_monthly_results.csv',index=False)
    (out/'stage5_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=True),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=True))

if __name__=='__main__': main()
