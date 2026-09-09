#!/usr/bin/env python3
"""Build current exchange-traded ETF+LOF metadata universe, independent of bar coverage.

V2 corrects a key limitation exposed by the first pass: `daily_bars` contains only
645 products and omits some relevant wrappers (e.g. 511220, 511380). Metadata must
represent the tradable product universe, not merely the already-ingested price set.

Sources:
- current ETF list: AKShare `fund_etf_spot_em`;
- current LOF list: `fund_lof_spot_em`, with Sina/THS fallbacks;
- fund master names/types: `fund_name_em`;
- current price-data coverage: Supabase `public.daily_bars`.

Current-name automatic labels remain `historical_safe=false`. Manual reference
exposures remain structural, performance-independent labels.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd
from sqlalchemy import create_engine, text

from build_instrument_metadata import MANUAL as BASE_MANUAL, auto_classify

SNAPSHOT = date(2026, 9, 9)

# Correct known economic-exposure identity and seed the two original fixed-pool
# bond instruments even though they are absent from the 645-symbol price table.
MANUAL = {k: dict(v) for k, v in BASE_MANUAL.items()}
MANUAL["513920"] = dict(
    name="港股通央企红利ETF华安", product_type="ETF", asset_class="EQUITY", region_primary="HK",
    region_tags=["HK", "CN_OFFSHORE"], exposure_level1="HK_EQUITY", exposure_level2="CENTRAL_SOE_DIVIDEND",
    underlying_key="HK_CONNECT_CENTRAL_SOE_DIVIDEND", risk_bucket="HK_SOE_DIVIDEND", style_sector="DIVIDEND_SOE",
    is_qdii=False, premium_sensitive=False, derivative_exposure=False, roll_cost_exposure=False,
    currency_exposure="HKD", t0_flag=False,
    notes="Original fixed15 code; corrected from prior domestic-SOE shorthand to actual HK Stock Connect central-SOE dividend exposure."
)

# First-bar proxies from the legacy strategy database for reference instruments
# missing from ETF_daily_bars. They are metadata validity anchors, not proof that
# the new price warehouse currently contains those bars.
MANUAL_VALID_FROM = {"511220": date(2015, 1, 5), "511380": date(2020, 10, 9)}


def db_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg2://" + raw[len("postgresql://"):]
    return raw


def frame_map(df: pd.DataFrame, code_cols: list[str], name_cols: list[str]) -> dict[str, str]:
    if df is None or df.empty:
        return {}
    cc = next((c for c in code_cols if c in df.columns), None)
    nc = next((c for c in name_cols if c in df.columns), None)
    if cc is None or nc is None:
        return {}
    out: dict[str, str] = {}
    for _, r in df.iterrows():
        raw = str(r[cc]).strip()
        if not raw or raw.lower() == "nan":
            continue
        try:
            code = str(int(float(raw))).zfill(6)
        except Exception:
            code = raw.zfill(6)
        out[code] = str(r[nc])
    return out


def get_current_lists() -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str], list[str]]:
    warnings: list[str] = []
    etf: dict[str, str] = {}
    lof: dict[str, str] = {}
    names: dict[str, str] = {}
    ftypes: dict[str, str] = {}

    try:
        d = ak.fund_etf_spot_em()
        etf = frame_map(d, ["代码", "基金代码"], ["名称", "基金名称"])
    except Exception as exc:
        warnings.append(f"fund_etf_spot_em failed: {exc!r}")

    try:
        d = ak.fund_lof_spot_em()
        lof = frame_map(d, ["代码", "基金代码"], ["名称", "基金名称"])
    except Exception as exc:
        warnings.append(f"fund_lof_spot_em failed: {exc!r}")

    if not lof:
        try:
            d = ak.fund_etf_category_sina(symbol="LOF基金")
            lof = frame_map(d, ["代码", "基金代码"], ["名称", "基金名称"])
            warnings.append("LOF list used Sina fallback")
        except Exception as exc:
            warnings.append(f"fund_etf_category_sina LOF fallback failed: {exc!r}")

    if not lof:
        try:
            d = ak.fund_etf_category_ths(symbol="LOF", date="")
            lof = frame_map(d, ["基金代码", "代码"], ["基金名称", "名称"])
            warnings.append("LOF list used THS fallback")
        except Exception as exc:
            warnings.append(f"fund_etf_category_ths LOF fallback failed: {exc!r}")

    try:
        fm = ak.fund_name_em()
        for _, r in fm.iterrows():
            code = str(r.get("基金代码", "")).zfill(6)
            names[code] = str(r.get("基金简称", code))
            ftypes[code] = str(r.get("基金类型", ""))
        if not lof:
            # Last-resort conservative inference. Avoid ETF feeder funds.
            for code, nm in names.items():
                nmu = nm.upper()
                if "LOF" in nmu and "联接" not in nm:
                    lof[code] = nm
            warnings.append("LOF list used name-inference fallback")
        if not etf:
            for code, nm in names.items():
                nmu = nm.upper()
                if "ETF" in nmu and "联接" not in nm:
                    etf[code] = nm
            warnings.append("ETF list used name-inference fallback")
    except Exception as exc:
        warnings.append(f"fund_name_em failed: {exc!r}")

    # Prefer exchange-list names, then fund-master names.
    names = {**names, **etf, **lof}
    return etf, lof, names, ftypes, warnings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--summary-path", default="instrument-metadata-v2-summary.json")
    ap.add_argument("--csv-path", default="instrument-metadata-v2-current.csv")
    ap.add_argument("--review-path", default="instrument-metadata-v2-review.csv")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(db_url(args.database_url), pool_pre_ping=True)
    cov = pd.read_sql_query(text("""
        select symbol, min(date) as data_start_date, max(date) as data_end_date, count(*)::int as bars_count
        from public.daily_bars group by symbol order by symbol
    """), engine)
    cov["symbol"] = cov["symbol"].astype(str).str.zfill(6)
    coverage = {str(r.symbol): r for r in cov.itertuples(index=False)}

    etf, lof, names, ftypes, warnings = get_current_lists()
    current_codes = set(etf) | set(lof)
    universe = sorted(current_codes | set(coverage) | set(MANUAL))

    rows: list[dict[str, Any]] = []
    for sym in universe:
        c = coverage.get(sym)
        listed = sym in current_codes
        if sym in etf:
            ptype = "ETF"
        elif sym in lof:
            ptype = "LOF"
        else:
            ptype = "UNKNOWN"
        nm = names.get(sym, sym)

        if sym in MANUAL:
            meta = dict(MANUAL[sym])
            if nm != sym:
                meta["name"] = nm
            start = pd.Timestamp(c.data_start_date).date() if c is not None else MANUAL_VALID_FROM.get(sym, SNAPSHOT)
            meta.update(
                classification_method="MANUAL_REFERENCE_V2", confidence=0.99, needs_review=False,
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
            data_start_date=pd.Timestamp(c.data_start_date).date() if c is not None else None,
            data_end_date=pd.Timestamp(c.data_end_date).date() if c is not None else None,
            bars_count=int(c.bars_count) if c is not None else None,
            current_exchange_listed=listed,
            has_daily_bars=c is not None,
            valid_to=None,
        )
        rows.append(meta)

    out = pd.DataFrame(rows)
    records = out.where(pd.notna(out), None).to_dict("records")

    with engine.begin() as conn:
        conn.execute(text("""
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
        """), records)

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
        "current_products_missing_daily_bars": int((listed["has_daily_bars"].fillna(False) == False).sum()),
        "historical_safe_rows": int(current["historical_safe"].fillna(False).sum()),
        "manual_reference_rows": int(current["classification_method"].astype(str).str.startswith("MANUAL_REFERENCE").sum()),
        "needs_review_rows": int(current["needs_review"].fillna(True).sum()),
        "current_product_type_counts": listed["product_type"].value_counts(dropna=False).to_dict(),
        "current_asset_class_counts": listed["asset_class"].value_counts(dropna=False).to_dict(),
        "current_risk_bucket_top25": listed["risk_bucket"].fillna("NULL").value_counts().head(25).to_dict(),
        "missing_fixed15_bars": [s for s in ["511220", "511380"] if s in set(current["symbol"]) and not bool(current.loc[current["symbol"]==s, "has_daily_bars"].iloc[0])],
        "warnings": warnings,
    }
    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
