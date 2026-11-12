from copy import deepcopy
import json
from pathlib import Path
import pandas as pd
import pytest
from .collect import parse_profile
from .model import classifications_at, economic_labels, name_key, validate_intervals, supplemental_labels_v31
from .representatives import Policy, select_representatives
from .build import registry_inputs, quality_audit
from .model import supplemental_labels_v31
from .evidence import verify_documents


def record(symbol='510300', key='CSI:300', **kwargs):
    return dict(symbol=symbol, valid_from='2020-01-01', valid_to=None,
        known_from='2020-01-01', needs_review=False, exact_index_verified=True,
        exact_index_key=key, exposure_id='EXP:'+key, listing_date='2019-01-01',
        listing_known_from='2019-01-01', tracking_mode='PASSIVE_INDEX',
        premium_sensitive=False, execution_attributes_verified=True, **kwargs)


@pytest.fixture
def market():
    calendar = pd.bdate_range('2021-01-01', periods=9).strftime('%Y-%m-%d').tolist()
    rows = [dict(symbol=s, date=d, open=1., high=1.1, low=.9, close=1., amount=a)
            for s,a in [('510300',10.),('510330',20.)] for d in calendar]
    return calendar, pd.DataFrame(rows)


def choose(market, records=None, **kwargs):
    cal, bars = market
    return select_representatives(records or [record(),record('510330')], bars, cal, cal[6],
        policy=Policy(window=3,min_history=4,min_mean_amount=1,recent_sessions=2), **kwargs)


def test_choose_before_signal(market):
    result = choose(market)
    assert [r['symbol'] for r in result['representatives']] == ['510330']
    assert result['data_through'] == market[0][5]
    assert result['representatives'][0]['mean_amount_prior'] == 20


def test_future_and_today_mutation_cannot_change_selection(market):
    before = choose(market)
    cal,bars = market
    changed = bars.copy()
    changed.loc[(changed.symbol=='510300') & (changed.date>=cal[6]),'amount'] = 1e30
    changed['ols_score'] = 1e50
    changed['future_return'] = -1e20
    changed = pd.concat([changed, changed.loc[changed.date==cal[8]]])
    assert choose((cal,changed)) == before


def test_signal_absence_cannot_change_carrier(market):
    cal,bars=market
    bars=bars.assign(qualifies=bars.symbol.eq('510300'))
    assert choose((cal,bars))['representatives'][0]['symbol']=='510330'


def test_prior_turnover_changes_carrier(market):
    cal,bars=market
    bars=bars.copy()
    bars.loc[(bars.symbol=='510300') & bars.date.isin(cal[3:6]),'amount']=100
    assert choose((cal,bars))['representatives'][0]['symbol']=='510300'


def test_missing_prior_session_does_not_use_last_available(market):
    cal,bars=market
    bars=bars.loc[~((bars.symbol=='510330') & (bars.date==cal[5]))]
    result=choose((cal,bars))
    assert result['representatives'][0]['symbol']=='510300'
    assert 'MISSING_PREVIOUS_SESSION_BAR' in [r['reason'] for r in result['excluded']]


def test_missing_window_is_not_compressed(market):
    cal,bars=market
    bars=bars.loc[~((bars.symbol=='510330') & (bars.date==cal[3]))]
    assert choose((cal,bars))['representatives'][0]['symbol']=='510300'


def test_zero_turnover_and_bad_ohlc_excluded(market):
    cal,bars=market
    bars=bars.copy()
    bars.loc[(bars.symbol=='510330') & (bars.date==cal[5]),'high']=.5
    assert choose((cal,bars))['representatives'][0]['symbol']=='510300'
    bars.loc[(bars.symbol=='510300') & (bars.date==cal[5]),'amount']=0
    assert not choose((cal,bars))['representatives']


def test_calendar_must_be_explicit(market):
    cal,bars=market
    with pytest.raises(ValueError,match='calendar'):
        choose((cal[::-1],bars))


def test_ambiguity_fails_closed():
    with pytest.raises(ValueError,match='overlapping'):
        classifications_at([record(),record()], '2021-01-01')


def test_half_open_boundary_one_match():
    old=record();old['valid_to']='2021-01-01'
    new=record();new.update(valid_from='2021-01-01',known_from='2021-01-01')
    assert len(classifications_at([old,new],'2021-01-01')[0])==1


def test_effective_is_not_known():
    r=record();r.update(known_from='2022-01-01')
    active,excluded=classifications_at([r],'2021-01-01')
    assert not active and excluded[0]['reason']=='CLASSIFICATION_NOT_YET_KNOWN'


@pytest.mark.parametrize('field,value,reason',[
    ('needs_review',True,'UNVERIFIED_CLASSIFICATION'),
    ('listing_date',None,'LISTING_DATE_NOT_VERIFIED'),
    ('listing_date','2022-01-01','NOT_YET_LISTED'),
    ('listing_known_from','2022-01-01','LISTING_NOT_YET_KNOWN'),
    ('tracking_mode','ACTIVE','STRATEGY_NOT_APPROVED_FOR_PASSIVE_POOL')])
def test_metadata_guards(field,value,reason):
    r=record();r[field]=value
    assert classifications_at([r],'2021-01-01')[1][0]['reason']==reason


def test_each_distinct_index_survives_same_sector(market):
    result=choose(market,[record(),record('510330','CSI:500')])
    assert len(result['representatives'])==2


def test_unapproved_cross_index_merge_is_rejected(market):
    r=record('510330','CSI:500');r['exposure_id']='EXP:CSI:300'
    with pytest.raises(ValueError,match='unapproved cross-index'):
        choose(market,[record(),r])


def test_pre_conversion_bars_do_not_count_as_current_history(market):
    r=record('510330');r['listing_date']=market[0][4]
    out=choose(market,[record(),r])
    assert out['representatives'][0]['symbol']=='510300'
    assert 'INSUFFICIENT_PAST_VALID_HISTORY' in [x['reason'] for x in out['excluded']]


def test_tie_is_deterministic(market):
    cal,bars=market
    bars=bars.assign(amount=10.)
    one=choose((cal,bars))
    two=choose((cal,bars.sample(frac=1,random_state=9)),[record('510330'),record()])
    assert one==two and one['representatives'][0]['symbol']=='510300'


def test_duplicate_past_bar_rejected(market):
    cal,bars=market
    with pytest.raises(ValueError,match='duplicate historical'):
        choose((cal,pd.concat([bars,bars.iloc[:1]])))


def test_premium_requires_publication_time(market):
    r1,r2=record(),record('510330');r2['premium_sensitive']=True
    result=choose(market,[r1,r2],risk_observations=[dict(symbol='510330',observation_date=market[0][5],premium=0)])
    assert result['representatives'][0]['symbol']=='510300'
    result=choose(market,[r1,r2],risk_observations=[dict(symbol='510330',observation_date=market[0][5],known_from=market[0][6],premium=.01)])
    assert result['representatives'][0]['symbol']=='510330'


def test_future_premium_cannot_help(market):
    r1,r2=record(),record('510330');r2['premium_sensitive']=True
    result=choose(market,[r1,r2],risk_observations=[dict(symbol='510330',observation_date=market[0][5],known_from=market[0][7],premium=0)])
    assert result['representatives'][0]['symbol']=='510300'


def test_known_preopen_suspension_is_respected(market):
    cal,_=market
    out=choose(market,risk_observations=[dict(symbol='510330',observation_date=cal[6],known_from=cal[6],suspended=True)])
    assert out['representatives'][0]['symbol']=='510300'
    assert 'KNOWN_SUSPENSION' in [x['reason'] for x in out['excluded']]


def test_code_does_not_invent_index_from_benchmark():
    html='<table><tr><th>基金代码</th><td>501018（主代码）<th>基金类型</th><td>QDII</td></td></tr><tr><th>基金全称</th><td>南方原油证券投资基金</td></tr><tr><th>业绩比较基准</th><td>原油指数</td></tr></table>'
    facts=parse_profile(html,'501018')
    assert facts['基金类型']=='QDII'
    assert facts.get('跟踪标的') is None
    with pytest.raises(ValueError):
        parse_profile(html,'501019')


def test_index_names_keep_qualifiers():
    names=['中证红利指数','中证红利低波动指数','上证科创板50成份指数','上证科创板医药指数',
           '中证机器人指数','中证人工智能指数','黄金现货指数','黄金产业指数']
    assert len({name_key(n) for n in names})==len(names)


def test_healthcare_and_energy_distinctions():
    assert economic_labels('中证全指医疗器械指数')['sector_level2']=='MEDICAL_DEVICES'
    assert economic_labels('中证医疗指数')['sector_level2']=='MEDICAL_MIXED'
    assert economic_labels('恒生创新药指数')['region_primary']=='HK'
    assert economic_labels('标普生物科技指数')['region_primary']=='US'
    assert economic_labels('中证石油天然气指数')['exposure_type']=='EQUITY'
    assert economic_labels('中证能源化工期货指数')['exposure_type']=='COMMODITY_FUTURES'


def test_unknown_region_is_not_guessed():
    assert economic_labels('某新主题指数')['region_primary'] is None


def test_unknown_execution_attributes_block_ranking(market):
    r=record('510330');r['execution_attributes_verified']=False
    out=choose(market,[record(),r])
    assert out['representatives'][0]['symbol']=='510300'
    assert 'EXECUTION_ATTRIBUTES_UNVERIFIED' in [x['reason'] for x in out['excluded']]


def test_delisting_and_late_prices(market):
    cal,bars=market
    r=record('510330');r['delisting_date']=cal[6]
    assert choose(market,[record(),r])['representatives'][0]['symbol']=='510300'
    bars=bars.assign(available_on='2020-01-01')
    bars.loc[(bars.symbol=='510330') & (bars.date==cal[5]),'available_on']=cal[7]
    assert choose((cal,bars))['representatives'][0]['symbol']=='510300'


def test_frozen_real_artifact_invariants():
    p=Path(__file__).with_name('output')/'classifications.json'
    if not p.exists():
        pytest.skip('run the offline build to validate frozen real artifacts')
    rows=json.loads(p.read_text())
    validate_intervals(rows)
    assert not classifications_at(rows,'2021-12-31')[0]
    assert len(rows)==len({r['symbol'] for r in rows})
    for r in rows:
        assert r['known_from']>r['observed_on']
        assert r['source_date'] is None
        if r['tracking_mode']=='UNVERIFIED_NON_INDEX_STRATEGY':
            assert r['exact_index_key'] is None


def test_v31_fill_missing_broad_index_descriptors_without_merging_keys():
    names=[
        ("中证科创创业50指数","CN","EQUITY","MULTI_SECTOR"),
        ("上证科创板100指数","CN","EQUITY","MULTI_SECTOR"),
        ("中证稀有金属主题指数","CN","EQUITY","MATERIALS"),
        ("中证港股通互联网指数","HK","EQUITY","TECHNOLOGY"),
        ("MSCI中国A股国际通人民币指数","CN","EQUITY","MULTI_SECTOR"),
        ("巴西BOVESPA","BR","EQUITY","MULTI_SECTOR"),
        ("中证全指家用电器指数","CN","EQUITY","CONSUMER"),
        ("中证工业互联网主题指数","CN","EQUITY","TECHNOLOGY"),
        ("中证短融指数","CN","BOND","FIXED_INCOME"),
    ]
    for n,region,asset,sector in names:
        x=supplemental_labels_v31(n,economic_labels(n))
        assert (x['region_primary'],x['exposure_type'],x['sector_level1'])==(region,asset,sector), (n,x)


def test_v31_index_descriptor_filling_does_not_override_verified_details():
    before=dict(region_primary='CN',exposure_type='EQUITY',sector_level1='HEALTHCARE',
       sector_level2='INNOVATIVE_DRUGS',index_style='SECTOR_OR_THEME',risk_bucket='CN|EQUITY|HEALTHCARE')
    after=supplemental_labels_v31("中证工业互联网主题指数",before)
    assert after==before


def test_v31_unknown_index_remains_unclassified():
    x=supplemental_labels_v31("某全新专项指数",economic_labels("某全新专项指数"))
    assert not x['region_primary'] and not x['exposure_type'] and not x['sector_level1']


def test_v31_index_name_boundary_regressions():
    def parse(name):
        return supplemental_labels_v31(name,economic_labels(name))
    assert parse("中证港股通信息技术综合指数")['sector_level2']=="INFORMATION_TECHNOLOGY"
    assert parse("中证港股通非银行金融主题指数")['sector_level2']=="NON_BANK_FINANCIALS"
    assert parse("中证海外中国互联网30指数")['region_primary']=="CN_OFFSHORE"
    assert parse("S&P Oil & Gas Exploration & Production Select Industry")['region_primary']=="US"
    assert parse("S&P Oil & Gas Exploration & Production Select Industry")['sector_level2']=="OIL_GAS_EQUITY"
    assert parse("中证港股通信息技术综合指数")['region_primary']=="HK"


def test_v31_actual_fund_mandates_if_rebuilt():
    p=Path(__file__).with_name('output_v31')/'classifications.json'
    if not p.exists():
        pytest.skip('V3.1 actual artifact is built by the official catalog CI workflow')
    rows={r['symbol']:r for r in json.loads(p.read_text())}
    a=rows['159981']
    assert a['legal_mandate_verified'] and not a['needs_review']
    assert a['tracking_mode']=='PASSIVE_INDEX'
    assert a['index_name']=='易盛郑商所能源化工指数A'
    assert a['exposure_type']=='COMMODITY_FUTURES'
    assert a['exact_index_key'].startswith('INDEX_NAME:')
    b=rows['159100']
    assert b['legal_mandate_verified'] and not b['needs_review']
    assert b['region_primary']=='BR' and b['tracking_mode']=='PASSIVE_INDEX'
    assert b['replication_method']=='TARGET_ETF_FOF'
    c=rows['501018']
    assert c['legal_mandate_verified'] and c['needs_review']
    assert c['tracking_mode']=='ACTIVE_QDII_FOF'
    assert c['exact_index_key'] is None
    assert c['exposure_type']=='COMMODITY_FOF'
    assert all(r['execution_attributes_verified'] is False for r in [a,b,c])
    assert all(r['known_from']=='2026-11-13' for r in [a,b,c])
    meal=rows['159985']
    assert meal['legal_mandate_verified'] and not meal['needs_review']
    assert meal['index_name']=='大连商品交易所豆粕期货价格指数'
    assert meal['exposure_type']=='COMMODITY_FUTURES'
    city=rows['511220']
    assert city['legal_mandate_verified'] and not city['needs_review']
    assert city['exposure_type']=='BOND'
    assert city['index_name']=='上证城投债指数'
    gold=rows['159934']
    assert gold['legal_mandate_verified'] and gold['needs_review']
    assert gold['exposure_id']=='SPOT:SGE_AU9999'
    assert gold['exact_index_key'] is None
    assert gold['exposure_type']=='COMMODITY_SPOT'
    silver=rows['161226']
    assert silver['legal_mandate_verified'] and silver['needs_review']
    assert silver['exposure_id']=='FUTURES_CONTRACT:SHFE_SILVER_MAIN'
    assert silver['exact_index_key'] is None
    assert silver['exposure_type']=='COMMODITY_FUTURES'
    tech=rows['159509']
    assert tech['legal_mandate_verified'] and tech['index_name']=='纳斯达克科技市值加权指数（价格指数）'
    assert tech['region_primary']=='US' and tech['sector_level2']=='NASDAQ_100_TECHNOLOGY'
    consumer=rows['159529']
    assert consumer['legal_mandate_verified'] and consumer['index_name']=='标普500消费精选指数'
    assert consumer['region_primary']=='US' and consumer['sector_level2']=='SP500_CONSUMER_SELECT_15_60'
    assert all(not x['needs_review'] for x in [tech,consumer])
    assert all(not x['execution_attributes_verified'] for x in [tech,consumer])
    assert all(x['known_from']=='2026-11-13' for x in [meal,city,gold,silver])
    assert all(x['execution_attributes_verified'] is False for x in [meal,city,gold,silver])


def test_v32_cross_market_and_private_enterprise_regressions():
    def parse(n):
        return supplemental_labels_v31(n,economic_labels(n))
    assert parse('富时中国国企开放共赢指数')['region_primary']=='CN_HK'
    assert parse('国证民企领先100指数')['sector_level2']=='PRIVATE_ENTERPRISE'
    assert parse('恒生A股电网设备指数')['region_primary']=='CN'
    assert parse('富时中国50指数')['region_primary'] is None
    assert parse('MSCI中国指数')['region_primary'] is None
    assert parse('富时中国A50指数')['region_primary']=='CN'
    assert parse('恒生医疗保健指数')['sector_level2']=='HEALTHCARE_BROAD'


def test_v32_aliases_reuse_canonical_identity_without_inventing_code():
    root=Path(__file__).parent
    by_code,by_name=registry_inputs(root/'snapshot/official','2026-11-12')
    a=by_code[next(iter(by_name['巴西伊博维斯帕指数']))]
    b=by_code[next(iter(by_name['巴西IBOVESPA指数']))]
    assert a['key']==b['key']
    assert a['index_code'] is None and b['index_code'] is None
    assert by_code['HSTECH']['key']=='HSI:HSTECH'
    assert by_code['HSBIO']['key']=='HSI:HSBIO'
    assert by_code['HSSCITI']['index_code']=='.HSSCITI'
    assert 'HSTECHT' not in by_code and 'HSTECHN' not in by_code
    assert by_code['399903']['key']==by_code['000903']['key']=='CSI:000903'
    assert by_code['980092']['index_name']=='国证自由现金流指数'
    assert by_code['NDX']['key']=='NASDAQ:NDX' and 'XNDX' not in by_code


def test_v32_frozen_document_bytes_and_price_rows_are_verified():
    root=Path(__file__).parent
    for a in json.loads((root/'index_aliases.json').read_text()):
        refs=a.get('evidence_documents',[])
        verify_documents(refs,'2026-11-12')
    bad=[dict(manifest='snapshot/supplement_v32/hsi-methodology-hstech.json',
              required_patterns=[r'价格指数\s+\.HSTECHN(?:\s|$)'])]
    with pytest.raises(ValueError,match='table row absent'):
        verify_documents(bad,'2026-11-12')
    with pytest.raises(ValueError,match='captured after'):
        verify_documents(bad,'2021-01-01')


def test_v32_actual_aliases_and_statuses_if_rebuilt():
    p=Path(__file__).parent/'output_v32/classifications.json'
    if not p.exists():
        pytest.skip('build V3.2 real artifacts first')
    rows={r['symbol']:r for r in json.loads(p.read_text())}
    assert rows['159100']['exact_index_key']==rows['520870']['exact_index_key']
    assert rows['159100']['exposure_id']==rows['520870']['exposure_id']
    for s in ['517090','517180']:
        assert rows[s]['region_primary']=='CN_HK' and not rows[s]['needs_review']
    assert rows['159973']['sector_level2']=='PRIVATE_ENTERPRISE'
    assert rows['159320']['region_primary']=='CN'
    for s in ['501018','159934','161226']:
        r=rows[s]
        assert r['economic_classification_verified'] and not r['unresolved_reasons']
        assert r['classification_status']=='VERIFIED_EXCLUDED_STRATEGY'
        assert r['needs_review'] and not r['exact_index_verified']
    _,excluded=classifications_at([rows['501018']], '2026-11-13')
    assert excluded[0]['reason']=='VERIFIED_STRATEGY_OUTSIDE_PASSIVE_INDEX_POOL'
    assert all(not r['execution_attributes_verified'] for r in rows.values())


def test_v32_two_brazil_products_cannot_inflate_pre_signal_pool():
    p=Path(__file__).parent/'output_v32/classifications.json'
    if not p.exists():
        pytest.skip('build V3.2 real artifacts first')
    rows=[r for r in json.loads(p.read_text()) if r['symbol'] in ['159100','520870']]
    for r in rows:
        r.update(execution_attributes_verified=True,premium_sensitive=False)
    cal=['2026-11-13','2026-11-16']
    bars=pd.DataFrame([dict(symbol=r['symbol'],date='2026-11-13',open=1.,high=1.,low=1.,close=1.,
                           amount=10. if r['symbol']=='159100' else 20.) for r in rows])
    out=select_representatives(rows,bars,cal,cal[-1],policy=Policy(window=1,min_history=1,min_mean_amount=1,recent_sessions=1))
    assert len(out['representatives'])==1
    assert out['representatives'][0]['symbol']=='520870'


def test_v32_lof_share_classes_require_actual_mandates():
    p=Path(__file__).parent/'output_v32/classifications.json'
    if not p.exists():
        pytest.skip('build V3.2 real artifacts first')
    rows={r['symbol']:r for r in json.loads(p.read_text())}
    for a,b in [('501005','501006'),('501007','501008'),('501009','501010'),('501011','501012')]:
        x,y=rows[a],rows[b]
        assert x['legal_mandate_verified'] and y['legal_mandate_verified']
        assert x['exact_index_key']==y['exact_index_key']
        assert x['share_class']=='A' and y['share_class']=='C'
        assert x['tracking_mode']==y['tracking_mode']=='PASSIVE_INDEX'
        assert not x['needs_review'] and not y['needs_review']
        assert x['source_date']>='2026-01-01'
        assert x['valid_from']=='2026-11-12' and x['known_from']=='2026-11-13'
    assert rows['501011']['replication_method']=='TARGET_ETF_FOF'
    assert rows['501011']['reported_contract_effective_date']=='2022-12-02'
    # Unresearched LOFs do not inherit their peers' legal approval.
    assert rows['501016']['needs_review'] and not rows['501016']['legal_mandate_verified']


def test_v32_parquet_is_readable_data_instead_of_lfs_pointer():
    p=Path(__file__).parent/'output_v32/classifications.parquet'
    if not p.exists():
        pytest.skip('build V3.2 real artifacts first')
    assert p.read_bytes().startswith(b'PAR1')
    frame=pd.read_parquet(p)
    rows=json.loads(p.with_suffix('.json').read_text())
    assert frame.symbol.tolist()==[r['symbol'] for r in rows]
    assert len(frame)==2147


def test_v32_current_rename_alias_does_not_create_historical_knowledge():
    root=Path(__file__).parent
    events=json.loads((root/'index_history_events_v32.json').read_text())
    assert {x['reported_effective_date'] for x in events}=={'2024-12-09','2025-09-08','2025-09-15'}
    assert all(not x['historical_publication_date_verified'] for x in events)
    by_code,by_name=registry_inputs(root/'snapshot/official','2026-11-12')
    old=by_code[next(iter(by_name['恒生香港上市生物科技指数']))]
    new=by_code[next(iter(by_name['恒生生物科技指数']))]
    assert old['key']==new['key']=='HSI:HSBIO'
    p=root/'output_v32/classifications.json'
    if p.exists():
        rows=json.loads(p.read_text())
        assert not classifications_at(rows,'2025-09-16')[0]
        assert all(r['known_from']=='2026-11-13' for r in rows)

