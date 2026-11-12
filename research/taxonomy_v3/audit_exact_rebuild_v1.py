#!/usr/bin/env python3
"""Research-only exact-index ETF OLS rebuilding event and trend-age audit.

The taxonomy is a 2026-11-12 snapshot. Group labels before 2026-11-13
are retrospective and NOT point-in-time (PIT) verified. This is not a
backtest of the user's live execution strategy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

WINDOW = 26
MIN_HISTORY = 200
MIN_PRIOR_AMOUNT = 3_000_000
COST_SIDE = .0006
START = pd.Timestamp('2021-01-01')
SPLIT = pd.Timestamp('2025-01-01')
COOLDOWN = 20


def ols26(close):
    n = len(close)
    beta = np.full(n, np.nan)
    r2 = np.full(n, np.nan)
    if n < WINDOW:
        return beta, r2
    y = np.lib.stride_tricks.sliding_window_view(np.log(close), WINDOW)
    x = np.arange(WINDOW, dtype=float)
    xc = x - x.mean()
    means = y.mean(axis=1)
    b = ((y - means[:, None]) @ xc) / (xc * xc).sum()
    fit = means[:, None] + b[:, None] * xc[None, :]
    sst = ((y - means[:, None]) ** 2).sum(axis=1)
    sse = ((y - fit) ** 2).sum(axis=1)
    beta[WINDOW-1:] = b
    r2[WINDOW-1:] = np.where(sst > 1e-14, np.clip(1-sse/np.maximum(sst, 1e-14), 0, 1), 0)
    return beta, r2


def age_bucket(n):
    if n <= 2: return '01-02'
    if n <= 5: return '03-05'
    if n <= 10: return '06-10'
    if n <= 20: return '11-20'
    return '21+'


def summarize(df):
    if df.empty:
        return {'events': 0, 'signal_days': 0}
    byday = df.groupby('date').agg(ret=('net10','mean'), n=('symbol','size'))
    net = df.net10.dropna()
    result = {'events': int(len(df)), 'signal_days': int(len(byday)),
              'forward10_observed': int(len(net)),
              'mean_candidates_per_signal_day': round(float(byday.n.mean()), 2)}
    if len(net):
        result.update(event_net10_pct=round(float(net.mean()*100), 3),
                      day_equal_net10_pct=round(float(byday.ret.dropna().mean()*100), 3),
                      median_net10_pct=round(float(net.median()*100), 3),
                      win_pct=round(float((net>0).mean()*100), 2))
    return result


def build_daily(bars, taxonomy):
    required = {'symbol','date','open','high','low','close','amount'}
    if not required.issubset(bars): raise ValueError('Missing OHLC/turnover fields')
    bars = bars.copy()
    bars.symbol = bars.symbol.astype(str).str.zfill(6)
    bars.date = pd.to_datetime(bars.date).dt.normalize()
    if bars.duplicated(['symbol','date']).any(): raise ValueError('Duplicate source quotes')
    bars = bars.sort_values(['symbol','date'])
    for c in ['open','high','low','close','amount']:
        bars[c] = pd.to_numeric(bars[c], errors='coerce')
    bars = bars.loc[(bars[['open','high','low','close']]>0).all(axis=1) & bars.amount.ge(0)]
    global_dates = sorted(bars.date.unique())
    day_ids = {d:i for i,d in enumerate(global_dates)}
    taxonomy = taxonomy.copy()
    taxonomy.symbol = taxonomy.symbol.astype(str).str.zfill(6)
    if taxonomy.symbol.duplicated().any(): raise ValueError('Overlapping classification rows')
    taxonomy = taxonomy.loc[
        (taxonomy.classification_status == 'VERIFIED_CURRENT_INDEX') &
        (taxonomy.exposure_type == 'EQUITY') &
        taxonomy.exact_index_key.notna() &
        taxonomy.sector_level1.notna() &
        taxonomy.region_primary.notna()
    ].set_index('symbol')
    clash = taxonomy.groupby('exact_index_key').agg(
        region=('region_primary','nunique'), asset=('exposure_type','nunique'))
    if ((clash.region>1)|(clash.asset>1)).any():
        raise ValueError('Exact identity mixes incompatible regions or asset types')
    rows = []
    skipped = defaultdict(int)
    for code, g in bars.groupby('symbol', sort=True):
        if code not in taxonomy.index:
            skipped['outside_verified_equity'] += 1
            continue
        m = taxonomy.loc[code]
        if pd.notna(m.get('listing_date')):
            g = g.loc[g.date>=pd.Timestamp(m.listing_date)]
        if len(g) < MIN_HISTORY+12:
            skipped['insufficient_postlisting_history'] += 1
            continue
        g = g.reset_index(drop=True)
        close = g.close.to_numpy(float)
        op = g.open.to_numpy(float)
        n = len(g)
        beta, r2 = ols26(close)
        ix = np.arange(n)
        ids = np.array([day_ids[d] for d in g.date])
        prior_amount = g.amount.shift(1).rolling(60,min_periods=60).mean().to_numpy()
        contiguous = np.zeros(n, dtype=bool)
        contiguous[60:] = ids[60:] - ids[:-60] == 60
        # Eligibility uses the ten sessions ending yesterday, not today's volume.
        vol10 = (g.amount.shift(1).gt(0).rolling(10,min_periods=10).sum()==10).to_numpy()
        eligible = (ix>=MIN_HISTORY)&(prior_amount>=MIN_PRIOR_AMOUNT)&contiguous&vol10
        eligible &= g.date.to_numpy() >= START.to_datetime64()
        ret1 = np.r_[np.nan,close[1:]/close[:-1]-1]
        crosses = np.flatnonzero((beta[1:]>0)&(beta[:-1]<=0))+1
        qualifies = set()
        for s in crosses:
            for j in range(s+1,min(s+4,n)):
                if (eligible[j] and beta[j]>0 and r2[j]>r2[s] and
                    r2[j]>r2[j-1] and j>=2 and (ret1[j-2:j+1]>=-.03).all()):
                    qualifies.add(j)
                    break
        streak = np.zeros(n, dtype=int)
        confirmed = np.zeros(n, dtype=bool)
        confirmed_alive = False
        for i in range(n):
            if np.isfinite(beta[i]) and beta[i]>0:
                streak[i] = 1+(streak[i-1] if i else 0)
            else:
                confirmed_alive = False
            if i in qualifies:
                confirmed_alive = True
            confirmed[i] = confirmed_alive
        fwd = np.full(n, np.nan)
        for i in range(n-11):
            if ids[i+11]-ids[i] == 11:
                fwd[i] = op[i+11]/op[i+1]*(1-COST_SIDE)**2-1
        survival = {}
        for h in (5,10):
            s = np.full(n,np.nan)
            for i in range(n-h):
                if ids[i+h]-ids[i] == h:
                    s[i] = float(np.all(beta[i+1:i+h+1]>0))
            survival[h] = s
        for i in np.flatnonzero(eligible):
            rows.append((
                g.date.iloc[i],code,str(m.exact_index_key),
                str(m.region_primary)+'|'+str(m.sector_level1),
                None if pd.isna(m.sector_level2) else str(m.sector_level2),
                float(prior_amount[i]), i in qualifies, int(streak[i]),
                bool(confirmed[i]),float(beta[i]),float(r2[i]),float(fwd[i]),
                float(survival[5][i]),float(survival[10][i])
            ))
    cols = ['date','symbol','exact_key','broad_key','subsector',
            'prior_amount','signal','positive_streak','confirmed','slope','r2',
            'net10','survive5','survive10']
    daily = pd.DataFrame(rows,columns=cols)
    if daily.empty: raise RuntimeError('No eligible symbols')
    return daily,dict(skipped)


def make_variants(daily):
    result = {}
    global_days = {d:i for i,d in enumerate(sorted(daily.date.unique()))}
    for mode,key in [('ALL',None),('EXACT_PRE','exact_key'),('BROAD_PRE','broad_key')]:
        selected = (daily.copy() if key is None else
                    daily.sort_values(['date',key,'prior_amount','symbol'],
                                      ascending=[True,True,False,True])
                    .drop_duplicates(['date',key],keep='first'))
        events = selected.loc[selected.signal].sort_values(['date','symbol'])
        if key is not None:
            kept = []
            last = {}
            for ix,rec in events.iterrows():
                day = global_days[rec.date]
                if day-last.get(rec[key],-10000)<COOLDOWN: continue
                last[rec[key]] = day
                kept.append(ix)
            events = events.loc[kept]
        result[mode] = (selected,events)
    return result


def paired_months(a,b):
    """Difference in matched calendar-date equal-weight returns, with month blocks."""
    x = a.groupby('date').net10.mean().to_frame('a')
    y = b.groupby('date').net10.mean().to_frame('b')
    both = x.join(y,how='inner').dropna()
    both = both.loc[both.index>=SPLIT]
    if both.empty:
        return {'paired_dates':0}
    z = both.a-both.b
    months = z.groupby(z.index.to_period('M'))
    sums = months.sum().to_numpy(float)
    counts = months.size().to_numpy(int)
    rng = np.random.default_rng(20261112)
    draws = rng.integers(0,len(sums),size=(2000,len(sums)))
    boot = 100*sums[draws].sum(axis=1)/counts[draws].sum(axis=1)
    return {'paired_dates':int(len(z)),
            'mean_difference_pp':round(float(z.mean()*100),4),
            'month_block_ci95_pp':[round(float(v),4) for v in np.quantile(boot,[.025,.975])]}


def build_report(daily,modes,source,skipped):
    result = {'contract':'ETF_EXACT_REBUILD_EXPLORATORY_V1',
              'source':source,
              'not_historical_pit':True,'not_executable_backtest':True,
              'skipped_symbols':skipped,'metrics':{},'age_cohorts':{},
              'taxonomy_audit':{
                  'eligible_symbol_days':int(len(daily)),
                  'eligible_symbols':int(daily.symbol.nunique()),
                  'exact_indices':int(daily.exact_key.nunique()),
                  'broad_groups':int(daily.broad_key.nunique()),
                  'subsector_unknown_symbols':int(daily.loc[daily.subsector.isna(),'symbol'].nunique())}}
    result['paired_vs_all_valid'] = {
        mode:paired_months(modes[mode][1],modes['ALL'][1])
        for mode in ('EXACT_PRE','BROAD_PRE')}
    # Audit how many distinct official indices each broad sector would erase.
    grouped = daily[['broad_key','exact_key','subsector']].drop_duplicates()
    rank = (grouped.groupby('broad_key').agg(
                exact_indices=('exact_key','nunique'),
                subsectors=('subsector','nunique'))
            .sort_values('exact_indices',ascending=False).head(12))
    result['broad_group_compression_top12'] = [
        {'broad_group':key,'exact_indices':int(v.exact_indices),
         'verified_subsectors':int(v.subsectors)} for key,v in rank.iterrows()]
    for mode,(_,ev) in modes.items():
        result['metrics'][mode] = {}
        for name,frame in [('TRAIN',ev.loc[ev.date<SPLIT]),
                           ('VALID',ev.loc[ev.date>=SPLIT]),
                           ('2025',ev.loc[ev.date.dt.year==2025]),
                           ('2026',ev.loc[ev.date.dt.year==2026])]:
            obj = summarize(frame)
            if mode=='EXACT_PRE':
                for h in (5,10):
                    z = frame['survive'+str(h)].dropna()
                    obj['d'+str(h)+'_mature_events'] = int(len(z))
                    obj['d'+str(h)+'_survival_pct'] = (
                        round(float(z.mean()*100),2) if len(z) else None)
            result['metrics'][mode][name] = obj
    # Daily observations of ongoing positive OLS, NOT independent events.
    positive = modes['EXACT_PRE'][0]
    positive = positive.loc[positive.confirmed & (positive.positive_streak>0)].copy()
    positive['age_bucket'] = positive.positive_streak.map(age_bucket)
    result['age_paired_valid'] = {}
    for name,g in [('TRAIN',positive.loc[positive.date<SPLIT]),
                   ('VALID',positive.loc[positive.date>=SPLIT])]:
        result['age_cohorts'][name] = {}
        for age,frame in g.groupby('age_bucket'):
            obj = summarize(frame)
            obj['mean_r2'] = round(float(frame.r2.mean()),3)
            strict = summarize(frame.loc[frame.r2>=0.5])
            obj['r2_ge_0_5_observations'] = strict['events']
            obj['r2_ge_0_5_day_equal_net10_pct'] = strict.get('day_equal_net10_pct')
            result['age_cohorts'][name][age] = obj
    cohorts = positive.loc[positive.date>=SPLIT]
    baseline = cohorts.loc[cohorts.age_bucket=='03-05']
    for age in ('01-02','06-10','11-20','21+'):
        follow = cohorts.loc[cohorts.age_bucket==age]
        result['age_paired_valid'][age+'_vs_03-05'] = paired_months(follow,baseline)
    lines = ['# ETF精确指数去重与重建持续性 V1（探索性）','',
       '冻结分类：2026-11-12；冻结行情截止：'+source['as_of']+'。','',
       '**本报告的2021–2026历史分组套用了2026-11-12分类，非严格历史PIT，不是可交易策略回测。**','',
       '26日非加权OLS斜率翻正、1–3日内R²改善；以信号日前60日成交额确定唯一指数代表；组内20交易日冷却。','',
       '## 相同基金范围的候选池比较（2025–2026）','',
       '| 候选池 | 事件 | 信号日 | 日均候选 | 10日净收益（日等权） |',
       '|---|---:|---:|---:|---:|']
    for mode in ('ALL','EXACT_PRE','BROAD_PRE'):
        v = result['metrics'][mode]['VALID']
        val = v.get('day_equal_net10_pct')
        lines.append('| {} | {} | {} | {} | {} |'.format(
            mode,v['events'],v['signal_days'],
            v.get('mean_candidates_per_signal_day','—'),
            ('{:+.3f}%'.format(val) if val is not None else '—')))
    lines += ['','## 相同日期配对（相对 ALL 的日等权10日净收益差）','',
               '| 比较 | 共同交易日 | 差值百分点 | 月份区块95%区间 |',
               '|---|---:|---:|---:|']
    for mode,obj in result['paired_vs_all_valid'].items():
        interval=obj.get('month_block_ci95_pp')
        label='['+', '.join('{:+.3f}'.format(t) for t in interval)+']' if interval else '—'
        lines.append('| {} | {} | {:+.4f} | {} |'.format(
            mode,obj.get('paired_dates',0),obj.get('mean_difference_pp',float('nan')),label))
    lines += ['','## 粗行业会合并最多不同指数的分组','',
              '| 区域×行业 | 精确指数 | 已确认细分标签 |',
              '|---|---:|---:|']
    for x in result['broad_group_compression_top12']:
        lines.append('| {} | {} | {} |'.format(
            x['broad_group'],x['exact_indices'],x['verified_subsectors']))
    lines += ['','## 精确指数重建事件存续（完整成熟样本）','']
    for name in ('TRAIN','VALID'):
        obj = result['metrics']['EXACT_PRE'][name]
        lines.append('{}：D5 {}%（{}事件），D10 {}%（{}事件）。'.format(
            name,obj['d5_survival_pct'],obj['d5_mature_events'],
            obj['d10_survival_pct'],obj['d10_mature_events']))
    lines += ['','## 已确认且未中断重建：连续正斜率天数与之后10日表现（2025–2026）','',
       '| 已连续天数 | 基金日观察 | 日等权10日净收益 | R²≥0.5样本数 |',
       '|---|---:|---:|---:|']
    for age,obj in sorted(result['age_cohorts']['VALID'].items()):
        value = obj.get('day_equal_net10_pct')
        lines.append('| {} | {} | {} | {} |'.format(
            age,obj['events'],('{:+.3f}%'.format(value) if value is not None else '—'),
            obj['r2_ge_0_5_observations']))
    lines += ['','## 已确认重建持续期的同日配对（相对3–5天）','',
        '| 连续天数 | 共同日期 | 10日收益差pp | 月份区块95%区间 |',
        '|---|---:|---:|---:|']
    for label,obj in result['age_paired_valid'].items():
        interval=obj.get('month_block_ci95_pp')
        ci=('['+', '.join('{:+.3f}'.format(v) for v in interval)+']') if interval else '—'
        lines.append('| {} | {} | {} | {} |'.format(
            label,obj.get('paired_dates',0),
            '{:+.3f}'.format(obj['mean_difference_pp']) if 'mean_difference_pp' in obj else '—',ci))
    lines += ['','## 审计边界','',
       '- 历史分类并非当时可知；退市基金及变更合同历史尚缺。不能据此确定历史策略收益。',
       '- 部分产品尚缺完整交易属性、NAV公布时点、溢价与盘中拦截证据。',
       '- 事件收益使用次一开盘到第11根开盘，单边6bp；是重叠事件研究，不是仓位回测。',
       '- 当日若基金停牌或缺失收盘行情，该研究数据不会生成该基金的日期行；不能声称已完整处理所有潜在代表的开盘前资格。',
       '- 只有此前在该基金完成1–3日确认且自此β持续为正的观察才进入持续期分组；代表切换仍需单独核查。',
       '- 正斜率持续天数是当日已知量，事后分组不能被误读为独立或因果预测。',
       '- 粗行业去重仅作敏感性；不同指数不能未经官方证据直接合并。',
       '- 后续需同日匹配、月份区块置信区间，以及2026-11-13以后的真正前瞻影子记录。',
       '- 发现指数键、区域、细行业冲突，进入人工官方证据复核；不得按收益好坏重贴标签。']
    return result,'\n'.join(lines)+'\n'


def self_test():
    close = np.exp(np.linspace(0,1,60))
    b,r = ols26(close)
    assert b[-1]>0 and r[-1]>.999999
    assert age_bucket(2)=='01-02' and age_bucket(9)=='06-10'
    assert summarize(pd.DataFrame(columns=['date','symbol','net10']))['events']==0
    toy = pd.DataFrame({'date':[pd.Timestamp('2026-01-02')]*2,
                        'symbol':['000001','000002'],
                        'exact_key':['X','X'],
                        'broad_key':['CN|HEALTHCARE']*2,
                        'prior_amount':[10.0,20.0],
                        'signal':[True,False],'net10':[.1,.2],
                        'positive_streak':[2,3]})
    mode = make_variants(toy)
    assert len(mode['ALL'][1])==1 and len(mode['EXACT_PRE'][1])==0
    print('SELF_TEST_PASS')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--bars', type=Path)
    p.add_argument('--taxonomy', type=Path)
    p.add_argument('--summary', type=Path)
    p.add_argument('--output',type=Path,default=Path('research/taxonomy_v3/output_v32/rebuild_exact_audit_v1.json'))
    p.add_argument('--report',type=Path,default=Path('research/taxonomy_v3/output_v32/rebuild_exact_audit_v1.md'))
    args = p.parse_args()
    if args.self_test: return self_test()
    if not args.bars or not args.taxonomy or not args.summary:
        p.error('bars, taxonomy and summary are required')
    sha = hashlib.sha256(args.bars.read_bytes()).hexdigest()
    summary = json.loads(args.summary.read_text())
    if sha!=summary['archive_sha256']:
        raise ValueError('Archive checksum differs from frozen taxonomy source')
    bars = pd.read_parquet(args.bars,columns=['symbol','date','open','high','low','close','amount'])
    taxonomy = pd.read_parquet(args.taxonomy)
    daily,skipped = build_daily(bars,taxonomy)
    source = {'sha256':sha,'as_of':str(pd.to_datetime(bars.date).max().date()),
              'source_rows':len(bars),'source_symbols':int(bars.symbol.nunique()),
              'taxonomy_date':summary['snapshot_date']}
    result,md = build_report(daily,make_variants(daily),source,skipped)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    args.report.write_text(md)
    print(md)


if __name__=='__main__':
    main()
