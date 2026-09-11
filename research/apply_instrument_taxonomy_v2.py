#!/usr/bin/env python3
"""Idempotent V2 post-processor for ETF/LOF instrument metadata.

Purpose
-------
The first-pass metadata builder intentionally uses coarse name rules. This script
runs *after* the builder and upgrades current rows to the research taxonomy used
for universe de-duplication and later Trendability work.

Principles
----------
- No returns, backtest results, scores, or future performance are used.
- product wrapper (ETF/LOF) is separate from economic exposure.
- underlying_key is the finer exposure identity; risk_bucket is the coarser
  economic bucket used for de-duplication.
- verified fixed-income products and a few cross-border edge cases use exact
  symbol overrides; deterministic name rules handle the remaining clear cases.
- ambiguous rows are left needs_review=True instead of being guessed.

This script is safe to re-run after `build_instrument_metadata_universe_v4.py`.
"""
from __future__ import annotations

import argparse
import os
from typing import Any

from sqlalchemy import create_engine, text


MANUAL_BONDS: dict[str, tuple[str, str, str, str, str]] = {
    # symbol: (name, exposure_level2, underlying_key, risk_bucket, style_sector)
    "159110": ("科创债ETF万家", "TECH_INNOVATION_BOND", "CHINA_TECH_INNOVATION_BOND_AAA", "CHINA_TECH_INNOVATION_BOND", "TECH_INNOVATION_BOND"),
    "159111": ("科创债ETF天弘", "TECH_INNOVATION_BOND", "CHINA_TECH_INNOVATION_BOND_AAA", "CHINA_TECH_INNOVATION_BOND", "TECH_INNOVATION_BOND"),
    "159112": ("科创债ETF银华", "TECH_INNOVATION_BOND", "CHINA_TECH_INNOVATION_BOND_AAA", "CHINA_TECH_INNOVATION_BOND", "TECH_INNOVATION_BOND"),
    "159113": ("科创债ETF大成", "TECH_INNOVATION_BOND", "CHINA_TECH_INNOVATION_BOND_AAA", "CHINA_TECH_INNOVATION_BOND", "TECH_INNOVATION_BOND"),
    "159115": ("科创债ETF华安", "TECH_INNOVATION_BOND", "CHINA_TECH_INNOVATION_BOND_AAA", "CHINA_TECH_INNOVATION_BOND", "TECH_INNOVATION_BOND"),
    "159116": ("科创债ETF工银", "TECH_INNOVATION_BOND", "CHINA_TECH_INNOVATION_BOND_AAA", "CHINA_TECH_INNOVATION_BOND", "TECH_INNOVATION_BOND"),
    "159200": ("科创债ETF富国", "TECH_INNOVATION_BOND", "CHINA_TECH_INNOVATION_BOND_AAA", "CHINA_TECH_INNOVATION_BOND", "TECH_INNOVATION_BOND"),
    "159400": ("科创债ETF景顺长城", "TECH_INNOVATION_BOND", "CHINA_TECH_INNOVATION_BOND_AAA", "CHINA_TECH_INNOVATION_BOND", "TECH_INNOVATION_BOND"),
    "159600": ("科创债ETF嘉实", "TECH_INNOVATION_BOND", "CHINA_TECH_INNOVATION_BOND_AAA", "CHINA_TECH_INNOVATION_BOND", "TECH_INNOVATION_BOND"),
    "159700": ("科创债ETF南方", "TECH_INNOVATION_BOND", "CHINA_TECH_INNOVATION_BOND_AAA", "CHINA_TECH_INNOVATION_BOND", "TECH_INNOVATION_BOND"),
    "511120": ("科创债ETF广发", "TECH_INNOVATION_BOND", "CHINA_TECH_INNOVATION_BOND_AAA", "CHINA_TECH_INNOVATION_BOND", "TECH_INNOVATION_BOND"),
    "511150": ("科创债ETF永赢", "TECH_INNOVATION_BOND", "CHINA_TECH_INNOVATION_BOND_AAA", "CHINA_TECH_INNOVATION_BOND", "TECH_INNOVATION_BOND"),
    "159395": ("信用债ETF大成", "CREDIT_BOND", "CHINA_MARKET_MAKING_CREDIT_BOND", "CHINA_CREDIT_BOND", "CREDIT"),
    "159396": ("信用债ETF博时", "CREDIT_BOND", "CHINA_MARKET_MAKING_CREDIT_BOND", "CHINA_CREDIT_BOND", "CREDIT"),
    "159397": ("信用债ETF广发", "CREDIT_BOND", "CHINA_MARKET_MAKING_CREDIT_BOND", "CHINA_CREDIT_BOND", "CREDIT"),
    "159398": ("信用债ETF天弘", "CREDIT_BOND", "CHINA_MARKET_MAKING_CREDIT_BOND", "CHINA_CREDIT_BOND", "CREDIT"),
    "511030": ("公司债ETF平安", "CREDIT_BOND", "CHINA_CORPORATE_BOND", "CHINA_CREDIT_BOND", "CREDIT"),
    "511070": ("公司债ETF南方", "CREDIT_BOND", "CHINA_CORPORATE_BOND", "CHINA_CREDIT_BOND", "CREDIT"),
    "511110": ("公司债ETF易方达", "CREDIT_BOND", "CHINA_MARKET_MAKING_CORPORATE_BOND", "CHINA_CREDIT_BOND", "CREDIT"),
    "511190": ("信用债ETF海富通", "CREDIT_BOND", "CHINA_CREDIT_BOND", "CHINA_CREDIT_BOND", "CREDIT"),
    "511200": ("信用债ETF华夏", "CREDIT_BOND", "CHINA_CREDIT_BOND", "CHINA_CREDIT_BOND", "CREDIT"),
    "159816": ("0-4年地方债ETF鹏华", "LOCAL_GOV_BOND", "CHINA_LOCAL_GOV_BOND_0_4Y", "CHINA_LOCAL_GOV_BOND", "LOCAL_GOVERNMENT"),
    "159972": ("5年地方债ETF鹏华", "LOCAL_GOV_BOND", "CHINA_LOCAL_GOV_BOND_5Y", "CHINA_LOCAL_GOV_BOND", "LOCAL_GOVERNMENT"),
    "511010": ("国债ETF国泰", "GOVERNMENT_BOND", "CHINA_GOV_BOND_5Y", "CHINA_GOV_BOND", "GOVERNMENT"),
    "511020": ("国债ETF平安", "GOVERNMENT_BOND", "CHINA_GOV_BOND_5_10Y", "CHINA_GOV_BOND", "GOVERNMENT"),
    "511060": ("5年地方债ETF海富通", "LOCAL_GOV_BOND", "CHINA_LOCAL_GOV_BOND_5Y", "CHINA_LOCAL_GOV_BOND", "LOCAL_GOVERNMENT"),
    "511090": ("30年国债ETF鹏扬", "GOVERNMENT_BOND", "CHINA_GOV_BOND_30Y", "CHINA_GOV_BOND", "GOVERNMENT"),
    "511100": ("国债ETF华夏", "GOVERNMENT_BOND", "CHINA_GOV_BOND_GENERAL", "CHINA_GOV_BOND", "GOVERNMENT"),
    "511130": ("30年国债ETF博时", "GOVERNMENT_BOND", "CHINA_GOV_BOND_30Y", "CHINA_GOV_BOND", "GOVERNMENT"),
    "511160": ("国债ETF东财", "GOVERNMENT_BOND", "CHINA_GOV_BOND_1_3Y", "CHINA_GOV_BOND", "GOVERNMENT"),
    "511260": ("十年国债ETF国泰", "GOVERNMENT_BOND", "CHINA_GOV_BOND_10Y", "CHINA_GOV_BOND", "GOVERNMENT"),
    "511270": ("10年地方债ETF海富通", "LOCAL_GOV_BOND", "CHINA_LOCAL_GOV_BOND_10Y", "CHINA_LOCAL_GOV_BOND", "LOCAL_GOVERNMENT"),
    "511520": ("政金债ETF富国", "POLICY_BANK_BOND", "CHINA_POLICY_BANK_BOND_7_10Y", "CHINA_POLICY_BANK_BOND", "POLICY_BANK"),
    "511580": ("国债政金债ETF招商", "GOV_POLICY_BANK_BOND", "CHINA_GOV_POLICY_BANK_BOND_0_3Y", "CHINA_GOV_POLICY_BANK_BOND", "GOV_POLICY_BANK"),
    "511180": ("可转债ETF海富通", "CONVERTIBLE_BOND", "CHINA_INVESTMENT_GRADE_CONVERTIBLE_BOND", "CHINA_CONVERTIBLE_BOND", "CONVERTIBLE"),
    "511360": ("短融ETF海富通", "SHORT_CREDIT_BOND", "CHINA_SHORT_TERM_FINANCING_BOND", "CHINA_SHORT_CREDIT_BOND", "SHORT_CREDIT"),
}


def db_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg2://" + raw[len("postgresql://"):]
    return raw


def anyof(name: str, words: tuple[str, ...]) -> bool:
    return any(w in name for w in words)


def output(asset_class: str, region: str, exp1: str, bucket: str, key: str,
           style: str = "BROAD", qdii: bool | None = None,
           confidence: float = 0.90) -> dict[str, Any]:
    if qdii is None:
        qdii = region in {"US", "BR", "GLOBAL", "CN_OFFSHORE"}
    tags = {
        "US": ["US"], "BR": ["BR"], "GLOBAL": ["GLOBAL", "CN", "HK", "US"],
        "CN_OFFSHORE": ["CN_OFFSHORE", "HK", "US"], "CN": ["CN"],
    }.get(region, [region])
    currency = {"US": "USD", "BR": "BRL", "GLOBAL": "MULTI", "CN_OFFSHORE": "MULTI", "CN": "CNY"}.get(region)
    return dict(asset_class=asset_class, region_primary=region, region_tags=tags,
                exposure_level1=exp1, exposure_level2=bucket,
                underlying_key=key, risk_bucket=bucket, style_sector=style,
                is_qdii=qdii, premium_sensitive=qdii, currency_exposure=currency,
                confidence=confidence)


def classify(symbol: str, name: str | None) -> dict[str, Any] | None:
    n = name or ""

    # Verified edge cases first.
    if symbol == "162719":
        return output("EQUITY", "US", "US_EQUITY", "US_ENERGY_EQUITY",
                      "DOW_JONES_US_OIL_GAS_EXPLORATION_PRODUCTION", "ENERGY", True, 0.99)
    if symbol == "513360":
        return output("EQUITY", "GLOBAL", "GLOBAL_CHINA_EQUITY", "GLOBAL_CHINA_EDUCATION",
                      "CSI_GLOBAL_CHINA_EDUCATION", "EDUCATION", True, 0.99)
    if symbol == "563330":
        return output("EQUITY", "CN", "CHINA_EQUITY", "CHINA_BROAD_A_SHARE",
                      "CSI_A_SHARE", "BROAD", False, 0.99)
    exact = {
        "561780": ("CHINA_SMALL_CSI1000", "CSI1000_ENHANCED", "ENHANCED_INDEX"),
        "159678": ("CHINA_MID_CSI500", "CSI500_ENHANCED", "ENHANCED_INDEX"),
        "512380": ("CHINA_BROAD_MSCI_A", "MSCI_CHINA_A_RMB", "BROAD"),
        "159918": ("CHINA_SMALL_GROWTH", "SME_CHINEXT_400", "GROWTH"),
        "515200": ("CHINA_INNOVATION_GROWTH", "CSI_RND_INNOVATION_100", "GROWTH"),
        "510020": ("CHINA_LARGE_MEGA_CAP", "SSE_SUPER_LARGE_CAP", "BROAD"),
    }
    if symbol in exact:
        bucket, key, style = exact[symbol]
        return output("EQUITY", "CN", "CHINA_EQUITY", bucket, key, style, False, 0.95)

    # Wrapper-independent asset classes.
    if (("黄金ETF" in n and "黄金股" not in n) or n.startswith("上海金ETF") or n.startswith("金ETF")):
        return output("COMMODITY", "GLOBAL", "COMMODITY", "PRECIOUS_METALS_GOLD", "GOLD_SPOT", "COMMODITY", False)
    if anyof(n, ("日利ETF", "添益ETF", "日日鑫ETF", "快线ETF", "快钱ETF", "财富宝ETF", "货币ETF")):
        return output("CASHLIKE", "CN", "CHINA_CASH_MANAGEMENT", "CHINA_CASHLIKE", "CNY_CASH_MANAGEMENT", "CASH", False)

    # Cross-border equity exposures.
    if anyof(n, ("中概互联", "中概互联网")):
        return output("EQUITY", "CN_OFFSHORE", "CHINA_OFFSHORE_EQUITY", "CHINA_OFFSHORE_INTERNET", "CHINA_OFFSHORE_INTERNET", "TECHNOLOGY", True)
    if "巴西" in n:
        return output("EQUITY", "BR", "BRAZIL_EQUITY", "BRAZIL_EQUITY", "BRAZIL_EQUITY", "BROAD", True)
    if "道琼斯" in n:
        return output("EQUITY", "US", "US_EQUITY", "US_DOW_JONES", "DOW_JONES_INDUSTRIAL_AVERAGE", "BROAD", True)
    if "美国50" in n:
        return output("EQUITY", "US", "US_EQUITY", "US_LARGE_50", "US_LARGE_CAP_50", "BROAD", True)

    # Broad China indices and factors.
    broad: list[tuple[tuple[str, ...], str, str, str]] = [
        (("富时A50",), "CHINA_LARGE_A50", "FTSE_CHINA_A50", "BROAD"),
        (("中证A50",), "CHINA_LARGE_A50", "CSI_A50", "BROAD"),
        (("中国A50ETF", "A50ETF"), "CHINA_LARGE_A50", "MSCI_CHINA_A50_CONNECT", "BROAD"),
        (("中证A100", "A100ETF"), "CHINA_LARGE_A100", "CSI_A100", "BROAD"),
        (("中证800",), "CHINA_BROAD_CSI800", "CSI800", "BROAD"),
        (("MSCI中国A股", "MSCIA股"), "CHINA_BROAD_MSCI_A", "MSCI_CHINA_A_RMB", "BROAD"),
        (("上证180",), "CHINA_LARGE_SSE180", "SSE180", "BROAD"),
        (("上证380",), "CHINA_MID_SSE380", "SSE380", "BROAD"),
        (("上证中盘",), "CHINA_MID_SSE_MIDCAP", "SSE_MIDCAP", "BROAD"),
        (("上证指数",), "CHINA_BROAD_SSE_COMPOSITE", "SSE_COMPOSITE", "BROAD"),
        (("深证100", "深100ETF"), "CHINA_LARGE_SZSE100", "SZSE100", "BROAD"),
        (("深证50",), "CHINA_LARGE_SZSE50", "SZSE50", "BROAD"),
        (("深证成指", "深成ETF"), "CHINA_BROAD_SZSE_COMPONENT", "SZSE_COMPONENT", "BROAD"),
        (("中小100",), "CHINA_SMALL_SME100", "SME100", "BROAD"),
        (("创100",), "CHINA_GROWTH_CHINEXT100", "CHINEXT100", "GROWTH"),
        (("创业大盘",), "CHINA_GROWTH_CHINEXT_LARGE", "CHINEXT_LARGE_CAP", "GROWTH"),
        (("创业综指",), "CHINA_GROWTH_CHINEXT_COMPOSITE", "CHINEXT_COMPOSITE", "GROWTH"),
        (("双创50",), "CHINA_GROWTH_STAR_CHINEXT50", "STAR_CHINEXT_50", "GROWTH"),
    ]
    for words, bucket, key, style in broad:
        if anyof(n, words):
            return output("EQUITY", "CN", "CHINA_EQUITY", bucket, key, style, False)

    if anyof(n, ("现金流", "自由现金流")):
        if "300自由现金流" in n: key = "CSI300_FREE_CASH_FLOW"
        elif anyof(n, ("800现金流", "现金流ETF800", "自由现金流800")): key = "CSI800_CASH_FLOW"
        elif anyof(n, ("全指现金流", "现金流全指")): key = "ALL_SHARE_CASH_FLOW"
        else: key = "CHINA_CASH_FLOW_FACTOR"
        return output("EQUITY", "CN", "CHINA_EQUITY", "CHINA_FACTOR_CASH_FLOW", key, "CASH_FLOW", False)
    factor_rules = [
        (("价值ETF", "大盘价值"), "CHINA_FACTOR_VALUE", "CHINA_VALUE_FACTOR", "VALUE"),
        (("质量ETF", "质量成长", "漂亮50"), "CHINA_FACTOR_QUALITY", "CHINA_QUALITY_FACTOR", "QUALITY"),
        (("成长ETF", "深成长ETF"), "CHINA_FACTOR_GROWTH", "CHINA_GROWTH_FACTOR", "GROWTH"),
        (("ESG",), "CHINA_FACTOR_ESG", "CHINA_ESG_FACTOR", "ESG"),
        (("基本面50",), "CHINA_FACTOR_FUNDAMENTAL", "CHINA_FUNDAMENTAL_50", "FACTOR"),
        (("等权",), "CHINA_FACTOR_EQUAL_WEIGHT", "CHINA_EQUAL_WEIGHT_FACTOR", "FACTOR"),
    ]
    for words, bucket, key, style in factor_rules:
        if anyof(n, words):
            return output("EQUITY", "CN", "CHINA_EQUITY", bucket, key, style, False)

    # China industries/themes. Order is intentional (specific before generic).
    theme_rules = [
        (("信创", "信息安全"), "CHINA_CYBERSECURITY", "CHINA_CYBERSECURITY", "TECHNOLOGY"),
        (("数字经济",), "CHINA_DIGITAL_ECONOMY", "CHINA_DIGITAL_ECONOMY", "TECHNOLOGY"),
        (("工业互联网",), "CHINA_INDUSTRIAL_INTERNET", "CHINA_INDUSTRIAL_INTERNET", "TECHNOLOGY"),
        (("物联网",), "CHINA_IOT", "CHINA_IOT", "TECHNOLOGY"),
        (("TMT",), "CHINA_TMT", "CHINA_TMT", "TECHNOLOGY"),
        (("VR",), "CHINA_VR", "CHINA_VR", "TECHNOLOGY"),
        (("信息技术", "信息科技"), "CHINA_INFORMATION_TECH", "CHINA_INFORMATION_TECH", "TECHNOLOGY"),
        (("互联网",), "CHINA_INTERNET", "CHINA_INTERNET", "TECHNOLOGY"),
        (("科技",), "CHINA_TECH_BROAD", "CHINA_TECH_BROAD", "TECHNOLOGY"),
        (("中药",), "CHINA_HEALTHCARE_TCM", "CHINA_TRADITIONAL_CHINESE_MEDICINE", "HEALTHCARE"),
        (("疫苗",), "CHINA_HEALTHCARE_VACCINE", "CHINA_VACCINE", "HEALTHCARE"),
        (("生物科技",), "CHINA_HEALTHCARE_BIOTECH", "CHINA_BIOTECH", "HEALTHCARE"),
        (("药ETF",), "CHINA_HEALTHCARE_PHARMA", "CHINA_PHARMA", "HEALTHCARE"),
        (("卫星",), "CHINA_AEROSPACE_DEFENSE", "CHINA_SATELLITE", "DEFENSE"),
        (("航天",), "CHINA_AEROSPACE_DEFENSE", "CHINA_SPACE", "DEFENSE"),
        (("通用航空",), "CHINA_AEROSPACE_DEFENSE", "CHINA_GENERAL_AVIATION", "DEFENSE"),
        (("航空",), "CHINA_AEROSPACE_DEFENSE", "CHINA_AVIATION", "DEFENSE"),
        (("军工", "国防"), "CHINA_DEFENSE", "CHINA_DEFENSE", "DEFENSE"),
        (("交运", "交通运输"), "CHINA_TRANSPORTATION", "CHINA_TRANSPORTATION", "INDUSTRIALS"),
        (("化工",), "CHINA_CHEMICAL", "CHINA_CHEMICAL", "MATERIALS"),
        (("稀有金属",), "CHINA_RARE_METALS", "CHINA_RARE_METALS", "MATERIALS"),
        (("新材料", "材料ETF"), "CHINA_MATERIALS", "CHINA_MATERIALS", "MATERIALS"),
        (("矿业",), "CHINA_MINING", "CHINA_MINING", "MATERIALS"),
        (("石化",), "CHINA_PETROCHEMICAL", "CHINA_PETROCHEMICAL", "ENERGY"),
        (("油气", "石油ETF"), "CHINA_OIL_GAS_EQUITY", "CHINA_OIL_GAS_EQUITY", "ENERGY"),
        (("能源ETF",), "CHINA_ENERGY_EQUITY", "CHINA_ENERGY_EQUITY", "ENERGY"),
        (("农牧",), "CHINA_AGRICULTURE_EQUITY", "CHINA_AGRICULTURE_LIVESTOCK", "AGRICULTURE"),
        (("粮食",), "CHINA_AGRICULTURE_EQUITY", "CHINA_AGRICULTURE_GRAIN", "AGRICULTURE"),
        (("低碳", "碳中和"), "CHINA_LOW_CARBON", "CHINA_LOW_CARBON", "LOW_CARBON"),
        (("环保",), "CHINA_ENVIRONMENTAL", "CHINA_ENVIRONMENTAL", "ENVIRONMENTAL"),
        (("电网设备",), "CHINA_POWER_GRID", "CHINA_POWER_GRID", "INDUSTRIALS"),
        (("机床",), "CHINA_MACHINERY", "CHINA_MACHINE_TOOL", "INDUSTRIALS"),
        (("工程机械",), "CHINA_MACHINERY", "CHINA_CONSTRUCTION_MACHINERY", "INDUSTRIALS"),
        (("机械ETF",), "CHINA_MACHINERY", "CHINA_MACHINERY", "INDUSTRIALS"),
        (("高端制造",), "CHINA_ADVANCED_MANUFACTURING", "CHINA_ADVANCED_MANUFACTURING", "INDUSTRIALS"),
        (("高端装备",), "CHINA_ADVANCED_MANUFACTURING", "CHINA_ADVANCED_EQUIPMENT", "INDUSTRIALS"),
        (("保险",), "CHINA_INSURANCE", "CHINA_INSURANCE", "FINANCIALS"),
        (("影视",), "CHINA_MEDIA_FILM", "CHINA_MEDIA_FILM", "MEDIA"),
        (("旅游",), "CHINA_TOURISM", "CHINA_TOURISM", "CONSUMER"),
        (("一带一路",), "CHINA_BELT_ROAD", "CHINA_BELT_ROAD", "THEME"),
        (("长三角",), "CHINA_REGIONAL_YRD", "CHINA_REGIONAL_YRD", "REGIONAL"),
        (("成渝",), "CHINA_REGIONAL_CHENGYU", "CHINA_REGIONAL_CHENGYU", "REGIONAL"),
        (("浙江国资", "之江凤凰"), "CHINA_REGIONAL_ZHEJIANG", "CHINA_REGIONAL_ZHEJIANG", "REGIONAL"),
        (("专精特新",), "CHINA_SPECIALIZED_SME", "CHINA_SPECIALIZED_SME", "SME"),
        (("战略新兴",), "CHINA_NEW_ECONOMY", "CHINA_STRATEGIC_EMERGING", "GROWTH"),
        (("新经济",), "CHINA_NEW_ECONOMY", "CHINA_NEW_ECONOMY", "GROWTH"),
        (("国货",), "CHINA_DOMESTIC_BRANDS", "CHINA_DOMESTIC_BRANDS", "CONSUMER"),
        (("大宗商品",), "CHINA_RESOURCES_EQUITY", "CHINA_COMMODITY_PRODUCER_EQUITY", "MATERIALS"),
        (("消电",), "CHINA_ELECTRONICS", "CHINA_CONSUMER_ELECTRONICS", "TECHNOLOGY"),
        (("电子ETF", "电子50"), "CHINA_ELECTRONICS", "CHINA_ELECTRONICS", "TECHNOLOGY"),
        (("电信",), "CHINA_TELECOM", "CHINA_TELECOM", "COMMUNICATION"),
    ]
    for words, bucket, key, style in theme_rules:
        if anyof(n, words):
            return output("EQUITY", "CN", "CHINA_EQUITY", bucket, key, style, False)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    engine = create_engine(db_url(args.database_url), pool_pre_ping=True)

    # If a first-pass rebuild inserted a newer active row for one of the manually
    # verified bond codes, close any older overlapping active row. The older row
    # remains the historical segment; the newest row becomes the current segment.
    manual_syms = tuple(MANUAL_BONDS)
    with engine.begin() as conn:
        conn.execute(text("""
            with latest as (
              select symbol, max(valid_from) as latest_from
              from public.instrument_metadata
              where valid_to is null and symbol = any(:symbols)
              group by symbol
            )
            update public.instrument_metadata m
               set valid_to = l.latest_from - 1, updated_at=now()
              from latest l
             where m.symbol=l.symbol and m.valid_to is null and m.valid_from < l.latest_from
        """), {"symbols": list(manual_syms)})

        current = conn.execute(text("""
            select * from public.instrument_metadata_current
            where has_daily_bars
              and (needs_review or risk_bucket in ('CHINA_EQUITY_OTHER','US_EQUITY_OTHER')
                   or underlying_key is null or risk_bucket is null
                   or symbol = any(:manual_symbols)
                   or symbol in ('162719','513360','563330'))
            order by symbol
        """), {"manual_symbols": list(manual_syms)}).mappings().all()

        upd = text("""
            update public.instrument_metadata set
              name=coalesce(:name,name), product_type=coalesce(:product_type,product_type),
              asset_class=:asset_class, region_primary=:region_primary, region_tags=:region_tags,
              exposure_level1=:exposure_level1, exposure_level2=:exposure_level2,
              underlying_key=:underlying_key, risk_bucket=:risk_bucket, style_sector=:style_sector,
              is_qdii=:is_qdii, premium_sensitive=:premium_sensitive,
              derivative_exposure=coalesce(:derivative_exposure,derivative_exposure),
              roll_cost_exposure=coalesce(:roll_cost_exposure,roll_cost_exposure),
              currency_exposure=:currency_exposure,
              classification_method=:classification_method, confidence=:confidence,
              needs_review=:needs_review, metadata_source=:metadata_source, updated_at=now()
            where id=:id
        """)
        updated = 0
        unresolved: list[tuple[str, str | None]] = []
        for row in current:
            sym = row["symbol"]
            if sym in MANUAL_BONDS:
                nm, exp2, key, bucket, style = MANUAL_BONDS[sym]
                meta = output("BOND", "CN", "CHINA_FIXED_INCOME", bucket, key, style, False, 0.99)
                meta["exposure_level2"] = exp2
                extra = dict(name=nm, product_type="ETF", derivative_exposure=False,
                             roll_cost_exposure=False, classification_method="MANUAL_VERIFIED_V2",
                             needs_review=False, metadata_source="verified fixed-income identity; taxonomy v2")
            else:
                meta = classify(sym, row["name"])
                if meta is None:
                    unresolved.append((sym, row["name"]))
                    continue
                extra = dict(name=None, product_type=None, derivative_exposure=None,
                             roll_cost_exposure=None,
                             classification_method="MANUAL_VERIFIED_V2" if sym in {"162719","513360","563330"} else "AUTO_NAME_V2",
                             needs_review=False,
                             metadata_source="instrument exposure taxonomy v2; no performance data used")
            params = dict(row=0, id=row["id"], **meta, **extra)
            conn.execute(upd, params)
            updated += 1

        stats = conn.execute(text("""
            select count(*) as with_bars,
                   count(*) filter(where needs_review) as needs_review,
                   count(*) filter(where risk_bucket='CHINA_EQUITY_OTHER') as china_other,
                   count(*) filter(where risk_bucket='US_EQUITY_OTHER') as us_other,
                   count(*) filter(where underlying_key is null or risk_bucket is null) as missing_key_or_bucket,
                   count(*) filter(where name is null) as missing_name
            from public.instrument_metadata_current where has_daily_bars
        """)).mappings().one()

    print(f"taxonomy_v2 updated={updated}")
    print(dict(stats))
    if unresolved:
        print("unresolved:")
        for sym, nm in unresolved:
            print(sym, nm)


if __name__ == "__main__":
    main()
