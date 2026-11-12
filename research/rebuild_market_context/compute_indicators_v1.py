#!/usr/bin/env python3
"""Three pre-trade ETF rebuilding context signals; research-only, PIT prices.

Inputs: frozen GitHub Release parquet + current Supabase ETF taxonomy.
Current underlying/style taxonomy is NOT historically PIT; historical study is
descriptive pending archived taxonomy. Price features use only dates <= signal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

WINDOW = 15
HALF_LIFE = 10.0
FIRST_DATE = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")
MIN_HISTORY = 200
MIN_AMOUNT = 3_000_000.0
COOLDOWN = 20
COST_SIDE = 0.0006
REGIONS = ("ALL", "CN", "HK", "US")
GENERIC_KEYS = {"CHINA_EQUITY_OTHER", "OTHER", "UNKNOWN", ""}
EXCLUDED_SECTORS = {"CASH", "CASHLIKE"}


def weighted_ols(close: np.ndarray, n: int = WINDOW) -> tuple[np.ndarray,np.ndarray]:
    k = len(close)
    slope = np.full(k, np.nan, dtype=float)
    r2 = np.full(k, np.nan, dtype=float)
    if k < n:
        return slope, r2
    windows = np.lib.stride_tricks.sliding_window_view(np.log(close), n)
    x = np.arange(n, dtype=float)
    w = 0.5 ** (2 * (n - 1 - x) / HALF_LIFE)
    sw = w.sum()
    wx = (w*x).sum()
    wxx = (w*x*x).sum()
    den = sw*wxx - wx*wx
    wy = windows @ w
    wxy = windows @ (w*x)
    b = (sw*wxy - wx*wy) / den
    a = (wy-b*wx)/sw
    residuals = windows - (a[:,None]+b[:,None]*x[None,:])
    variance = windows - wy[:,None]/sw
    sse = (residuals**2) @ w
    sst = (variance**2) @ w
    slope[n-1:] = b
    r2[n-1:] = np.where(sst>1e-14, np.clip(1-sse/np.maximum(sst,1e-14),0,1),0)
    return slope,r2


def metadata(db_url: str) -> pd.DataFrame:
    if not db_url: raise RuntimeError("Missing ETF_DAILY_BARS_DATABASE_URL (metadata read only)")
    if db_url.startswith("postgres://"):
        db_url="postgresql://"+db_url[len("postgres://"):]
    if db_url.startswith("postgresql://"):
        db_url="postgresql+psycopg2://"+db_url[len("postgresql://"):]
    from sqlalchemy import create_engine, text
    eng=create_engine(db_url,pool_pre_ping=True)
    try:
        with eng.connect() as cx:
            df=pd.read_sql_query(text("""
              SELECT symbol,name,underlying_key,style_sector,region_primary,asset_class,
                     leveraged_flag,inverse_flag,product_type,valid_from,historical_safe
              FROM public.instrument_metadata
            """),cx)
    finally:
        eng.dispose()
    df["symbol"]=df.symbol.astype(str).str.zfill(6)
    return df.sort_values("symbol").drop_duplicates("symbol",keep="last").set_index("symbol")


def prepare(source: Path, meta: pd.DataFrame) -> tuple[pd.DataFrame,dict]:
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    raw=pd.read_parquet(source,columns=["symbol","date","open","high","low","close","amount"])
    original_n=int(len(raw))
    raw["symbol"]=raw.symbol.astype(str).str.zfill(6)
    raw["date"]=pd.to_datetime(raw.date).dt.normalize()
    duplicates=int(raw.duplicated(["symbol","date"]).sum())
    raw=raw.sort_values(["symbol","date"]).drop_duplicates(["symbol","date"],keep="last")
    for col in ["open","high","low","close","amount"]:
        raw[col]=pd.to_numeric(raw[col],errors="coerce")
    raw=raw.loc[(raw[["open","high","low","close"]]>0).all(axis=1)&raw.amount.notna()].copy()
    if raw.symbol.nunique()<1000 or len(raw)<500000:
        raise RuntimeError("This is not an all-market daily archive")
    manifest=Path("data/full-market-rebuild-latest.json")
    expected=json.loads(manifest.read_text()) if manifest.exists() else {}
    if expected.get("sha256_snapshot") and sha!=expected["sha256_snapshot"]:
        raise RuntimeError("Frozen market snapshot hash mismatches latest manifest")
    if raw.date.max()<pd.Timestamp("2026-11-01"):
        raise RuntimeError("Archive is stale")
    info={"original_rows":original_n,"valid_rows":int(len(raw)),
          "raw_symbols":int(raw.symbol.nunique()),"duplicates":duplicates,
          "as_of":str(raw.date.max().date()),"sha256":sha,
          "current_metadata_count":len(meta)}
    return raw,info


def calc_symbol(symbol: str, g: pd.DataFrame, m: pd.Series) -> tuple[pd.DataFrame,list[dict]]:
    g=g.sort_values("date").reset_index(drop=True)
    n=len(g)
    if n<MIN_HISTORY+11:
        return pd.DataFrame(),[]
    d=g.date.to_numpy()
    c=g.close.to_numpy(float)
    op=g.open.to_numpy(float)
    amt=g.amount.to_numpy(float)
    slope,r2=weighted_ols(c)
    amt60=pd.Series(amt).rolling(60,min_periods=60).mean().to_numpy()
    ret10=np.full(n,np.nan)
    ret10[10:]=c[10:]/c[:-10]-1
    one=np.r_[np.nan,c[1:]/c[:-1]-1]
    good=(np.arange(n)+1>=MIN_HISTORY)&(amt60>=MIN_AMOUNT)&np.isfinite(slope)&np.isfinite(ret10)
    good &= pd.Series(amt>0).rolling(10,min_periods=10).sum().to_numpy()>=10
    sel=np.where(good & (d>=np.datetime64(FIRST_DATE)))[0]
    if not len(sel):return pd.DataFrame(),[]
    region=str(m.get("region_primary") or "UNKNOWN")
    sector=str(m.get("style_sector") or "UNKNOWN")
    key=str(m.get("underlying_key") or "")
    daily=pd.DataFrame({
       "date":d[sel],"symbol":symbol,"key":key,"region":region,"sector":sector,
       "amount60":amt60[sel],"ret10":ret10[sel],"positive":(slope[sel]>0)
    })
    signals=[]
    crosses=np.flatnonzero((slope[1:]>0)&(slope[:-1]<=0))+1
    last=-100000
    eligible_indices=set(sel.tolist())
    for s in crosses:
        if s<MIN_HISTORY or s+3>=n:continue
        q=None
        for j in range(s+1,s+4):
            if slope[j]>0 and r2[j]>r2[j-1] and r2[j]>r2[s]:
                q=j
                break
        if q is None or q not in eligible_indices or q-last<COOLDOWN:continue
        if not bool(np.all(one[q-2:q+1]>=-0.03)):continue
        last=q
        maturity=q+5
        future=q+11
        success=bool(np.all(slope[q:maturity+1]>0)) if maturity<n else None
        # D5 outcomes are computed now for research, but only made available as
        # market context on their observable maturity_date (never before).
        record={"date":pd.Timestamp(d[q]),"symbol":symbol,"key":key,
          "region":region,"sector":sector,"amount60":float(amt60[q]),
          "maturity_date":pd.Timestamp(d[maturity]) if maturity<n else pd.NaT,
          "d5_survived":success,
          "net10":float(op[future]/op[q+1]*(1-COST_SIDE)**2-1) if future<n else np.nan,
          "entry_date":pd.Timestamp(d[q+1]) if q+1<n else pd.NaT,
          "exit_date":pd.Timestamp(d[future]) if future<n else pd.NaT,
          "slope_delta":float(slope[q]-slope[q-1]),
          "price_ret10":float(ret10[q])}
        signals.append(record)
    if signals:
        qdays={x["date"] for x in signals}
        daily["qualifies"]=daily.date.isin(qdays)
    else:
        daily["qualifies"]=False
    return daily,signals


def build_representatives(bars: pd.DataFrame, meta: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame,dict]:
    frames=[]; sig=[]
    skip={"metadata_missing":0,"not_equity":0,"unsupported_index_group":0,
          "cash_or_leveraged":0,"short_or_illiquid":0}
    for symbol,g in bars.groupby("symbol",sort=True):
        if symbol not in meta.index:
            skip["metadata_missing"]+=1
            continue
        m=meta.loc[symbol]
        if str(m["asset_class"])!="EQUITY":
            skip["not_equity"]+=1
            continue
        if bool(m["leveraged_flag"]) or bool(m["inverse_flag"]) or str(m["product_type"]) not in ("ETF","LOF"):
            skip["cash_or_leveraged"]+=1
            continue
        key=str(m.get("underlying_key") or "")
        if key in GENERIC_KEYS:
            skip["unsupported_index_group"]+=1
            continue
        d,events=calc_symbol(symbol,g,m)
        if d.empty:
            skip["short_or_illiquid"]+=1
            continue
        frames.append(d);sig.extend(events)
    if not frames:raise RuntimeError("No eligible full-market representative data")
    all_daily=pd.concat(frames,ignore_index=True)
    representatives=(all_daily.sort_values(["date","key","amount60","symbol"],
                       ascending=[True,True,False,True])
                     .drop_duplicates(["date","key"],keep="first")
                     .sort_values(["date","key"]).reset_index(drop=True))
    signal_data=pd.DataFrame(sig)
    if signal_data.empty:raise RuntimeError("No eligible 15d qualified signals")
    # The event belongs to today's actual representative; non-representative
    # signals do not inflate distinct themes or persistence denominators.
    selected=representatives.loc[representatives.qualifies,["date","key","symbol"]]
    events=signal_data.merge(selected,on=["date","key","symbol"],how="inner")
    # An underlying theme contributes no more than one new episode per 20
    # market sessions, even if the most liquid ETF changes over time.
    days=pd.Index(sorted(representatives.date.unique()))
    ix={day:i for i,day in enumerate(days)}
    kept=[];last={}
    for r in events.sort_values(["date","key","symbol"]).to_dict("records"):
        i=ix[r["date"]]
        if i-last.get(r["key"],-10000)<COOLDOWN:continue
        last[r["key"]]=i
        kept.append(r)
    ev=pd.DataFrame(kept)
    if ev.empty:raise RuntimeError("No representative qualifying events")
    diagnostics={
        "raw_eligible_symbol_days":int(len(all_daily)),
        "representative_group_days":int(len(representatives)),
        "representative_symbols":int(representatives.symbol.nunique()),
        "distinct_proxy_groups":int(representatives.key.nunique()),
        "raw_symbol_qualified_events":int(len(signal_data)),
        "representative_before_group_cooldown":int(len(events)),
        "distinct_group_events":int(len(ev)),
        "skipped_symbols":skip,
        "narrow_classification_warning":"Underlying_key is a coarse 2026 taxonomy, not exact tracked-index identity."
    }
    return representatives,ev,diagnostics


def context_daily(reps:pd.DataFrame,events:pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    all_dates=pd.DatetimeIndex(sorted(reps.date.unique()),name="date")
    eligible=(reps.assign(active=1)
              .pivot(index="date",columns="key",values="active")
              .reindex(index=all_dates).fillna(0))
    qualified=(events[["date","key"]].assign(new=1)
              .pivot(index="date",columns="key",values="new")
              .reindex(index=all_dates,columns=eligible.columns).fillna(0))
    recent5=qualified.rolling(5,min_periods=1).max()
    positive=(reps.assign(pos=reps.positive.astype(int))
              .pivot(index="date",columns="key",values="pos")
              .reindex(index=all_dates,columns=eligible.columns).fillna(0))
    # Outcomes ONLY enter after their D+5 date. 20-session trailing mature cohorts.
    matured=events.loc[events.maturity_date.notna()].copy()
    # Future outcome is explicitly re-indexed to date observed, not signal date.
    mat_count=matured.groupby("maturity_date").size().reindex(all_dates,fill_value=0)
    mat_win=matured.groupby("maturity_date").d5_survived.sum().reindex(all_dates,fill_value=0)
    mcount=mat_count.rolling(20,min_periods=1).sum()
    mwin=mat_win.rolling(20,min_periods=1).sum()
    persist=(100*mwin/mcount.where(mcount>=5)).rename("persistence_d5_pct")
    d=pd.DataFrame(index=all_dates)
    d["active_proxies"]=eligible.sum(axis=1).astype(int)
    d["positive_proxies"]=positive.sum(axis=1).astype(int)
    d["trend_breadth15_pct"]=(100*d.positive_proxies/d.active_proxies).round(4)
    d["new_rebuild_5d"]= (recent5*eligible).sum(axis=1).astype(int)
    d["rebuild_diffusion5_pct"]=(100*d.new_rebuild_5d/d.active_proxies).round(4)
    d["matured_cohorts20"]=mcount.astype(int)
    d["matured_success20"]=mwin.astype(int)
    d["persistence_d5_pct"]=persist.round(4)
    d["qualified_today"]=qualified.sum(axis=1).astype(int)
    d=d.reset_index()
    # Industry strength from medians across distinct proxy group representatives.
    # Regional benchmark avoids treating US and mainland return scales as identical.
    region=reps.groupby(["date","region"]).ret10.median().rename("region_median_ret10")
    sector=(reps.groupby(["date","region","sector"])
                .agg(sector_median_ret10=("ret10","median"),
                     proxy_count=("key","nunique")).reset_index())
    sector=sector.join(region,on=["date","region"])
    sector["sector_rs10_pp"]=100*(sector.sector_median_ret10-sector.region_median_ret10)
    sector["sector_strength_valid"]=sector.proxy_count>=3
    sector["sector_rs10_rank_pct"]=sector.loc[sector.sector_strength_valid].groupby(["date","region"]).sector_rs10_pp.rank(pct=True)*100
    assert not sector.duplicated(["date","region","sector"]).any()
    return d,sector


def evaluate(daily:pd.DataFrame,sector:pd.DataFrame,events:pd.DataFrame) -> dict:
    ev=events.loc[events.net10.notna()].copy()
    ev=ev.merge(daily[["date","rebuild_diffusion5_pct","persistence_d5_pct",
                       "trend_breadth15_pct"]],on="date",how="left")
    ev=ev.merge(sector[["date","region","sector","sector_rs10_pp","proxy_count","sector_strength_valid"]],
                on=["date","region","sector"],how="left")
    ev.loc[~ev.sector_strength_valid.fillna(False),"sector_rs10_pp"]=np.nan
    train=ev.loc[ev.date<SPLIT]
    test=ev.loc[ev.date>=SPLIT]
    def mean_ret(f:pd.DataFrame) -> dict:
        if f.empty:return {"n":0}
        return {"n":len(f),"mean_net10_pct":round(float(f.net10.mean()*100),4),
                "win10_pct":round(float((f.net10>0).mean()*100),2)}
    features=["rebuild_diffusion5_pct","persistence_d5_pct","sector_rs10_pp"]
    tests={}
    for feature in features:
        x=train[feature].dropna()
        if len(x)<100:continue
        low,high=np.quantile(x,[.25,.75])
        hi=test.loc[test[feature]>=high]
        lo=test.loc[test[feature]<=low]
        tests[feature]={"train_threshold_low":round(float(low),4),
                        "train_threshold_high":round(float(high),4),
                        "test_coverage":int(test[feature].notna().sum()),
                        "high":mean_ret(hi),"low":mean_ret(lo),
                        "high_minus_low_net10_pp":round(float(100*(hi.net10.mean()-lo.net10.mean())),4),
                        "year":{str(year):{
                          "high":mean_ret(t.loc[t[feature]>=high]),
                          "low":mean_ret(t.loc[t[feature]<=low])
                          } for year,t in test.groupby(test.date.dt.year)}}
    return {"all_events":len(ev),"train":mean_ret(train),"validation":mean_ret(test),
            "feature_tests":tests,
            "caution":"Not portfolio backtest; current taxonomy retrospective; cross-correlated ETFs and months; no premium veto."}


def records(df:pd.DataFrame)->list[dict]:
    rows=json.loads(df.to_json(orient="records",date_format="iso",double_precision=6))
    for r in rows:
        for name,val in r.items():
            if isinstance(val,str) and val.endswith("T00:00:00.000"):
                r[name]=val[:10]
    return rows


def main():
    pa=argparse.ArgumentParser()
    pa.add_argument("--parquet",required=True)
    pa.add_argument("--output",default="research/rebuild_market_context/indicators_v1.json")
    pa.add_argument("--latest",default="data/rebuild-market-context-latest.json")
    pa.add_argument("--report",default="research/rebuild_market_context/README_RESULTS.md")
    pa.add_argument("--self-test",action="store_true")
    args=pa.parse_args()
    if args.self_test:
        x=np.exp(np.linspace(-.05,.05,70)+0.02*np.sin(np.arange(70)/3))
        before=weighted_ols(x)
        after=weighted_ols(np.r_[x,np.exp(np.linspace(.01,.09,18))])
        assert np.allclose(before[0],after[0][:len(x)],equal_nan=True)
        assert np.allclose(before[1],after[1][:len(x)],equal_nan=True)
        print("SELF_TEST_PASS: OLS prefix unchanged after future observations")
        return
    source=Path(args.parquet)
    meta=metadata(os.getenv("ETF_DAILY_BARS_DATABASE_URL",""))
    bars,data_info=prepare(source,meta)
    rep,events,quality=build_representatives(bars,meta)
    daily,sector=context_daily(rep,events)
    study=evaluate(daily,sector,events)
    # Security/consistency assertions: no same-date repeat, denominators fixed.
    assert daily.active_proxies.ge(daily.new_rebuild_5d).all()
    assert daily.positive_proxies.le(daily.active_proxies).all()
    assert daily.rebuild_diffusion5_pct.between(0,100).all()
    assert daily.persistence_d5_pct.dropna().between(0,100).all()
    assert daily.date.is_monotonic_increasing
    latest_day=daily.iloc[-1]
    latest_sector=sector.loc[(sector.date==latest_day.date)&sector.sector_strength_valid].copy()
    latest_sector=latest_sector.sort_values("sector_rs10_pp",ascending=False)
    previous120=daily.tail(120)
    payload={
        "contract":"ETF_REBUILD_CONTEXT_V1_RESEARCH_ONLY",
        "source":data_info,"quality":quality,
        "metrics":{
            "rebuild_diffusion5_pct":"Past 5 market sessions with a 15-bar qualified new signal, distinct current-taxonomy proxy; divided by today's eligible proxies",
            "persistence_d5_pct":"Success rate of 15-bar episodes when they first reached D+5, only episodes matured in past 20 market sessions; minimum 5 matured",
            "sector_rs10_pp":"Median 10-session return of distinct regional/sector proxies minus contemporaneous region-wide proxy median, in percentage points",
            "trend_breadth15_pct":"Positive 15-bar slopes / eligible independent current-taxonomy proxies, supplementary"
        },
        "signal_source":"15d weighted log OLS, first improvement R2 within D1-D3 after slope crosses 0, D2 filter, 20-session per-symbol and proxy cooldown",
        "latest_day":records(daily.tail(1))[0],
        "latest_top_sectors":records(latest_sector.head(12)),
        "latest_bottom_sectors":records(latest_sector.tail(12)),
        "history_120_sessions":records(previous120),
        "validation":study,
        "limitations":[
            "Current taxonomy not PIT before 2026-09; historical RS and proxy grouping are exploratory and must not be used for live decision backtests as validated factors.",
            "Current-listed ETF archive omits complete historical liquidations; ratio denominators only include archive-known survivors with at least 200 past bars.",
            "underlying_key coarsely combines different tracked indices; CHINA_EQUITY_OTHER omitted, so these are proxies not verified independent indices.",
            "Sector strength uses style_sector current label and representative ETF returns, not officially published index returns.",
            "Persistence uses matured episodes only; 20-session maturity window; no look-ahead from still-unmatured event outcomes.",
            "ETF premium, NAV, live order execution and factor stability by regime have not yet been verified."
        ]
    }
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False,default=str),encoding="utf-8")
    latest={"contract":payload["contract"],"as_of":data_info["as_of"],
            "latest_day":payload["latest_day"],"latest_top_sectors":payload["latest_top_sectors"],
            "latest_bottom_sectors":payload["latest_bottom_sectors"],
            "history_120_sessions":payload["history_120_sessions"],"quality":quality,
            "research_only":True}
    out_latest=Path(args.latest);out_latest.parent.mkdir(parents=True,exist_ok=True)
    out_latest.write_text(json.dumps(latest,ensure_ascii=False,indent=2,allow_nan=False,default=str),encoding="utf-8")
    lines=["# 全市场重建环境三指标 · 研究 V1","",
           f"数据日期：{data_info['as_of']}；全市场原始代码：{data_info['raw_symbols']}；",
           f"研究代理主题组：{quality['distinct_proxy_groups']}；去重合格事件：{quality['distinct_group_events']}。","",
           "## 三指标","",
           f"- 过去 5 日重建扩散率：{latest_day.rebuild_diffusion5_pct:.2f}%（{latest_day.new_rebuild_5d}/{latest_day.active_proxies} 组）",
           f"- 既往成熟事件 D5 存续率：{latest_day.persistence_d5_pct:.2f}%（{latest_day.matured_success20}/{latest_day.matured_cohorts20}）" if pd.notna(latest_day.persistence_d5_pct) else "- 既往成熟事件 D5 存续率：样本不足",
           "- 行业相对强度：按日/地区分别计算 10 日主题组中位涨幅减地区中位涨幅，行业排序见 JSON。",
           f"- 附加观察：15 日正趋势宽度 {latest_day.trend_breadth15_pct:.2f}%。",
           "","## 样本外按研究期四分位阈值筛选（仅描述）","","| 指标 | 高组 n / 10日平均净收益 | 低组 n / 10日平均净收益 | 高-低 pp |",
           "|---|---|---|---:|"]
    for key,v in study["feature_tests"].items():
        hi,lo=v["high"],v["low"]
        lines.append(f"| {key} | {hi['n']} / {hi['mean_net10_pct']:+.3f}% | {lo['n']} / {lo['mean_net10_pct']:+.3f}% | {v['high_minus_low_net10_pp']:+.3f} |")
    lines+=["","## 方法注意","",*["- "+x for x in payload["limitations"]]]
    out_r=Path(args.report);out_r.parent.mkdir(parents=True,exist_ok=True)
    out_r.write_text("\n".join(lines),encoding="utf-8")
    print("REBUILD_CONTEXT_COMPLETE "+json.dumps({
        "as_of":data_info["as_of"],"quality":quality,
        "latest_day":payload["latest_day"],"validation":study,
        "top_sectors":payload["latest_top_sectors"][:5],
        "paths":[str(out),str(out_latest),str(out_r)]
    },ensure_ascii=False,default=str),flush=True)


if __name__=="__main__":
    main()
