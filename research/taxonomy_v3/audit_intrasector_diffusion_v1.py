#!/usr/bin/env python3
"""Study whether later distinct *descriptive sub-sector* rebuilds predict pioneer persistence.

Research-only. 2026-11-12 taxonomy is retroactively applied to history: NOT
point-in-time, not an executable backtest, and no causal inference.
No later event is allowed into the state observed at an earlier checkpoint.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import audit_exact_rebuild_v1 as base

SECTOR_SILENCE = 20
CHECKPOINTS = (5,10)
N_BOOT = 2400
BROAD_EXCLUDE = {'MULTI_SECTOR','FIXED_INCOME','COMMODITY'}
UNSPECIFIC = {'BROAD','FACTOR','MEDICAL_MIXED','BIOPHARMA_MIXED',
              'PHARMA_BROAD','HEALTHCARE_BROAD','FINANCIAL_BROAD',
              'CONSUMER_BROAD','TECHNOLOGY_BROAD','UTILITIES_BROAD',
              'MATERIALS','MEDICAL_MIXED','OTHER','SECTOR_OTHER'}
# Conservative sensitivity: umbrella labels may contain narrower subsectors.
HIERARCHY_AGGREGATES = frozenset({
    'ENERGY_EQUITY','NON_BANK_FINANCIALS','INFORMATION_TECHNOLOGY','EQUIPMENT'
})


def specific(sub):
    return (pd.notna(sub) and bool(str(sub)) and
            str(sub) not in UNSPECIFIC and not str(sub).endswith('_BROAD')
            and not str(sub).endswith('_MIXED'))


def sector_name(k):
    return str(k).split('|',1)[-1]


def events_for_episodes(events, strict=True):
    """Only officially linked exact indices; different index != different sub-sector."""
    e=events.copy()
    e=e.loc[~e.broad_key.map(sector_name).isin(BROAD_EXCLUDE)]
    e=e.loc[e.subsector.notna()]
    if strict: e=e.loc[e.subsector.map(specific)]
    return e.sort_values(['broad_key','date','subsector','prior_amount','symbol'],
             ascending=[True,True,True,False,True]).copy()


def build_episodes(events, dates, silence=SECTOR_SILENCE):
    """Fresh sector episodes start after >=silence sessions without events.

    Same-date distinct subsectors are *simultaneous*, not a first-mover.
    """
    idx={d:i for i,d in enumerate(dates)}
    episodes=[]
    for broad,g in events.groupby('broad_key',sort=True):
        blocks=[];block=[];last=None
        for rec in g.to_dict('records'):
            day=idx.get(rec['date'])
            if day is None: raise ValueError('event absent from exchange calendar')
            if last is not None and day-last>=silence:
                blocks.append(block);block=[]
            block.append(rec);last=day
        if block:blocks.append(block)
        for b in blocks:
            first=b[0]['date']
            initial=[r for r in b if r['date']==first]
            subtypes=sorted({r['subsector'] for r in initial})
            if len(subtypes)>1:
                episodes.append({'broad':broad,'first_date':first,
                                 'first_day_multi':True,'events':b,
                                 'leader':None,'leader_subsector':None})
                continue
            initial.sort(key=lambda r:(-float(r['prior_amount']),str(r['symbol'])))
            pioneer=initial[0]
            episodes.append({'broad':broad,'first_date':first,
                             'first_day_multi':False,'events':b,
                             'leader':pioneer['symbol'],
                             'leader_subsector':pioneer['subsector'],
                             'leader_exact_key':pioneer['exact_key']})
    return episodes


def expansion_state(episode, observation):
    # This state is a function ONLY of events at or before the observation.
    prior=[r for r in episode['events'] if r['date']<=observation]
    seen={r['subsector']:r['date'] for r in prior}
    first={}
    for r in prior:
        first[r['subsector']]=min(first.get(r['subsector'],r['date']),r['date'])
    n=len(first)
    return {'n':n,'tier':'1' if n==1 else ('2' if n==2 else '3+'),
            'subsectors':sorted(first),
            'second_date':sorted(first.values())[1] if n>=2 else None,
            'third_date':sorted(first.values())[2] if n>=3 else None}


def checkpoints(episodes, daily, exact_daily, calendar,
                excluded_subsectors=frozenset()):
    date_to_index={d:i for i,d in enumerate(calendar)}
    lookup=daily.set_index(['date','symbol'],verify_integrity=True)
    ref=exact_daily.copy()
    ref['region']=ref.broad_key.str.split('|',n=1).str[0]
    # Dynamic eligibility: only sub-sector opportunities already eligible on the
    # pioneer DATE may enter the comparison. No future listings/counts as peers.
    specific_today=ref.loc[
        ref.subsector.map(specific) & ~ref.subsector.isin(excluded_subsectors)]
    possible={
        key:set(g.subsector.dropna())
        for key,g in specific_today.groupby(['date','broad_key'])
    }
    sector_ref=ref.groupby(['date','broad_key']).net10.median()
    region_ref=ref.groupby(['date','region']).net10.median()
    output=[];unusable=0;simultaneous=0
    for ep in episodes:
        if ep['first_day_multi']:
            simultaneous+=1
            continue
        start=date_to_index[ep['first_date']]
        possible_at_start=possible.get((ep['first_date'],ep['broad']),set())
        # Do not let a subsequently listed/newly liquid sub-sector inflate breadth.
        admitted={**ep, 'events':[e for e in ep['events']
                                   if e['subsector'] in possible_at_start]}
        for offset in CHECKPOINTS:
            if start+offset>=len(calendar):continue
            day=calendar[start+offset]
            state=expansion_state(admitted,day)
            # Ensure no future discoveries in the checkpoint state.
            assert all(x['date']<=day for x in ep['events']
                       if x['subsector'] in state['subsectors']
                       and x['date']<=day)
            leader_key=(day,ep['leader'])
            available=leader_key in lookup.index
            if not available:unusable+=1
            leader=lookup.loc[leader_key] if available else None
            alive=bool(leader.confirmed and leader.positive_streak>0) if available else False
            ret=float(leader.net10) if available and pd.notna(leader.net10) else np.nan
            region=ep['broad'].split('|',1)[0]
            sector_bench=sector_ref.get((day,ep['broad']),np.nan)
            region_bench=region_ref.get((day,region),np.nan)
            output.append({
                'date':day,'year':int(day.year),'month':str(day.to_period('M')),
                'broad':ep['broad'],'region':region,'checkpoint':offset,
                'first_date':ep['first_date'],'leader':ep['leader'],
                'leader_subsector':ep['leader_subsector'],
                'tier':state['tier'],'distinct_subsectors':state['n'],
                'start_eligible_subsectors':len(possible_at_start),
                'subsectors':'/'.join(state['subsectors']),
                'second_date':state['second_date'],'third_date':state['third_date'],
                'leader_available':bool(available),'leader_alive':alive,
                'leader_r2':float(leader.r2) if available else np.nan,
                'net10':ret,
                'excess_sector10':ret-sector_bench if pd.notna(sector_bench) else np.nan,
                'excess_region10':ret-region_bench if pd.notna(region_bench) else np.nan,
                'survive5':float(leader.survive5) if available else np.nan,
                'survive10':float(leader.survive10) if available else np.nan,
            })
    return pd.DataFrame(output),{'first_day_simultaneous_excluded':simultaneous,
                                 'leader_missing_checkpoint_rows':unusable}


def describe(z):
    out={'episodes':int(len(z)),
         'leader_available':int(z.leader_available.sum()) if len(z) else 0,
         'leader_alive_pct':round(float(z.leader_alive.mean()*100),2) if len(z) else None}
    if z.empty:return out
    for field in ('net10','excess_sector10','excess_region10','survive5','survive10'):
        ok=z[field].dropna()
        out[field+'_n']=int(len(ok))
        out[field+'_mean_pct']=round(float(ok.mean()*100),3) if len(ok) else None
        if field=='net10':
            out['net10_win_pct']=round(float((ok>0).mean()*100),2) if len(ok) else None
    return out


def bootstrap_difference(df,metric='net10'):
    """Month-block event-weighted expanded vs singleton cohort contrast."""
    d=df.loc[df.tier.isin(['1','2','3+']) & df[metric].notna()].copy()
    d['expanded']=d.tier!='1'
    g0=d.loc[~d.expanded];g1=d.loc[d.expanded]
    out={'base_n':len(g0),'expanded_n':len(g1)}
    if min(len(g0),len(g1))<5:
        out['not_estimated_reason']='FEWER_THAN_5_EACH'
        return out
    out['expanded_minus_singleton_pp']=round(float((g1[metric].mean()-g0[metric].mean())*100),4)
    month=d.groupby(['month','expanded'])[metric].agg(['sum','count']).unstack(fill_value=0)
    # Ensure both sides exist in every bootstrap aggregate via padded cells.
    allm=sorted(d.month.unique())
    sum0=np.array([g0.loc[g0.month==m,metric].sum() for m in allm])
    sum1=np.array([g1.loc[g1.month==m,metric].sum() for m in allm])
    n0=np.array([(g0.month==m).sum() for m in allm])
    n1=np.array([(g1.month==m).sum() for m in allm])
    rng=np.random.default_rng(20261112)
    draws=rng.integers(0,len(allm),(N_BOOT,len(allm)))
    den0=n0[draws].sum(axis=1)
    den1=n1[draws].sum(axis=1)
    valid=(den0>0)&(den1>0)
    if valid.sum()<N_BOOT*.8:return out
    diff=100*(sum1[draws].sum(axis=1)[valid]/den1[valid]-
              sum0[draws].sum(axis=1)[valid]/den0[valid])
    out['month_bootstrap_ci95_pp']=[round(float(x),4)
                                   for x in np.quantile(diff,[.025,.975])]
    return out


def matched_day(df,metric='net10'):
    """Day-equal contrast only on dates having both groups."""
    x=df.loc[df[metric].notna()].copy()
    x['expanded']=x.tier!='1'
    date=x.groupby(['date','expanded'])[metric].mean().unstack()
    if 0 not in date.columns or 1 not in date.columns:
        # pandas bool columns compare equal to integers, but don't assume both present.
        return {'paired_dates':0}
    matched=date.dropna()
    if matched.empty:return {'paired_dates':0}
    delta=(matched[True]-matched[False])
    return {'paired_dates':len(matched),
            'expanded_minus_singleton_pp':round(float(delta.mean()*100),4),
            'day_match_mean_pp':round(float(delta.mean()*100),4)}


def sector_year_difference(df,metric='net10'):
    """Compare within sector × year only when each exposure state occurs >=2 times."""
    z=df.loc[df[metric].notna()].copy()
    z['expanded']=z.tier!='1'
    ag=z.groupby(['broad','year','expanded'])[metric].agg(['mean','count'])
    rows=[]
    for (sec,year),x in ag.groupby(level=[0,1]):
        vals={k[2]:val for k,val in x.iterrows()}
        if set(vals)!={False,True}:continue
        if min(vals[False]['count'],vals[True]['count'])<2:continue
        rows.append({'sector':sec,'year':int(year),
                     'n0':int(vals[False]['count']),
                     'n1':int(vals[True]['count']),
                     'diff_pp':round(100*(vals[True]['mean']-vals[False]['mean']),4)})
    return {'eligible_strata':len(rows),
            'equal_strata_mean_pp':round(float(np.mean([v['diff_pp'] for v in rows])),4) if rows else None,
            'strata':rows}


def analyze(cohorts,episodes,diagnostics,source):
    if cohorts.empty:raise RuntimeError('No checkpoint observations')
    result={'contract':'ETF_REBUILD_INTRA_SECTOR_DIFFUSION_V2',
            'source':source,'research_only':True,'historical_taxonomy_pit':False,
            'diagnostics':diagnostics,'cohorts':{},'differences':{},
            'robustness':{},'recent_examples':[]}
    diagnostics['checkpoint_rows_total']=int(len(cohorts))
    diagnostics['checkpoint_rows_with_2plus_available']=int((cohorts.start_eligible_subsectors>=2).sum())
    diagnostics['checkpoint_rows_with_3plus_available']=int((cohorts.start_eligible_subsectors>=3).sum())
    # Primary: every sector episode had at least THREE specific, trade-eligible
    # sub-sector alternatives at its start, even if no others subsequently signaled.
    all_cohorts=cohorts
    cohorts=cohorts.loc[cohorts.start_eligible_subsectors>=3].copy()
    if cohorts.empty:raise RuntimeError('No structurally comparable checkpoint observations')
    for checkpoint in CHECKPOINTS:
        result['cohorts'][str(checkpoint)]={}
        result['differences'][str(checkpoint)]={}
        df=cohorts.loc[cohorts.checkpoint==checkpoint]
        for period, z in [('TRAIN',df.loc[df.date<base.SPLIT]),
                          ('VALID',df.loc[df.date>=base.SPLIT]),
                          ('2025',df.loc[df.year==2025]),('2026',df.loc[df.year==2026])]:
            result['cohorts'][str(checkpoint)][period]={
                tier:describe(z.loc[z.tier==tier]) for tier in ['1','2','3+']}
            result['differences'][str(checkpoint)][period]={
                'raw10':bootstrap_difference(z),
                'sector_excess10':bootstrap_difference(z,'excess_sector10'),
                'region_excess10':bootstrap_difference(z,'excess_region10'),
                'alive_only':bootstrap_difference(z.loc[z.leader_alive]),
                'matched_date':matched_day(z),
                'within_sector_year':sector_year_difference(z)
            }
    # Sensitivities: at least 2 initial opportunities, and current R2 gate.
    for offset in CHECKPOINTS:
        year=all_cohorts.loc[
            (all_cohorts.checkpoint==offset)&(all_cohorts.date>=base.SPLIT)]
        atleast2=year.loc[year.start_eligible_subsectors>=2]
        strict=cohorts.loc[(cohorts.checkpoint==offset)&(cohorts.date>=base.SPLIT)&
                           (cohorts.leader_r2>=.50)&cohorts.leader_alive]
        result['robustness'][str(offset)]={
            'potential_2plus':bootstrap_difference(atleast2),
            'potential_2plus_sector_excess':bootstrap_difference(atleast2,'excess_sector10'),
            'r2_gate_and_alive':bootstrap_difference(strict),
            'r2_gate_sample':int(len(strict)),
            'primary_sample':int(len(cohorts.loc[(cohorts.checkpoint==offset)&(cohorts.date>=base.SPLIT)]))
        }
    valid=cohorts.loc[cohorts.date>=base.SPLIT]
    examples=valid.loc[(valid.checkpoint==10)&(valid.tier!='1')].sort_values('date',ascending=False)
    result['recent_examples']=[
       {'first_date':str(x['first_date'].date()),'checkpoint_date':str(x['date'].date()),
        'broad':str(x['broad']),'leader':str(x['leader']),
        'leader_subsector':str(x['leader_subsector']),
        'distinct_subsectors':int(x['distinct_subsectors']),
        'subsectors':str(x['subsectors']),'leader_alive':bool(x['leader_alive'])}
       for _,x in examples.head(20).iterrows()]
    return result


def report(r):
    lines=['# 细分 ETF 重建扩散对先行者的增量预测价值 V1',
           '',
           '> 历史探索报告：2026-11-12分类回贴历史、非历史PIT。行业细分标签仅基于指数名称等已采集证据，不能等同于经成分验证的独立经济暴露。',
           '',
           '研究时间：'+r['source']['as_of']+'收盘前所有可获得历史行情；训练<=2024，验证2025–2026。',
           '先行者定义：某地区×一级行业20个交易日无合格重建后首个精确指数组的确认信号。',
           '首次日同时出现不同细分方向的样本不定义先行者；排除综合跨行业及泛化细分标签。',
           '主比较只选先行当日已具备至少3个不同细分、均有合格代表基金的地区×行业；新增上市或后来才达流动性门槛的细分不会追溯加入。',
           '固定在首信号后第5或10个市场交易日观察已出现的不同二级标签数=1、2、3+；绝不用之后才出现的重建事件分类。',
           '收益是观察日收盘确认后从次日开盘到11个市场交易日后的开盘（净、单边6bp），不是从先行日倒推，也不是可交易资金回测。',
           '',
           '## 验证期先行者：后续10日收益（事件等权）',
           '| 检查点 | 截止当日细分数 | 先行者数 | 仍在正斜率确认趋势% | 收益样本 | 10日净收益 | 同行业超额 |',
           '|---|---|---:|---:|---:|---:|---:|']
    for k in ['5','10']:
        for tier,d in r['cohorts'][k]['VALID'].items():
            fmt=lambda v: '—' if v is None else f'{v:+.3f}%'
            alive='—' if d['leader_alive_pct'] is None else str(d['leader_alive_pct'])+'%'
            lines.append('| {} | {} | {} | {} | {} | {} | {} |'.format(
                k,tier,d['episodes'],alive,d.get('net10_n',0),
                fmt(d.get('net10_mean_pct')),fmt(d.get('excess_sector10_mean_pct'))))
    lines+=['','## 相比仍单一细分方向（扩散>=2 vs 仅1）','',
            '| 检查点 | 验证收益差pp | 月份区块95%区间 | 同行业超额差pp | 控制同地区行业×年度（条件组） |',
            '|---|---:|---:|---:|---:|']
    for k in ['5','10']:
        d=r['differences'][k]['VALID']
        main=d['raw10']; exc=d['sector_excess10']
        ci=main.get('month_bootstrap_ci95_pp')
        ci_label='['+', '.join(f'{x:+.3f}' for x in ci)+']' if ci else '—'
        fmt=lambda v:'—' if v is None else f'{v:+.3f}'
        within=d['within_sector_year']
        within_label=(fmt(within['equal_strata_mean_pp'])+' (n='+str(within['eligible_strata'])+')'
                      if within['eligible_strata'] else '不可估')
        lines.append('| {} | {} | {} | {} | {} |'.format(
            k,fmt(main.get('expanded_minus_singleton_pp')),ci_label,
            fmt(exc.get('expanded_minus_singleton_pp')),within_label))
    lines+=['','## 结构可比性与R²敏感性','',
            '| 第几日 | 起点至少2个细分的收益差pp | 起点至少2个细分的行业超额差pp | R²≥0.5且先行者活跃的样本 | 该样本收益差pp |',
            '|---|---:|---:|---:|---:|']
    for k in ['5','10']:
        z=r['robustness'][k]
        fmt=lambda v:'—' if v is None else f'{v:+.3f}'
        lines.append('| {} | {} | {} | {} | {} |'.format(
            k,fmt(z['potential_2plus'].get('expanded_minus_singleton_pp')),
            fmt(z['potential_2plus_sector_excess'].get('expanded_minus_singleton_pp')),
            z['r2_gate_sample'],
            fmt(z['r2_gate_and_alive'].get('expanded_minus_singleton_pp'))))
    lines+=['','## 排除可能包含其他细分的上位标签（保守敏感性）','',
            '额外排除ENERGY_EQUITY、NON_BANK_FINANCIALS、INFORMATION_TECHNOLOGY、EQUIPMENT；只用于这次实验，不修改正式分类身份。','',
            '| 检查点 | 未扩散样本 | 扩散样本 | 净收益差pp | 同行业超额差pp |',
            '|---|---:|---:|---:|---:|']
    for k in ['5','10']:
        n=r['nested_label_sensitivity'][k]
        raw=n['raw10'];sub=n['sector_excess10']
        fmt=lambda z:'—' if z is None else f'{z:+.3f}'
        lines.append('| {} | {} | {} | {} | {} |'.format(
            k,raw['base_n'],raw['expanded_n'],
            fmt(raw.get('expanded_minus_singleton_pp')),
            fmt(sub.get('expanded_minus_singleton_pp'))))
    lines+=['','## 2025与2026分别观察','',
            '| 检查点 | 年份 | 扩散组收益差pp | 月份区块95%区间 |',
            '|---|---|---:|---:|']
    for k in ['5','10']:
        for year in ['2025','2026']:
            q=r['differences'][k][year]['raw10']
            ci=q.get('month_bootstrap_ci95_pp')
            lines.append('| {} | {} | {} | {} |'.format(
                k,year,
                f"{q['expanded_minus_singleton_pp']:+.3f}" if 'expanded_minus_singleton_pp' in q else '—',
                '['+', '.join(f'{v:+.3f}' for v in ci)+']' if ci else '—'))
    lines+=['','## 分类复核导向','',
           '- 只有二级分类标签不同才计作细分扩散；同一指数的多只ETF只算一次；一级行业本身不去重。',
           '- 严格主样本排除MULTI_SECTOR及广义、混合二级标签；同类ETF不同指数不增加细分计数。',
           '- 结构可比性：先行当日不少于3个已合格细分方向；仅统计起点即存在的具体方向，避免单一方向行业天然不可能扩散。',
           '- 真实经济独立性仍需要官方成分股、行业权重和指数规则书审计，不得据此修改经济等价分组。',
           '- 从出现信号的精确指数到细行业子类的映射应独立于本实验收益，防止回测结果反向污染分类。',
           '',
           '## 推断边界',
           '- 第一/第二/第三细分是通过2026静态标签的回溯观察，不是当年已知。历史样本存在幸存者与策略历史前视问题。',
           '- “扩散”定义只是截至检查点曾经确认出现，不代表该细分今日仍持续；先行者存活和未来收益应分别观察。',
           '- 扩散需要等待后续5或10日才观察；不能把扩散后收益冒充最初入场的收益，亦不能把已经夭折的先行者当作可执行买入。',
           '- 行业超额是事后同地区同行业ETF平均未来收益的相对比较，不是可投资基准。',
           '- 事件时间与行业市场状态关联，月份抽样不消除因果混杂；地区行业×年度条件组仅是弱控制，需新的前瞻数据复核。',
           '- 本实验试验多种窗口和分组，95%月份区块区间没有多重检验调整，小样本区间勉强不跨零不能作为已验证交易优势。',
           '- R²≥0.5条件组若仅有1个对照样本，收益差标为不可估计，不以此推论正式OLS信号。',
           '- 缺失报价、溢价/NAV公布时点、退市基金、盘中拦截与实际仓位约束均未完整入模。',
           '',
           '## 近期确认的扩散事件（静态分类回溯，仅展示）']
    for row in r['recent_examples'][:10]:
        lines.append('- {} {}：{} {}先启动（{}），至{}出现{}类：{}；检查点在趋势中：{}'.format(
            row['first_date'],row['broad'],row['leader'],row['leader_subsector'],
            row['first_date'],row['checkpoint_date'],row['distinct_subsectors'],
            row['subsectors'],row['leader_alive']))
    return '\n'.join(lines)+'\n'


def test():
    dates=list(pd.date_range('2026-01-01',periods=35,freq='D'))
    def mk(i,sub):
        return {'date':dates[i],'broad_key':'CN|HEALTHCARE','subsector':sub,
                'prior_amount':1000.,'symbol':str(i),'exact_key':'INDEX:'+sub}
    e=pd.DataFrame([mk(0,'CXO'),mk(3,'BIOTECH'),mk(7,'MEDICAL_DEVICES'),
                    mk(30,'TCM')])
    episodes=build_episodes(events_for_episodes(e),dates,silence=20)
    assert len(episodes)==2
    a=episodes[0]
    assert expansion_state(a,dates[2])['n']==1
    assert expansion_state(a,dates[3])['n']==2
    assert expansion_state(a,dates[6])['n']==2
    assert expansion_state(a,dates[7])['n']==3
    assert not specific('PHARMA_BROAD')
    x=pd.DataFrame([
        {'date':dates[i],'tier':'1' if i<5 else '2',
         'month':'2026-01','net10':.01 if i<5 else .03,
         'broad':'A','year':2026} for i in range(10)])
    assert bootstrap_difference(x)['expanded_minus_singleton_pp']==2.
    assert bootstrap_difference(x.iloc[:6]).get('not_estimated_reason')=='FEWER_THAN_5_EACH'
    print('SELF_TEST_PASS')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--bars',type=Path)
    p.add_argument('--taxonomy',type=Path)
    p.add_argument('--summary',type=Path)
    p.add_argument('--output',type=Path,default=Path('research/taxonomy_v3/output_v32/intrasector_diffusion_v1.json'))
    p.add_argument('--report',type=Path,default=Path('research/taxonomy_v3/output_v32/intrasector_diffusion_v1.md'))
    args=p.parse_args()
    if args.self_test:return test()
    if not all((args.bars,args.taxonomy,args.summary)):
        p.error('--bars --taxonomy --summary required')
    summary=json.loads(args.summary.read_text())
    digest=hashlib.sha256(args.bars.read_bytes()).hexdigest()
    if digest!=summary['archive_sha256']:
        raise ValueError('Frozen archive mismatch')
    bars=pd.read_parquet(args.bars,columns=['symbol','date','open','high','low','close','amount'])
    taxonomy=pd.read_parquet(args.taxonomy)
    daily,skipped=base.build_daily(bars,taxonomy)
    exact_daily,exact_events=base.make_variants(daily)['EXACT_PRE']
    event=events_for_episodes(exact_events)
    dates=sorted(daily.date.unique())
    episodes=build_episodes(event,dates)
    observed,diag=checkpoints(episodes,daily,exact_daily,dates)
    diag.update({'filtered_signal_events':len(event),
                 'sector_episodes':len(episodes),
                 'checkpoint_rows':len(observed),
                 'source_eligible_symbols':int(daily.symbol.nunique()),
                 'source_exact_indices':int(daily.exact_key.nunique()),
                 'distinct_subsector_labels':int(event.subsector.nunique()),
                 'skipped':skipped})
    source={'archive_sha256':digest,'as_of':str(pd.to_datetime(bars.date).max().date()),
            'taxonomy_date':summary['snapshot_date']}
    result=analyze(observed,episodes,diag,source)
    nested_events=event.loc[~event.subsector.isin(HIERARCHY_AGGREGATES)]
    nested_episodes=build_episodes(nested_events,dates)
    nested_observed,_=checkpoints(nested_episodes,daily,exact_daily,dates,
                                  excluded_subsectors=HIERARCHY_AGGREGATES)
    result['nested_label_sensitivity']={}
    for offset in CHECKPOINTS:
        section=nested_observed.loc[(nested_observed.checkpoint==offset)&
                (nested_observed.date>=base.SPLIT)&
                (nested_observed.start_eligible_subsectors>=3)]
        result['nested_label_sensitivity'][str(offset)]={
            'cohorts':{tier:describe(section.loc[section.tier==tier])
                       for tier in ('1','2','3+')},
            'raw10':bootstrap_difference(section),
            'sector_excess10':bootstrap_difference(section,'excess_sector10')}
    md=report(result)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    args.report.write_text(md)
    print(md)


if __name__=='__main__':
    main()
