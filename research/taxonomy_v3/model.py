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


def supplemental_labels_v31(index_name: str, base: dict) -> dict:
    """Fill only high-confidence *descriptive* gaps from an official index title.

    This is not official index methodology/constituent verification.
    It must NEVER change an existing exposure identity, code, region, sector,
    or asset that has already been populated. Names that could imply a broad
    or thematic portfolio are assigned MULTI_SECTOR, not a fabricated industry.
    """
    n = normalize_name(index_name)
    u = n.upper()
    out = dict(base)
    region = out.get("region_primary")
    if not region:
        if any(w in u for w in ("MSCI USA", "S&P OIL & GAS", "S&P500")) or any(w in n
                for w in ("标准普尔500", "标普500", "道琼斯工业", "美国", "纳斯达克")):
            region="US"
        elif any(w in n for w in ("巴西", "BOVESPA")) or "IBOVESPA" in u:
            region="BR"
        elif "沙特" in n:
            region="SA"
        elif any(w in n for w in ("日经", "东证指数", "东京")) or "TOPIX" in u:
            region="JP"
        elif "CAC40" in u or "法国" in n:
            region="FR"
        elif "DAX" in u:
            region="DE"
        elif any(w in n for w in ("亚太", "东南亚")):
            region="ASIA"
        elif any(w in n for w in ("中国A股", "A股", "深证", "细分", "国证", "中小企业",
                                   "中小创业", "上证", "央视财经", "创业板", "富时中国", "MSCI中国")) or "MSCI CHINA A" in u:
            region="CN"
    if region and not out.get("region_primary"):
        out["region_primary"]=region

    # Only identify equity/commodity by a structurally recognizable
    # index name. Futures must never be inferred to be equity.
    if not out.get("exposure_type"):
        if "期货" in n:
            out["exposure_type"]="COMMODITY_FUTURES"
        elif any(w in n for w in ("黄金9999", "上海金", "黄金现货", "黄金Au99.99")):
            out["exposure_type"]="COMMODITY_SPOT"
        elif "短融" in n:
            out["exposure_type"]="BOND"
        elif out.get("region_primary") and not any(w in n for w in
                    ("上期有色金属指数", "易盛郑商所能源化工指数", "上证商品期货")):
            out["exposure_type"]="EQUITY"

    # Classify unambiguous title descriptors without inventing a more
    # granular 3rd-level industry or collapsing distinct index identities.
    sector=out.get("sector_level1")
    sub=out.get("sector_level2")
    if not sector:
        sector_rules=[
          ("TECHNOLOGY","INTERNET",("互联网",)),
          ("TECHNOLOGY","INDUSTRIAL_IOT",("工业互联网","物联网")),
          ("TECHNOLOGY","DATA",("大数据","计算机","信息安全","虚拟现实")),
          ("TECHNOLOGY","ELECTRONICS",("电子50","中证电子指数")),
          ("MATERIALS","RARE_METALS",("稀有金属",)),
          ("MATERIALS","MATERIALS",("细分有色","细分化工","细分食品","细分机械")),
          ("CONSUMER","HOME_APPLIANCES",("家用电器",)),
          ("CONSUMER","AGRICULTURE",("农牧渔","农牧主题")),
          ("INDUSTRIALS","GRID_EQUIPMENT",("电网设备",)),
          ("INDUSTRIALS","EQUIPMENT",("装备产业",)),
          ("ENERGY","ENERGY_EQUITY",("中证能源","全指能源")),
          ("FINANCIALS","SECURITIES",("证券龙头",)),
          ("MULTI_SECTOR","LOW_CARBON",("碳中和","低碳经济","环保产业")),
          ("MULTI_SECTOR","SOE_REFORM",("央企","国企","国有企业","国证民企")),
        ]
        for a,b,words in sector_rules:
            if any(w in n for w in words):
                sector,sub=a,b
                break
    if not sector and out.get("exposure_type")=="BOND":
        sector,sub="FIXED_INCOME","BOND_INDEX"
    if not sector:
        # A confirmed broad index / region market / factor is not an
        # 'unclassifiable industry'; explicitly identify MULTI_SECTOR.
        broad_words=("科创创业50","科创板100","科创板200","科创板综合",
                     "深证100","深证50","深证主板50","创业板50","创业板200",
                     "上证50","上证180","上证380","上证580","中证A100",
                     "中证A股","中证100","中证800","恒生中国企业",
                     "恒指港股通","港股通50","港股通中国100",
                     "MSCI中国A股","MSCI CHINA A","MSCI USA",
                     "国证创业板中盘精选","创业板大盘","中小企业100",
                     "中小创业企业400","国证民企领先","上证中盘",
                     "上证超级大盘","央视财经50","基本面120",
                     "基本面60","沪深300","中证500","富时中国A50",
                     "日经225","BOVESPA","CAC40","DAX")
        if any(w.upper() in u for w in broad_words):
            sector,sub="MULTI_SECTOR","BROAD_OR_FACTOR"
    if sector and not out.get("sector_level1"):
        out["sector_level1"]=sector
        out["sector_level2"]=sub
        out["index_style"]=out.get("index_style") if out.get("index_style") not in (None,"INDEX_OTHER") else (
            "BROAD" if sub=="BROAD_OR_FACTOR" else "SECTOR_OR_THEME"
        )
    if out.get("region_primary") and out.get("exposure_type"):
        out["risk_bucket"]="|".join((out["region_primary"],out["exposure_type"],
                          out.get("sector_level1") or "UNRESOLVED"))
    return out


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
