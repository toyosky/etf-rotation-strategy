#!/usr/bin/env python3
"""Build a first-pass ETF + LOF metadata taxonomy and persist it to Supabase.

Principles
----------
1. Product wrapper != economic exposure. We tag both.
2. Current-name based labels are NOT automatically considered historical-safe.
3. The original fixed15 and a few explicitly researched candidates have manual,
   exposure-level overrides. These are seeded as historical-manual labels from
   the first available bar date.
4. Everything else is deterministic AUTO_NAME_V1 classification from current
   AKShare/Eastmoney fund metadata. Unknown/generic rows remain needs_review.
5. No returns or future performance are used anywhere in the classification.

This is metadata infrastructure, not a strategy rule.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd
from sqlalchemy import create_engine, text

SNAPSHOT_DATE = date(2026, 9, 9)

# Canonical manually curated exposure labels for the original strategy universe
# plus the two repeatedly researched candidate exposures. These are structural
# labels only; they do not encode whether the asset was profitable.
MANUAL: dict[str, dict[str, Any]] = {
    "518880": dict(name="黄金ETF", product_type="ETF", asset_class="COMMODITY", region_primary="GLOBAL",
                   region_tags=["GLOBAL"], exposure_level1="COMMODITY", exposure_level2="PRECIOUS_METALS_GOLD",
                   underlying_key="GOLD", risk_bucket="PRECIOUS_METALS_GOLD", style_sector=None,
                   is_qdii=False, premium_sensitive=False, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure=None, t0_flag=None, notes="Original fixed15; physical/spot-gold exposure bucket."),
    "159985": dict(name="豆粕ETF", product_type="ETF", asset_class="COMMODITY", region_primary="CN",
                   region_tags=["CN"], exposure_level1="COMMODITY", exposure_level2="AGRICULTURE_SOYMEAL",
                   underlying_key="SOYMEAL_FUTURES", risk_bucket="AGRICULTURE_SOYMEAL", style_sector=None,
                   is_qdii=False, premium_sensitive=False, derivative_exposure=True, roll_cost_exposure=True,
                   currency_exposure="CNY", t0_flag=None, notes="Original fixed15; domestic soymeal-futures exposure."),
    "159825": dict(name="农业ETF富国", product_type="ETF", asset_class="EQUITY", region_primary="CN",
                   region_tags=["CN"], exposure_level1="CHINA_EQUITY", exposure_level2="AGRICULTURE_EQUITY",
                   underlying_key="CHINA_AGRICULTURE_EQUITY", risk_bucket="CHINA_AGRICULTURE_EQUITY", style_sector="AGRICULTURE",
                   is_qdii=False, premium_sensitive=False, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure="CNY", t0_flag=False, notes="Original fixed15; later retired from formal pool, retained as research reference."),
    "161226": dict(name="白银LOF", product_type="LOF", asset_class="COMMODITY", region_primary="CN",
                   region_tags=["CN", "GLOBAL_COMMODITY"], exposure_level1="COMMODITY", exposure_level2="PRECIOUS_METALS_SILVER",
                   underlying_key="SILVER_FUTURES", risk_bucket="PRECIOUS_METALS_SILVER", style_sector=None,
                   is_qdii=False, premium_sensitive=True, derivative_exposure=True, roll_cost_exposure=True,
                   currency_exposure="CNY", t0_flag=None, notes="Original fixed15; LOF wrapper, silver-futures economic exposure."),
    "513100": dict(name="纳指ETF", product_type="ETF", asset_class="EQUITY", region_primary="US",
                   region_tags=["US"], exposure_level1="US_EQUITY", exposure_level2="US_LARGE_GROWTH",
                   underlying_key="NASDAQ100", risk_bucket="US_NASDAQ100", style_sector="GROWTH_TECH_HEAVY",
                   is_qdii=True, premium_sensitive=True, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure="USD", t0_flag=True, notes="Original fixed15; QDII/cross-border execution constraints apply."),
    "159915": dict(name="创业板ETF", product_type="ETF", asset_class="EQUITY", region_primary="CN",
                   region_tags=["CN"], exposure_level1="CHINA_EQUITY", exposure_level2="CHINA_GROWTH",
                   underlying_key="CHINEXT", risk_bucket="CHINA_GROWTH_CHINEXT", style_sector="GROWTH",
                   is_qdii=False, premium_sensitive=False, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure="CNY", t0_flag=False, notes="Original fixed15."),
    "511220": dict(name="城投债ETF", product_type="ETF", asset_class="BOND", region_primary="CN",
                   region_tags=["CN"], exposure_level1="CHINA_FIXED_INCOME", exposure_level2="CREDIT_MUNICIPAL",
                   underlying_key="CITY_INVESTMENT_BOND", risk_bucket="CHINA_CREDIT_BOND", style_sector="CREDIT",
                   is_qdii=False, premium_sensitive=False, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure="CNY", t0_flag=None, notes="Original fixed15; strategy cash/carry proxy role."),
    "159509": dict(name="纳指科技ETF", product_type="ETF", asset_class="EQUITY", region_primary="US",
                   region_tags=["US"], exposure_level1="US_EQUITY", exposure_level2="US_TECH",
                   underlying_key="NASDAQ_TECH", risk_bucket="US_TECH", style_sector="TECHNOLOGY",
                   is_qdii=True, premium_sensitive=True, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure="USD", t0_flag=True, notes="Original fixed15; QDII/cross-border execution constraints apply."),
    "513290": dict(name="纳指生物ETF", product_type="ETF", asset_class="EQUITY", region_primary="US",
                   region_tags=["US"], exposure_level1="US_EQUITY", exposure_level2="US_BIOTECH",
                   underlying_key="NASDAQ_BIOTECH", risk_bucket="US_BIOTECH", style_sector="BIOTECH",
                   is_qdii=True, premium_sensitive=True, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure="USD", t0_flag=True, notes="Original fixed15; QDII/cross-border execution constraints apply."),
    "159529": dict(name="标普消费ETF", product_type="ETF", asset_class="EQUITY", region_primary="US",
                   region_tags=["US"], exposure_level1="US_EQUITY", exposure_level2="US_CONSUMER",
                   underlying_key="SP500_CONSUMER", risk_bucket="US_CONSUMER", style_sector="CONSUMER",
                   is_qdii=True, premium_sensitive=True, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure="USD", t0_flag=True, notes="Original fixed15; QDII/cross-border execution constraints apply."),
    "159981": dict(name="能源化工期货ETF", product_type="ETF", asset_class="COMMODITY", region_primary="CN",
                   region_tags=["CN"], exposure_level1="COMMODITY", exposure_level2="ENERGY_CHEMICAL",
                   underlying_key="ENERGY_CHEMICAL_FUTURES", risk_bucket="ENERGY_CHEMICAL", style_sector=None,
                   is_qdii=False, premium_sensitive=False, derivative_exposure=True, roll_cost_exposure=True,
                   currency_exposure="CNY", t0_flag=None, notes="Original fixed15; domestic commodity-futures basket."),
    "501018": dict(name="南方原油LOF", product_type="LOF", asset_class="COMMODITY", region_primary="GLOBAL",
                   region_tags=["GLOBAL", "US"], exposure_level1="COMMODITY", exposure_level2="ENERGY_CRUDE_OIL",
                   underlying_key="CRUDE_OIL", risk_bucket="ENERGY_CRUDE_OIL", style_sector=None,
                   is_qdii=True, premium_sensitive=True, derivative_exposure=True, roll_cost_exposure=True,
                   currency_exposure="USD", t0_flag=None, notes="Original fixed15; QDII LOF, premium/NAV-lag controls required."),
    "513920": dict(name="央企40ETF", product_type="ETF", asset_class="EQUITY", region_primary="CN",
                   region_tags=["CN"], exposure_level1="CHINA_EQUITY", exposure_level2="CENTRAL_SOE",
                   underlying_key="CENTRAL_SOE_40", risk_bucket="CHINA_SOE", style_sector="SOE_VALUE",
                   is_qdii=False, premium_sensitive=False, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure="CNY", t0_flag=False, notes="Original fixed15."),
    "511380": dict(name="转债ETF", product_type="ETF", asset_class="BOND", region_primary="CN",
                   region_tags=["CN"], exposure_level1="CHINA_FIXED_INCOME", exposure_level2="CONVERTIBLE_BOND",
                   underlying_key="CHINA_CONVERTIBLE_BOND", risk_bucket="CHINA_CONVERTIBLE_BOND", style_sector="CONVERTIBLE",
                   is_qdii=False, premium_sensitive=False, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure="CNY", t0_flag=None, notes="Original fixed15; hybrid equity/rates/credit exposure."),
    "164824": dict(name="印度基金LOF", product_type="LOF", asset_class="EQUITY", region_primary="IN",
                   region_tags=["IN"], exposure_level1="INDIA_EQUITY", exposure_level2="INDIA_BROAD",
                   underlying_key="INDIA_EQUITY", risk_bucket="INDIA_EQUITY", style_sector="BROAD",
                   is_qdii=True, premium_sensitive=True, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure="INR", t0_flag=None, notes="Original fixed15; QDII LOF, premium/NAV-lag controls required."),
    "512660": dict(name="军工ETF", product_type="ETF", asset_class="EQUITY", region_primary="CN",
                   region_tags=["CN"], exposure_level1="CHINA_EQUITY", exposure_level2="DEFENSE",
                   underlying_key="CHINA_DEFENSE", risk_bucket="CHINA_DEFENSE", style_sector="DEFENSE",
                   is_qdii=False, premium_sensitive=False, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure="CNY", t0_flag=False, notes="Researched candidate; not promoted to formal pool."),
    "513030": dict(name="德国DAXETF", product_type="ETF", asset_class="EQUITY", region_primary="DE",
                   region_tags=["DE", "EU"], exposure_level1="EUROPE_EQUITY", exposure_level2="GERMANY_BROAD",
                   underlying_key="DAX", risk_bucket="GERMANY_EQUITY", style_sector="BROAD",
                   is_qdii=True, premium_sensitive=True, derivative_exposure=False, roll_cost_exposure=False,
                   currency_exposure="EUR", t0_flag=True, notes="Researched candidate; not promoted to formal pool."),
}


def contains_any(name: str, words: list[str]) -> bool:
    s = name.upper()
    return any(w.upper() in s for w in words)


def canonical_region(name: str, asset_class: str) -> tuple[str | None, list[str]]:
    if contains_any(name, ["纳指", "纳斯达克", "标普", "S&P", "道琼斯", "美国", "罗素"]):
        return "US", ["US"]
    if contains_any(name, ["恒生", "港股", "香港", "H股", "港股通"]):
        return "HK", ["HK", "CN_OFFSHORE"]
    if contains_any(name, ["日经", "日本"]):
        return "JP", ["JP"]
    if contains_any(name, ["德国", "DAX"]):
        return "DE", ["DE", "EU"]
    if contains_any(name, ["法国", "CAC"]):
        return "FR", ["FR", "EU"]
    if contains_any(name, ["欧洲", "欧元区", "EURO"]):
        return "EU", ["EU"]
    if "印度" in name:
        return "IN", ["IN"]
    if "越南" in name:
        return "VN", ["VN"]
    if "沙特" in name:
        return "SA", ["SA"]
    if contains_any(name, ["东南亚", "亚太"]):
        return "ASIA", ["ASIA"]
    if contains_any(name, ["全球", "世界", "MSCI WORLD"]):
        return "GLOBAL", ["GLOBAL"]
    if asset_class in {"EQUITY", "BOND", "CASHLIKE"}:
        return "CN", ["CN"]
    return None, []


def classify_equity_cn(name: str) -> tuple[str, str, str | None, str]:
    rules = [
        (["沪深300", "300ETF"], "CHINA_LARGE", "CSI300", "CHINA_LARGE_CSI300"),
        (["中证500", "500ETF"], "CHINA_MID", "CSI500", "CHINA_MID_CSI500"),
        (["中证1000", "1000ETF"], "CHINA_SMALL", "CSI1000", "CHINA_SMALL_CSI1000"),
        (["中证2000", "2000ETF"], "CHINA_MICRO", "CSI2000", "CHINA_MICRO_CSI2000"),
        (["A500", "中证A500"], "CHINA_BROAD", "CSI_A500", "CHINA_BROAD_A500"),
        (["上证50"], "CHINA_LARGE", "SSE50", "CHINA_LARGE_SSE50"),
        (["创业板"], "CHINA_GROWTH", "CHINEXT", "CHINA_GROWTH_CHINEXT"),
        (["科创50"], "CHINA_GROWTH", "STAR50", "CHINA_GROWTH_STAR50"),
        (["科创100"], "CHINA_GROWTH", "STAR100", "CHINA_GROWTH_STAR100"),
        (["科创板", "科创"], "CHINA_GROWTH", "STAR_MARKET", "CHINA_GROWTH_STAR"),
        (["红利", "股息"], "DIVIDEND", "CHINA_DIVIDEND", "CHINA_DIVIDEND"),
        (["央企", "国企"], "CENTRAL_SOE", "CHINA_SOE", "CHINA_SOE"),
        (["军工", "国防", "航空航天"], "DEFENSE", "CHINA_DEFENSE", "CHINA_DEFENSE"),
        (["半导体", "芯片", "集成电路"], "SEMICONDUCTOR", "CHINA_SEMICONDUCTOR", "CHINA_SEMICONDUCTOR"),
        (["医药", "医疗", "创新药", "生物医药"], "HEALTHCARE", "CHINA_HEALTHCARE", "CHINA_HEALTHCARE"),
        (["消费", "食品饮料", "酒", "家电"], "CONSUMER", "CHINA_CONSUMER", "CHINA_CONSUMER"),
        (["证券", "券商"], "SECURITIES", "CHINA_SECURITIES", "CHINA_SECURITIES"),
        (["银行"], "BANKS", "CHINA_BANKS", "CHINA_BANKS"),
        (["金融", "非银"], "FINANCIALS", "CHINA_FINANCIALS", "CHINA_FINANCIALS"),
        (["新能源", "光伏", "电池", "锂电", "新能源车"], "NEW_ENERGY", "CHINA_NEW_ENERGY", "CHINA_NEW_ENERGY"),
        (["汽车", "智能车"], "AUTOMOTIVE", "CHINA_AUTOMOTIVE", "CHINA_AUTOMOTIVE"),
        (["机器人", "智能制造", "工业母机"], "ROBOTICS_MANUFACTURING", "CHINA_ROBOTICS", "CHINA_ROBOTICS"),
        (["人工智能", "AI", "软件", "计算机", "云计算", "大数据"], "SOFTWARE_AI", "CHINA_SOFTWARE_AI", "CHINA_SOFTWARE_AI"),
        (["通信", "5G"], "COMMUNICATION", "CHINA_COMMUNICATION", "CHINA_COMMUNICATION"),
        (["传媒", "游戏", "动漫"], "MEDIA", "CHINA_MEDIA", "CHINA_MEDIA"),
        (["有色", "稀土", "钢铁", "煤炭", "资源"], "MATERIALS_ENERGY_EQUITY", "CHINA_RESOURCES_EQUITY", "CHINA_RESOURCES_EQUITY"),
        (["农业", "畜牧", "养殖"], "AGRICULTURE_EQUITY", "CHINA_AGRICULTURE_EQUITY", "CHINA_AGRICULTURE_EQUITY"),
        (["地产", "房地产"], "REAL_ESTATE", "CHINA_REAL_ESTATE", "CHINA_REAL_ESTATE"),
        (["基建", "建筑", "建材"], "INFRASTRUCTURE", "CHINA_INFRASTRUCTURE", "CHINA_INFRASTRUCTURE"),
        (["电力", "公用事业", "绿电"], "UTILITIES", "CHINA_UTILITIES", "CHINA_UTILITIES"),
    ]
    for words, exp2, key, bucket in rules:
        if contains_any(name, words):
            return exp2, key, exp2, bucket
    return "CHINA_EQUITY_OTHER", "CHINA_EQUITY_OTHER", None, "CHINA_EQUITY_OTHER"


def auto_classify(symbol: str, name: str, product_type: str, fund_type: str | None) -> dict[str, Any]:
    nm = name or symbol
    ft = fund_type or ""
    is_qdii = "QDII" in ft.upper() or contains_any(nm, ["纳指", "纳斯达克", "标普", "S&P", "道琼斯", "美国", "日经", "日本", "德国", "DAX", "法国", "CAC", "印度", "越南", "沙特"])

    leveraged = contains_any(nm, ["杠杆", "2倍", "两倍", "2X"])
    inverse = contains_any(nm, ["反向", "做空", "-1X"])

    # Wrapper-independent asset class first.
    if contains_any(nm, ["黄金"]):
        asset_class, exp1, exp2, key, bucket = "COMMODITY", "COMMODITY", "PRECIOUS_METALS_GOLD", "GOLD", "PRECIOUS_METALS_GOLD"
        derivative, roll = False, False
    elif contains_any(nm, ["白银"]):
        asset_class, exp1, exp2, key, bucket = "COMMODITY", "COMMODITY", "PRECIOUS_METALS_SILVER", "SILVER", "PRECIOUS_METALS_SILVER"
        derivative, roll = True, True
    elif contains_any(nm, ["原油", "石油基金"]):
        asset_class, exp1, exp2, key, bucket = "COMMODITY", "COMMODITY", "ENERGY_CRUDE_OIL", "CRUDE_OIL", "ENERGY_CRUDE_OIL"
        derivative, roll = True, True
        is_qdii = True if "原油" in nm else is_qdii
    elif contains_any(nm, ["豆粕"]):
        asset_class, exp1, exp2, key, bucket = "COMMODITY", "COMMODITY", "AGRICULTURE_SOYMEAL", "SOYMEAL_FUTURES", "AGRICULTURE_SOYMEAL"
        derivative, roll = True, True
    elif "期货" in nm and contains_any(nm, ["商品", "能源", "化工", "有色"]):
        asset_class, exp1, exp2, key, bucket = "COMMODITY", "COMMODITY", "COMMODITY_FUTURES", "COMMODITY_FUTURES", "COMMODITY_FUTURES"
        derivative, roll = True, True
    elif contains_any(nm, ["货币ETF", "货币基金", "现金ETF"]):
        asset_class, exp1, exp2, key, bucket = "CASHLIKE", "CHINA_FIXED_INCOME", "CASHLIKE", "CASHLIKE", "CHINA_CASHLIKE"
        derivative, roll = False, False
    elif contains_any(nm, ["转债", "可转债"]):
        asset_class, exp1, exp2, key, bucket = "BOND", "CHINA_FIXED_INCOME", "CONVERTIBLE_BOND", "CHINA_CONVERTIBLE_BOND", "CHINA_CONVERTIBLE_BOND"
        derivative, roll = False, False
    elif contains_any(nm, ["国债", "政金债", "信用债", "城投债", "地方债", "债券", "债ETF", "债基"]):
        asset_class, exp1 = "BOND", "CHINA_FIXED_INCOME"
        derivative, roll = False, False
        if contains_any(nm, ["城投", "信用"]):
            exp2, key, bucket = "CREDIT", "CHINA_CREDIT_BOND", "CHINA_CREDIT_BOND"
        elif contains_any(nm, ["国债", "政金债", "地方债"]):
            exp2, key, bucket = "GOVERNMENT", "CHINA_GOV_BOND", "CHINA_GOV_BOND"
        else:
            exp2, key, bucket = "BOND_OTHER", "CHINA_BOND_OTHER", "CHINA_BOND_OTHER"
    else:
        asset_class, derivative, roll = "EQUITY", False, False
        region, _ = canonical_region(nm, asset_class)
        if region == "US":
            exp1 = "US_EQUITY"
            if contains_any(nm, ["生物", "BIO", "医药"]):
                exp2, key, bucket = "US_BIOTECH", "NASDAQ_BIOTECH", "US_BIOTECH"
            elif contains_any(nm, ["科技", "TECH", "互联网"]):
                exp2, key, bucket = "US_TECH", "US_TECH", "US_TECH"
            elif contains_any(nm, ["消费"]):
                exp2, key, bucket = "US_CONSUMER", "US_CONSUMER", "US_CONSUMER"
            elif contains_any(nm, ["标普", "S&P"]):
                exp2, key, bucket = "US_BROAD", "SP500", "US_SP500"
            elif contains_any(nm, ["纳指", "纳斯达克"]):
                exp2, key, bucket = "US_LARGE_GROWTH", "NASDAQ100", "US_NASDAQ100"
            else:
                exp2, key, bucket = "US_EQUITY_OTHER", "US_EQUITY_OTHER", "US_EQUITY_OTHER"
        elif region == "HK":
            exp1 = "HK_EQUITY"
            if contains_any(nm, ["科技", "互联网"]):
                exp2, key, bucket = "HK_TECH", "HK_TECH", "HK_TECH"
            elif contains_any(nm, ["红利", "股息"]):
                exp2, key, bucket = "HK_DIVIDEND", "HK_DIVIDEND", "HK_DIVIDEND"
            else:
                exp2, key, bucket = "HK_BROAD", "HK_BROAD", "HK_BROAD"
        elif region in {"JP", "DE", "FR", "EU", "IN", "VN", "SA", "ASIA", "GLOBAL"}:
            exp1 = {"JP":"JAPAN_EQUITY", "DE":"EUROPE_EQUITY", "FR":"EUROPE_EQUITY", "EU":"EUROPE_EQUITY",
                    "IN":"INDIA_EQUITY", "VN":"VIETNAM_EQUITY", "SA":"SAUDI_EQUITY", "ASIA":"ASIA_EQUITY", "GLOBAL":"GLOBAL_EQUITY"}[region]
            if region == "JP": exp2, key, bucket = "JAPAN_BROAD", "NIKKEI_OR_JAPAN", "JAPAN_EQUITY"
            elif region == "DE": exp2, key, bucket = "GERMANY_BROAD", "DAX" if "DAX" in nm.upper() else "GERMANY_EQUITY", "GERMANY_EQUITY"
            elif region == "FR": exp2, key, bucket = "FRANCE_BROAD", "CAC40" if "CAC" in nm.upper() else "FRANCE_EQUITY", "FRANCE_EQUITY"
            elif region == "IN": exp2, key, bucket = "INDIA_BROAD", "INDIA_EQUITY", "INDIA_EQUITY"
            else: exp2, key, bucket = f"{region}_EQUITY", f"{region}_EQUITY", f"{region}_EQUITY"
        else:
            exp1 = "CHINA_EQUITY"
            exp2, key, style, bucket = classify_equity_cn(nm)

    region, region_tags = canonical_region(nm, asset_class)
    if asset_class == "COMMODITY" and region is None:
        if bucket in {"PRECIOUS_METALS_GOLD", "PRECIOUS_METALS_SILVER", "ENERGY_CRUDE_OIL"}:
            region, region_tags = "GLOBAL", ["GLOBAL"]
        else:
            region, region_tags = "CN", ["CN"]

    style = None
    if asset_class == "EQUITY":
        if region == "CN":
            _, _, style, _ = classify_equity_cn(nm)
        elif contains_any(nm, ["红利", "股息"]): style = "DIVIDEND"
        elif contains_any(nm, ["科技", "TECH"]): style = "TECHNOLOGY"
        elif contains_any(nm, ["消费"]): style = "CONSUMER"
        elif contains_any(nm, ["医药", "生物"]): style = "HEALTHCARE"
        else: style = "BROAD"

    premium_sensitive = bool(product_type == "LOF" or is_qdii)
    currency = "USD" if region == "US" or bucket == "ENERGY_CRUDE_OIL" else (
        "EUR" if region in {"DE", "FR", "EU"} else "JPY" if region == "JP" else "INR" if region == "IN" else "CNY" if region == "CN" else None
    )
    # Cross-border ETFs are commonly T+0; leave LOF/other cases unknown unless manually curated.
    t0 = True if (product_type == "ETF" and is_qdii) else False if (product_type == "ETF" and asset_class == "EQUITY" and region == "CN") else None

    generic = bucket.endswith("OTHER") or bucket in {"COMMODITY_FUTURES", "CHINA_EQUITY_OTHER"}
    confidence = 0.82
    if product_type == "UNKNOWN": confidence -= 0.15
    if generic: confidence -= 0.17
    needs_review = confidence < 0.75

    return dict(
        product_type=product_type,
        asset_class=asset_class,
        region_primary=region,
        region_tags=region_tags,
        exposure_level1=exp1,
        exposure_level2=exp2,
        underlying_key=key,
        risk_bucket=bucket,
        style_sector=style,
        is_qdii=bool(is_qdii),
        nav_lag_days=None,
        premium_sensitive=premium_sensitive,
        t0_flag=t0,
        derivative_exposure=derivative,
        roll_cost_exposure=roll,
        currency_exposure=currency,
        leveraged_flag=leveraged,
        inverse_flag=inverse,
        classification_method="AUTO_NAME_V1",
        confidence=round(max(0.1, min(0.95, confidence)), 3),
        needs_review=needs_review,
        notes=None,
    )


def load_market_names() -> tuple[dict[str, str], dict[str, str], dict[str, str], list[str]]:
    warnings: list[str] = []
    etf: dict[str, str] = {}
    lof: dict[str, str] = {}
    fund_type: dict[str, str] = {}

    try:
        d = ak.fund_etf_spot_em()
        if not d.empty:
            etf = {str(r["代码"]).zfill(6): str(r["名称"]) for _, r in d.iterrows()}
    except Exception as exc:
        warnings.append(f"fund_etf_spot_em failed: {exc!r}")
    try:
        d = ak.fund_lof_spot_em()
        if not d.empty:
            lof = {str(r["代码"]).zfill(6): str(r["名称"]) for _, r in d.iterrows()}
    except Exception as exc:
        warnings.append(f"fund_lof_spot_em failed: {exc!r}")
    try:
        d = ak.fund_name_em()
        if not d.empty:
            for _, r in d.iterrows():
                code = str(r["基金代码"]).zfill(6)
                if code not in etf and code not in lof:
                    # names from the basic fund master are used only as fallback
                    pass
                fund_type[code] = str(r.get("基金类型", ""))
                # fill missing wrapper-list names through caller using separate lookup
            basic_names = {str(r["基金代码"]).zfill(6): str(r["基金简称"]) for _, r in d.iterrows()}
        else:
            basic_names = {}
    except Exception as exc:
        warnings.append(f"fund_name_em failed: {exc!r}")
        basic_names = {}

    # Merge fallback names into a fourth dictionary via sentinel key convention.
    for k, v in basic_names.items():
        if k not in etf and k not in lof:
            # no wrapper assertion; name-only fallback
            fund_type.setdefault(k, fund_type.get(k, ""))
    return etf, lof, {**fund_type, **{f"NAME::{k}": v for k, v in basic_names.items()}}, warnings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--snapshot-date", default=SNAPSHOT_DATE.isoformat())
    ap.add_argument("--summary-path", default="instrument-metadata-summary.json")
    ap.add_argument("--csv-path", default="instrument-metadata-current.csv")
    ap.add_argument("--review-path", default="instrument-metadata-review.csv")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    snapshot = date.fromisoformat(args.snapshot_date)

    engine = create_engine(args.database_url.replace("postgres://", "postgresql+psycopg2://", 1) if args.database_url.startswith("postgres://") else args.database_url.replace("postgresql://", "postgresql+psycopg2://", 1), pool_pre_ping=True)
    coverage = pd.read_sql_query(text("""
        select symbol, min(date) as data_start_date, max(date) as data_end_date, count(*)::int as bars_count
        from public.daily_bars group by symbol order by symbol
    """), engine)
    coverage["symbol"] = coverage["symbol"].astype(str).str.zfill(6)

    etf, lof, aux, warnings = load_market_names()
    basic_names = {k.split("::", 1)[1]: v for k, v in aux.items() if k.startswith("NAME::")}
    fund_types = {k: v for k, v in aux.items() if not k.startswith("NAME::")}

    rows: list[dict[str, Any]] = []
    source = "AKShare 1.18.94 / Eastmoney current fund masters"
    for r in coverage.itertuples(index=False):
        sym = str(r.symbol)
        if sym in etf:
            ptype, nm = "ETF", etf[sym]
        elif sym in lof:
            ptype, nm = "LOF", lof[sym]
        else:
            ptype, nm = "UNKNOWN", basic_names.get(sym, sym)

        if sym in MANUAL:
            meta = dict(MANUAL[sym])
            # Preserve live official name if one is available, while retaining manual semantic labels.
            if nm and nm != sym:
                meta["name"] = nm
            meta.update(classification_method="MANUAL_REFERENCE_V1", confidence=0.99, needs_review=False,
                        label_scope="HISTORICAL_MANUAL", historical_safe=True,
                        valid_from=pd.Timestamp(r.data_start_date).date(), metadata_source="manual reference universe + current fund master")
            meta.setdefault("nav_lag_days", None)
            meta.setdefault("leveraged_flag", False)
            meta.setdefault("inverse_flag", False)
        else:
            meta = auto_classify(sym, nm, ptype, fund_types.get(sym))
            meta.update(name=nm, label_scope="CURRENT_SNAPSHOT", historical_safe=False,
                        valid_from=snapshot, metadata_source=source)

        meta.update(symbol=sym,
                    data_start_date=pd.Timestamp(r.data_start_date).date(),
                    data_end_date=pd.Timestamp(r.data_end_date).date(),
                    bars_count=int(r.bars_count), valid_to=None)
        rows.append(meta)

    out = pd.DataFrame(rows)

    # Close older current-snapshot rows before adding this snapshot. Historical-manual rows are untouched.
    with engine.begin() as conn:
        conn.execute(text("""
            update public.instrument_metadata
               set valid_to = :prev, updated_at = now()
             where valid_to is null
               and label_scope = 'CURRENT_SNAPSHOT'
               and valid_from < :snap
        """), {"prev": snapshot - timedelta(days=1), "snap": snapshot})

        sql = text("""
            insert into public.instrument_metadata (
                symbol,name,product_type,asset_class,region_primary,region_tags,exposure_level1,exposure_level2,
                underlying_key,risk_bucket,style_sector,is_qdii,nav_lag_days,premium_sensitive,t0_flag,
                derivative_exposure,roll_cost_exposure,currency_exposure,leveraged_flag,inverse_flag,
                data_start_date,data_end_date,bars_count,label_scope,historical_safe,valid_from,valid_to,
                classification_method,confidence,needs_review,metadata_source,notes,updated_at
            ) values (
                :symbol,:name,:product_type,:asset_class,:region_primary,:region_tags,:exposure_level1,:exposure_level2,
                :underlying_key,:risk_bucket,:style_sector,:is_qdii,:nav_lag_days,:premium_sensitive,:t0_flag,
                :derivative_exposure,:roll_cost_exposure,:currency_exposure,:leveraged_flag,:inverse_flag,
                :data_start_date,:data_end_date,:bars_count,:label_scope,:historical_safe,:valid_from,:valid_to,
                :classification_method,:confidence,:needs_review,:metadata_source,:notes,now()
            )
            on conflict (symbol,valid_from) do update set
                name=excluded.name, product_type=excluded.product_type, asset_class=excluded.asset_class,
                region_primary=excluded.region_primary, region_tags=excluded.region_tags,
                exposure_level1=excluded.exposure_level1, exposure_level2=excluded.exposure_level2,
                underlying_key=excluded.underlying_key, risk_bucket=excluded.risk_bucket, style_sector=excluded.style_sector,
                is_qdii=excluded.is_qdii, nav_lag_days=excluded.nav_lag_days,
                premium_sensitive=excluded.premium_sensitive, t0_flag=excluded.t0_flag,
                derivative_exposure=excluded.derivative_exposure, roll_cost_exposure=excluded.roll_cost_exposure,
                currency_exposure=excluded.currency_exposure, leveraged_flag=excluded.leveraged_flag,
                inverse_flag=excluded.inverse_flag, data_start_date=excluded.data_start_date,
                data_end_date=excluded.data_end_date, bars_count=excluded.bars_count,
                label_scope=excluded.label_scope, historical_safe=excluded.historical_safe, valid_to=excluded.valid_to,
                classification_method=excluded.classification_method, confidence=excluded.confidence,
                needs_review=excluded.needs_review, metadata_source=excluded.metadata_source, notes=excluded.notes,
                updated_at=now()
        """)
        conn.execute(sql, out.where(pd.notna(out), None).to_dict("records"))

    # Read back the current view as the single source for artifacts/verification.
    current = pd.read_sql_query(text("select * from public.instrument_metadata_current order by symbol"), engine)
    current.to_csv(args.csv_path, index=False)
    current.loc[current["needs_review"].fillna(True)].to_csv(args.review_path, index=False)

    summary = {
        "snapshot_date": snapshot.isoformat(),
        "source_universe_symbols": int(len(coverage)),
        "current_metadata_rows": int(len(current)),
        "manual_reference_rows": int((current["classification_method"] == "MANUAL_REFERENCE_V1").sum()),
        "historical_safe_rows": int(current["historical_safe"].fillna(False).sum()),
        "needs_review_rows": int(current["needs_review"].fillna(True).sum()),
        "product_type_counts": current["product_type"].value_counts(dropna=False).to_dict(),
        "asset_class_counts": current["asset_class"].value_counts(dropna=False).to_dict(),
        "region_counts": current["region_primary"].fillna("NULL").value_counts().to_dict(),
        "risk_bucket_top20": current["risk_bucket"].fillna("NULL").value_counts().head(20).to_dict(),
        "name_coverage": int(current["name"].notna().sum()),
        "etf_spot_count": len(etf),
        "lof_spot_count": len(lof),
        "warnings": warnings,
    }
    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
