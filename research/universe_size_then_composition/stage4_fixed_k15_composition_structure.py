#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

K=15

def sp(a,b):
    x=pd.DataFrame({'a':a,'b':b}).dropna()
    if len(x)<3:
        return np.nan
    ra=x.a.rank(method='average')
    rb=x.b.rank(method='average')
    return float(ra.corr(rb,method='pearson'))

def inclusion(df):
    rows=[]
    allr=df.total_return.astype(float)
    symbols=sorted(set().union(*df.member_set))
    for s in symbols:
        inc=df.member_set.map(lambda z:s in z)
        ni=int(inc.sum()); no=int((~inc).sum())
        rows.append({'symbol':s,'n_in':ni,'n_out':no,
                     'mean_in':float(allr[inc].mean()) if ni else np.nan,
                     'mean_out':float(allr[~inc].mean()) if no else np.nan,
                     'inclusion_contrast':float(allr[inc].mean()-allr[~inc].mean()) if ni and no else np.nan})
    return pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--stage1-dir',required=True); ap.add_argument('--output-dir',default='stage4-output')
    a=ap.parse_args(); src=Path(a.stage1_dir); out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    d=pd.read_parquet(src/'sampled_universe_detail.parquet')
    d=d[(d.source=='same_k_mc') & (d.k==K)].copy()
    d['member_set']=d.members.fillna('').map(lambda x:set(str(x).split(','))-{''})
    d['month']=d.month.astype(str); d['year']=d.month.str[:4].astype(int)
    head=[]; effects=[]; split=[]
    for m,g0 in d.groupby('month',sort=True):
        g=g0.sort_values('universe_id').reset_index(drop=True)
        r=g.total_return.astype(float)
        head.append({'month':m,'year':int(m[:4]),'n':len(g),'mean':r.mean(),'median':r.median(),'p10':r.quantile(.1),'p90':r.quantile(.9),'best':r.max(),'worst':r.min(),'p90_minus_mean':r.quantile(.9)-r.mean(),'best_minus_mean':r.max()-r.mean(),'p90_minus_p10':r.quantile(.9)-r.quantile(.1)})
        e=inclusion(g); e['month']=m; e['year']=int(m[:4]); effects.append(e)
        ga=g.iloc[::2].copy(); gb=g.iloc[1::2].copy(); ea=inclusion(ga); eb=inclusion(gb)
        z=ea.merge(eb,on='symbol',suffixes=('_a','_b'))
        z=z[(z.n_in_a>=3)&(z.n_in_b>=3)]
        split.append({'month':m,'year':int(m[:4]),'n_symbols':len(z),'spearman':sp(z.inclusion_contrast_a,z.inclusion_contrast_b)})
    h=pd.DataFrame(head); e=pd.concat(effects,ignore_index=True); sh=pd.DataFrame(split)
    adj=[]; months=sorted(e.month.unique())
    for m0,m1 in zip(months[:-1],months[1:]):
        if pd.Period(m1,'M') != pd.Period(m0,'M')+1: continue
        a0=e[(e.month==m0)&(e.n_in>=5)][['symbol','inclusion_contrast']]
        a1=e[(e.month==m1)&(e.n_in>=5)][['symbol','inclusion_contrast']]
        z=a0.merge(a1,on='symbol',suffixes=('_0','_1'))
        adj.append({'month0':m0,'month1':m1,'year1':int(m1[:4]),'n_symbols':len(z),'spearman':sp(z.inclusion_contrast_0,z.inclusion_contrast_1)})
    ad=pd.DataFrame(adj)
    def era(y): return '2021-24' if y<=2024 else '2025-26'
    h['era']=h.year.map(era); sh['era']=sh.year.map(era)
    if len(ad): ad['era']=ad.year1.map(era)
    summary={'stage':'new_stage_4','name':'fixed_k15_composition_structure_audit','k':K,'months':int(h.month.nunique()),'universes':int(len(d)),'by_era':{}}
    for er in ['2021-24','2025-26']:
        hh=h[h.era==er]; ss=sh[sh.era==er]; aa=ad[ad.era==er] if len(ad) else pd.DataFrame()
        summary['by_era'][er]={
          'months':int(len(hh)),
          'headroom_p90_minus_mean_mean':float(hh.p90_minus_mean.mean()),
          'headroom_best_minus_mean_mean':float(hh.best_minus_mean.mean()),
          'spread_p90_minus_p10_mean':float(hh.p90_minus_p10.mean()),
          'split_half_spearman_median':float(ss.spearman.median()),
          'split_half_spearman_mean':float(ss.spearman.mean()),
          'split_half_valid_months':int(ss.spearman.notna().sum()),
          'adjacent_spearman_median':float(aa.spearman.median()) if len(aa) else np.nan,
          'adjacent_spearman_mean':float(aa.spearman.mean()) if len(aa) else np.nan,
          'adjacent_valid_pairs':int(aa.spearman.notna().sum()) if len(aa) else 0}
    summary['overall']={'headroom_p90_minus_mean_mean':float(h.p90_minus_mean.mean()),'headroom_best_minus_mean_mean':float(h.best_minus_mean.mean()),'split_half_spearman_median':float(sh.spearman.median()),'adjacent_spearman_median':float(ad.spearman.median()) if len(ad) else np.nan}
    h.to_csv(out/'stage4_monthly_k15_headroom.csv',index=False)
    e.drop(columns=[],errors='ignore').to_csv(out/'stage4_monthly_symbol_inclusion_contrasts.csv',index=False)
    sh.to_csv(out/'stage4_split_half_stability.csv',index=False); ad.to_csv(out/'stage4_adjacent_month_stability.csv',index=False)
    (out/'stage4_report.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=True),encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=True))
if __name__=='__main__': main()
