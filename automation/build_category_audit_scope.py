#!/usr/bin/env python3
"""Prepare a post-close, category-deduplicated fundamental/news audit scope.

Input: production fixed-pool OLS Top1 + independent qualified full-market
R2 rebuild list. Category taxonomy groups common economic drivers, not ETF
codes or generic product type. Unknown/conflicting exposures require review.
No news conclusions or trade commands are generated here.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]

CATEGORY_INFO = {
    "CN_CONSUMER": ("A股消费（不含白酒专项）", "国内消费需求、零售/食品饮料、盈利与估值"),
    "CN_BAIJIU": ("A股白酒", "高端与次高端白酒动销、库存、批价、渠道与政策"),
    "HK_CONSUMER": ("港股消费", "港股消费成分股、港币汇率、离岸流动性和消费需求"),
    "CROSS_BORDER_CONSUMER": ("沪港深消费", "跨市场指数权重、A/H估值及境内外消费需求"),
    "CN_CASHFLOW_FACTOR": ("A股现金流因子", "自由现金流策略选股、行业权重与价值风格"),
    "CN_BANKS": ("A股银行", "净息差、信贷需求、资产质量、分红、地产与地方债"),
    "US_EQUITY": ("美股宽基", "美股盈利、利率、估值、汇率与指数权重"),
    "US_BONDS": ("美元债", "美国利率曲线、信用利差、久期与汇率"),
    "HK_BROAD": ("港股宽基", "港股指数权重、南向资金、离岸流动性与政策"),
    "CRUDE_OIL": ("原油", "全球供需、OPEC政策、库存、期限结构与外汇"),
    "ENERGY_CHEMICAL": ("能源化工", "甲醇/PX/PTA、MTO、开工、库存和下游需求"),
    "GOLD": ("黄金", "美元、实际利率、央行购金与资金流"),
    "SILVER": ("白银", "工业需求、实际利率及金银比"),
    "SOYBEAN_MEAL": ("豆粕", "大豆供需、压榨、库存、养殖与天气"),
    "INDIA_EQUITY": ("印度股票", "印度盈利、估值、汇率与资本流动"),
    "BRAZIL_EQUITY": ("巴西股票", "巴西政策、财政、商品出口与汇率"),
    "US_TECH": ("美股科技", "科技盈利、半导体需求、利率和权重集中"),
    "US_BIOTECH": ("美国生物科技", "研发审批、融资成本、政策与行业盈利"),
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def db_url(raw):
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        raw = "postgresql+psycopg2://" + raw[len("postgresql://"):]
    return raw


def fetch_metadata(symbols, engine):
    if not symbols:
        return {}
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT ON (symbol) symbol,name,product_type,region_primary,
                   exposure_level1,exposure_level2,underlying_key,risk_bucket,
                   confidence,needs_review
            FROM public.instrument_metadata
            WHERE symbol = ANY(:symbols)
            ORDER BY symbol,updated_at DESC NULLS LAST
        """), {"symbols":sorted(symbols)}).mappings().all()
    return {str(row["symbol"]):dict(row) for row in rows}


def classify(symbol, name, meta=None):
    """Primary economic driver. Never merge unknown funds into an OTHER bucket."""
    meta = meta or {}
    n = str(name or meta.get("name") or "")
    level = str(meta.get("exposure_level2") or "").upper()
    underlying = str(meta.get("underlying_key") or "").upper()
    region = str(meta.get("region_primary") or "").upper()
    key = None
    rule = "metadata"

    # Specific index exposures must precede broad metadata CONSUMER/HK_BROAD.
    if re.search(r"白酒|酿酒|(?:^|[^白])酒(?:ETF|LOF|基金|指数)", n):
        key = "CN_BAIJIU"
    elif "沪港深消费" in n:
        key = "CROSS_BORDER_CONSUMER"
    elif re.search(r"港股.*消费|恒生消费|港股通消费", n) or "HK_CONSUMER" in level:
        key = "HK_CONSUMER"
    elif "美元债" in n or "美债" in n:
        key = "US_BONDS"
    elif "自由现金流" in n or "现金流" in n or "CASH_FLOW" in level:
        key = "CN_CASHFLOW_FACTOR"
    elif re.search(r"食品|饮料|消费", n) and region != "HK":
        key = "CN_CONSUMER"
    if key is not None:
        rule = "name_specific"

    if key is None:
        if underlying == "CRUDE_OIL" or "原油" in n:
            key = "CRUDE_OIL"
        elif underlying == "ENERGY_CHEMICAL_FUTURES" or "能源化工" in n:
            key = "ENERGY_CHEMICAL"
        elif "BANK" in level or "银行" in n:
            key = "CN_BANKS"
        elif "GOLD" in level or "黄金" in n:
            key = "GOLD"
        elif "SILVER" in level or "白银" in n:
            key = "SILVER"
        elif "SOY" in level or "豆粕" in n:
            key = "SOYBEAN_MEAL"
        elif "BRAZIL" in underlying or "巴西" in n:
            key = "BRAZIL_EQUITY"
        elif "INDIA" in underlying or "印度" in n:
            key = "INDIA_EQUITY"
        elif "BIOTECH" in underlying or "生物" in n:
            key = "US_BIOTECH"
        elif "US" in region and re.search(r"科技|纳斯达克|纳指|半导体", n):
            key = "US_TECH"
        elif region == "US" or re.search(r"道琼斯|标普500", n):
            key = "US_EQUITY"
        elif region == "HK":
            key = "HK_BROAD"
        elif level == "CONSUMER":
            key = "CN_CONSUMER"
        elif "BANK" in underlying:
            key = "CN_BANKS"

    if key is None:
        key = "UNCLASSIFIED_" + symbol
        label, drivers = "待核实：" + n, "先核对基金跟踪指数、前十大权重与真实风险因子，再决定是否合并"
        return {"key":key,"name":label,"drivers":drivers,"needs_review":True,
                "classification_rule":"unclassified"}

    label,drivers=CATEGORY_INFO[key]
    # Broad/low-confidence metadata can contradict an explicit name rule.
    confidence=meta.get("confidence")
    low_confidence = confidence is not None and float(confidence) < 0.7
    mismatch = (key == "US_BONDS" and str(meta.get("exposure_level1") or "").startswith("CHINA_EQUITY"))
    return {"key":key,"name":label,"drivers":drivers,
            "needs_review":bool(meta.get("needs_review")) or low_confidence or mismatch,
            "classification_rule":rule}


def build(current,market,metadata,actual=None):
    day=str(current.get("market_data_date") or "")
    if not day or day != str(market.get("as_of") or ""):
        raise ValueError("OLS and full-market rebuild signal dates differ")
    target=current.get("next_strategy_target") or {}
    if str(target.get("signal_date") or "") != day:
        raise ValueError("OLS signal is stale")
    if market.get("data_quality_gate") != "PASS" or float(market.get("asof_coverage") or 0)<0.90:
        raise ValueError("Full-market snapshot is incomplete")
    rows=market.get("qualified_candidates")
    if not isinstance(rows,list) or len(rows)!=int(market.get("raw_qualified",-1)):
        raise ValueError("Full-market qualified list is missing or inconsistent")
    symbols=[str(r.get("symbol") or "") for r in rows]
    if len(symbols)!=len(set(symbols)) or any(r.get("stage")!="REBUILDING_QUALIFIED" for r in rows):
        raise ValueError("Invalid full-market qualified list")
    top=str(target.get("model_target") or "")
    if top and (not top.isdigit() or len(top)!=6):
        raise ValueError("Invalid OLS Top1")
    indexed={}
    for r in rows:
        code=str(r["symbol"])
        indexed[code]={"symbol":code,"name":r.get("name") or code,
                       "roles":["REBUILD_QUALIFIED"],
                       "first_qualified_date":r.get("first_qualified_date"),
                       "cross_date":r.get("cross_date"),
                       "annual":r.get("annual"),"r2":r.get("r2"),
                       "new_today":r.get("first_qualified_date")==day}
    if top:
        obj=indexed.setdefault(top,{"symbol":top,"name":target.get("model_target_name") or top,
                    "roles":[],"first_qualified_date":None,"cross_date":None,
                    "annual":None,"r2":None,"new_today":False})
        obj["roles"].insert(0,"OLS_TOP1")
    groups=defaultdict(list)
    for item in indexed.values():
        key=classify(item["symbol"],item["name"],metadata.get(item["symbol"]))
        item["category"]=key["key"]
        item["classification_rule"]=key["classification_rule"]
        item["needs_review"]=key["needs_review"]
        groups[key["key"]].append(item)

    output=[]
    for k,members in groups.items():
        label,drivers=(CATEGORY_INFO[k] if k in CATEGORY_INFO else
                       ("待核实：" + members[0]["name"],
                        "核实基金实际指数与成分，暂不与其他标的合并审计"))
        output.append({
            "category_id":k, "category_name":label,"drivers":drivers,
            "count":len(members),
            "ols_top1":top if any("OLS_TOP1" in x["roles"] for x in members) else None,
            "new_today_count":sum(x["new_today"] for x in members),
            "needs_review":any(x["needs_review"] for x in members),
            "members":sorted(members,key=lambda x:("OLS_TOP1" not in x["roles"],
                         not x["new_today"],x["symbol"])),
        })
    output.sort(key=lambda x:(not bool(x["ols_top1"]),not bool(x["new_today_count"]),
                              -x["count"],x["category_id"]))
    actual=actual or {}
    if actual.get("as_of") and actual["as_of"]>day:
        raise ValueError("Actual holding timestamp after signal date")
    result={
        "version":"category-audit-scope-v1", "as_of":day,
        "source_ols":"data/fundamental-audit-trigger.json:next_strategy_target.model_target",
        "source_rebuild":"data/full-market-rebuild-latest.json:qualified_candidates",
        "data_quality_gate":"PASS",
        "ols_top1":top or None,
        "execution_target":target.get("symbol"),
        "actual_holding":actual,
        "all_market_rebuild_count":len(rows),
        "new_rebuild_count":sum(x["new_today"] for x in indexed.values()),
        "unique_symbols":len(indexed),
        "category_count":len(output),"categories":output,
        "audit_instruction":"Each category receives one shared macro/fundamental/news audit; "
            "individual ETF exceptions (premium, currency, index, liquidity, tracking) "
            "are separately checked for each candidate. No automatic veto/trade.",
    }
    if sum(x["count"] for x in output)!=len(indexed):
        raise AssertionError("Incomplete audit categorization")
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--current",required=True)
    ap.add_argument("--market",required=True)
    ap.add_argument("--actual",default="")
    ap.add_argument("--output",required=True)
    ap.add_argument("--metadata-json",default="",help="Offline tests only")
    args=ap.parse_args()
    current,market=read_json(args.current),read_json(args.market)
    actual=read_json(args.actual) if args.actual else {}
    symbols=set(str(x.get("symbol")) for x in market.get("qualified_candidates",[]))
    top=(current.get("next_strategy_target") or {}).get("model_target")
    if top: symbols.add(str(top))
    if args.metadata_json:
        meta=read_json(args.metadata_json)
    else:
        database=os.getenv("ETF_DAILY_BARS_DATABASE_URL","")
        if not database:
            raise RuntimeError("ETF_DAILY_BARS_DATABASE_URL required for classification")
        engine=create_engine(db_url(database),pool_pre_ping=True)
        meta=fetch_metadata(symbols,engine)
    result=build(current,market,meta,actual)
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps({"as_of":result["as_of"],"ols_top1":result["ols_top1"],
                      "rebuild":result["all_market_rebuild_count"],
                      "audit_categories":result["category_count"],
                      "categories":[(x["category_name"],x["count"]) for x in result["categories"]]},
                     ensure_ascii=False))


if __name__=="__main__":
    main()
