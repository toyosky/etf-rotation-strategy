#!/usr/bin/env python3
"""OURE Stage3B: strict broad-exposure-disjoint search.

Mechanical wrapper around Stage3. It changes only the exclusion taxonomy and
maximum search cardinality. Frozen OLS semantics and portfolio-value objective
remain unchanged.
"""
from __future__ import annotations

import pandas as pd

import oure_stage3_exposure_disjoint_search as base

# Avoid repeating the Stage3 boundary artifact where the champion hit K=15.
base.MAX_NONCASH = 30

BANNED_SYMBOLS = set(base.BANNED_SYMBOLS)


def _s(x) -> str:
    return "" if pd.isna(x) else str(x).upper()


def strict_exclusion_reason(r: pd.Series) -> str | None:
    sym = str(r["symbol"])
    if sym in BANNED_SYMBOLS:
        return "EXPLICIT_STAGE1_K7_RISK_SYMBOL"

    fields = {
        k: _s(r.get(k))
        for k in (
            "name", "exposure_level1", "exposure_level2", "underlying_key",
            "risk_bucket", "style_sector", "asset_class", "region_primary"
        )
    }
    blob = "|".join(fields.values())

    # 159915: broad China-growth family, not only the exact ChiNext board label.
    if "GROWTH" in blob or "创业板" in blob:
        return "BROAD_GROWTH"

    # 159985: agriculture / farm-commodity family.
    if any(x in blob for x in ("AGRICULTURE", "SOYMEAL", "农", "豆粕")):
        return "BROAD_AGRICULTURE"

    # 161226: precious-metals family.
    if any(x in blob for x in ("PRECIOUS_METALS", "GOLD", "SILVER", "黄金", "白银")):
        return "BROAD_PRECIOUS_METALS"

    # 501018: energy/oil/gas family across commodity and equity wrappers.
    if any(x in blob for x in ("ENERGY", "CRUDE", "OIL", "GAS", "石油", "原油", "油气", "能源")):
        return "BROAD_ENERGY_OIL_GAS"

    # 513100: growth-tech family. Use a broad technology-chain veto so the
    # replication cannot simply replace Nasdaq with semis/electronics/HK tech.
    if any(x in blob for x in (
        "TECH", "SEMICONDUCTOR", "ELECTRONICS", "COMMUNICATION", "DIGITAL",
        "NASDAQ", "芯片", "半导体", "电子", "通信", "科技", "数字"
    )):
        return "BROAD_TECH_CHAIN"

    # 513920: SOE/state-owned family. Include the Chinese name as a guard
    # because some metadata rows are currently classified under DIVIDEND.
    if any(x in blob for x in ("SOE", "CENTRAL", "STATE_OWNED", "央企", "国企")):
        return "BROAD_SOE"

    return None


base.exclusion_reason = strict_exclusion_reason

if __name__ == "__main__":
    base.main()
