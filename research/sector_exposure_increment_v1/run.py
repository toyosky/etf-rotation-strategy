#!/usr/bin/env python3
"""Isolated sector-universe admission experiment: bank, agriculture, defence.
No changes to the live pool, notifications or trading engine.
"""
from __future__ import annotations
import io
import json
import math
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import boto3
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))
from automation.tencent_daily_sync import run_westock, normalize
from full_market_ols_storage import build_features, _db_url
from walk_forward_candidate_pool import (
    build_daily_targets, backtest_open_to_open, summarize_variant
)

PROJECT = "gsyziuzezmmnvgdoazkg"
BUCKET = "etf-research-archive"
PREFIX = "raw_daily_bars/frozen_20260917"
SECTORS = {
    "512800": ("BANK", "sh512800"),
    "516550": ("AGRICULTURE", "sh516550"),
    "512660": ("DEFENSE", "sh512660"),
}
BASE = [
    "159934", "159985", "161226", "513100", "159957", "159509",
    "513290", "159529", "159981", "501018", "513530", "511380", "164824"
]
OUT = ROOT / "data" / "sector-exposure-increment-20261018.json"

def storage():
    access = os.getenv("SUPABASE_STORAGE_S3_ACCESS_KEY_ID", "")
    secret = os.getenv("SUPABASE_STORAGE_S3_SECRET_ACCESS_KEY", "")
    if not access or not secret:
        raise RuntimeError("Missing Supabase Storage S3 credentials")
    return boto3.client("s3",
        endpoint_url=f"https://{PROJECT}.storage.supabase.co/storage/v1/s3",
        region_name="ap-southeast-1",
        aws_access_key_id=access, aws_secret_access_key=secret)

def archive_sector_bars(client):
    manifest = json.loads(client.get_object(
        Bucket=BUCKET, Key=f"{PREFIX}/manifest.json")["Body"].read())
    counts = {str(x["symbol"]).zfill(6): int(x["rows"])
              for x in manifest["symbol_counts"]}
    frames = []
    for part in manifest["objects"]:
        year = int(part["year"])
        if year < 2016:
            continue
        raw = client.get_object(Bucket=BUCKET, Key=part["key"])["Body"].read()
        # Archive verification: S3 object checksum is part of the frozen manifest.
        import hashlib
        if hashlib.sha256(raw).hexdigest() != part["sha256"]:
            raise RuntimeError("Archive checksum mismatch: " + part["key"])
        df = pd.read_parquet(io.BytesIO(raw))
        df["symbol"] = df["symbol"].astype(str).str.zfill(6)
        df = df.loc[df.symbol.isin(SECTORS)]
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame(), counts
    return pd.concat(frames, ignore_index=True), counts

def fetch_fresh():
    # 100 calendar days deliberately overlap the frozen 2026-09-17 snapshot.
    asof = date.today()
    codes = [pair[1] for pair in SECTORS.values()]
    types = {sym: "ETF" for sym in SECTORS}
    payload = run_westock(codes, asof-timedelta(days=100), asof, attempts=3)
    rows = normalize(payload, codes, types, asof)
    received = {row[0] for row in rows}
    for sym,(kind,code) in SECTORS.items():
        if sym not in received:
            rows.extend(normalize(run_westock([code], asof-timedelta(days=100), asof, 3),
                                  [code], types, asof))
    fields = ["symbol","date","open","high","low","close","volume","amount","instrument_type","ingested_on"]
    return pd.DataFrame(rows, columns=fields)

def harmonize(old, recent, counts):
    all_groups, notes = [], {}
    for sym,(sector, code) in SECTORS.items():
        archived = old.loc[old.symbol==sym].copy() if not old.empty else pd.DataFrame()
        fresh = recent.loc[recent.symbol==sym].copy()
        if len(fresh)<10:
            raise RuntimeError(f"{sym}: fresh Tencent data not available")
        if archived.empty:
            # For an absent symbol in the archive, query Tencent from its first feasible
            # listing year. Do not backfill by cloning a proxy.
            historical = normalize(run_westock([code],date(2015,1,1),
                date.today(),3),[code],{sym:"ETF"},date.today())
            columns = ["symbol","date","open","high","low","close","volume",
                       "amount","instrument_type","ingested_on"]
            archived = pd.DataFrame(historical,columns=columns)
            if len(archived)<200:
                raise RuntimeError(f"{sym}: insufficient verified full history")
            fresh = fresh.iloc[0:0].copy()
            seam_note = "full Tencent HFQ history, no archive available"
        else:
            archived["date"] = pd.to_datetime(archived["date"])
            fresh["date"] = pd.to_datetime(fresh["date"])
            match = archived[["date","close"]].merge(
                fresh[["date","close"]],on="date",suffixes=("_old","_new"))
            if len(match)<8:
                raise RuntimeError(f"{sym}: archive / Tencent history overlap too small")
            ratio = float(np.median(match.close_new/match.close_old))
            discrepancies = np.abs(match.close_new/(match.close_old*ratio)-1)
            if not np.isfinite(ratio) or ratio<=0 or float(np.quantile(discrepancies,0.9))>0.025:
                raise RuntimeError(f"{sym}: unverified adjustment seam, refuse splice")
            archived = archived.copy()
            for col in ("open","high","low","close"):
                archived[col] = pd.to_numeric(archived[col])*ratio
            seam_note = {"overlap_days":len(match),"archive_to_tencent_ratio":ratio,
                "overlap_p90_error":float(np.quantile(discrepancies,.9))}
        g = pd.concat([archived,fresh],ignore_index=True)
        g["date"] = pd.to_datetime(g["date"])
        g = g.sort_values("date").drop_duplicates(["symbol","date"],keep="last")
        g["symbol"] = sym
        for col in ("open","high","low","close","volume","amount"):
            g[col] = pd.to_numeric(g[col],errors="coerce")
        if g[["open","high","low","close","volume","amount"]].isna().any().any():
            raise RuntimeError(f"{sym}: nonnumeric/null OHLCVA")
        if (g[["open","high","low","close"]]<=0).any().any():
            raise RuntimeError(f"{sym}: invalid prices")
        ret = g.close.pct_change()
        if ((ret.abs()>0.45) & (g.date>=pd.Timestamp("2020-01-01"))).any():
            raise RuntimeError(f"{sym}: suspicious >45% daily return")
        if (pd.Timestamp(date.today()) - g.date.max()).days > 7:
            raise RuntimeError(f"{sym}: stale data {g.date.max()}")
        if len(g)<200:
            raise RuntimeError(f"{sym}: insufficient bars")
        all_groups.append(g)
        notes[sym]={"sector":sector,"n":len(g),"first":str(g.date.min().date()),
            "last":str(g.date.max().date()),"archived_count":counts.get(sym,0),
            "seam":seam_note}
    return pd.concat(all_groups,ignore_index=True),notes

def save_research_bars(df):
    db=os.environ["ETF_DAILY_BARS_DATABASE_URL"]
    tuples=[(str(r.symbol),r.date.date(),float(r.open),float(r.high),float(r.low),
            float(r.close),float(r.volume),float(r.amount))
            for r in df.itertuples(index=False)]
    with psycopg2.connect(db,connect_timeout=30) as conn:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO research.sector_candidate_bars
                (symbol,date,open,high,low,close,volume,amount)
                VALUES %s
                ON CONFLICT(symbol,date) DO UPDATE SET
                open=excluded.open,high=excluded.high,low=excluded.low,
                close=excluded.close,volume=excluded.volume,amount=excluded.amount,
                recorded_at=now()
            """,tuples,page_size=1000)

def summary_events(features, selected):
    out={}
    for sym in selected:
        g=features.loc[features.symbol==sym].sort_values("date").reset_index(drop=True)
        cross=(g.annual.shift(1)<=0)&(g.annual>0)
        qualified=[]
        for i in np.flatnonzero(cross.to_numpy()):
            for j in range(i+1,min(i+4,len(g))):
                if (g.at[j,"annual"]>0 and
                    g.at[j,"r2"]>g.at[i,"r2"] and
                    g.at[j,"r2"]>g.at[j-1,"r2"]):
                    if g.at[j,"date"]>=pd.Timestamp("2021-01-01") and j+1<len(g):
                        result={"signal_date":str(g.at[j,"date"].date()),
                                "first_cross_date":str(g.at[i,"date"].date()),
                                "r2":float(g.at[j,"r2"]),
                                "universe_eligible":bool(g.at[j,"universe_eligible"])}
                        for h in (5,10,20,40):
                            result[f"next_open_to_{h}d_close"]= (
                              float(g.at[j+h,"close"]/g.at[j+1,"open"]-1)
                              if j+h<len(g) else None)
                        qualified.append(result)
                    break
        out[sym]={"events":len(qualified),
                  "eligible_events":sum(x["universe_eligible"] for x in qualified),
                  "signals":qualified,
                  "post_entry_20d_mean":float(np.mean([
                    x["next_open_to_20d_close"] for x in qualified
                    if x["next_open_to_20d_close"] is not None]))
                    if any(x["next_open_to_20d_close"] is not None for x in qualified) else None}
    return out

def main():
    s3=storage()
    old,counts=archive_sector_bars(s3)
    recent=fetch_fresh()
    additional,quality=harmonize(old,recent,counts)
    save_research_bars(additional)
    db=os.environ["ETF_DAILY_BARS_DATABASE_URL"]
    engine=create_engine(_db_url(db),pool_pre_ping=True)
    with engine.connect() as conn:
        base=pd.read_sql_query(text("""
         SELECT symbol,date,open,high,low,close,volume,amount
         FROM public.daily_bars WHERE symbol=ANY(:codes)
         ORDER BY symbol,date
        """),conn,params={"codes":BASE},parse_dates=["date"])
    additional["date"]=pd.to_datetime(additional["date"])
    bars=pd.concat([base,additional[base.columns]],ignore_index=True)
    if bars.symbol.nunique()!=len(BASE)+len(SECTORS):
        raise RuntimeError("Baseline or sector bars incomplete")
    features=build_features(bars)
    eligible=features.loc[features.date>=pd.Timestamp("2021-01-01")]
    for sym in SECTORS:
        quality[sym]["eligible_days"] = int(eligible.loc[eligible.symbol==sym,"trend_eligible"].sum())
        quality[sym]["universe_admissible_days"] = int(eligible.loc[eligible.symbol==sym,"universe_eligible"].sum())
    tests={
        "BASE":BASE,
        "ADD_BANK":BASE+["512800"],
        "ADD_AGRICULTURE":BASE+["516550"],
        "ADD_DEFENSE":BASE+["512660"],
        "ADD_ALL":BASE+list(SECTORS),
    }
    results={}
    target_frames={}
    for key,codes in tests.items():
        targets,count=build_daily_targets(features.loc[features.symbol.isin(codes)],"baseline")
        pnl=backtest_open_to_open(bars.loc[bars.symbol.isin(codes)],targets)
        results[key]=summarize_variant(key,pnl,targets,count)
        target_frames[key]=targets
    baseline=target_frames["BASE"]
    for name,targets in target_frames.items():
        if name=="BASE": continue
        both=pd.concat([baseline.rename("base"),targets.rename("expanded")],axis=1)
        chosen=both["expanded"].isin(SECTORS)
        results[name]["sector_top1_signal_days"]=int(chosen.sum())
        results[name]["sector_top1_when_baseline_cash"]=int((chosen&both.base.isna()).sum())
        results[name]["sector_takeover_vs_baseline"]=int((chosen&both.base.notna()).sum())
    record={
      "created_at_utc":pd.Timestamp.now(tz="UTC").isoformat(),
      "study":"sector_exposure_increment_v1",
      "production_changed":False,
      "data_storage":"research.sector_candidate_bars; not public.daily_bars",
      "data_quality":quality,
      "baseline":BASE,
      "research_assets":SECTORS,
      "method":"Frozen 26-bar weighted OLS, HL10, existing research liquidity/D2 filters; top1 close(t)->next open; 6bps each side; no C2/state-map/premium veto",
      "variants":results,
      "rebuilding_events":summary_events(features,list(SECTORS))
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({"status":"PASS","quality":quality,
        "metrics":{k:{"discovery":v["period_2021_2024"],
                      "validation":v["period_2025_2026"],
                      "sector_top1_signal_days":v.get("sector_top1_signal_days",0)}
                   for k,v in results.items()}},ensure_ascii=False))

if __name__=="__main__":
    main()
