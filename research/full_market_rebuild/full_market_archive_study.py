#!/usr/bin/env python3
"""Frozen historical ETF/LOF panel => independent R2 rebuilding event study.

Research only; reads frozen Supabase Storage snapshot but NEVER writes to the
live PostgreSQL database. Requires S3 secrets in GitHub Actions.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import os
import tarfile
from collections import defaultdict
from pathlib import Path

import boto3
import numpy as np
import pandas as pd

from automation.build_fundamental_audit_trigger import calc_ols

BUCKET = "etf-research-archive"
PREFIX = "raw_daily_bars/frozen_20260917"
HORIZONS = (5, 10, 20, 40)
EPS_ANNUAL = 1e-8  # avoid false zero-crossings from exactly-flat price stretches
SNAPSHOT_DATE = "2026-09-17"

def s3client():
    keys = ("SUPABASE_STORAGE_S3_ACCESS_KEY_ID", "SUPABASE_STORAGE_S3_SECRET_ACCESS_KEY")
    if any(not os.getenv(k) for k in keys):
        raise RuntimeError("Missing S3 archive credentials; cannot silently use 19-ETF DB")
    return boto3.client("s3", endpoint_url="https://gsyziuzezmmnvgdoazkg.storage.supabase.co/storage/v1/s3",
                        region_name="ap-southeast-1", aws_access_key_id=os.environ[keys[0]],
                        aws_secret_access_key=os.environ[keys[1]])

def read_snapshot(bundle_path: Path):
    s3 = s3client()
    manifest_bytes = s3.get_object(Bucket=BUCKET, Key=PREFIX+"/manifest.json")["Body"].read()
    manifest = json.loads(manifest_bytes)
    if manifest.get("source_symbols", 0) < 1000 or manifest.get("source_rows", 0) < 1000000:
        raise RuntimeError("Full-market source manifest unexpectedly small")
    if manifest.get("source_max_date", "") > SNAPSHOT_DATE:
        raise RuntimeError("Unexpected future dates in frozen source")
    if not manifest.get("objects") or len(manifest["objects"]) < 20:
        raise RuntimeError("Too few snapshot partitions")
    parts = []
    checks = []
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(bundle_path, "w:gz") as tar:
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest_bytes)
        tar.addfile(info, io.BytesIO(manifest_bytes))
        for idx, item in enumerate(manifest["objects"]):
            key = item["key"]
            if not key.startswith(PREFIX+"/year=") or not key.endswith("/daily_bars.parquet"):
                raise RuntimeError(f"Unexpected archive member {key}")
            payload = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
            digest = hashlib.sha256(payload).hexdigest()
            if digest != item["sha256"] or len(payload) != int(item["bytes"]):
                raise RuntimeError(f"Archive byte/checksum mismatch {key}")
            df = pd.read_parquet(io.BytesIO(payload))
            if len(df) != int(item["rows"]):
                raise RuntimeError(f"Archive parquet row-count mismatch {key}")
            parts.append(df)
            arcname = "years/"+key[len(PREFIX)+1:]
            info = tarfile.TarInfo(arcname)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
            checks.append({"key":key,"sha256":digest,"rows":len(df),"bytes":len(payload)})
            if (idx+1)%5 == 0:
                print(f"VALIDATED_ARCHIVE_PARTITIONS {idx+1}/{len(manifest['objects'])}", flush=True)
    data = pd.concat(parts, ignore_index=True)
    data["symbol"] = data.symbol.astype(str).str.zfill(6)
    data["date"] = pd.to_datetime(data.date)
    for field in ("open","high","low","close","volume","amount"):
        data[field] = pd.to_numeric(data[field], errors="coerce")
    if data.duplicated(["symbol", "date"]).any():
        raise RuntimeError("Archive contains duplicate symbol-date keys")
    if len(data) != int(manifest["source_rows"]) or data.symbol.nunique() != int(manifest["source_symbols"]):
        raise RuntimeError("Archive total count differs from signed manifest")
    if data[["open","close","amount"]].isna().any().any() or (data[["open","close"]] <= 0).any().any():
        raise RuntimeError("Archive contains invalid prices/amounts")
    if str(data.date.max().date()) != str(manifest["source_max_date"]):
        raise RuntimeError("Date span differs from archive manifest")
    return data.sort_values(["symbol","date"]).reset_index(drop=True), manifest, checks

def extract(g: pd.DataFrame):
    g = g.sort_values("date").reset_index(drop=True)
    n = len(g)
    if n < 64: return []
    close = g.close.to_numpy(dtype=float)
    open_ = g.open.to_numpy(dtype=float)
    dates = g.date.to_numpy()
    amount = g.amount.to_numpy(dtype=float)
    volume = g.volume.to_numpy(dtype=float)
    if np.any(close<=0) or np.any(open_<=0):return []
    with np.errstate(divide="ignore",invalid="ignore",over="ignore"):
        annual,r2 = calc_ols(close)
    annual = np.asarray(annual,dtype=float)
    r2 = np.asarray(r2,dtype=float)
    # Numerical tolerance targets exactly-flat/quantized-price false crossings.
    rising = np.flatnonzero((annual[1:] > EPS_ANNUAL) & (annual[:-1] <= EPS_ANNUAL)) + 1
    rolling_amount = pd.Series(amount).rolling(60,min_periods=60)
    avg60 = rolling_amount.mean().to_numpy()
    med60 = rolling_amount.median().to_numpy()
    traded60 = pd.Series((volume>0).astype(float)).rolling(60,min_periods=60).mean().to_numpy()
    symbol = str(g.at[0,"symbol"])
    typ = str(g.at[0,"instrument_type"])
    first = pd.Timestamp(g.at[0,"date"])
    results = []
    for c in rising:
        for i in range(c+1, min(c+4,n)):
            if not (np.isfinite(r2[i]) and np.isfinite(r2[c]) and annual[i] > EPS_ANNUAL
                    and r2[i] > r2[c]+1e-12 and r2[i] > r2[i-1]+1e-12):
                continue
            # 200 historical bars / 365 listed calendar days / 60-day liquidity
            age = int((pd.Timestamp(g.at[i,"date"])-first).days)
            strict = bool(i+1>=200 and age>=365 and avg60[i]>=20e6
                          and med60[i]>=10e6 and traded60[i]>=0.95)
            broad = bool(i+1>=60 and avg60[i]>=3e6 and traded60[i]>=0.90)
            if i < 5:
                break
            ret2 = close[i]/close[i-2]-1
            ret1max = max(close[k]/close[k-1]-1 for k in range(i-2,i+1))
            # Labels derived only from information known by signal-date close.
            shock = bool(ret2>=0.10 or ret1max>=0.08)
            mild = bool(ret2>=0.08 or ret1max>=0.06)
            entry = i+1
            gap = int((pd.Timestamp(dates[entry])-pd.Timestamp(dates[i])).days) if entry<n else None
            row = {"symbol":symbol,"instrument_type":typ,
                   "cross_date":str(pd.Timestamp(dates[c]).date()),
                   "signal_date":str(pd.Timestamp(dates[i]).date()),
                   "entry_date":str(pd.Timestamp(dates[entry]).date()) if entry<n else None,
                   "bars_seen":i+1,"listing_age_days":age,
                   "avg_amount60":float(avg60[i]) if np.isfinite(avg60[i]) else None,
                   "strict_eligible":strict,"broad_eligible":broad,
                   "entry_gap_calendar_days":gap,
                   "signal_annual":float(annual[i]),"signal_r2":float(r2[i]),
                   "ret2_pre":float(ret2),"max1d_pre3":float(ret1max),
                   "shock10_8":shock,"shock8_6":mild,
                   "type":"SHOCK" if shock else "GRADUAL"}
            row["entry_usable"] = bool(entry<n and gap is not None and gap<=7)
            for h in HORIZONS:
                j=i+h
                row[f"return_{h}d"] = float(close[j]/open_[entry]-1) if entry<n and j<n and row["entry_usable"] else None
                row[f"mae_close_{h}d"] = float(np.min(close[entry:j+1]/open_[entry]-1)) if entry<n and j<n and row["entry_usable"] else None
            results.append(row)
            break
    return results

def summaries(events: pd.DataFrame):
    output={}
    cuts={
        "raw_all": events,
        "broad_2021_2024":events[(events.year.between(2021,2024))&events.broad_eligible&events.entry_usable],
        "broad_2025_2026":events[(events.year>=2025)&events.broad_eligible&events.entry_usable],
        "strict_2021_2024":events[(events.year.between(2021,2024))&events.strict_eligible&events.entry_usable],
        "strict_2025_2026":events[(events.year>=2025)&events.strict_eligible&events.entry_usable],
        "strict_all_2021plus":events[(events.year>=2021)&events.strict_eligible&events.entry_usable],
    }
    for cut, a in cuts.items():
        output[cut]={}
        for typ,part in {"all":a,"shock":a[a.shock10_8],"gradual":a[~a.shock10_8],
                         "moderate":a[a.shock8_6&~a.shock10_8]}.items():
            result={"events":len(part),"symbols":int(part.symbol.nunique())}
            for h in HORIZONS:
                s=part[f"return_{h}d"].dropna()
                result[str(h)+"d"]={"n":len(s),"mean":float(s.mean()) if len(s) else None,
                                     "median":float(s.median()) if len(s) else None,
                                     "win":float((s>0).mean()) if len(s) else None,
                                     "p10":float(s.quantile(.1)) if len(s) else None}
            output[cut][typ]=result
    return output

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="research/full_market_rebuild/full_market_output")
    a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    data,manifest,checks=read_snapshot(out/"frozen_20260917_source.tar.gz")
    # Do not include stable parking proxy in risk-asset rebuild events.
    risk=data[data.symbol!="511220"]
    results=[]
    for idx,(sym,g) in enumerate(risk.groupby("symbol",sort=True)):
        results.extend(extract(g))
        if (idx+1)%200==0:
            print(f"EXTRACTED_SYMBOLS {idx+1}/{risk.symbol.nunique()} EVENTS {len(results)}",flush=True)
    events=pd.DataFrame(results)
    if events.empty:raise RuntimeError("No rebuilt events from full historical archive")
    events["year"]=pd.to_datetime(events.signal_date).dt.year
    events.sort_values(["signal_date","symbol"]).to_csv(out/"full_market_events.csv",index=False)
    stats=summaries(events)
    info={"status":"EXPLORATORY_ARCHIVE_STUDY","archive_version":manifest.get("archive_version"),
          "archive_as_of":manifest.get("source_max_date"),"data_year_min":str(data.date.min().date()),
          "source_rows":len(data),"source_symbols":int(data.symbol.nunique()),
          "symbols_tested":int(risk.symbol.nunique()),"events_total":len(events),
          "source_manifest_sha256":hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
          "archive_object_checksums_verified":len(checks),
          "ols":"weighted log price, 26 sessions, 10-day half-life, tolerance 1e-8",
          "eligibility":{"broad":"60 observed sessions, 60d mean amount >=3m, >=90% positive-volume days",
                         "strict":"200 observed sessions, >=365 calendar days since first observed trade, 60d mean amount>=20m, median>=10m, >=95% positive-volume days"},
          "summary":stats,
          "caveats":["frozen Sep17 2026 archive; not Oct20 live market",
                     "1090 archived instruments are not guaranteed to include liquidated ETFs; current-contemporary universe may bias historical representation",
                     "different from unchanged OLS rule only through numerical near-zero tolerance 1e-8",
                     "HFQ historical-price as-of knowledge / share splits not verified",
                     "ETF duplicate underlying index events remain correlated; no canonical underlying-index de-dup yet",
                     "no historical premium PIT, no transaction costs, no actual executable portfolio",
                     "events counted as separate ETF observations, not distinct macro information shocks"]}
    (out/"full_market_report.json").write_text(json.dumps(info,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf8")
    print("FULL_MARKET_REPORT "+json.dumps({
        "source_symbols":info["source_symbols"],"source_rows":info["source_rows"],
        "events":len(events),"strict_2021plus":stats["strict_all_2021plus"]},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
