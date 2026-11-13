#!/usr/bin/env python3
"""Research-only V2 carrier-continuity sensitivity audit.
Quantifies whether index-level episodes are falsely labelled negative because
V2 follows the original ETF symbol after the index carrier changes.
"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
import audit_drawdown_rebuild_episode_v1 as v1
import audit_drawdown_rebuild_exact_uncensored_v2 as v2
from audit_exact_rebuild_v1 import build_daily

def assess(e,d):
    d=d.sort_values(['date','exact_key','prior_amount','symbol'],
                    ascending=[True,True,False,True]).copy()
    carrier=v2.one_carrier_per_index(d)
    carrier_lookup={(x.date,x.exact_key):x.symbol for x in carrier.itertuples()}
    grouped={key:g.sort_values('global_id') for key,g in d.groupby('exact_key',sort=False)}
    records=[]
    for x in e.itertuples():
        if x.global_id+20>int(d.global_id.max()):continue
        g=grouped[x.exact_key]
        future=g.loc[g.global_id.between(x.global_id,x.global_id+20)]
        same=future.loc[(future.symbol==x.symbol)&future.signal]
        any_signal=future.loc[future.signal]
        chosen=future.loc[future.apply(lambda r:carrier_lookup.get((r.date,r.exact_key))==r.symbol,axis=1)&future.signal]
        records.append({'date':str(x.date.date()),'symbol':x.symbol,
          'exact_key':x.exact_key,'year':int(x.date.year),
          'same_symbol_signal':not same.empty,
          'any_member_signal':not any_signal.empty,
          'chosen_carrier_signal':not chosen.empty,
          'first_any_delay':None if any_signal.empty else int(any_signal.global_id.min()-x.global_id),
          'carrier_changed':any(carrier_lookup.get((r.date,r.exact_key))!=x.symbol
                                for r in future.itertuples())})
    return pd.DataFrame(records)

def selftest():
    dates=pd.date_range('2026-01-01',periods=3)
    d=pd.DataFrame([
       dict(date=dates[0],exact_key='X',symbol='A',prior_amount=100,global_id=0,signal=False),
       dict(date=dates[1],exact_key='X',symbol='A',prior_amount=100,global_id=1,signal=False),
       dict(date=dates[2],exact_key='X',symbol='A',prior_amount=50,global_id=2,signal=False),
       dict(date=dates[2],exact_key='X',symbol='B',prior_amount=200,global_id=2,signal=True)])
    # A is the event carrier, but B signals at t+2.
    e=pd.DataFrame([dict(date=dates[0],exact_key='X',symbol='A',global_id=0)])
    # Need 20 days maturity for production; this toy asserts carrier selection and mismatch.
    assert v2.one_carrier_per_index(d).iloc[-1].symbol=='B'
    assert not d.loc[d.symbol=='A','signal'].any()
    assert d.loc[(d.symbol=='B')&d.signal].shape[0]==1
    print('SELF_TEST_PASS')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--bars',type=Path)
    p.add_argument('--taxonomy',type=Path)
    p.add_argument('--summary',type=Path)
    p.add_argument('--output',type=Path,default=Path('research/taxonomy_v3/output_v32/carrier_continuity_audit_v1.json'))
    p.add_argument('--report',type=Path,default=Path('research/taxonomy_v3/output_v32/carrier_continuity_audit_v1.md'))
    a=p.parse_args()
    if a.self_test:return selftest()
    sha=hashlib.sha256(a.bars.read_bytes()).hexdigest()
    src=json.loads(a.summary.read_text())
    if sha!=src['archive_sha256']:
        raise RuntimeError(f'Archive hash mismatch: actual={sha} expected={src["archive_sha256"]} bytes={a.bars.stat().st_size}; frozen data must not be silently replaced')
    bars=pd.read_parquet(a.bars,columns=['symbol','date','open','high','low','close','amount'])
    daily,_=build_daily(bars,pd.read_parquet(a.taxonomy))
    d=v1.attach(v2.add_prior_state(daily),bars)
    e=v2.episodes_index_grouped(d)
    r=assess(e,d)
    segments={'ALL':r,'VALID':r.loc[r.year>=2025],
              '2025':r.loc[r.year==2025],'2026':r.loc[r.year==2026]}
    stats={}
    for name,g in segments.items():
        stats[name]={'n':len(g),'carrier_changed_n':int(g.carrier_changed.sum()),
          'same_symbol_signal_n':int(g.same_symbol_signal.sum()),
          'any_member_signal_n':int(g.any_member_signal.sum()),
          'chosen_carrier_signal_n':int(g.chosen_carrier_signal.sum()),
          'any_member_only_n':int((g.any_member_signal&~g.same_symbol_signal).sum()),
          'carrier_only_n':int((g.chosen_carrier_signal&~g.same_symbol_signal).sum())}
    out={'contract':'CARRIER_CONTINUITY_AUDIT_V1','sha256':sha,'stats':stats,
         'caveat':'Descriptive all-member and chosen-carrier signals, not an executable PIT backtest',
         'examples':r.loc[r.any_member_signal&~r.same_symbol_signal].head(25).to_dict('records')}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    lines=['# V2 重建检测率的ETF载体切换敏感性','',
      '问题：V2以指数为单位选择触发事件，但在未来20日只跟踪触发时的同一ETF代码。若指数代表基金切换，同指数其他ETF的OLS确认可能被遗漏。',
      '本研究并行比较同代码、当日流动性最高代表、同指数任一基金三个口径；它们是不同的估计对象，不应简单把任一基金信号视作可交易优势。','',
      '| 分组 | 成熟事件 | 载体切换 | 原代码确认 | 任一同指数确认 | 任一有但原代码无 |',
      '|---|---:|---:|---:|---:|---:|']
    for k,v in stats.items():
        lines.append(f"| {k} | {v['n']} | {v['carrier_changed_n']} | {v['same_symbol_signal_n']} | {v['any_member_signal_n']} | {v['any_member_only_n']} |")
    lines+=['','说明：此审计仅要求事件20个市场交易日成熟，不强制完整未来开盘价，故分母与V2可交易收益子样本可能不同。任何同指数成员确认仍需独立的当日可知流动性、上市历史和价格可执行性审计。','',
      '冻结行情SHA256：'+sha]
    a.report.write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
if __name__=='__main__':main()
