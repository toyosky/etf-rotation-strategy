"""Pure metadata functions. No market returns, scores, or OLS dependencies."""
from __future__ import annotations
import hashlib
import re
import unicodedata


def normalize_name(value: str) -> str:
    # Do not erase price/TR, low-volatility, region, sector or factor qualifiers.
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value or "")).strip()


def name_key(name: str) -> str:
    return "INDEX_NAME:" + hashlib.sha256(normalize_name(name).encode()).hexdigest()[:20]


def valid_index_name(name: str) -> bool:
    return bool(name and name.strip() not in {"-", "--", "无", "该基金无跟踪标的"})


def economic_labels(index_name: str) -> dict:
    """Descriptors of an evidenced index, never an identity inferred from a fund name.

    Unknown regions/assets stay unknown. Distinct indices ALWAYS retain distinct
    exposure IDs downstream, even when these reporting descriptors match.
    Rulebooks/holdings are still required to approve cross-index equivalence.
    """
    n = normalize_name(index_name)
    region = None
    if any(x in n for x in ("港股", "恒生", "香港", "H股")):
        region = "HK"
    elif any(x in n for x in ("纳斯达克", "标普500", "标普生物", "标普油气", "美国", "道琼斯美国", "纳指")):
        region = "US"
    elif any(x in n for x in ("日经", "日本")):
        region = "JP"
    elif "德国" in n or "DAX" in n.upper():
        region = "DE"
    elif "全球" in n:
        region = "GLOBAL"
    elif any(x in n for x in ("中证", "上证", "国证", "沪深", "深证", "创业板", "科创", "中债", "中债登")):
        region = "CN"
    if "沪深港" in n or "沪港深" in n:
        region = "CN_HK"
    asset = None
    if "期货" in n:
        asset = "COMMODITY_FUTURES"
    elif any(x in n for x in ("债", "国开", "政策性金融")):
        asset = "BOND"
    elif any(x in n for x in ("上海金", "黄金现货", "黄金9999", "Au99.99")):
        asset = "COMMODITY_SPOT"
    elif region:
        asset = "EQUITY"
    sector, sub = None, None
    rules = [
        ("HEALTHCARE", "CXO", ("创新药产业", "CXO", "医药研发")),
        ("HEALTHCARE", "MEDICAL_DEVICES", ("医疗器械",)),
        ("HEALTHCARE", "MEDICAL_SERVICES", ("医疗服务",)),
        ("HEALTHCARE", "VACCINES", ("疫苗",)),
        ("HEALTHCARE", "TCM", ("中药",)),
        ("HEALTHCARE", "INNOVATIVE_DRUGS", ("创新药",)),
        ("HEALTHCARE", "BIOTECH", ("生物科技", "生物技术",)),
        ("HEALTHCARE", "BIOPHARMA_MIXED", ("生物医药",)),
        ("HEALTHCARE", "MEDICAL_MIXED", ("医疗",)),
        ("HEALTHCARE", "PHARMA_BROAD", ("医药", "制药", "卫生")),
        ("TECHNOLOGY", "SEMICONDUCTOR", ("半导体", "芯片", "集成电路")),
        ("TECHNOLOGY", "COMPUTE_CLOUD", ("算力", "云计算", "数据中心")),
        ("TECHNOLOGY", "ARTIFICIAL_INTELLIGENCE", ("人工智能",)),
        ("TECHNOLOGY", "SOFTWARE", ("软件",)),
        ("TECHNOLOGY", "CONSUMER_ELECTRONICS", ("消费电子",)),
        ("INDUSTRIALS", "ROBOTICS", ("机器人",)),
        ("COMMUNICATION", "TELECOM", ("通信", "电信", "5G")),
        ("CONSUMER", "BAIJIU", ("白酒",)),
        ("CONSUMER", "ALCOHOL_MIXED", ("酒",)),
        ("CONSUMER", "FOOD_BEVERAGE", ("食品", "饮料")),
        ("CONSUMER", "HOME_APPLIANCES", ("家电",)),
        ("CONSUMER", "AUTOMOTIVE", ("汽车",)),
        ("CONSUMER", "DISCRETIONARY", ("可选消费",)),
        ("CONSUMER", "CONSUMER_BROAD", ("消费",)),
        ("MULTI_SECTOR", "SOLAR_CHAIN", ("光伏",)),
        ("MULTI_SECTOR", "BATTERY_CHAIN", ("电池", "锂电")),
        ("MULTI_SECTOR", "NEW_ENERGY_CHAIN", ("新能源",)),
        ("ENERGY", "OIL_GAS_EQUITY", ("石油", "油气",)),
        ("ENERGY", "COAL_EQUITY", ("煤炭",)),
        ("MATERIALS", "GOLD_MINERS", ("黄金产业", "黄金股")),
        ("FINANCIALS", "BANKS", ("银行",)),
        ("FINANCIALS", "SECURITIES", ("证券公司", "证券行业",)),
        ("FINANCIALS", "INSURANCE", ("保险",)),
        ("FINANCIALS", "FINANCIAL_BROAD", ("金融",)),
        ("INDUSTRIALS", "DEFENSE", ("国防", "军工",)),
        ("INDUSTRIALS", "AEROSPACE", ("航空", "航天", "卫星",)),
        ("INDUSTRIALS", "MACHINERY", ("机械", "机床",)),
        ("INDUSTRIALS", "TRANSPORT", ("交通", "运输", "物流",)),
        ("INDUSTRIALS", "INFRASTRUCTURE", ("基建", "建筑",)),
        ("UTILITIES", "ELECTRIC_POWER", ("电力", "绿电",)),
        ("UTILITIES", "UTILITIES_BROAD", ("公用事业",)),
        ("REAL_ESTATE", "REAL_ESTATE", ("房地产", "地产",)),
        ("MATERIALS", "MATERIALS", ("有色", "稀土", "材料", "钢铁", "化工",)),
        ("TECHNOLOGY", "TECHNOLOGY_BROAD", ("信息技术", "数字经济", "科技",)),
        ("COMMUNICATION", "MEDIA", ("传媒", "游戏", "影视",)),
        ("CONSUMER", "TOURISM", ("旅游",)),
        ("CONSUMER", "AGRICULTURE", ("农业", "养殖", "粮食",)),
    ]
    # Innovative-drug value chain is broader than pure CXO; do not assert CXO.
    rules[0] = ("HEALTHCARE", "CXO", ("CXO", "医药研发"))
    for a, b, words in rules:
        if any(w in n for w in words):
            sector, sub = a, b
            break
    kind = "INDEX_OTHER"
    if any(x in n for x in ("红利", "低波", "价值", "成长", "质量", "现金流", "动量", "ESG")):
        kind = "FACTOR"
    elif sector:
        kind = "SECTOR_OR_THEME"
    elif any(x in n for x in ("300指数", "500指数", "1000指数", "2000指数", "A500", "A50", "成份指数", "综合指数", "创业板指数", "创业板指", "恒生指数", "纳斯达克100")):
        kind = "BROAD"
    if asset == "BOND":
        sector, sub, kind = "FIXED_INCOME", "BOND_INDEX", "BOND"
    elif asset in {"COMMODITY_SPOT", "COMMODITY_FUTURES"}:
        sector, sub, kind = "COMMODITY", asset, asset
    elif not sector and kind in {"BROAD", "FACTOR"}:
        sector, sub = "MULTI_SECTOR", kind
    return dict(region_primary=region, exposure_type=asset, sector_level1=sector,
                sector_level2=sub, sector_level3=None, index_style=kind,
                risk_bucket="|".join((region, asset, sector or "UNRESOLVED")) if region and asset else None)


def validate_intervals(rows: list[dict]):
    by_symbol = {}
    for r in rows:
        start, end = r.get("valid_from"), r.get("valid_to")
        if not start or (end and end <= start):
            raise ValueError("V3 uses nonempty half-open [valid_from, valid_to) intervals")
        if not r.get("known_from"):
            raise ValueError("known_from is required separately from validity")
        by_symbol.setdefault(r["symbol"], []).append(r)
    for symbol, group in by_symbol.items():
        prev_end = None
        for i, r in enumerate(sorted(group, key=lambda x: x["valid_from"])):
            if i and (prev_end is None or r["valid_from"] < prev_end):
                raise ValueError(f"overlapping classification intervals: {symbol}")
            prev_end = r.get("valid_to")


def classifications_at(rows: list[dict], date: str) -> tuple[list[dict], list[dict]]:
    validate_intervals(rows)
    active, excluded = [], []
    symbols = sorted({r["symbol"] for r in rows})
    by_symbol = {}
    for r in rows:
        by_symbol.setdefault(r["symbol"], []).append(r)
    for symbol in symbols:
        candidates = [r for r in by_symbol[symbol] if r["valid_from"] <= date
                      and (not r.get("valid_to") or date < r["valid_to"])]
        reason = None
        if not candidates:
            reason = "NO_EFFECTIVE_CLASSIFICATION"
        else:
            r = candidates[0]
            if r["known_from"] > date:
                reason = "CLASSIFICATION_NOT_YET_KNOWN"
            elif r.get("needs_review") or not r.get("exact_index_verified") or not r.get("exposure_id"):
                reason = "UNVERIFIED_CLASSIFICATION"
            elif r.get("tracking_mode") != "PASSIVE_INDEX":
                reason = "STRATEGY_NOT_APPROVED_FOR_PASSIVE_POOL"
            elif not r.get("listing_date"):
                reason = "LISTING_DATE_NOT_VERIFIED"
            elif r["listing_date"] > date:
                reason = "NOT_YET_LISTED"
            elif r.get("delisting_date") and date >= r["delisting_date"]:
                reason = "DELISTED"
            elif not r.get("listing_known_from") or r["listing_known_from"] > date:
                reason = "LISTING_NOT_YET_KNOWN"
            else:
                active.append(r)
        if reason:
            excluded.append(dict(symbol=symbol, date=date, reason=reason))
    return active, excluded
