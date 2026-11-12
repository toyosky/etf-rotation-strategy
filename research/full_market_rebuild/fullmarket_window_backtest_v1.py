#!/usr/bin/env python3
"""Research-only multi-window ETF rebuilding audit on frozen full-market parquet.

No production/holding/scheduler writes.  No future data used to construct signals.
Historical universe is the snapshot's known surviving instruments, NOT a complete
delisted-ETF census. Current underlying_key is used only for post-hoc robustness.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd

WINDOWS = (10, 15, 20, 26)
HALF_LIFE = 10.0
COST_SIDE = 0.0006
COOLDOWN = 20
HORIZONS = (5, 10, 20)
START = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")
MIN_AMOUNT_60 = 3_000_000
EXCLUDED_SYMBOLS = {"159005"}  # known cash-management fund


def ols_arrays(close: np.ndarray, length: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(close)
    slope = np.full(n, np.nan)
    r2 = np.full(n, np.nan)
    if n < length:
        return slope, r2
    y = np.log(close)
    window = np.lib.stride_tricks.sliding_window_view(y, length)
    x = np.arange(length, dtype=float)
    w = np.power(0.5, 2.0 * (length - 1 - x) / HALF_LIFE)
    sw = w.sum()
    swx = np.dot(w, x)
    swxx = np.dot(w, x * x)
    den = sw * swxx - swx * swx
    wy = window @ w
    wxy = window @ (w * x)
    b = (sw * wxy - swx * wy) / den
    a = (wy - b * swx) / sw
    fitted = a[:, None] + b[:, None] * x
    sse = np.sum(w[None, :] * np.square(window - fitted), axis=1)
    sst = np.sum(w[None, :] * np.square(window - (wy / sw)[:, None]), axis=1)
    fit_r2 = np.clip(np.divide(sst - sse, sst, out=np.zeros_like(sst), where=sst > 1e-15), 0, 1)
    slope[length-1:] = b
    r2[length-1:] = fit_r2
    return slope, r2


def load_metadata() -> pd.DataFrame:
    url = os.getenv("ETF_DAILY_BARS_DATABASE_URL", "").strip()
    if not url:
        return pd.DataFrame()
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as cn:
            data = pd.read_sql_query(text("""
                SELECT symbol, name, underlying_key, historical_safe,
                       valid_from, leveraged_flag, inverse_flag,
                       product_type, asset_class
                FROM public.instrument_metadata
            """), cn)
    finally:
        engine.dispose()
    data["symbol"] = data["symbol"].astype(str).str.zfill(6)
    return data.drop_duplicates("symbol").set_index("symbol")


def statistics(rows: pd.DataFrame) -> dict:
    if rows.empty:
        return {"n": 0}
    r = rows["net"].to_numpy(dtype=float)
    return {
        "n": int(len(rows)),
        "mean_pct": round(float(r.mean()*100), 4),
        "median_pct": round(float(np.median(r)*100), 4),
        "win_pct": round(float((r>0).mean()*100), 2),
        "p10_pct": round(float(np.quantile(r, .1)*100), 3),
        "mae_mean_pct": round(float(rows["mae"].mean()*100), 3),
        "mfe_mean_pct": round(float(rows["mfe"].mean()*100), 3),
        "mean_amount60_m": round(float(rows["amount60"].mean()/1e6), 3),
        "symbols": int(rows["symbol"].nunique())
    }


def bootstrap_monthly(subset: pd.DataFrame, a: str, b: str, n_rep: int = 1200) -> dict:
    s = subset.loc[subset["variant"].isin((a, b))].copy()
    if s.empty:
        return {}
    s["month"] = s["signal_date"].dt.strftime("%Y-%m")
    months = sorted(s["month"].unique())
    grouped = s.groupby(["month","variant"])["net"].agg(["sum","count"])
    agg = np.zeros((len(months),2,2), dtype=float)
    for i,month in enumerate(months):
        for j,variant in enumerate((a,b)):
            if (month,variant) in grouped.index:
                t = grouped.loc[(month,variant)]
                agg[i,j] = [float(t["sum"]),float(t["count"])]
    rng = np.random.default_rng(20261112)
    out = []
    for _ in range(n_rep):
        idx = rng.integers(0,len(months),len(months))
        z = agg[idx].sum(axis=0)
        if (z[:,1] > 0).all():
            out.append(100*(z[0,0]/z[0,1]-z[1,0]/z[1,1]))
    return {
        "months": len(months), "replicates": len(out),
        "diff_mean_pp": round(float(100*(s.loc[s.variant==a,"net"].mean()-s.loc[s.variant==b,"net"].mean())),4),
        "ci95_pp": [round(float(v),3) for v in np.quantile(out,[.025,.975])] if out else None
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--output", default="research/full_market_rebuild/window_comparison_fullmarket_v1.json")
    ap.add_argument("--markdown", default="research/full_market_rebuild/window_comparison_fullmarket_v1.md")
    ap.add_argument("--events", default="research/full_market_rebuild/window_comparison_fullmarket_v1_events.csv.gz")
    args = ap.parse_args()
    source = Path(args.parquet)
    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    bars = pd.read_parquet(source, columns=["symbol","date","open","high","low","close","amount"])
    bars["symbol"] = bars["symbol"].astype(str).str.zfill(6)
    bars["date"] = pd.to_datetime(bars["date"]).dt.normalize()
    for c in ("open","high","low","close","amount"):
        bars[c] = pd.to_numeric(bars[c], errors="coerce")
    original_rows = len(bars)
    original_symbols = bars.symbol.nunique()
    raw_duplicated = int(bars.duplicated(["symbol","date"]).sum())
    bars = bars.sort_values(["symbol","date"]).drop_duplicates(["symbol","date"],keep="last")
    bars = bars.loc[(bars["open"]>0)&(bars["high"]>0)&(bars["low"]>0)&(bars["close"]>0)&bars["amount"].notna()].copy()
    if len(bars)<500000 or bars.symbol.nunique()<1000:
        raise RuntimeError(f"Not whole-market: {len(bars)} rows, {bars.symbol.nunique()} symbols")
    asof = bars.date.max()
    if asof<pd.Timestamp("2026-11-01"):
        raise RuntimeError(f"Stale full-market Release: max date {asof}")
    expected_file = Path("data/full-market-rebuild-latest.json")
    expected = json.loads(expected_file.read_text()) if expected_file.exists() else {}
    sha_matches = (expected.get("sha256_snapshot")==sha256) if expected.get("sha256_snapshot") else None
    if sha_matches is False:
        raise RuntimeError("Latest snapshot checksum mismatch vs GitHub manifest")
    meta = load_metadata()
    if meta.empty:
        raise RuntimeError("Cannot load ETF metadata; universe eligibility unverified")
    fast = {}
    counts = {"symbols_source":int(original_symbols),"rows_source":int(original_rows),
              "duplicates":raw_duplicated,"rows_valid":int(len(bars)),
              "symbols_valid":int(bars.symbol.nunique()),"first_date":str(bars.date.min().date()),
              "last_date":str(asof.date()),"snapshot_sha256":sha256,
              "metadata_symbols":int(len(meta)), "snapshot_sha256_matches":sha_matches,
              "missing_meta_symbols":int(sum(~pd.Index(bars.symbol.unique().astype(str)).isin(meta.index)))}
    skipped = defaultdict(int)
    signals = []
    horizon_rows = []
    details = {}
    for no, (symbol, g) in enumerate(bars.groupby("symbol",sort=True),1):
        if symbol in EXCLUDED_SYMBOLS:
            skipped["cash-management"] += 1
            continue
        if symbol in meta.index:
            m = meta.loc[symbol]
            if bool(m["leveraged_flag"]) or bool(m["inverse_flag"]):
                skipped["leveraged_inverse"] += 1
                continue
            if str(m["product_type"]) not in ("ETF","LOF"):
                skipped["not_etf_lof"] += 1
                continue
            if str(m["asset_class"]).upper()=="CASHLIKE":
                skipped["cashlike_metadata"] += 1
                continue
            underlying = str(m["underlying_key"]) if pd.notna(m["underlying_key"]) else None
            historical_safe = bool(m["historical_safe"])
            valid_from = str(m["valid_from"]) if pd.notna(m["valid_from"]) else None
        else:
            underlying = None
            historical_safe = False
            valid_from = None
        g = g.sort_values("date")
        if len(g)<50:
            skipped["short_history"] += 1
            continue
        date = g.date.to_numpy()
        first_valid = date.searchsorted(np.datetime64(START))
        close = g.close.to_numpy(float)
        opn = g.open.to_numpy(float)
        lo = g.low.to_numpy(float)
        hi = g.high.to_numpy(float)
        amount = g.amount.to_numpy(float)
        r1 = np.r_[np.nan, close[1:]/close[:-1]-1]
        am60 = pd.Series(amount).rolling(60,min_periods=60).mean().to_numpy()
        result = {w:ols_arrays(close,w) for w in WINDOWS}
        s26 = result[26][0]
        count_per_symbol = 0
        for w in WINDOWS:
            slope,r2 = result[w]
            crossings = np.flatnonzero((slope[1:]>0)&(slope[:-1]<=0))+1
            last_qualified = -10000
            for start in crossings:
                if start<first_valid or start+2>=len(g):
                    continue
                q = None
                for ix in range(start+1,min(start+4,len(g))):
                    if (np.isfinite(r2[ix-1]) and slope[ix]>0
                            and r2[ix]>r2[ix-1] and r2[ix]>r2[start]):
                        q=ix
                        break
                if q is None or q-last_qualified<COOLDOWN:
                    continue
                last_qualified=q
                if q+1>=len(g):
                    continue
                if not np.isfinite(am60[q]):
                    continue
                guard_d2 = bool(np.all(r1[max(1,q-2):q+1]>=-0.03))
                hybrid = bool(w==15 and np.isfinite(s26[q-3]) and
                              np.isfinite(s26[q]) and s26[q]<=0 and s26[q]>s26[q-3])
                live_ok = bool(am60[q]>=MIN_AMOUNT_60 and np.all(amount[max(0,q-9):q+1]>0) and guard_d2)
                common = {
                    "symbol":symbol, "window":w, "signal_date":pd.Timestamp(date[q]),
                    "cross_date":pd.Timestamp(date[start]), "signal_i":int(q),
                    "qual_age":int(q-start), "hybrid":hybrid, "d2_pass":guard_d2,
                    "tradeable":live_ok, "amount60":float(am60[q]),
                    "underlying_key": underlying, "historical_safe":historical_safe,
                    "underlying_valid_from": valid_from, "slope_at_signal":float(slope[q]),
                    "r2_at_signal":float(r2[q]),"r2_at_cross":float(r2[start])
                }
                signals.append({k:v for k,v in common.items() if k not in ("amount60",)})
                entry=q+1
                for h in HORIZONS:
                    end=entry+h
                    if end>=len(g):continue
                    if not (np.isfinite(opn[entry]) and np.isfinite(opn[end]) and opn[entry]>0 and opn[end]>0):continue
                    net=float((opn[end]/opn[entry])*(1-COST_SIDE)**2-1)
                    interval = slice(entry,end)  # end open: do not include end-day high/low
                    adverse=float(lo[interval].min()/opn[entry]-1)
                    favorable=float(hi[interval].max()/opn[entry]-1)
                    row = {
                        **common, "horizon":h, "entry_date":pd.Timestamp(date[entry]),
                        "exit_date":pd.Timestamp(date[end]),
                        "net":net, "mae":adverse, "mfe":favorable,
                        "variant":"OLS"+str(w)
                    }
                    horizon_rows.append(row)
                    if hybrid:
                        horizon_rows.append({**row,"variant":"HYBRID15_26"})
                count_per_symbol+=1
        details[symbol]=count_per_symbol
    if not horizon_rows: raise RuntimeError("No valid historical rebuilt events")
    ev = pd.DataFrame(horizon_rows)
    sig = pd.DataFrame(signals)
    ev["segment"] = np.where(ev.signal_date<SPLIT,"DISCOVERY_2021_2024","VALIDATION_2025_2026")
    ev["year"] = ev.signal_date.dt.year
    ev["month"] = ev.signal_date.dt.to_period("M").astype(str)
    # Current metadata is not point-in-time: use only as post-hoc dependence sensitivity.
    # Include unverified names as individual units to avoid claiming verified index identity.
    ev["proxy_key"] = np.where(ev.underlying_key.notna(),ev.underlying_key,ev.symbol)
    ev["proxy_key"] = ev["proxy_key"].astype(str)
    variants = [f"OLS{w}" for w in WINDOWS]+["HYBRID15_26"]
    results = []
    for segment in ("DISCOVERY_2021_2024","VALIDATION_2025_2026"):
        for horizon in HORIZONS:
            for variant in variants:
                base = ev.loc[(ev.segment==segment)&(ev.horizon==horizon)&(ev.variant==variant)]
                for filt in ("ALL_PRICE","TRADEABLE_D2_AMOUNT3M"):
                    b = base if filt=="ALL_PRICE" else base.loc[base.tradeable]
                    results.append({"segment":segment,"horizon":horizon,"variant":variant,
                        "filter":filt, **statistics(b)})
    by_year = []
    for year in sorted(ev.year.unique()):
        for variant in variants:
            r=ev.loc[(ev.year==year)&(ev.horizon==10)&(ev.variant==variant)]
            by_year.append({"year":int(year),"variant":variant,**statistics(r)})
    robust=[]
    for (segment, variant),grp in ev.loc[ev.horizon==10].groupby(["segment","variant"]):
        # Among simultaneous signals with identical current underlying label,
        # select highest prior-60-day traded amount as point-time representative.
        reduce = grp.sort_values(["amount60","symbol"],ascending=[False,True]).drop_duplicates(["signal_date","proxy_key"])
        robust.append({"segment":segment,"variant":variant,"raw":statistics(grp),
                       "current_label_grouped":statistics(reduce),
                       "dedup_proxy_warning":"Current underlying labels are not point-in-time; sensitivity only."})
    leads=[]
    # Count how frequently each early qualified signal receives a later qualified
    # 26-day signal on the SAME security within 30 observed trading sessions.
    signal_26 = sig.loc[sig.window==26]
    for symbol, ss in sig.groupby("symbol"):
        b26 = signal_26.loc[signal_26.symbol==symbol]
        if b26.empty: continue
        for x in ss.itertuples(index=False):
            if x.window==26:continue
            n = b26.loc[(b26.signal_date>=x.signal_date)&
                        (b26.signal_date<=x.signal_date+pd.Timedelta(days=50))]
            # Calendar bound only as first cut; exact per-symbol trading-day offset
            # requires dates from symbol bar rows, captured by event index.
            n = n.loc[(n.signal_i-x.signal_i>=0)&(n.signal_i-x.signal_i<=30)]
            found = len(n)>0
            lead=int((n.signal_i-x.signal_i).min()) if found else None
            leads.append({"window":int(x.window),"hybrid":bool(x.hybrid),"segment":
                          "DISCOVERY_2021_2024" if x.signal_date<SPLIT else "VALIDATION_2025_2026",
                          "lead":lead,"has26":bool(found)})
    lead_summary=[]
    if leads:
        lf=pd.DataFrame(leads)
        for seg in ("DISCOVERY_2021_2024","VALIDATION_2025_2026"):
            for w in (10,15,20):
                for name,mask in [("OLS"+str(w),lf.window==w)] + ([("HYBRID15_26",(lf.window==15)&lf.hybrid)] if w==15 else []):
                    t=lf.loc[(lf.segment==seg)&mask]
                    if len(t):
                        valid=t.loc[t.has26,"lead"].dropna()
                        lead_summary.append({"segment":seg,"variant":name,"events":int(len(t)),
                             "later_26_pct":round(float(t.has26.mean()*100),2),
                             "lead_median_sessions":float(valid.median()) if len(valid) else None,
                             "lead_mean_sessions":float(valid.mean()) if len(valid) else None})
    val=ev.loc[(ev.segment=="VALIDATION_2025_2026")&(ev.horizon==10)]
    ci={}
    for group_name,sub in [("all",val),("tradeable",val.loc[val.tradeable]),
                           ("exclude_seam_2026",val.loc[(val.signal_date<pd.Timestamp("2026-06-01"))|
                                                           (val.signal_date>pd.Timestamp("2026-09-01"))])]:
        ci[group_name] = {
            "hybrid_minus_26":bootstrap_monthly(sub,"HYBRID15_26","OLS26"),
            "hybrid_minus_15":bootstrap_monthly(sub,"HYBRID15_26","OLS15")
        }
    sensitivity=[]
    for name,sub in [("all",val),("tradeable",val.loc[val.tradeable]),
                     ("2025_only",val.loc[val.year==2025]),
                     ("2026_only",val.loc[val.year==2026]),
                     ("exclude_seam",val.loc[(val.signal_date<pd.Timestamp("2026-06-01"))|
                                             (val.signal_date>pd.Timestamp("2026-09-01"))]),
                     ("remove_duplicate_brazil",val.loc[val.symbol!="520870"])]:
        sensitivity.append({"cut":name,**{variant:statistics(sub.loc[sub.variant==variant])
                               for variant in variants}})
    payload = {
        "version":"full-market-multicycle-rebuild-v1",
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "production_changed":False, "data":counts,
        "definition":{
            "windows":WINDOWS,"half_life":HALF_LIFE,
            "signal":"annual OLS crosses nonpositive to positive, first D1-D3 improved R2, slope stays positive",
            "hybrid":"15-day qualified, 26-day slope<=0, positive 26-day 3-session slope delta",
            "entry":"next actual symbol trading-session OPEN",
            "exit":"open-to-open after 5, 10 or 20 symbol sessions, fixed horizon",
            "cost_per_side":COST_SIDE,"event_cooldown_sessions":COOLDOWN,
            "amount60_filter":MIN_AMOUNT_60,
            "tradeable_filter":"D2 no >3% daily fall, last 10 days traded amount>0, trailing 60-day mean amount>=3 million RMB",
            "no_intraday_or_premium_veto":True
        },
        "population":{"signal_events":int(len(sig)), "return_rows":int(len(ev)),
                      "event_symbols":int(sig.symbol.nunique()),"skipped_symbols":dict(skipped),
                      "historically_safe_symbol_labels":int(meta.historical_safe.fillna(False).sum())},
        "results":results,"by_year_10d":by_year,"robustness_current_label":robust,
        "lead_to_26":lead_summary,"validation_10d_sensitivity":sensitivity,
        "monthly_block_bootstrap":ci,
        "limitations":[
            "Snapshot source uses currently known instruments; incomplete delisted funds cause survivorship bias",
            "Most index labels are current snapshots, not historical PIT; dedup by current label is only a sensitivity",
            "Historical NAV premium, LOF tradability, intraday opening constraints and short-selling are not modeled",
            "OHLC adjusted-source splice is not independently checked for every symbol; 2026 June-Aug sensitivity included",
            "Event averages are not capital-weighted portfolio equity curves; strategies have different signal counts",
            "Calendar-trading-day overlap and simultaneous ETF correlation reduce effective independent sample size",
            "The source archive is an already-existing private GitHub Release; not a freshly fetched delisted census"
        ]
    }
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str,allow_nan=False))
    md=["# 全市场 ETF 多周期重建回测 · V1","",
       f"归档截止：{counts['last_date']}；{counts['symbols_valid']} 只；{counts['rows_valid']:,} 行。",
       f"原始资格事件：{len(sig):,}；用于固定持有期的回测记录：{len(ev):,}。","",
       "## 验证期 2025–2026","",
       "| 方案 | 5日平均净收益 | 10日平均净收益 | 20日平均净收益 | 10日事件数 | 10日胜率 |",
       "|---|---:|---:|---:|---:|---:|"]
    rr={(r["segment"],r["horizon"],r["variant"],r["filter"]):r for r in results}
    for variant in variants:
        v=[rr[("VALIDATION_2025_2026",h,variant,"ALL_PRICE")] for h in HORIZONS]
        md.append("| "+variant+" | "+" | ".join(f"{z.get('mean_pct',0):+.3f}%" for z in v)+
                  f" | {v[1]['n']} | {v[1].get('win_pct',0):.1f}% |")
    md+=["","## 2025–2026 10日收益筛选敏感性","",
           "| 方案 | 全样本 | 流动性+D2样本 |",
           "|---|---:|---:|"]
    for variant in variants:
        a=rr[("VALIDATION_2025_2026",10,variant,"ALL_PRICE")]
        b=rr[("VALIDATION_2025_2026",10,variant,"TRADEABLE_D2_AMOUNT3M")]
        md.append(f"| {variant} | {a.get('mean_pct',0):+.3f}% (n={a['n']}) | {b.get('mean_pct',0):+.3f}% (n={b['n']}) |")
    md+=["","## 领先26日信号","",
         json.dumps([x for x in lead_summary if x["segment"]=="VALIDATION_2025_2026"],ensure_ascii=False,indent=2),
         "","## 按月份区块重抽样区间（百分点）","",
         json.dumps(ci,ensure_ascii=False,indent=2),
         "","## 主要风险","",*["- "+x for x in payload["limitations"]]]
    report=Path(args.markdown);report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text("\n".join(md))
    events_path=Path(args.events);events_path.parent.mkdir(parents=True,exist_ok=True)
    ev.drop(columns=["proxy_key"]).to_csv(events_path,index=False,compression="gzip")
    print("AUDIT_COMPLETE "+json.dumps({
        "asof":counts["last_date"],"symbols":counts["symbols_valid"],
        "rows":counts["rows_valid"],"events":len(sig),
        "validation_10d":[x for x in results if x["segment"]=="VALIDATION_2025_2026"
                          and x["horizon"]==10 and x["filter"]=="ALL_PRICE"],
        "leading_validation":[x for x in lead_summary if x["segment"]=="VALIDATION_2025_2026"],
        "report":str(out)
    },ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
