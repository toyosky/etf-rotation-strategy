#!/usr/bin/env python3
"""V2 audit: uncensored, exact-index, preexisting-rebuild-aware drawdown episodes.

Research only; historical ETF taxonomy captured Nov 12 2026 is NOT historical
point-in-time. No production trading tasks or holdings touched.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
import audit_drawdown_rebuild_episode_v1 as v1
from audit_exact_rebuild_v1 import build_daily

SPLIT = pd.Timestamp('2025-01-01')
SEED = 20261113
H = 20
COOLDOWN = 40


def add_prior_state(daily):
    d=daily.sort_values(['symbol','date']).copy()
    d['prior_confirmed']=d.groupby('symbol',sort=False).confirmed.shift(1).fillna(False).astype(bool)
    d['prior_positive_streak']=d.groupby('symbol',sort=False).positive_streak.shift(1).fillna(0).astype(int)
    return d


def one_carrier_per_index(d):
    """Choose most liquid eligible carrier before today's close signal."""
    if d.duplicated(['date','symbol']).any():raise ValueError('duplicate symbol date')
    carrier=(d.sort_values(['date','exact_key','prior_amount','symbol'],
               ascending=[True,True,False,True])
               .drop_duplicates(['date','exact_key'],keep='first'))
    assert not carrier.duplicated(['date','exact_key']).any()
    return carrier


def episodes_index_grouped(d):
    eligible=one_carrier_per_index(d)
    raw=v1.events(eligible)
    if raw.empty:return raw
    raw=raw.sort_values(['date','exact_key','prior_amount','symbol'],
         ascending=[True,True,False,True])
    chosen=[];last={}
    for ix,e in raw.iterrows():
        key=e.exact_key;day=int(e.global_id)
        if day-last.get(key,-9999)<COOLDOWN:continue
        chosen.append(ix);last[key]=day
    out=raw.loc[chosen].sort_values(['date','symbol']).reset_index(drop=True)
    return out


def measure(e,d,bars):
    outcome=v1.match_rebuild(e,d)
    if len(outcome)!=len(e):raise ValueError('event reconciliation mismatch')
    outcome['exact_key']=e.exact_key.to_numpy()
    outcome['broad_key']=e.broad_key.to_numpy()
    outcome['prior_confirmed']=e.prior_confirmed.to_numpy(bool)
    outcome['prior_positive_streak']=e.prior_positive_streak.to_numpy(int)
    outcome['already_signaled_at_t']=e.signal.to_numpy(bool)
    # If an episode is younger than 20 GLOBAL exchange trading days at archive
    # end, its 20-day label is unknown and MUST NOT be counted as a failure.
    end_id=int(d.global_id.max())
    outcome['calendar_mature20']=(e.global_id.to_numpy(int)+H<=end_id)
    # For complete, executable-horizon event sample, require next-open and
    # h+1-open quotes, without converting missing quotes into "failed rebuild".
    outcome['complete_quote20']=e.fwd20.notna().to_numpy()
    outcome['analysis_ready']=outcome.calendar_mature20&outcome.complete_quote20
    outcome['new_rebuild_after_trigger']=(outcome.signal_within20 &
                                         ~outcome.prior_confirmed)
    outcome['trigger_ret5_pct']=100*e.ret5.to_numpy(float)
    outcome['trigger_drawdown_pct']=100*e.drawdown.to_numpy(float)
    outcome['pre_signal_return_pct']=100*pd.to_numeric(outcome.pre_signal_return,errors='coerce')
    return outcome


def metric(df):
    total=len(df)
    rebuild=int(df.signal_within20.sum()) if total else 0
    future=df.loc[~df.prior_confirmed]
    # Use observations that had full 20-day bar coverage at archive cutoff.
    delays=df.delay.dropna()
    ret=df.fwd10.dropna()
    return {'episodes':total,
       'already_in_confirmed_rebuild':int(df.prior_confirmed.sum()),
       'new_rebuild_eligible_episodes':len(future),
       'new_rebuild_within20':int(future.signal_within20.sum()),
       'new_rebuild_within20_pct':round(float(future.signal_within20.mean()*100),2)
                                   if len(future) else None,
       'rebuild_within20_total_pct':round(100*rebuild/total,2) if total else None,
       'delay_median':round(float(delays.median()),1) if len(delays) else None,
       'rebound_before_confirmation_median_pct':round(float(
             pd.to_numeric(df.pre_signal_return_pct,errors='coerce').median()),3)
             if len(delays) else None,
       'trigger_ret5_median_pct':round(float(df.trigger_ret5_pct.median()),3) if total else None,
       'd10_n':len(ret),'d10_mean_pct':round(float(ret.mean()*100),3) if len(ret) else None,
       'd10_p10_pct':round(float(ret.quantile(.1)*100),3) if len(ret) else None,
       'd10_win_pct':round(float((ret>0).mean()*100),2) if len(ret) else None,
       'd20_n':int(df.fwd20.notna().sum()),
       'd20_mean_pct':round(float(df.fwd20.dropna().mean()*100),3) if df.fwd20.notna().any() else None,
       'bad3_blocked_pct':round(float(df.bad3.mean()*100),2) if total else None}


def monthly_ci(df, bool_col='signal_within20'):
    d=df.copy()
    if d.empty:return {'n':0}
    d=d.loc[~d.prior_confirmed].copy()
    d['month']=pd.to_datetime(d.date).dt.to_period('M')
    g=d.groupby('month')[bool_col].agg(['sum','count'])
    if len(g)<4:return {'n':len(d),'months':len(g),'ci95_pct':None}
    rng=np.random.default_rng(SEED)
    draws=rng.integers(0,len(g),size=(2400,len(g)))
    sums=g['sum'].to_numpy(float);counts=g['count'].to_numpy(float)
    boots=100*sums[draws].sum(axis=1)/counts[draws].sum(axis=1)
    return {'n':len(d),'months':len(g),
            'estimate_pct':round(100*float(d[bool_col].mean()),3),
            'month_block_ci95_pct':[round(float(v),3) for v in np.quantile(boots,[.025,.975])]}


def matched_association(df):
    """Descriptive post-event association only; NOT a tradable or causal split."""
    d=df.loc[df.fwd10.notna() & ~df.prior_confirmed].copy()
    a=d.loc[d.signal_within20].fwd10
    b=d.loc[~d.signal_within20].fwd10
    return {'new_rebuild_n':len(a),'no_new_rebuild_n':len(b),
            'new_rebuild_mean_pct':round(float(a.mean()*100),3) if len(a) else None,
            'no_new_rebuild_mean_pct':round(float(b.mean()*100),3) if len(b) else None,
            'difference_pp':round(float((a.mean()-b.mean())*100),3) if len(a) and len(b) else None,
            'warning':'Future 20-day labels must never be used as signal-date trading rules'}


def analyze(e):
    excluded={
      'calendar_censored_n':int((~e.calendar_mature20).sum()),
      'missing_future_quotes_n':int((e.calendar_mature20&~e.complete_quote20).sum()),
      'mature_valid_n':int(e.analysis_ready.sum()),
      'all_events_before_censor':len(e)}
    ready=e.loc[e.analysis_ready].copy()
    segments={
      'TRAIN':ready.loc[ready.year<2025],
      'VALID':ready.loc[ready.year>=2025],
      '2025':ready.loc[ready.year==2025],
      '2026':ready.loc[ready.year==2026],
      'VALID_BAD3':ready.loc[(ready.year>=2025)&ready.bad3],
      'VALID_CLEAR':ready.loc[(ready.year>=2025)&~ready.bad3],
    }
    return {'contract':'ETF_DRAWDOWN_REBUILD_EXACT_UNCENSORED_V2',
            'source':{'taxonomy_snapshot':'2026-11-12','history_pit':False},
            'censoring':excluded,
            'stats':{name:metric(d) for name,d in segments.items()},
            'new_rebuild_ci':{name:monthly_ci(d) for name,d in segments.items()},
            'hindsight_only':{name:matched_association(d) for name,d in
                              segments.items() if name in ('TRAIN','VALID','2025','2026')},
            'examples':[
               {'symbol':str(x.symbol),'date':str(x.date),'already_confirmed':bool(x.prior_confirmed),
                'rebuild_within20':bool(x.signal_within20),'delay':None if pd.isna(x.delay) else int(x.delay)}
               for x in ready.loc[ready.year>=2025].head(15).itertuples()]}


def markdown(z):
    lines=['# 超跌修复到26日重建 V2：剔除同指数重复与右端删失','',
        '**研究范围**：2026-11-12静态分类回贴历史，非严格PIT/实盘资金回测。',
        '同一日期同一精确指数组只取前60日成交额最高合格ETF，再以指数为单位设置40交易日触发冷却。',
        '超跌触发沿用V1: prior5日内曾相对前60日高点回撤≥15%，最近5日反弹≥3%，前5日涨幅≤0。未以验证期表现重新调阈值。',
        '仅统计从事件日开始未来20个市场交易日已成熟、且有完整21日后开盘报价的事件，完整行情缺失作为删失，绝不作阴性样本。',
        '再剔除在触发前一日已处于26日OLS确认正趋势的事件，才计算“新重建”比例。近期跌幅<-3%只作单独描述，不提前排除样本。',
        '重建确认是26日β转正后1–3日R²改善，不要求R²≥0.50。收益为次日开盘入场，10日/20日持有，单边6bp。',
        '',
        '## 可比事件与独立新增重建检测率','',
        f"原始指数级事件 {z['censoring']['all_events_before_censor']}；时间不足 {z['censoring']['calendar_censored_n']}；完整报价缺失 {z['censoring']['missing_future_quotes_n']}；有效成熟事件 {z['censoring']['mature_valid_n']}。",
        '',
        '| 样本 | 成熟事件 | 事前已有重建 | 新重建分母 | 未来20日新重建率 | 月份区块95%区间 | 10日均值% |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for name,obj in z['stats'].items():
        ci=z['new_rebuild_ci'][name].get('month_block_ci95_pct')
        ci_s=('['+', '.join(f'{v:.2f}' for v in ci)+']') if ci else '—'
        lines.append('| {} | {} | {} | {} | {} | {} | {} |'.format(
          name,obj['episodes'],obj['already_in_confirmed_rebuild'],
          obj['new_rebuild_eligible_episodes'],obj['new_rebuild_within20_pct'],
          ci_s,obj['d10_mean_pct']))
    lines+=['','## 事后按重建结局分组（不能用于交易）','',
            '| 样本 | 未来重建组n | 未来未重建组n | 重建组D10均值% | 未重建组D10均值% | 差值pp |',
            '|---|---:|---:|---:|---:|---:|']
    for name,obj in z['hindsight_only'].items():
        lines.append('| {} | {} | {} | {} | {} | {} |'.format(
         name,obj['new_rebuild_n'],obj['no_new_rebuild_n'],
         obj['new_rebuild_mean_pct'],obj['no_new_rebuild_mean_pct'],obj['difference_pp']))
    lines+=['','## 必要解释','',
        '- 若接近档案右端，未来20日是否重建未知；此前V1将其误计作未重建。本版更正为删失，同时要求有可观察未来21日开盘价。',
        '- V1同指数多只ETF可能重复贡献事件；本版使用前日成交额选定一个载体，再按精确指数组冷却。',
        '- 已有重建并不等同于修复触发后才确认；本版记录前一日已确认比例。重建日信号本身仍由当日收盘价产生。',
        '- 20日内能否重新确认是一项事后结局，与当日已知早期信号不能混作可交易规则。',
        '- 10/20日收益是重叠事件的模拟持有而非有资金约束的仓位回测；当前静态分组没有历史PIT。',
        '- 因未来报价缺失而排除的基金可能不是随机，数据右删失与历史幸存者偏差仍待补证。',
        '- 超跌阈值是探索性，仍需按指数、市场状态、时间区间验证；严格风险规则未复现。',
        '- 未做多重探索调整，不得宣布原策略存在或不存在有效超跌修复α。']
    return '\n'.join(lines)+'\n'


def selftest():
    a=pd.DataFrame({'date':pd.to_datetime(['2026-01-01']*2),
                    'symbol':['000001','000002'],'exact_key':['X','X'],
                    'prior_amount':[10.,20.]})
    assert one_carrier_per_index(a).iloc[0].symbol=='000002'
    z=pd.DataFrame({'date':['2026-01-01','2026-02-01'],
                    'signal_within20':[True,False],'prior_confirmed':[False,False]})
    assert monthly_ci(z)['n']==2
    print('SELF_TEST_PASS')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--bars',type=Path)
    p.add_argument('--taxonomy',type=Path)
    p.add_argument('--summary',type=Path)
    p.add_argument('--output',type=Path,default=Path(
      'research/taxonomy_v3/output_v32/drawdown_rebuild_exact_uncensored_v2.json'))
    p.add_argument('--report',type=Path,default=Path(
      'research/taxonomy_v3/output_v32/drawdown_rebuild_exact_uncensored_v2.md'))
    a=p.parse_args()
    if a.self_test:return selftest()
    if not(a.bars and a.taxonomy and a.summary):p.error('--bars --taxonomy --summary required')
    sha=hashlib.sha256(a.bars.read_bytes()).hexdigest()
    src=json.loads(a.summary.read_text())
    if sha!=src['archive_sha256']:raise RuntimeError('market snapshot checksum mismatch')
    bars=pd.read_parquet(a.bars,columns=['symbol','date','open','high','low','close','amount'])
    taxonomy=pd.read_parquet(a.taxonomy)
    daily,skipped=build_daily(bars,taxonomy)
    d=v1.attach(add_prior_state(daily),bars)
    e=episodes_index_grouped(d)
    measured=measure(e,d,bars)
    result=analyze(measured)
    result['source']={'sha256':sha,'as_of':str(pd.to_datetime(bars.date).max().date()),
        'taxonomy_snapshot':src['snapshot_date'],'historical_pit':False,
        'eligible_funds':int(d.symbol.nunique()),'exact_indices':int(d.exact_key.nunique()),
        'excluded_symbols':skipped}
    md=markdown(result)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
    a.report.write_text(md)
    print(md)


if __name__=='__main__':main()
