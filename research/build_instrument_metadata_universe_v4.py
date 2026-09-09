#!/usr/bin/env python3
"""V4 wrapper: robust ETF + LOF current universe without unstable Eastmoney LOF endpoint.

- ETF current list: Eastmoney ETF spot (verified available in prior runs).
- LOF current list: Sina LOF category directly (verified fallback in V2).
- Names/types: Eastmoney static fund master.
- Reuses V3 normalization, database persistence, manual exposure corrections.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import akshare as ak

import build_instrument_metadata_universe_v3 as base


def current_lists() -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str], list[str]]:
    warnings: list[str] = []
    etf: dict[str, str] = {}
    lof: dict[str, str] = {}
    names: dict[str, str] = {}
    ftypes: dict[str, str] = {}

    try:
        etf = base.frame_map(
            ak.fund_etf_spot_em(),
            ["代码", "基金代码"],
            ["名称", "基金名称"],
        )
    except Exception as exc:
        warnings.append(f"fund_etf_spot_em failed: {exc!r}")

    # Do not call fund_lof_spot_em here: it is known to hang/fail intermittently
    # from GitHub-hosted runners. Use the independently verified Sina list.
    try:
        lof = base.frame_map(
            ak.fund_etf_category_sina(symbol="LOF基金"),
            ["代码", "基金代码"],
            ["名称", "基金名称"],
        )
        warnings.append("LOF list source: Sina category")
    except Exception as exc:
        warnings.append(f"Sina LOF source failed: {exc!r}")

    try:
        fm = ak.fund_name_em()
        for _, r in fm.iterrows():
            code = base.normalize_code(r.get("基金代码"))
            if code is None:
                continue
            names[code] = str(r.get("基金简称", code))
            ftypes[code] = str(r.get("基金类型", ""))
    except Exception as exc:
        warnings.append(f"fund_name_em failed: {exc!r}")

    if not etf:
        etf = {c: n for c, n in names.items() if "ETF" in n.upper() and "联接" not in n}
        warnings.append("ETF list used name-inference fallback")
    if not lof:
        lof = {c: n for c, n in names.items() if "LOF" in n.upper() and "联接" not in n}
        warnings.append("LOF list used name-inference fallback")

    names = {**names, **etf, **lof}
    return etf, lof, names, ftypes, warnings


base.current_lists = current_lists

if __name__ == "__main__":
    base.main()
