#!/usr/bin/env python3
"""Static-master variant of instrument metadata builder.

Uses only AKShare/Eastmoney `fund_name_em` (static fund master), avoiding realtime
ETF/LOF quote endpoints. Product wrapper is inferred conservatively from fund
name/type; unresolved wrappers remain UNKNOWN + needs_review. Manual reference
labels in build_instrument_metadata.py override all automatic inference.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd
from sqlalchemy import create_engine, text

from build_instrument_metadata import MANUAL, auto_classify


def db_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg2://" + raw[len("postgresql://"):]
    return raw


def wrapper_from_name_type(name: str, fund_type: str) -> str:
    n = (name or "").upper()
    t = (fund_type or "").upper()
    if "ETF" in n or "ETF" in t:
        return "ETF"
    if "LOF" in n or "LOF" in t or "上市型开放式" in fund_type:
        return "LOF"
    return "UNKNOWN"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--snapshot-date", default="2026-09-09")
    ap.add_argument("--summary-path", default="instrument-metadata-summary.json")
    ap.add_argument("--csv-path", default="instrument-metadata-current.csv")
    ap.add_argument("--review-path", default="instrument-metadata-review.csv")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    snapshot = date.fromisoformat(args.snapshot_date)
    engine = create_engine(db_url(args.database_url), pool_pre_ping=True)

    coverage = pd.read_sql_query(text("""
        select symbol, min(date) as data_start_date, max(date) as data_end_date, count(*)::int as bars_count
        from public.daily_bars group by symbol order by symbol
    """), engine)
    coverage["symbol"] = coverage["symbol"].astype(str).str.zfill(6)

    warnings: list[str] = []
    try:
        fm = ak.fund_name_em()
    except Exception as exc:
        warnings.append(f"fund_name_em failed: {exc!r}")
        fm = pd.DataFrame(columns=["基金代码", "基金简称", "基金类型"])
    names: dict[str, str] = {}
    types: dict[str, str] = {}
    for _, r in fm.iterrows():
        sym = str(r.get("基金代码", "")).zfill(6)
        names[sym] = str(r.get("基金简称", sym))
        types[sym] = str(r.get("基金类型", ""))

    rows: list[dict[str, Any]] = []
    for r in coverage.itertuples(index=False):
        sym = str(r.symbol)
        nm = names.get(sym, sym)
        ft = types.get(sym, "")
        ptype = wrapper_from_name_type(nm, ft)

        if sym in MANUAL:
            meta = dict(MANUAL[sym])
            if nm != sym:
                meta["name"] = nm
            meta.update(
                classification_method="MANUAL_REFERENCE_V1", confidence=0.99, needs_review=False,
                label_scope="HISTORICAL_MANUAL", historical_safe=True,
                valid_from=pd.Timestamp(r.data_start_date).date(),
                metadata_source="manual reference universe + AKShare/Eastmoney fund_name_em",
            )
            meta.setdefault("nav_lag_days", None)
            meta.setdefault("leveraged_flag", False)
            meta.setdefault("inverse_flag", False)
        else:
            meta = auto_classify(sym, nm, ptype, ft)
            meta.update(
                name=nm, label_scope="CURRENT_SNAPSHOT", historical_safe=False,
                valid_from=snapshot,
                metadata_source="AKShare 1.18.94 / Eastmoney fund_name_em current master",
            )

        meta.update(
            symbol=sym,
            data_start_date=pd.Timestamp(r.data_start_date).date(),
            data_end_date=pd.Timestamp(r.data_end_date).date(),
            bars_count=int(r.bars_count), valid_to=None,
        )
        rows.append(meta)

    out = pd.DataFrame(rows)
    records = out.where(pd.notna(out), None).to_dict("records")
    with engine.begin() as conn:
        conn.execute(text("""
            update public.instrument_metadata
               set valid_to=:prev, updated_at=now()
             where valid_to is null and label_scope='CURRENT_SNAPSHOT' and valid_from<:snap
        """), {"prev": snapshot - timedelta(days=1), "snap": snapshot})
        conn.execute(text("""
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
            ) on conflict (symbol,valid_from) do update set
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
              bars_count=excluded.bars_count, label_scope=excluded.label_scope,
              historical_safe=excluded.historical_safe, valid_to=excluded.valid_to,
              classification_method=excluded.classification_method, confidence=excluded.confidence,
              needs_review=excluded.needs_review, metadata_source=excluded.metadata_source,
              notes=excluded.notes, updated_at=now()
        """), records)

    current = pd.read_sql_query(text("select * from public.instrument_metadata_current order by symbol"), engine)
    current.to_csv(args.csv_path, index=False)
    current.loc[current["needs_review"].fillna(True)].to_csv(args.review_path, index=False)
    summary = {
        "snapshot_date": snapshot.isoformat(),
        "source_universe_symbols": int(len(coverage)),
        "fund_master_rows": int(len(fm)),
        "name_matches": int(sum(s in names for s in coverage["symbol"])),
        "current_metadata_rows": int(len(current)),
        "manual_reference_rows": int((current["classification_method"] == "MANUAL_REFERENCE_V1").sum()),
        "historical_safe_rows": int(current["historical_safe"].fillna(False).sum()),
        "needs_review_rows": int(current["needs_review"].fillna(True).sum()),
        "product_type_counts": current["product_type"].value_counts(dropna=False).to_dict(),
        "asset_class_counts": current["asset_class"].value_counts(dropna=False).to_dict(),
        "region_counts": current["region_primary"].fillna("NULL").value_counts().to_dict(),
        "risk_bucket_top20": current["risk_bucket"].fillna("NULL").value_counts().head(20).to_dict(),
        "warnings": warnings,
    }
    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
