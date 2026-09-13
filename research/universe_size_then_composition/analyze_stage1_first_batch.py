#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

SEED=20260914

def qci(vals, rng, b=10000):
    x=np.asarray(vals,float); x=x[np.isfinite(x)]
    if len(x)==0: return {"mean":None,"lo":None,"hi":None,"p_gt0":None}
    draws=np.empty(b)
    for i in range(b): draws[i]=rng.choice(x,size=len(x),replace=True).mean()
    lo,hi=np.quantile(draws,[.025,.975])
    return {"mean":float(x.mean()),"lo":float(lo),"hi":float(hi),"p_gt0":float((draws>0).mean())}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input-dir',required=True); ap.add_argument('--output-dir',default='stage1-first-batch-analysis')
    a=ap.parse_args(); inp=Path(a.input_dir); out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    mk=pd.read_csv(inp/'monthly_k_distribution.csv'); nd=pd.read_csv(inp/'nested_15_to_3_deltas.csv'); snap=pd.read_csv(inp/'monthly_parent_pool_snapshots.csv')
    detail=pd.read_parquet(inp/'sampled_universe_detail.parquet')
    mk['year']=mk.month.str[:4].astype(int); mk['era']=np.where(mk.year<=2024,'2021-24','2025-26')
    detail['year']=detail.month.str[:4].astype(int); detail['era']=np.where(detail.year<=2024,'2021-24','2025-26')
    nd['year']=nd.month.str[:4].astype(int); nd['era']=np.where(nd.year<=2024,'2021-24','2025-26')
    era=mk.groupby(['era','k'],as_index=False).agg(months=('month','nunique'),return_mean=('return_mean','mean'),return_median=('return_median','median'),p10=('return_p10','mean'),p25=('return_p25','mean'),p75=('return_p75','mean'),p90=('return_p90','mean'),top_decile_probability=('top_decile_probability','mean'),switches=('switches_median','mean'),tenure=('tenure_median','mean'),winner_coverage=('winner_coverage_median','mean'),dormant=('dormant_share_median','mean'),effective_n=('effective_n_median','mean'))
    era.to_csv(out/'stage1_k_era_summary.csv',index=False)
    curves=mk.pivot(index='month',columns='k',values='return_mean')
    rows=[]
    for m,g in mk.groupby('month'):
        rho=float(g.k.corr(g.return_mean,method='spearman')); best=int(g.loc[g.return_mean.idxmax(),'k'])
        rows.append({'month':m,'era':'2021-24' if int(m[:4])<=2024 else '2025-26','spearman_k_return':rho,'best_k_by_mc_mean':best,'k30_minus_k3':float(curves.loc[m,30]-curves.loc[m,3])})
    shapes=pd.DataFrame(rows); shapes.to_csv(out/'stage1_month_shape.csv',index=False)
    ns=nd.groupby(['era','k_from','k_to'],as_index=False).agg(mean_delta=('delta','mean'),median_delta=('delta','median'),p_delete_improves=('delta',lambda s:float((s>0).mean())),n=('delta','size'))
    ns.to_csv(out/'stage1_nested_summary.csv',index=False)
    mc=detail[detail.source=='same_k_mc'].copy()
    rel=mc.groupby(['era','k'],as_index=False).agg(mean_return=('total_return','mean'),mean_pairwise_corr=('mean_pairwise_corr','mean'),effective_n=('effective_n','mean'),switches=('switches','mean'),tenure=('mean_top1_tenure','mean'),winner_coverage=('winner_coverage','mean'),dormant_share=('dormant_member_share','mean'))
    rel.to_csv(out/'stage1_relation_by_era_k.csv',index=False)
    rng=np.random.default_rng(SEED)
    boot={}
    for label,sub in [('all',shapes),('2021-24',shapes[shapes.era=='2021-24']),('2025-26',shapes[shapes.era=='2025-26'])]: boot[label]=qci(sub.k30_minus_k3,rng)
    counts=snap.groupby('month').size()
    report={'source_run_id':34772895471,'months':int(mk.month.nunique()),'parent_pool_recomputed':{'mean':float(counts.mean()),'median':float(counts.median()),'min':int(counts.min()),'max':int(counts.max())},'summary_json_pool_stat_bug':True,'month_shape':{'negative_spearman_share':float((shapes.spearman_k_return<0).mean()),'rho_below_minus_half_share':float((shapes.spearman_k_return<-.5).mean()),'positive_spearman_share':float((shapes.spearman_k_return>0).mean()),'best_k_3_share':float((shapes.best_k_by_mc_mean==3).mean()),'best_k_20plus_share':float((shapes.best_k_by_mc_mean>=20).mean())},'month_cluster_bootstrap_k30_minus_k3':boot,'interpretation':'Stage1 not frozen. 2021-24 shows robust negative size effect; 2025-26 point estimate reverses positive but month-bootstrap interval crosses zero. Prioritize predeclared seed convergence and corr=0.90 sensitivity before Stage2.'}
    (out/'stage1_first_batch_analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
