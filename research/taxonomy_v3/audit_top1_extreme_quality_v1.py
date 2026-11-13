#!/usr/bin/env python3
"""V3.2 exact-index Top1 extreme-value audit, RESEARCH ONLY.

Taxonomy captured 2026-11-12 is retrofitted historically; results are NOT
historical PIT or production-investable. Does not change trading code.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
import audit_exact_rebuild_v1 as base

DATE_SPLIT = pd.Timestamp('2025-01-01')
SEED = 20261112
COST_SIDE = .0006
R2_MIN = .50
MIN_PRIOR_AMOUNT = 10_000_000.0
MIN_AGE = 400


def qualified_daily(bars, taxonomy):
    """Apply only known-at-close fields to the SAME verified equity universe."""
    daily, skipped = base.build_daily(bars, taxonomy)
    b = bars.copy()
    b.symbol = b.symbol.astype(str).str.zfill(6)
    b.date = pd.to_datetime(b.date).dt.normalize()
    for field in ('open','high','low','close','amount'):
        b[field] = pd.to_numeric(b[field], errors='coerce')
    b = b.loc[(b[['open','high','low','close']]>0).all(axis=1)&b.amount.ge(0)].copy()
    t = taxonomy[['symbol','listing_date']].copy()
    t.symbol=t.symbol.astype(str).str.zfill(6)
    t.listing_date=pd.to_datetime(t.listing_date,errors='coerce')
    b = b.merge(t,on='symbol',how='inner',validate='many_to_one')
    b = b.loc[b.listing_date.isna()|(b.date>=b.listing_date)].sort_values(['symbol','date'])
    g = b.groupby('symbol',sort=False)
    b['age'] = g.cumcount()+1
    b['ret1'] = g.close.pct_change(fill_method=None)
    b['min_ret3'] = b.groupby('symbol',sort=False).ret1.transform(
        lambda x:x.rolling(3,min_periods=3).min())
    daily = daily.merge(b[['symbol','date','age','min_ret3']],
                        on=['symbol','date'],how='left',validate='one_to_one')
    if daily.age.isna().any() or daily.min_ret3.isna().any():
        raise ValueError('missing trailing 3-day history for eligible fund')
    return daily,skipped


def rank_top(df):
    return (df.sort_values(['date','slope','r2','prior_amount','symbol'],
            ascending=[True,False,False,False,True])
            .drop_duplicates('date',keep='first').sort_values('date'))


def pools(daily):
    pre=(daily.sort_values(['date','exact_key','prior_amount','symbol'],
             ascending=[True,True,False,True])
             .drop_duplicates(['date','exact_key'],keep='first'))
    good=lambda df:df.loc[(df.slope>0)&(df.r2>=R2_MIN)&(df.min_ret3>=-.03)].copy()
    quality=pre.loc[(pre.age>=MIN_AGE)&(pre.prior_amount>=MIN_PRIOR_AMOUNT)]
    threshold=float(good(daily).loc[daily.date<DATE_SPLIT,'slope'].quantile(.99))
    if not np.isfinite(threshold) or threshold<=0:
        raise RuntimeError('Missing pre-2025 training tail threshold')
    exact=good(pre)
    z={'ALL':good(daily),'EXACT_PRE':exact,
       'QUALITY_PRE':good(quality),
       'TRAIN_P99_CAP':exact.loc[exact.slope<=threshold].copy()}
    return z,threshold


def summarize(df):
    ret=rank_top(df)
    ret=ret.loc[(ret.date>=DATE_SPLIT)&ret.net10.notna()]
    group=df.groupby('date').agg(candidates=('symbol','size'),max_slope=('slope','max'))
    group=group.loc[group.index.isin(ret.date)]
    if ret.empty:return {'days':0}
    series=ret.net10.to_numpy(float)
    return {
      'days':len(ret),
      'avg_daily_candidates':round(float(group.candidates.mean()),2),
      'median_daily_candidates':round(float(group.candidates.median()),2),
      'max_slope_p95_bps':round(float(group.max_slope.quantile(.95)*10000),2),
      'top1_avg_slope_bps':round(float(ret.slope.mean()*10000),2),
      'top1_avg_r2':round(float(ret.r2.mean()),3),
      'top1_net10_mean_pct':round(float(series.mean()*100),3),
      'top1_net10_median_pct':round(float(np.median(series)*100),3),
      'top1_net10_p10_pct':round(float(np.quantile(series,.1)*100),3),
      'top1_net10_p05_pct':round(float(np.quantile(series,.05)*100),3),
      'top1_win_pct':round(float((series>0).mean()*100),2),
      'top1_unique_funds':int(ret.symbol.nunique()),
      'top1_unique_indices':int(ret.exact_key.nunique()),
      'top1_top10_fund_share_pct':round(float(ret.symbol.value_counts().head(10).sum()/len(ret)*100),2)
    }


def matched_compare(a,b):
    top_a=rank_top(a).set_index('date')
    top_b=rank_top(b).set_index('date')
    c=top_a[['net10','symbol','exact_key','slope']].join(
        top_b[['net10','symbol','exact_key','slope']],lsuffix='_a',rsuffix='_b',how='inner')
    c=c.loc[(c.index>=DATE_SPLIT)&c.net10_a.notna()&c.net10_b.notna()]
    if c.empty:return {'paired_days':0}
    delta=c.net10_a-c.net10_b
    month=delta.groupby(delta.index.to_period('M')).agg(['sum','count'])
    sums=month['sum'].to_numpy(float);ns=month['count'].to_numpy(int)
    rng=np.random.default_rng(SEED)
    pick=rng.integers(0,len(month),size=(2000,len(month)))
    boot=100*sums[pick].sum(axis=1)/ns[pick].sum(axis=1)
    return {
        'paired_days':len(c),
        'mean_return_diff_pp':round(float(delta.mean()*100),4),
        'month_block_ci95_pp':[round(float(v),4) for v in np.quantile(boot,[.025,.975])],
        'same_fund_pct':round(float((c.symbol_a==c.symbol_b).mean()*100),2),
        'same_index_pct':round(float((c.exact_key_a==c.exact_key_b).mean()*100),2),
        'slope_p95_drop_bps':round(float((c.slope_b-c.slope_a).quantile(.95)*10000),2),
    }


def calendar_year(x):
    top=rank_top(x).loc[lambda d:d.net10.notna()]
    return {str(year):{'days':len(g),
                       'top1_net10_pct':round(float(g.net10.mean()*100),3),
                       'top1_p10_pct':round(float(g.net10.quantile(.1)*100),3)}
            for year,g in top.groupby(top.date.dt.year) if year>=2025}


def extreme_bucket(x):
    top=rank_top(x)
    top=top.loc[(top.date>=DATE_SPLIT)&top.net10.notna()].copy()
    if len(top)<20:return {}
    median, upper=top.slope.quantile([.5,.9]).to_numpy()
    top['bucket']=pd.cut(top.slope,[-np.inf,median,upper,np.inf],
         labels=['lower_50pct','middle_40pct','highest_10pct'],
         include_lowest=True)
    return {str(k):{'n':len(v),
                    'net10_pct':round(float(v.net10.mean()*100),3),
                    'p10_pct':round(float(v.net10.quantile(.1)*100),3),
                    'win_pct':round(float((v.net10>0).mean()*100),2)}
            for k,v in top.groupby('bucket',observed=True)}


def extreme_by_year(x):
    """Validation tail cohorts use ex-post thresholds; not entry rules."""
    top=rank_top(x)
    top=top.loc[(top.date>=DATE_SPLIT)&top.net10.notna()].copy()
    med,top10=top.slope.quantile([.5,.9]).to_numpy()
    top['bucket']=pd.cut(top.slope,[-np.inf,med,top10,np.inf],
        labels=['lower_50pct','middle_40pct','highest_10pct'],
        include_lowest=True)
    result={'oos_median_slope_bps':round(float(med*10000),3),
            'oos_p90_slope_bps':round(float(top10*10000),3)}
    for year,part in top.groupby(top.date.dt.year):
        result[str(year)]={}
        for bucket,g in part.groupby('bucket',observed=True):
            result[str(year)][str(bucket)]={
                'n':len(g),
                'net10_mean_pct':round(float(g.net10.mean()*100),3),
                'net10_p10_pct':round(float(g.net10.quantile(.1)*100),3)}
    return result


def analyze(daily,source,skipped):
    variants,threshold=pools(daily)
    results={'contract':'ETF_TAXONOMY_TOP1_EXTREME_V1','research_only':True,
             'historical_taxonomy_pit':False,'source':source,'skipped':skipped,
             'sample':{'eligible_funds':int(daily.symbol.nunique()),
                       'exact_indices':int(daily.exact_key.nunique()),
                       'train_p99_slope_bps':round(threshold*10000,3)},
             'variants':{k:summarize(v) for k,v in variants.items()},
             'year':{k:calendar_year(v) for k,v in variants.items()},
             'matched_vs_all':{k:matched_compare(v,variants['ALL'])
                       for k,v in variants.items() if k!='ALL'},
             'matched_vs_exact':{k:matched_compare(v,variants['EXACT_PRE'])
                       for k,v in variants.items() if k not in ('ALL','EXACT_PRE')},
             'extreme_slope':extreme_bucket(variants['EXACT_PRE']),
             'extreme_slope_by_year':extreme_by_year(variants['EXACT_PRE'])}
    return results


def fmt(x):
    return '—' if x is None else str(x)


def report(r):
    lines=['# V3.2 ETF分类后：Top1极值与质量过滤审计 V1','',
      '**研究用途**：2026-11-12分类回贴历史，不是历史PIT或可执行实盘收益。',
      '26日OLS斜率>0、R²≥0.50、近3日无<-3%跌幅；次日开盘进入、10日后开盘退出，单边成本6bp。',
      '比较池均基于相同已核实指数型股票ETF历史子集。',
      'EXACT_PRE选代表使用当日前60日成交额，先定代表再计算信号。',
      'QUALITY_PRE进一步要求至少400根上市后有效历史、前60日均成交额≥1000万元。',
      'TRAIN_P99_CAP的β上限为训练期2025年以前合格信号99分位，固定后用于2025-2026；仅是敏感性，非优化规则。',
      '',
      '## 2025–2026 Top1 与极值程度','',
      '| 候选池 | 信号日期 | 日均候选 | 最大β P95(bps/日) | Top1后10日均值 | 收益P10 |',
      '|---|---:|---:|---:|---:|---:|']
    for mode,data in r['variants'].items():
        lines.append('| {} | {} | {} | {} | {} | {} |'.format(
            mode,fmt(data.get('days')),fmt(data.get('avg_daily_candidates')),
            fmt(data.get('max_slope_p95_bps')),
            fmt(data.get('top1_net10_mean_pct')),
            fmt(data.get('top1_net10_p10_pct'))))
    lines+=['','## 同日 Top1 结果对比（相对于 ALL）','',
            '| 收缩池 | 共同日期 | 收益差pp | 月份区块95%区间 | 同一基金比例% |',
            '|---|---:|---:|---:|---:|']
    for mode,data in r['matched_vs_all'].items():
        lines.append('| {} | {} | {} | {} | {} |'.format(
          mode,data['paired_days'],fmt(data.get('mean_return_diff_pp')),
          fmt(data.get('month_block_ci95_pp')),fmt(data.get('same_fund_pct'))))
    lines+=['','## 同日 Top1 结果对比（相对于精确指数去重）','',
            '| 收缩池 | 共同日期 | 收益差pp | 月份区块95%区间 | 同一基金比例% |',
            '|---|---:|---:|---:|---:|']
    for mode,data in r['matched_vs_exact'].items():
        lines.append('| {} | {} | {} | {} | {} |'.format(
          mode,data['paired_days'],fmt(data.get('mean_return_diff_pp')),
          fmt(data.get('month_block_ci95_pp')),fmt(data.get('same_fund_pct'))))
    lines+=['','## 年度分拆','',
            '| 池 | 年份 | 有信号日 | Top1后10日均值 | 收益P10 |',
            '|---|---|---:|---:|---:|']
    for mode,years in r['year'].items():
        for year,d in years.items():
            lines.append('| {} | {} | {} | {} | {} |'.format(
               mode,year,d['days'],d['top1_net10_pct'],d['top1_p10_pct']))
    lines+=['','## β极值内部检验（EXACT_PRE 选出Top1的β分位）','',
            '| β分段 | 日期 | 后10日均值 | 收益P10 | 胜率 |',
            '|---|---:|---:|---:|---:|']
    for name,d in r['extreme_slope'].items():
        lines.append('| {} | {} | {} | {} | {} |'.format(
            name,d['n'],d['net10_pct'],d['p10_pct'],d['win_pct']))
    lines+=['','## β极值各年度表现（验证期事后分位，仅用于诊断）','',
            '| 年份 | β分组 | 日期 | 后10日均值 | 收益P10 |',
            '|---|---|---:|---:|---:|']
    for year,info in r['extreme_slope_by_year'].items():
        if year in ('oos_median_slope_bps','oos_p90_slope_bps'):continue
        for bucket,z in info.items():
            lines.append('| {} | {} | {} | {} | {} |'.format(
                year,bucket,z['n'],z['net10_mean_pct'],z['net10_p10_pct']))
    lines+=['','## 结论边界','',
        '- 收盘当日已知的价格指标不能与前一日开盘的交易可行性混同；先选代表仅按事前成交额，但当日有报价才进入研究。',
        '- 降低最大β极值是数学上的候选数效应，只有同日Top1收益、尾部和换手共同改善才算交易价值。',
        '- β的训练P99属于研究固定阈值，筛除异常的同时可能删掉真实强趋势，不应直接纳入交易。',
        '- 没有纳入历史NAV公布时点、LOF/QDII溢价、09:31与14:05盘中否决、完整持仓资金模拟、退市基金。',
        '- 2026-11-12分类没有早于2026-11-13的历史知悉证据，历史分组是静态回溯，非严格历史样本外。',
        '- 10交易日收益会重叠；月份区块bootstrap未纠正多重探索，较窄置信区间也不等于因果优势。',
        '- “β最高10%”的分位在验证期全部观察完成后才可计算，此分组仅为事后诊断，不能当作预先可交易阈值。',
        '- 数据来自归档至2026-11-11；不能直接视为当前2026-11-12收盘信号。']
    return '\n'.join(lines)+'\n'


def self_test():
    a=pd.DataFrame([
        {'date':pd.Timestamp('2026-01-05'),'symbol':'111111','exact_key':'X',
         'slope':.01,'r2':.8,'prior_amount':10,'net10':.1},
        {'date':pd.Timestamp('2026-01-05'),'symbol':'222222','exact_key':'X',
         'slope':.02,'r2':.9,'prior_amount':20,'net10':-.1},
    ])
    assert len(rank_top(a))==1 and rank_top(a).iloc[0].symbol=='222222'
    assert matched_compare(a,a)['mean_return_diff_pp']==0
    print('SELF_TEST_PASS')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--bars',type=Path)
    ap.add_argument('--taxonomy',type=Path)
    ap.add_argument('--summary',type=Path)
    ap.add_argument('--output',type=Path,
                    default=Path('research/taxonomy_v3/output_v32/top1_extreme_quality_v1.json'))
    ap.add_argument('--report',type=Path,
                    default=Path('research/taxonomy_v3/output_v32/top1_extreme_quality_v1.md'))
    a=ap.parse_args()
    if a.self_test:return self_test()
    if not (a.bars and a.taxonomy and a.summary):
        ap.error('--bars, --taxonomy, --summary required')
    src=json.loads(a.summary.read_text())
    sha=hashlib.sha256(a.bars.read_bytes()).hexdigest()
    if sha!=src['archive_sha256']:raise ValueError('frozen market archive differs')
    b=pd.read_parquet(a.bars,columns=['symbol','date','open','high','low','close','amount'])
    t=pd.read_parquet(a.taxonomy)
    d,skipped=qualified_daily(b,t)
    res=analyze(d,{'archive_sha256':sha,'as_of':str(pd.to_datetime(b.date).max().date()),
                   'taxonomy_date':src['snapshot_date']},skipped)
    md=report(res)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(res,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
    a.report.write_text(md)
    print(md)


if __name__=='__main__':
    main()
