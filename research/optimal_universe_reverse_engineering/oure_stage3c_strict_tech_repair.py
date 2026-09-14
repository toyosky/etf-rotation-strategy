#!/usr/bin/env python3
"""OURE Stage3C: mechanical repair of Stage3B exclusion completeness and K cap."""
from __future__ import annotations

import pandas as pd

import oure_stage3b_strict_exposure_disjoint_search as s3b
import oure_stage3_exposure_disjoint_search as base

base.MAX_NONCASH = 60

EXTRA_TECH_TERMS = (
    "SOFTWARE", "ARTIFICIAL_INTELLIGENCE", "INTELLIGENCE", "BIG_DATA", "BIGDATA",
    "CLOUD_COMPUTING", "软件", "人工智能", "大数据", "云计算", "计算机",
)


def repaired_exclusion_reason(r: pd.Series) -> str | None:
    reason = s3b.strict_exclusion_reason(r)
    if reason is not None:
        return reason
    vals = []
    for k in (
        "name", "exposure_level1", "exposure_level2", "underlying_key",
        "risk_bucket", "style_sector", "asset_class", "region_primary"
    ):
        v = r.get(k)
        vals.append("" if pd.isna(v) else str(v).upper())
    blob = "|".join(vals)
    if any(term in blob for term in EXTRA_TECH_TERMS):
        return "BROAD_TECH_CHAIN_SOFTWARE_AI_REPAIR"
    return None

base.exclusion_reason = repaired_exclusion_reason

if __name__ == "__main__":
    base.main()
