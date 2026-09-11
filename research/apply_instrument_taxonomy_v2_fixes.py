#!/usr/bin/env python3
"""Second-stage deterministic fixes for taxonomy V2.

Covers systematic cases that coarse V1 rules can misclassify even when they are
not marked OTHER, notably gold-miner equities, S&P sector ETFs, global-oil equity
LOFs and Hong Kong sector/theme funds. No performance data is used.
"""
from __future__ import annotations
import argparse, os
from sqlalchemy import create_engine, text


def db_url(raw: str) -> str:
    if raw.startswith('postgres://'):
        return 'postgresql+psycopg2://' + raw[len('postgres://'):]
    if raw.startswith('postgresql://'):
        return 'postgresql+psycopg2://' + raw[len('postgresql://'):]
    return raw

SQL = r"""
update public.instrument_metadata
set asset_class='EQUITY', region_primary='CN', region_tags=array['CN','HK']::text[],
    exposure_level1='CHINA_HK_EQUITY', exposure_level2='CHINA_HK_GOLD_MINERS',
    underlying_key='CSI_SH_SZ_HK_GOLD_INDUSTRY', risk_bucket='CHINA_HK_GOLD_MINERS',
    style_sector='MATERIALS', is_qdii=false, premium_sensitive=false, currency_exposure='CNY',
    classification_method='MANUAL_VERIFIED_V2', confidence=0.99, needs_review=false,
    metadata_source='verified gold-miner equity index exposure; taxonomy v2', updated_at=now()
where valid_to is null and has_daily_bars and name like '%黄金股ETF%';

update public.instrument_metadata
set asset_class='EQUITY', region_primary='GLOBAL', region_tags=array['GLOBAL','US','EU']::text[],
    exposure_level1='GLOBAL_EQUITY', exposure_level2='GLOBAL_OIL_GAS_EQUITY',
    underlying_key='SP_GLOBAL_OIL_EQUITY', risk_bucket='GLOBAL_OIL_GAS_EQUITY', style_sector='ENERGY',
    is_qdii=true, premium_sensitive=true, currency_exposure='MULTI', derivative_exposure=false, roll_cost_exposure=false,
    classification_method='MANUAL_VERIFIED_V2', confidence=0.99, needs_review=false,
    metadata_source='verified Huaan S&P Global Oil equity-index QDII; taxonomy v2', updated_at=now()
where valid_to is null and symbol='160416';

update public.instrument_metadata
set asset_class='EQUITY', region_primary='US', region_tags=array['US']::text[], exposure_level1='US_EQUITY',
    exposure_level2='US_OIL_GAS_EQUITY', underlying_key='SP_OIL_GAS_EXPLORATION_PRODUCTION_SELECT',
    risk_bucket='US_OIL_GAS_EQUITY', style_sector='ENERGY', is_qdii=true, premium_sensitive=true,
    currency_exposure='USD', classification_method='MANUAL_VERIFIED_V2', confidence=0.99, needs_review=false,
    metadata_source='verified S&P Oil & Gas Exploration & Production Select Industry exposure', updated_at=now()
where valid_to is null and symbol in ('159518','513350');

update public.instrument_metadata
set asset_class='EQUITY', region_primary='US', region_tags=array['US']::text[], exposure_level1='US_EQUITY',
    exposure_level2='US_BIOTECH', underlying_key='SP_BIOTECH_SELECT_INDUSTRY', risk_bucket='US_BIOTECH',
    style_sector='BIOTECH', is_qdii=true, premium_sensitive=true, currency_exposure='USD',
    classification_method='MANUAL_VERIFIED_V2', confidence=0.99, needs_review=false,
    metadata_source='verified S&P Biotechnology Select Industry exposure', updated_at=now()
where valid_to is null and symbol='159502';

update public.instrument_metadata
set asset_class='EQUITY', region_primary='CN', region_tags=array['CN']::text[], exposure_level1='CHINA_EQUITY',
    exposure_level2='CHINA_DIVIDEND', underlying_key='SP_CHINA_A_SHARE_DIVIDEND_OPPORTUNITIES', risk_bucket='CHINA_DIVIDEND',
    style_sector='DIVIDEND', is_qdii=false, premium_sensitive=false, currency_exposure='CNY',
    classification_method='MANUAL_VERIFIED_V2', confidence=0.99, needs_review=false,
    metadata_source='verified S&P China A-Share Dividend Opportunities exposure', updated_at=now()
where valid_to is null and symbol='562060';

update public.instrument_metadata
set asset_class='CASHLIKE', region_primary='CN', region_tags=array['CN']::text[],
    exposure_level1='CHINA_CASH_MANAGEMENT', exposure_level2='CHINA_CASHLIKE',
    underlying_key='CNY_CASH_MANAGEMENT', risk_bucket='CHINA_CASHLIKE', style_sector='CASH',
    is_qdii=false, premium_sensitive=false, currency_exposure='CNY', needs_review=false, updated_at=now()
where valid_to is null and has_daily_bars and asset_class='CASHLIKE';

update public.instrument_metadata
set underlying_key='GOLD_SPOT', risk_bucket='PRECIOUS_METALS_GOLD', exposure_level2='PRECIOUS_METALS_GOLD',
    style_sector='COMMODITY', updated_at=now()
where valid_to is null and has_daily_bars and asset_class='COMMODITY'
  and risk_bucket='PRECIOUS_METALS_GOLD' and name not like '%黄金股ETF%';

update public.instrument_metadata
set exposure_level2='HK_INNOVATIVE_DRUG', underlying_key='HK_INNOVATIVE_DRUG', risk_bucket='HK_HEALTHCARE', style_sector='HEALTHCARE', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and name like '%创新药%';
update public.instrument_metadata
set exposure_level2='HK_BIOTECH', underlying_key='HK_BIOTECH', risk_bucket='HK_HEALTHCARE', style_sector='HEALTHCARE', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and name like '%生物科技%';
update public.instrument_metadata
set exposure_level2='HK_HEALTHCARE', underlying_key='HK_HEALTHCARE', risk_bucket='HK_HEALTHCARE', style_sector='HEALTHCARE', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and (name like '%医疗%' or name like '%医药%') and name not like '%创新药%' and name not like '%生物科技%';
update public.instrument_metadata
set exposure_level2='HK_CONSUMER', underlying_key='HK_CONSUMER', risk_bucket='HK_CONSUMER', style_sector='CONSUMER', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and name like '%消费%';
update public.instrument_metadata
set exposure_level2='HK_AUTOMOTIVE', underlying_key='HK_AUTOMOTIVE', risk_bucket='HK_AUTOMOTIVE', style_sector='AUTOMOTIVE', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and name like '%汽车%';
update public.instrument_metadata
set exposure_level2='HK_SECURITIES', underlying_key='HK_SECURITIES', risk_bucket='HK_SECURITIES', style_sector='FINANCIALS', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and name like '%证券%';
update public.instrument_metadata
set exposure_level2='HK_INFORMATION_TECH', underlying_key='HK_INFORMATION_TECH', risk_bucket='HK_TECH', style_sector='TECHNOLOGY', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and name like '%信息技术%';
update public.instrument_metadata
set exposure_level2='HK_NEW_ECONOMY', underlying_key='HK_NEW_ECONOMY', risk_bucket='HK_NEW_ECONOMY', style_sector='GROWTH', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and name like '%新经济%';
update public.instrument_metadata
set exposure_level2='HK_INTERNET', underlying_key='HK_INTERNET', risk_bucket='HK_TECH', style_sector='TECHNOLOGY', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and name like '%互联网%';

update public.instrument_metadata
set exposure_level2='HK_H_SHARE', underlying_key='HANG_SENG_CHINA_ENTERPRISES', risk_bucket='HK_H_SHARE', style_sector='BROAD', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and (name like '%恒生中国企业%' or name like '%恒生国企%');
update public.instrument_metadata
set exposure_level2='HK_CONNECT_100', underlying_key='HK_CONNECT_100', risk_bucket='HK_BROAD', style_sector='BROAD', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and name like '%港股通100%';
update public.instrument_metadata
set exposure_level2='HK_CONNECT_50', underlying_key='HK_CONNECT_50', risk_bucket='HK_BROAD', style_sector='BROAD', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and name like '%港股通50%';
update public.instrument_metadata
set exposure_level2='HANG_SENG_INDEX', underlying_key='HANG_SENG_INDEX', risk_bucket='HK_BROAD', style_sector='BROAD', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='HK' and (name like '%恒生指数%' or name like '%恒指港股通%' or name in ('恒生ETF华夏','恒生ETF易方达','恒生ETF鹏华'));

update public.instrument_metadata
set exposure_level2='HK_CONNECT_50', underlying_key='HANG_SENG_STOCK_CONNECT_50', risk_bucket='HK_BROAD', style_sector='BROAD', classification_method='MANUAL_VERIFIED_V2', confidence=0.99, updated_at=now()
where valid_to is null and symbol='159109';
update public.instrument_metadata
set exposure_level2='HK_SOE', underlying_key='CSI_HK_MAINLAND_SOE', risk_bucket='HK_SOE', style_sector='SOE', classification_method='MANUAL_VERIFIED_V2', confidence=0.99, updated_at=now()
where valid_to is null and symbol='159519';

update public.instrument_metadata
set exposure_level2='JAPAN_NIKKEI225', underlying_key='NIKKEI225', risk_bucket='JAPAN_EQUITY', style_sector='BROAD', classification_method='AUTO_NAME_V2', updated_at=now()
where valid_to is null and has_daily_bars and region_primary='JP' and name like '%日经%';
"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--database-url', default=os.getenv('ETF_DAILY_BARS_DATABASE_URL'))
    a = p.parse_args()
    if not a.database_url:
        raise SystemExit('Missing ETF_DAILY_BARS_DATABASE_URL')
    engine = create_engine(db_url(a.database_url), pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text(SQL))
        row = conn.execute(text("""
            select count(*) as with_bars,
                   count(*) filter(where needs_review) as needs_review,
                   count(*) filter(where risk_bucket in ('CHINA_EQUITY_OTHER','US_EQUITY_OTHER')) as other,
                   count(*) filter(where underlying_key is null or risk_bucket is null) as missing
            from public.instrument_metadata_current where has_daily_bars
        """)).mappings().one()
    print(dict(row))

if __name__ == '__main__':
    main()
