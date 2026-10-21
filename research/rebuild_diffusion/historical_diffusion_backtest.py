#!/usr/bin/env python3
"""PIT-style daily replay: sector R2-rebuild onset -> diffusion -> forward returns.

Research only. Does not trade, modify strategy thresholds, or use ex-post
diffusion to select the initial ETF. Classification metadata is CURRENT and
creates survivorship/taxonomy bias; results are exploratory, not audited OOS.
"""
import argparse
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from automation.build_fundamental_audit_trigger import calc_ols, db_url
from automation.build_category_audit_scope import classify, CATEGORY_INFO

CATEGORIES = set(CATEGORY_INFO)
EPS = 1e-8
MIN_HISTORY = 200
BROAD_AMOUNT60 = 3_000_000
STRICT_AMOUNT60 = 20_000_000
CORRELATION_THRESHOLD = 0.995
HORIZONS = (5, 10, 20)


def safe_float(v):
    return float(v) if v is not None and np.isfinite(v) else None


def metrics(values):
    a = np.asarray([float(x) for x in values if x is not None and math.isfinite(float(x))])
    if not len(a):
        return {"n": 0, "mean_pct": None, "median_pct": None, "positive_pct": None,
                "p10_pct": None, "p90_pct": None, "mean_ci95_pct": None}
    rng = np.random.default_rng(12345)
    ci = None
    if len(a) >= 10:
        idx = rng.integers(0, len(a), size=(1500, len(a)))
        ci = list(np.round(np.percentile(a[idx].mean(axis=1), [2.5, 97.5]) * 100, 3))
    return {"n": len(a), "mean_pct": round(float(a.mean()*100), 3),
            "median_pct": round(float(np.median(a)*100), 3),
            "positive_pct": round(float((a > 0).mean()*100), 1),
            "p10_pct": round(float(np.quantile(a, .10)*100), 3),
            "p90_pct": round(float(np.quantile(a, .90)*100), 3),
            "mean_ci95_pct": ci}


def fetch_metadata(symbols, eng):
    with eng.connect() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT ON (symbol) symbol,name,product_type,region_primary,
                exposure_level1,exposure_level2,underlying_key,risk_bucket,
                confidence,needs_review
            FROM public.instrument_metadata
            WHERE symbol = ANY(:symbols)
            ORDER BY symbol, updated_at DESC NULLS LAST
        """), {"symbols": list(symbols)}).mappings().all()
    return {str(r["symbol"]): dict(r) for r in rows}


def build_series(raw, metadata):
    """Reconstruct all DAILY qualifications; no use of future R2 values."""
    qualifications = defaultdict(list)
    price = {}
    categories = defaultdict(set)
    exclusion = defaultdict(int)
    for sym, g in raw.groupby("symbol", sort=False):
        sym = str(sym).zfill(6)
        m = metadata.get(sym)
        if not m:
            exclusion["missing_metadata"] += 1
            continue
        category = classify(sym, m.get("name"), m)["key"]
        if category not in CATEGORIES:
            exclusion["unclassified_or_unknown_category"] += 1
            continue
        g = g.drop_duplicates("date", keep="last").sort_values("date").copy()
        g["close"] = pd.to_numeric(g["close"], errors="coerce")
        g["open"] = pd.to_numeric(g["open"], errors="coerce")
        g["amount"] = pd.to_numeric(g["amount"], errors="coerce").fillna(0)
        g = g[g["close"].gt(0) & g["open"].gt(0)]
        if len(g) < MIN_HISTORY:
            exclusion["short_history"] += 1
            continue
        close = g["close"].to_numpy(dtype=float)
        with np.errstate(all="ignore"):
            annual, r2 = calc_ols(close)
        ix = np.arange(len(g))
        crossing = (annual > EPS) & (np.r_[np.nan, annual[:-1]] <= EPS)
        cross_ix = np.maximum.accumulate(np.where(crossing, ix, -1000000))
        ages = ix - cross_ix
        cross_r2 = r2[np.maximum(cross_ix, 0)]
        delta_r2 = r2 - np.r_[np.nan, r2[:-1]]
        qualified = ((ages >= 1) & (ages <= 3)
                     & (annual > EPS) & (delta_r2 > 1e-12)
                     & (r2 > cross_r2 + 1e-12)
                     & (ix >= MIN_HISTORY - 1))
        amount60 = g["amount"].rolling(60, min_periods=60).mean().to_numpy()
        liquid = amount60 >= BROAD_AMOUNT60
        dates = pd.to_datetime(g["date"]).dt.strftime("%Y-%m-%d").to_numpy()
        open_ = g["open"].to_numpy()
        point = pd.DataFrame({"date": dates, "open": open_, "close": close,
                              "amount60": amount60}).set_index("date")
        price[sym] = point
        categories[category].add(sym)
        for t in np.flatnonzero(qualified & liquid):
            qualifications[(category, dates[t])].append({
                "symbol": sym, "amount60": safe_float(amount60[t]),
                "r2": safe_float(r2[t]), "annual": safe_float(annual[t]),
                "strict_amount": bool(amount60[t] >= STRICT_AMOUNT60),
                "cross_date": str(dates[cross_ix[t]])})
    return qualifications, price, categories, exclusion


def corr_clusters(members, date, prices):
    """Trailing-only price correlation de-duplicates near-identical ETF returns."""
    symbols = sorted(set(x["symbol"] for x in members))
    if len(symbols) <= 1:
        return len(symbols)
    recent = []
    for sym in symbols:
        p = prices[sym].loc[:date, "close"].tail(62)
        v = p.pct_change().dropna().tail(60).rename(sym)
        recent.append(v)
    frame = pd.concat(recent, axis=1)
    corr = frame.corr(min_periods=40)
    roots = []
    for sym in symbols:
        if not any(pd.notna(corr.loc[sym, root]) and
                   corr.loc[sym, root] >= CORRELATION_THRESHOLD for root in roots):
            roots.append(sym)
    return len(roots)


def price_return(price, sym, entry_date, exit_date):
    p = price.get(sym)
    if p is None or entry_date not in p.index or exit_date not in p.index:
        return None
    enter, out = float(p.at[entry_date, "open"]), float(p.at[exit_date, "close"])
    return out/enter - 1.0 if enter > 0 else None


def replay(qualifications, prices, categories, calendar, start="2021-01-01", cooldown=10):
    trading_days = [str(d) for d in calendar]
    day_index = {d:i for i,d in enumerate(trading_days)}
    grouped = defaultdict(dict)
    for (cat,day), members in qualifications.items():
        if day in day_index:
            grouped[cat][day] = members

    events = []
    for cat, daily in sorted(grouped.items()):
        onset_last = -10000
        last_active = -10000
        for day in trading_days:
            members = daily.get(day, [])
            if not members:
                continue
            t=day_index[day]
            if day < start:
                last_active=t
                continue
            # Episode begins only if no broad-liquid qualification in prior
            # 'cooldown' market sessions; no future rows examined.
            if t-last_active <= cooldown:
                last_active=t
                continue
            last_active=t
            onset_last=t
            first = sorted(members, key=lambda x:(-float(x["amount60"]),x["symbol"]))
            lead=first[0]["symbol"]
            if t+21 >= len(trading_days):
                mature20=False
            else:
                mature20=True
            item={"category":cat,"onset_date":day,"leader_symbol":lead,
                  "leader_onset_r2":first[0]["r2"],
                  "leader_amount60":first[0]["amount60"],
                  "leader_strict_amount":first[0]["strict_amount"],
                  "leaders_onset_n":len(members),
                  "leaders_onset_corr_clusters":corr_clusters(members,day,prices),
                  "lookahead_20_complete":mature20}
            # Daily breadth can be observed ONLY at the close of the date.
            item["daily_breadth"]=[]
            for shift in range(0,6):
                if t+shift >= len(trading_days):
                    break
                d=trading_days[t+shift]
                m=daily.get(d,[])
                item["daily_breadth"].append({"day":d,"age":shift,
                    "n_etfs":len(m),"n_clusters":corr_clusters(m,d,prices)})
            for threshold in (2,3):
                for definition,key in (("n_etfs","etf"),("n_clusters","independent")):
                    confirm=next((r for r in item["daily_breadth"]
                                  if r[definition]>=threshold),None)
                    item[f"confirm_{key}_{threshold}_date"]=confirm["day"] if confirm else None
                    item[f"confirm_{key}_{threshold}_lag"]=confirm["age"] if confirm else None
            if t+1<len(trading_days):
                entry=trading_days[t+1]
                item["entry_date"]=entry
                for horizon in HORIZONS:
                    exit_idx=t+horizon
                    e=trading_days[exit_idx] if exit_idx<len(trading_days) else None
                    item[f"early_return_{horizon}"]=(
                        price_return(prices,lead,entry,e) if e else None)
                    if e and lead in prices and entry in prices[lead].index:
                        trail=prices[lead].loc[entry:e,"close"].to_numpy()
                        enter=float(prices[lead].at[entry,"open"])
                        if len(trail):
                            equity=np.r_[enter, trail]
                            peak=np.maximum.accumulate(equity)
                            item[f"early_mdd_{horizon}"]=float((equity/peak-1).min())
                        else:
                            item[f"early_mdd_{horizon}"]=None
                    else:
                        item[f"early_mdd_{horizon}"]=None
                    for threshold in (2,3):
                        for key in ("etf","independent"):
                            confirm_day=item[f"confirm_{key}_{threshold}_date"]
                            if confirm_day is None or day_index[confirm_day]+1>=len(trading_days) or not e:
                                value=None
                            else:
                                follow_entry=trading_days[day_index[confirm_day]+1]
                                value=(price_return(prices,lead,follow_entry,e)
                                       if day_index[confirm_day]+1<=exit_idx else None)
                            item[f"wait_{key}_{threshold}_return_{horizon}"]=value
            events.append(item)
    return events


def summarize(events, start, end):
    samples=[x for x in events if start<=x["onset_date"]<=end]
    result={"episode_count":len(samples),"by_category":{},
            "horizons":{},"diffusion":{},"year_counts":{}}
    for x in samples:
        year=x["onset_date"][:4]
        result["year_counts"][year]=result["year_counts"].get(year,0)+1
    for h in HORIZONS:
        result["horizons"][str(h)]={
            "early":metrics([x.get(f"early_return_{h}") for x in samples]),
            "early_mdd":metrics([x.get(f"early_mdd_{h}") for x in samples]),
        }
        for mode in ("etf","independent"):
            for threshold in (2,3):
                result["horizons"][str(h)][f"wait_{mode}_{threshold}"]=metrics(
                    [x.get(f"wait_{mode}_{threshold}_return_{h}") for x in samples])
                same=[(x.get(f"early_return_{h}"),x.get(f"wait_{mode}_{threshold}_return_{h}"))
                       for x in samples]
                result["horizons"][str(h)][f"early_minus_wait_{mode}_{threshold}"]=metrics(
                    [a-b for a,b in same if a is not None and b is not None])
    for mode in ("etf","independent"):
        for threshold in (2,3):
            lags=[x.get(f"confirm_{mode}_{threshold}_lag") for x in samples]
            d=[v for v in lags if v is not None]
            result["diffusion"][f"{mode}_{threshold}"]={
                "confirmed_within_5_days":len(d),"episodes":len(samples),
                "rate_pct":round(100*len(d)/len(samples),1) if samples else None,
                "median_confirm_lag_sessions":float(np.median(d)) if d else None}
    for cat in sorted(set(x["category"] for x in samples)):
        ex=[x for x in samples if x["category"]==cat]
        result["by_category"][cat]={
            "events":len(ex),"year_counts":{y:sum(a["onset_date"].startswith(y) for a in ex)
                                            for y in sorted(set(a["onset_date"][:4] for a in ex))},
            "next5":metrics([a.get("early_return_5") for a in ex]),
            "next10":metrics([a.get("early_return_10") for a in ex]),
            "next20":metrics([a.get("early_return_20") for a in ex]),
            "two_independent_within5":sum(a.get("confirm_independent_2_lag") is not None for a in ex),
            "two_etf_within5":sum(a.get("confirm_etf_2_lag") is not None for a in ex)}
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--parquet",required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--start",default="2021-01-01")
    ap.add_argument("--end",default="2026-09-30")
    ap.add_argument("--cooldown",type=int,default=10)
    args=ap.parse_args()
    raw=pd.read_parquet(args.parquet)
    required={"symbol","date","open","close","amount"}
    if not required.issubset(raw.columns):
        raise RuntimeError("Missing historical market columns "+str(required-set(raw.columns)))
    raw=raw[list(required)].copy()
    raw["symbol"]=raw.symbol.astype(str).str.zfill(6)
    raw["date"]=pd.to_datetime(raw.date)
    raw=raw[raw.date<=pd.Timestamp("2026-10-20")].copy()
    calendar=sorted(raw.loc[(raw.date>="2015-01-01") & (raw.date<="2026-10-21"),"date"].dt.strftime("%Y-%m-%d").unique())
    db=os.environ.get("ETF_DAILY_BARS_DATABASE_URL","")
    if not db:
        raise RuntimeError("Metadata read requires ETF_DAILY_BARS_DATABASE_URL")
    eng=create_engine(db_url(db),pool_pre_ping=True,connect_args={"connect_timeout":15})
    meta=fetch_metadata(raw.symbol.unique(),eng)
    qualifications,prices,groups,exclusion=build_series(raw,meta)
    events=replay(qualifications,prices,groups,calendar,start=args.start,cooldown=args.cooldown)
    result={
        "version":"onset-diffusion-replay-v1",
        "market_data_as_of":"2026-10-20",
        "population_start":args.start,
        "population_end":args.end,
        "source":"GitHub private research-data-fullmarket-current refreshed_daily_bars.parquet",
        "signal":"26-day weighted log-OLS annual crossing + next1-3 sessions R2 improvement, recomputed daily",
        "market_sample":"current-listed metadata (survivorship bias); history >=200 bars; avg amount60 >=3m",
        "entry":"next market session OPEN after first within-category qualifying ETF",
        "wait":"same initial leader bought at next session OPEN after >=2 or >=3 concurrent qualifying ETFs / trailing-corr clusters; next5/10/20 results measured from same onset exit date",
        "clusters":"greedy ETF trailing60-return corr >=.995 treated same; no future returns in cluster definition",
        "fixed_return_horizon":"T+5/10/20 close from category onset date",
        "cooldown_sessions":args.cooldown,
        "major_limitations":[
            "Current-listing and current metadata create survivor/sector reclassification bias",
            "No fundamental news audit or historical Premium10, so NOT directly executable",
            "HFQ adjusted vintage may differ from original decision-day quote",
            "Alternative category granularity and same-index clustering change breadth",
            "ETF entry may be unable to execute at exact opening price; no fees/slippage",
            "Category signal detection uses historical bars through that date only",
        ],
        "data_quality":{
            "snapshot_rows":len(raw),"snapshot_symbols":int(raw.symbol.nunique()),
            "metadata_symbols":len(meta),
            "included_symbols":len(prices),"categories_with_symbols":len(groups),
            "dated_qualified_rows":sum(len(v) for v in qualifications.values()),
            "category_count":len(set(k[0] for k in qualifications)),
            "exclusions":dict(exclusion)},
        "summary":summarize(events,args.start,args.end),
        "events":[x for x in events if args.start<=x["onset_date"]<=args.end]
    }
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False,default=str),encoding="utf-8")
    print(json.dumps({"status":"OK","episode_count":result["summary"]["episode_count"],
                     "year_counts":result["summary"]["year_counts"],
                     "data_quality":result["data_quality"],
                     "horizons":result["summary"]["horizons"],
                     "diffusion":result["summary"]["diffusion"]},ensure_ascii=False))


if __name__=="__main__":
    main()
