#!/usr/bin/env python3
"""Research-only, observable drawdown->rebound->OLS reconstruction episode audit.

Exploratory thresholds fixed BEFORE inspecting this output. Historical 2026
taxonomy is retrospectively applied, not historical point-in-time classification.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from audit_exact_rebuild_v1 import build_daily

HORIZONS=(3,5,10,20)
RECOVERY_WINDOW=20
EPISODE_GAP=40
DRAWDOWN=-.15
REBOUND5=.03
TRAIN_END=pd.Timestamp('2025-01-01')
COST=.0006


def attach(daily,bars):
    b=bars.copy()
    b.symbol=b.symbol.astype(str).str.zfill(6)
    b.date=pd.to_datetime(b.date).dt.normalize()
    b=b.sort_values(['symbol','date'])
    for k in ('open','high','low','close'):
        b[k]=pd.to_numeric(b[k],errors='coerce')
    # Prior rolling high must exclude today's close. 60 prior observations.
    gb=b.groupby('symbol',sort=False)
    b['prior60_high']=gb.close.transform(lambda s:s.shift(1).rolling(60,min_periods=60).max())
    b['drawdown']=b.close/b.prior60_high-1
    b['ret5']=gb.close.pct_change(5,fill_method=None)
    b['ret10']=gb.close.pct_change(10,fill_method=None)
    b['prev5']=b.groupby('symbol',sort=False).ret5.shift(5)
    b['dd_prev5']=b.groupby('symbol',sort=False).drawdown.shift(5)
    # The last five sessions must have shown a genuine drawdown.
    b['prior5_dd_min']=gb.drawdown.transform(lambda s:s.shift(1).rolling(5,min_periods=5).min())
    days=sorted(b.date.unique())
    idmap={d:i for i,d in enumerate(days)}
    b['global_id']=b.date.map(idmap).astype(int)
    b['ret1']=gb.close.pct_change(fill_method=None)
    b['bad3']=gb.ret1.transform(lambda s:(s.lt(-.03)).rolling(3,min_periods=3).max().astype(bool))
    # Entry is next opening price. Exit is the opening after h trading sessions.
    for h in HORIZONS:
        future=gb.open.shift(-(h+1))
        entry=gb.open.shift(-1)
        ids=gb.global_id.shift(-(h+1))
        b['fwd'+str(h)]=np.where(ids-b.global_id==h+1,
                                future/entry*(1-COST)**2-1,np.nan)
        # Drawdown between next open and exit open, including intervening daily lows.
        # A close-based drawdown is more robust than a synthetic high-frequency path.
        b['mae'+str(h)]=gb.close.transform(
            lambda s:s.shift(-1).rolling(h,min_periods=h).min().shift(-(h-1)))
        b['mae'+str(h)]=b['mae'+str(h)]/entry-1
    cols=['symbol','date','global_id','close','drawdown','ret5','ret10','prev5',
          'prior5_dd_min','bad3']+[f'{k}{h}' for h in HORIZONS for k in ('fwd','mae')]
    return daily.merge(b[cols],on=['symbol','date'],how='left',validate='one_to_one')


def events(d):
    # Trigger uses only as-of-t close; prior 5-day window had <=-15% drawdown,
    # last five-day return >=3%, and previous five-day return <=0.
    d=d.sort_values(['symbol','date'])
    signal=(d.prior5_dd_min<=DRAWDOWN)&(d.ret5>=REBOUND5)&(d.prev5<=0)
    # Dedup on symbol, not index, for full opportunity audit; no future-data
    # selection and no filtering out failed reversals.
    ev=[]
    for symbol,g in d.groupby('symbol',sort=False):
        ids=g.global_id.to_numpy()
        indices=np.flatnonzero(signal.loc[g.index].fillna(False).to_numpy())
        last=-100000
        for ix in indices:
            if ids[ix]-last<EPISODE_GAP:continue
            last=ids[ix]
            ev.append(g.iloc[ix])
    if not ev:return d.iloc[0:0].copy()
    return pd.DataFrame(ev).reset_index(drop=True)


def match_rebuild(ev,d):
    groups={s:g.sort_values('global_id') for s,g in d.groupby('symbol',sort=False)}
    rows=[]
    for _,e in ev.iterrows():
        g=groups[e.symbol]
        future=g.loc[(g.global_id>=e.global_id)&
                     (g.global_id<=e.global_id+RECOVERY_WINDOW)]
        confirmed=future.loc[future.signal]
        if confirmed.empty:
            delay=None; at_signal=None
        else:
            first=confirmed.iloc[0]
            delay=int(first.global_id-e.global_id)
            at_signal=float(first.close/e.close-1)
        row={'date':str(e.date.date()),'symbol':e.symbol,
             'year':int(e.date.year),'trigger_ret5':float(e.ret5),
             'trigger_drawdown':float(e.drawdown),
             'signal_within20':delay is not None,
             'delay':delay,'pre_signal_return':at_signal,
             'bad3':bool(e.bad3)}
        for h in HORIZONS:
            row[f'fwd{h}']=float(e[f'fwd{h}']) if pd.notna(e[f'fwd{h}']) else None
            row[f'mae{h}']=float(e[f'mae{h}']) if pd.notna(e[f'mae{h}']) else None
        rows.append(row)
    return pd.DataFrame(rows)


def metric(g):
    out={'episodes':int(len(g)),
         'rebuild20_count':int(g.signal_within20.sum()),
         'rebuild20_pct':round(float(g.signal_within20.mean()*100),2) if len(g) else None,
         'blocked_by_bad3_pct':round(float(g.bad3.mean()*100),2) if len(g) else None}
    delays=g.delay.dropna()
    out['rebuild_delay_median']=float(delays.median()) if len(delays) else None
    pre=g.pre_signal_return.dropna()
    out['already_rebounded_at_signal_pct']=round(float(pre.median()*100),3) if len(pre) else None
    for h in HORIZONS:
        v=g[f'fwd{h}'].dropna()
        m=g[f'mae{h}'].dropna()
        out[f'd{h}']={'n':int(len(v)),
                     'mean_pct':round(float(v.mean()*100),3) if len(v) else None,
                     'p10_pct':round(float(v.quantile(.1)*100),3) if len(v) else None,
                     'win_pct':round(float((v>0).mean()*100),2) if len(v) else None,
                     'mae_p10_pct':round(float(m.quantile(.1)*100),3) if len(m) else None}
    return out


def make_report(e):
    groups={'ALL':e,'TRAIN_PRE2025':e.loc[e.date<'2025-01-01'],
            'VALID_2025_2026':e.loc[e.date>='2025-01-01'],
            '2025':e.loc[e.year==2025],'2026':e.loc[e.year==2026],
            'REBUILD_WITHIN20':e.loc[e.signal_within20],
            'NO_REBUILD_WITHIN20':e.loc[~e.signal_within20],
            'BAD3_BLOCKED':e.loc[e.bad3],
            'BAD3_CLEAR':e.loc[~e.bad3]}
    return {k:metric(v) for k,v in groups.items()}


def markdown(stats,source):
    lines=['# 可观测超跌修复到26日OLS重建：事件研究V1','',
      '**研究性诊断，不是策略回测。** 历史基金身份使用2026-11-12快照回贴，不是历史PIT。',
      '触发：截至t日，过去5日内曾有相对前60日高点回撤≥15%，最近5日上涨≥3%，此前5日涨幅≤0；同基金40交易日冷却。',
      '只使用t日收盘前可知的价格。保留所有触发事件，包括失败反弹和20日内没有重建的事件。',
      '重建沿用26日OLS斜率翻正且1–3日内R²改善，不要求R²≥0.5；只检验t日及未来20交易日是否有确认信号。',
      '净收益按t+1开盘进入、t+h+1开盘退出，单边6bp；MAE为进入后h个收盘价相对入场价的最低值，不是盘中最大回撤。',
      '档案：'+source,'',
      '| 分组 | 事件 | 20日内重建% | 延迟中位天 | 重建前涨幅中位% | D10均值% | D10收益P10% |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for k,v in stats.items():
        lines.append('| {} | {} | {} | {} | {} | {} | {} |'.format(
            k,v['episodes'],v['rebuild20_pct'],v['rebuild_delay_median'],
            v['already_rebounded_at_signal_pct'],v['d10']['mean_pct'],v['d10']['p10_pct']))
    lines+=['','## 解释边界','',
      '- 此触发是预先固定的探索性定义，不能宣称覆盖所有超跌反弹；回撤和反弹阈值需要稳健性与独立样本。',
      '- “20日内出现重建”是事后结局，只能评价检测率，绝不能作为t日交易分组。',
      '- 历史基金分类、停牌、退市、溢价/NAV、真实买卖约束不完整；基金样本存在幸存者偏差。',
      '- 本报告的同基金冷却不消除跨基金、跨日和行业收益相关性；未给置信区间前不能据均值判定优势。',
      '- 延迟从可观测修复触发日算起，不是从事后最低价算起；重建信号可能在触发之前已经出现，因此该结果是“之后确认率”，非全量重建召回率。',
      '- 下一轮应检查该触发之前已有重建的比例、精确指数层去重、月区块置信区间及短周期预警基准。',
      '- 不得据此修改main实盘。']
    return '\n'.join(lines)+'\n'


def selftest():
    toy=pd.DataFrame({'symbol':['1']*8,'date':pd.date_range('2026-01-01',periods=8),
      'global_id':range(8),'prior5_dd_min':[-.2]*8,'ret5':[.04]*8,
      'prev5':[-.02]*8,'signal':[False]*8})
    assert len(events(toy))==1
    print('SELF_TEST_PASS')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--bars',type=Path)
    p.add_argument('--taxonomy',type=Path)
    p.add_argument('--summary',type=Path)
    p.add_argument('--output',type=Path,default=Path('research/taxonomy_v3/output_v32/drawdown_rebuild_episode_v1.json'))
    p.add_argument('--report',type=Path,default=Path('research/taxonomy_v3/output_v32/drawdown_rebuild_episode_v1.md'))
    a=p.parse_args()
    if a.self_test:return selftest()
    if not all([a.bars,a.taxonomy,a.summary]):p.error('bars, taxonomy, summary required')
    sha=hashlib.sha256(a.bars.read_bytes()).hexdigest()
    source=json.loads(a.summary.read_text())
    if sha!=source['archive_sha256']:raise RuntimeError('Frozen archive checksum mismatch')
    b=pd.read_parquet(a.bars,columns=['symbol','date','open','high','low','close','amount'])
    t=pd.read_parquet(a.taxonomy)
    daily,skipped=build_daily(b,t)
    d=attach(daily,b)
    e=match_rebuild(events(d),d)
    stats=make_report(e)
    result={'contract':'DRAWDOWN_REBUILD_EPISODE_V1',
            'archive_sha256':sha,'taxonomy_snapshot':source['snapshot_date'],
            'skipped':skipped,'stats':stats,
            'examples':e.loc[e.date>='2025-01-01'].sort_values('date').head(25).to_dict('records')}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    md=markdown(stats,sha)
    a.report.write_text(md)
    print(md)


if __name__=='__main__':main()
