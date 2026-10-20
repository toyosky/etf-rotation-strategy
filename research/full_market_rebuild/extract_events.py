#!/usr/bin/env python3
"""Research-only, point-in-time rebuild event extraction; never places orders."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import numpy as np
import pandas as pd
from automation.build_fundamental_audit_trigger import calc_ols, db_url

COLS=["symbol","date","open","high","low","close","volume","amount"]
HORIZONS=[5,10,20,40]

def load(args):
    if args.input:
        paths=sorted(Path().glob(args.input)) if "*" in args.input else [Path(args.input)]
        if not paths: raise RuntimeError("No input files matched")
        frames=[pd.read_parquet(p) if p.suffix==".parquet" else pd.read_csv(p) for p in paths]
        df=pd.concat(frames,ignore_index=True)
        origin="files:"+",".join(str(p) for p in paths)
    else:
        from sqlalchemy import create_engine, text
        raw=os.getenv("ETF_DAILY_BARS_DATABASE_URL")
        if not raw: raise RuntimeError("Provide --input or ETF_DAILY_BARS_DATABASE_URL")
        eng=create_engine(db_url(raw))
        with eng.connect() as con:
            df=pd.read_sql_query(text("select symbol,date,open,high,low,close,volume,amount from public.daily_bars order by symbol,date"),con)
        origin="public.daily_bars (current small live pool, NOT full market)"
    missing=set(COLS)-set(df)
    if missing: raise RuntimeError("Missing columns: "+str(sorted(missing)))
    df=df[COLS].copy()
    df["symbol"]=df.symbol.astype(str).str.zfill(6)
    df["date"]=pd.to_datetime(df.date,errors="raise").dt.normalize()
    for c in COLS[2:]: df[c]=pd.to_numeric(df[c],errors="coerce")
    if df.duplicated(["symbol","date"]).any():raise RuntimeError("Duplicate symbol/date bars")
    if df[["open","close"]].isna().any().any() or (df[["open","close"]]<=0).any().any():raise RuntimeError("Invalid OHLC")
    return df.sort_values(["symbol","date"]).reset_index(drop=True),origin

def events_one(g):
    g=g.sort_values("date").reset_index(drop=True).copy()
    if len(g)<30:return []
    annual,r2=calc_ols(g.close.to_numpy(float))
    crosses=np.flatnonzero((np.r_[False,annual[:-1]<=0]) & (annual>0))
    dr2=np.diff(r2,prepend=np.nan)
    rows=[]
    for i in crosses:
        for j in range(i+1,min(i+4,len(g))):
            if annual[j]>0 and dr2[j]>0 and r2[j]>r2[i]:
                rec={"symbol":g.at[j,"symbol"],"cross_date":str(g.at[i,"date"].date()),
                     "signal_date":str(g.at[j,"date"].date()),"cross_age":int(j-i),
                     "annual":float(annual[j]),"r2":float(r2[j]),
                     "r2_at_cross":float(r2[i]),"bars_seen":int(j+1)}
                # A close-of-day signal is executable only on the subsequent open.
                entry=j+1
                rec["entry_date"]=str(g.at[entry,"date"].date()) if entry<len(g) else None
                rec["entry_open"]=float(g.at[entry,"open"]) if entry<len(g) else None
                for h in HORIZONS:
                    end=j+h
                    rec[f"return_{h}d"]=float(g.at[end,"close"]/g.at[entry,"open"]-1) if entry<len(g) and end<len(g) else None
                rows.append(rec)
                break
    return rows

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--input",help="CSV/Parquet or glob, optional; default: Supabase small pool")
    a.add_argument("--out",default="research/full_market_rebuild/output")
    a.add_argument("--min-symbols",type=int,default=1)
    args=a.parse_args()
    frame,source=load(args)
    # 511220 is a cash/bond parking proxy, not a risk-asset rebuilding candidate.
    # Long exact-price plateaus cause floating-point-sensitive annual-zero crossings.
    # Exclusion is a pre-specified research-universe rule, NOT an OLS formula change.
    excluded_symbols = ["511220"]
    frame = frame.loc[~frame.symbol.isin(excluded_symbols)].copy()
    symbols=int(frame.symbol.nunique())
    if symbols<args.min_symbols:raise RuntimeError(f"Insufficient universe: {symbols} < {args.min_symbols}")
    records=[]
    for _,g in frame.groupby("symbol",sort=True):records.extend(events_one(g))
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    event_df=pd.DataFrame(records)
    csv=out/"events.csv"
    event_df.to_csv(csv,index=False)
    years={}
    if not event_df.empty:
        years={str(k):int(v) for k,v in event_df.signal_date.str[:4].value_counts().sort_index().items()}
    meta={"status":"research_only","universe_is_full_market":False if not args.input else None,
          "source":source,"universe_excluded_symbols":excluded_symbols,"symbols":symbols,"bars":int(len(frame)),
          "first_date":str(frame.date.min().date()),"last_date":str(frame.date.max().date()),
          "unique_events":len(records),"events_by_year":years,
          "signal":"frozen weighted-OLS26 half-life10; annual crosses 0; first R2 improving day 1..3",
          "trade":"next available ETF trading day open; raw next-open to forward close, no transaction costs",
          "pit_caveats":["current metadata not historical constituent list",
                         "no delisted-universe completeness verification",
                         "corporate actions/forward adjustment as-of source must be verified",
                         "premium and trading frictions not modeled"],
          "files":{"events.csv":{"sha256":hashlib.sha256(csv.read_bytes()).hexdigest(),"rows":len(records)}}}
    (out/"manifest.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(meta,ensure_ascii=False))
if __name__=="__main__":main()
