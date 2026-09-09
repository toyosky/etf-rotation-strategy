#!/usr/bin/env python3
"""Robust current ETF+LOF metadata universe builder (V3).

Fixes V2 ingestion issues:
- normalize exchange-prefixed Sina codes such as sz169106 -> 169106;
- preserve Python None for missing bar coverage instead of pandas NaN in integer fields.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd
from sqlalchemy import create_engine, text

from build_instrument_metadata import auto_classify
from build_instrument_metadata_universe_v2 import MANUAL, MANUAL_VALID_FROM, db_url

SNAPSHOT = date(2026, 9, 9)


def normalize_code(raw: Any) -> str | None:
    s = str(raw).strip()
    if not s or s.lower() in {"nan", "none"}:
        return None
    s = re.sub(r"^(sh|sz|SH|SZ)", "", s)
    m = re.search(r"(\d{6})$", s)
    if m:
        return m.group(1)
    try:
        return str(int(float(s))).zfill(6)
    except Exception:
        return None


def frame_map(df: pd.DataFrame, code_cols: list[str], name_cols: list[str]) -> dict[str, str]:
    if df is None or df.empty:
        return {}
    cc = next((c for c in code_cols if c in df.columns), None)
    nc = next((c for c in name_cols if c in df.columns), None)
    if cc is None or nc is None:
        return {}
    out: dict[str, str] = {}
    for _, r in df.iterrows():
        code = normalize_code(r[cc])
        if code is not None:
            out[code] = str(r[nc])
    return out


def current_lists() -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str], list[str]]:
    warnings: list[str] = []
    etf: dict[str, str] = {}
    lof: dict[str, str] = {}
    names: dict[str, str] = {}
    ftypes: dict[str, str] = {}

    try:
        etf = frame_map(ak.fund_etf_spot_em(), ["代码", "基金代码"], ["名称", "基金名称"])
    except Exception as exc:
        warnings.append(f"fund_etf_spot_em failed: {exc!r}")

    try:
        lof = frame_map(ak.fund_lof_spot_em(), ["代码", "基金代码"], ["名称", "基金名称"])
    except Exception as exc:
        warnings.append(f"fund_lof_spot_em failed: {exc!r}")

    if not lof:
        try:
            lof = frame_map(ak.fund_etf_category_sina(symbol="LOF基金"), ["代码", "基金代码"], ["名称", "基金名称"])
            warnings.append("LOF list used Sina fallback")
        except Exception as exc:
            warnings.append(f"Sina LOF fallback failed: {exc!r}")

    if not lof:
        try:
            lof = frame_map(ak.fund_etf_category_ths(symbol="LOF", date=""), ["基金代码", "代码"], ["基金名称", "名称"])
            warnings.append("LOF list used THS fallback")
        except Exception as exc:
            warnings.append(f"THS LOF fallback failed: {exc!r}")

    try:
        fm = ak.fund_name_em()
        for _, r in fm.iterrows():
            code = normalize_code(r.get("基金代码"))
            if code is None:
                continue
            names[code] = str(r.get("基金简称", code))
            ftypes[code] = str(r.get("基金类型", ""))
        if not etf:
            etf = {c:n for c,n in names.items() if "ETF" in n.upper() and "联接" not in n}
            warnings.append("ETF list used name-inference fallback")
        if not lof:
            lof = {c:n for c,n in names.items() if "LOF" in n.upper() and "联接" not in n}
            warnings.append("LOF list used name-inference fallback")
    except Exception as exc:
        warnings.append(f"fund_name_em failed: {exc!r}")

    names = {**names, **etf, **lof}
    return etf, lof, names, ftypes, warnings


def clean_value(v: Any) -> Any:
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--summary-path", default="instrument-metadata-summary.json")
    ap.add_argument("--csv-path", default="instrument-metadata-current.csv")
    ap.add_argument("--review-path", default="instrument-metadata-review.csv")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    engine = create_engine(db_url(args.database_url), pool_pre_ping=True)

    cov = pd.read_sql_query(text("""
        select symbol, min(date) as data_start_date, max(date) as data_end_date, count(*)::bigint as bars_count
        from public.daily_bars group by symbol order by symbol
    """), engine)
    coverage: dict[str, dict[str, Any]] = {}
    for _, r in cov.iterrows():
        sym = normalize_code(r["symbol"])
        if sym:
            coverage[sym] = {
                "data_start_date": pd.Timestamp(r["data_start_date"]).date(),
                "data_end_date": pd.Timestamp(r["data_end_date"]).date(),
                "bars_count": int(r["bars_count"]),
            }

    etf, lof, names, ftypes, warnings = current_lists()
    current_codes = set(etf) | set(lof)
    universe = sorted(current_codes | set(coverage) | set(MANUAL))
    rows: list[dict[str, Any]] = []

    for sym in universe:
        c = coverage.get(sym)
        ptype = "ETF" if sym in etf else "LOF" if sym in lof else "UNKNOWN"
        nm = names.get(sym, sym)
        if sym in MANUAL:
            meta = dict(MANUAL[sym])
            if nm != sym:
                meta["name"] = nm
            start = c["data_start_date"] if c else MANUAL_VALID_FROM.get(sym, SNAPSHOT)
            meta.update(
                classification_method="MANUAL_REFERENCE_V3", confidence=0.99, needs_review=False,
                label_scope="HISTORICAL_MANUAL", historical_safe=True, valid_from=start,
                metadata_source="manual structural reference + AKShare current exchange/fund masters",
            )
            meta.setdefault("nav_lag_days", None)
            meta.setdefault("leveraged_flag", False)
            meta.setdefault("inverse_flag", False)
        else:
            meta = auto_classify(sym, nm, ptype, ftypes.get(sym))
            meta.update(
                name=nm, label_scope="CURRENT_SNAPSHOT", historical_safe=False, valid_from=SNAPSHOT,
                metadata_source="AKShare 1.18.94 current ETF/LOF lists + Eastmoney fund master",
            )

        meta.update(
            symbol=sym,
            data_start_date=c["data_start_date"] if c else None,
            data_end_date=c["data_end_date"] if c else None,
            bars_count=c["bars_count"] if c else None,
            current_exchange_listed=sym in current_codes,
            has_daily_bars=c is not None,
            valid_to=None,
        )
        rows.append({k: clean_value(v) for k, v in meta.items()})

    sql = text("""
        insert into public.instrument_metadata (
          symbol,name,product_type,asset_class,region_primary,region_tags,exposure_level1,exposure_level2,
          underlying_key,risk_bucket,style_sector,is_qdii,nav_lag_days,premium_sensitive,t0_flag,
          derivative_exposure,roll_cost_exposure,currency_exposure,leveraged_flag,inverse_flag,
          data_start_date,data_end_date,bars_count,current_exchange_listed,has_daily_bars,
          label_scope,historical_safe,valid_from,valid_to,classification_method,confidence,needs_review,
          metadata_source,notes,updated_at
        ) values (
          :symbol,:name,:product_type,:asset_class,:region_primary,:region_tags,:exposure_level1,:exposure_level2,
          :underlying_key,:risk_bucket,:style_sector,:is_qdii,:nav_lag_days,:premium_sensitive,:t0_flag,
          :derivative_exposure,:roll_cost_exposure,:currency_exposure,:leveraged_flag,:inverse_flag,
          :data_start_date,:data_end_date,:bars_count,:current_exchange_listed,:has_daily_bars,
          :label_scope,:historical_safe,:valid_from,:valid_to,:classification_method,:confidence,:needs_review,
          :metadata_source,:notes,now()
        ) on conflict(symbol,valid_from) do update set
          name=excluded.name, product_type=excluded.product_type, asset_class=excluded.asset_class,
          region_primary=excluded.region_primary, region_tags=excluded.region_tags,
          exposure_level1=excluded.exposure_level1, exposure_level2=excluded.exposure_level2,
          underlying_key=excluded.underlying_key, risk_bucket=excluded.risk_bucket,
          style_sector=excluded.style_sector, is_qdii=excluded.is_qdii,
          nav_lag_days=excluded.nav_lag_days, premium_sensitive=excluded.premium_sensitive,
          t0_flag=excluded.t0_flag, derivative_exposure=excluded.derivative_exposure,
          roll_cost_exposure=excluded.roll_cost_exposure, currency_exposure=excluded.currency_exposure,
          leveraged_flag=excluded.leveraged_flag, inverse_flag=excluded.inverse_flag,
          data_start_date=excluded.data_start_date, data_end_date=excluded.data_end_date,
          bars_count=excluded.bars_count, current_exchange_listed=excluded.current_exchange_listed,
          has_daily_bars=excluded.has_daily_bars, label_scope=excluded.label_scope,
          historical_safe=excluded.historical_safe, valid_to=excluded.valid_to,
          classification_method=excluded.classification_method, confidence=excluded.confidence,
          needs_review=excluded.needs_review, metadata_source=excluded.metadata_source,
          notes=excluded.notes, updated_at=now()
    """)
    with engine.begin() as conn:
        conn.execute(sql, rows)

    current = pd.read_sql_query(text("select * from public.instrument_metadata_current order by symbol"), engine)
    current.to_csv(args.csv_path, index=False)
    current.loc[current["needs_review"].fillna(True)].to_csv(args.review_path, index=False)
    listed = current.loc[current["current_exchange_listed"].fillna(False)]

    summary = {
        "snapshot_date": SNAPSHOT.isoformat(),
        "metadata_rows": int(len(current)),
        "current_exchange_products": int(len(current_codes)),
        "current_etf_count": int(len(etf)),
        "current_lof_count": int(len(lof)),
        "products_with_daily_bars": int(current["has_daily_bars"].fillna(False).sum()),
        "current_products_missing_daily_bars": int((~listed["has_daily_bars"].fillna(False)).sum()),
        "historical_safe_rows": int(current["historical_safe"].fillna(False).sum()),
        "manual_reference_rows": int(current["classification_method"].astype(str).str.startswith("MANUAL_REFERENCE").sum()),
        "needs_review_rows": int(current["needs_review"].fillna(True).sum()),
        "current_product_type_counts": listed["product_type"].value_counts(dropna=False).to_dict(),
        "current_asset_class_counts": listed["asset_class"].value_counts(dropna=False).to_dict(),
        "current_region_counts": listed["region_primary"].fillna("NULL").value_counts().to_dict(),
        "current_risk_bucket_top25": listed["risk_bucket"].fillna("NULL").value_counts().head(25).to_dict(),
        "missing_fixed15_bars": [s for s in ["511220", "511380"] if s in set(current["symbol"]) and not bool(current.loc[current["symbol"] == s, "has_daily_bars"].iloc[0])],
        "warnings": warnings,
    }
    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
