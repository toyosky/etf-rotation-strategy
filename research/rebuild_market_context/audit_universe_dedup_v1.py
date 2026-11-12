#!/usr/bin/env python3
"""Universe-size and extreme-value bias audit for early ETF rebuild.

Compare full, pre-signal representatives by coarse underlying proxy, and
pre-signal representatives by broad sector. Uses prior-available trailing
turnover (lagged) for deterministic selection; signal ranking and execution
next-open. Also contrast post-signal index dedup as a sensitivity only.

Current labels are *not* true point-in-time or exact tracked-index identity.
Research-only, never modify production trading.
"""
from __future__ import annotations
import argparse, hashlib, json, os
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import compute_indicators_v1 as base

DATE_SPLIT = pd.Timestamp("2025-01-01")
COST_SIDE = .0006
THEME_COOLDOWN = 20
SIGNAL_COLS = ["date","symbol","key","region","sector","slope_delta",
               "price_ret10","amount60","net10","entry_date","exit_date"]
VARIANTS=("ALL","EXPOSURE_PRE","SECTOR_PRE","EXPOSURE_POST")
SCORES=("slope_delta","price_ret10")
MAX_HOLD=10


def load_symbols(bars,meta):
    elig=[],signals=[]
    skipped=defaultdict(int)
    for code,g in bars.groupby("symbol",sort=True):
        if code not in meta.index:
            skipped["no_metadata"]+=1;continue
        m=meta.loc[code]
        if str(m["asset_class"])!="EQUITY" or str(m["product_type"]) not in ("ETF","LOF"):
            skipped["not_equity_etflof"]+=1;continue
        if bool(m["leveraged_flag"]) or bool(m["inverse_flag"]):
            skipped["leveraged_inverse"]+=1;continue
        key=str(m["underlying_key"]) if pd.notna(m["underlying_key"]) else ""
        sector=str(m["style_sector"]) if pd.notna(m["style_sector"]) else ""
        region=str(m["region_primary"]) if pd.notna(m["region_primary"]) else ""
        if key in base.GENERIC_KEYS or not sector or not region or sector in ("UNKNOWN","CASH","CASHLIKE"):
            skipped["invalid_proxy_sector"]+=1;continue
        # Reuse first 200-day historical eligibility, D1-D3 R2, 3-day
        # sharp-drop filter and 3m CNY 60-day amount rule from V1.
        frame,ev=base.calc_symbol(code,g,m)
        if frame.empty:
            skipped["insufficient_eligibility"]+=1;continue
        frame["region_key"]=frame.region+"|"+frame.key
        frame["region_sector"]=frame.region+"|"+frame.sector
        elig.append(frame)
        signals.extend(ev)
    if not elig or not signals:raise RuntimeError("No universe candidates")
    daily=pd.concat(elig,ignore_index=True).sort_values(["symbol","date"])
    daily["turnover_pre"]=daily.groupby("symbol").amount60.shift(1)
    daily["turnover_pre"]=daily.turnover_pre.fillna(0)
    signals=pd.DataFrame(signals)
    signals=signals.merge(daily[["date","symbol","region_key","region_sector","turnover_pre"]],
                on=["date","symbol"],how="inner",validate="one_to_one")
    signals=signals.dropna(subset=["net10"]).copy()
    # Ignore last incomplete fwd10 events from all variants uniformly.
    available=daily.loc[daily.turnover_pre>0]
    return daily,signals,available,dict(skipped)


def pre_select(days,signal,group):
    rep=(days.sort_values([ "date",group,"turnover_pre","symbol"],
            ascending=[True,True,False,True])
         .drop_duplicates(["date",group]))
    return signal.merge(rep[["date","symbol"]],on=["date","symbol"],how="inner",validate="one_to_one")


def post_select(signal,group):
    return (signal.sort_values(["date",group,"turnover_pre","symbol"],
                ascending=[True,True,False,True])
             .drop_duplicates(["date",group],keep="first"))


def cooldown_group(d,group,days):
    # Group rebuilder event cooldown; for ALL v1 already 20d per symbol.
    idx={t:i for i,t in enumerate(pd.Index(sorted(days.date.unique())))}
    picked=[];last={}
    d=d.sort_values(["date","symbol"])
    for j,z in d.iterrows():
        identity=z[group]
        ix=idx[z["date"]]
        if ix-last.get(identity,-10000)<THEME_COOLDOWN:continue
        last[identity]=ix
        picked.append(j)
    return d.loc[picked].copy()


def avg_result(df,value="net10"):
    if df.empty:return {"n":0}
    z=df[value].to_numpy(float)
    return {"n":int(len(z)),"average_pct":round(float(z.mean()*100),4),
            "median_pct":round(float(np.median(z)*100),4),
            "win_pct":round(float((z>0).mean()*100),2),
            "p10_pct":round(float(np.quantile(z,.1)*100),3)}


def by_signal_day(d,score):
    # Ties are deterministic; score uses past and current ONLY.
    d=d.sort_values(["date",score,"turnover_pre","symbol"],
                ascending=[True,False,False,True])
    res=[]
    for date,g in d.groupby("date",sort=True):
        res.append({"date":date,"all":g.net10.mean(),
                    "top1":g.head(1).net10.mean(),
                    "top3":g.head(3).net10.mean(),
                    "n_etf":len(g),
                    "n_proxy":g.region_key.nunique(),
                    "n_sector":g.region_sector.nunique(),
                    "max_slope_delta":g.slope_delta.max(),
                    "max_price_ret10":g.price_ret10.max(),
                    "year":date.year,
                    "top1_symbol":g.iloc[0].symbol,
                    "top1_region_key":g.iloc[0].region_key,
                    "top1_sector":g.iloc[0].region_sector,
                    "top1_slope_delta":g.iloc[0].slope_delta})
    return pd.DataFrame(res)


def analyze_universe(variants,days):
    result={}
    for name,v in variants.items():
        d=v.loc[v.net10.notna()].copy()
        outcome={}
        for score in SCORES:
            byday=by_signal_day(d,score)
            sliced={}
            for label,f in (("TRAIN",byday.loc[byday.date<DATE_SPLIT]),
                             ("VALID",byday.loc[byday.date>=DATE_SPLIT]),
                             ("2025",byday.loc[byday.year==2025]),
                             ("2026",byday.loc[byday.year==2026])):
                if len(f)==0:continue
                sliced[label]={
                 "days":int(len(f)),"events":int(v.loc[v.date.isin(f.date)].shape[0]),
                 "per_day_candidates_mean":round(float(f.n_etf.mean()),3),
                 "per_day_candidates_median":round(float(f.n_etf.median()),3),
                 "per_day_candidates_p95":round(float(f.n_etf.quantile(.95)),3),
                 "per_day_exposures_mean":round(float(f.n_proxy.mean()),3),
                 "per_day_sectors_mean":round(float(f.n_sector.mean()),3),
                 "daily_equal_weight":avg_result(f.rename(columns={"all":"net10"})),
                 "top1":avg_result(f.rename(columns={"top1":"net10"})),
                 "top3":avg_result(f.rename(columns={"top3":"net10"})),
                 "top1_unique_symbols":int(f.top1_symbol.nunique()),
                 "max_signal_slope_p95":round(float(f.max_slope_delta.quantile(.95)),7),
                 "max_signal_ret10_p95":round(float(f.max_price_ret10.quantile(.95)*100),3)
                }
            outcome[score]=sliced
        result[name]={"events":len(d),"symbols":int(d.symbol.nunique()),
                      "exposures":int(d.region_key.nunique()),
                      "sectors":int(d.region_sector.nunique()),
                      "selection":outcome}
    return result


def matched_gap(variants,score,ref="ALL"):
    rows={k:by_signal_day(v,score).set_index("date") for k,v in variants.items()}
    result={}
    for name,other in rows.items():
        if name==ref:continue
        common=other.join(rows[ref][["all","top1","top3"]],rsuffix="_all",how="inner")
        common=common.loc[common.index>=DATE_SPLIT]
        res={"matched_days":int(len(common))}
        for target in ("all","top1","top3"):
            diff=(common[target]-common[target+"_all"]).dropna()
            res[target+"_diff_pp"]=round(float(100*diff.mean()),4) if len(diff) else None
            if len(diff)<12:continue
            series=diff.groupby(diff.index.strftime("%Y-%m"))
            sums=series.sum().to_numpy(float)
            ns=series.size().to_numpy(int)
            rng=np.random.default_rng(20261112)
            picks=rng.integers(0,len(sums),size=(1700,len(sums)))
            boots=100*sums[picks].sum(axis=1)/ns[picks].sum(axis=1)
            res[target+"_ci95_pp"]=[round(float(x),4) for x in np.quantile(boots,[.025,.975])]
        result[name]=res
    return result


def date_coverage(variants):
    return {k:{
        "train_dates":v.loc[v.date<DATE_SPLIT].date.nunique(),
        "valid_dates":v.loc[v.date>=DATE_SPLIT].date.nunique(),
        "recent_dates":v.loc[v.date>=pd.Timestamp("2026-10-01")].date.nunique()
        } for k,v in variants.items()}


def main():
    pa=argparse.ArgumentParser()
    pa.add_argument("--parquet",required=True)
    pa.add_argument("--output",default="research/rebuild_market_context/universe_extreme_value_audit_v1.json")
    pa.add_argument("--report",default="research/rebuild_market_context/universe_extreme_value_audit_v1.md")
    args=pa.parse_args()
    meta=base.metadata(os.environ.get("ETF_DAILY_BARS_DATABASE_URL",""))
    bars,source=base.prepare(Path(args.parquet),meta)
    daily,signal,eligible,skips=load_symbols(bars,meta)
    # Current-day trading data intentionally not used for carrier selection:
    # lagged 60-day mean picks carrier based only on t-1 availability.
    allpool=signal.loc[signal.turnover_pre>0].copy()
    raw_pre_exposure=pre_select(eligible,allpool,"region_key")
    raw_pre_sector=pre_select(eligible,allpool,"region_sector")
    raw_post_exposure=post_select(allpool,"region_key")
    variants={
      "ALL":allpool,
      "EXPOSURE_PRE":cooldown_group(raw_pre_exposure,"region_key",daily),
      "SECTOR_PRE":cooldown_group(raw_pre_sector,"region_sector",daily),
      "EXPOSURE_POST":cooldown_group(raw_post_exposure,"region_key",daily)
    }
    # audit matching and no duplicate source rows
    for name,v in variants.items():
        assert not v.duplicated(["symbol","date"]).any(),name
        if name=="EXPOSURE_PRE":
            assert not v.duplicated(["date","region_key"]).any()
        if name=="SECTOR_PRE":
            assert not v.duplicated(["date","region_sector"]).any()
        if name=="EXPOSURE_POST":
            assert not v.duplicated(["date","region_key"]).any()
    result={
      "contract":"REBUILD_UNIVERSE_EXTREME_VALUE_RESEARCH_V1",
      "source":source,
      "common_universe":"Equity ETFs/LOFs with current identifiable proxy & sector, 200 historical bars, previous 60d amount >=3m, positive turnover, D1-D3 slope crossing/R² improvement, D2 no <-3%, 20-bar symbol cooldown.",
      "carrier_selection":"Each date select ETF with highest *prior* date trailing 60d traded amount, before observing date-t rebuild; only that carrier may signal. Separate group-wide 20 market-day event cooldown.",
      "classification":"EXPOSURE_PRE groups by (region_primary, underlying_key); SECTOR_PRE groups by (region_primary, style_sector). BOTH are current labels, NOT proven true historical PIT or exact index identity. Broad keys collapse distinct subthemes.",
      "alternatives":"EXPOSURE_POST first forms signal events across every carrier then keeps highest lagged-turnover qualified ETF per exposure, which retains cross-carrier multiple-testing and is only a sensitivity.",
      "source_counts":{"eligible_symbol_days":len(daily),"candidate_signal_events_all":len(allpool),
                       "eligible_symbols":int(eligible.symbol.nunique()),
                       "current_proxy_count":int(eligible.region_key.nunique()),
                       "current_sector_count":int(eligible.region_sector.nunique()),
                       "skipped":skips},
      "variants":analyze_universe(variants,daily),
      "same_date_matched":{score:matched_gap(variants,score) for score in SCORES},
      "date_coverage":date_coverage(variants),
      "caveats":[
        "Current-taxonomy exposure keys are coarse; e.g., medical devices and biotech share CHINA_HEALTHCARE, and STAR_MARKET merges unrelated sector ETFs.",
        "A single ETF per sector can erase true cross-subsector exposures; sector uniqueness is a stress test, not default recommended production rule.",
        "Current metadata valid_from mostly 2026-09, thus 2021-2026 grouping is not historically verifiable PIT. Delisted ETFs missing; no guaranteed investable historical backtest.",
        "All variants intentionally use the same universe eligible with known keys: this is NOT a full 2003 ETF comparison.",
        "Fixed rank slope_delta or past 10d return is a diagnostic, NOT a trained optimal signal. Daily same-date return comparisons do not recreate funded overlapping open positions.",
        "No NAV premium filters, 09:31/14:05 intraday execution restrictions, LOF share class anomalies, or price adjustment source splice repairs.",
        "We estimate slope maximum across candidate pools as extreme-value diagnostic; it does not alone prove the best forecast is overfit."
      ]
    }
    report=Path(args.output);report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str,allow_nan=False),encoding="utf8")
    lines=["# ETF 重建候选池去重与极值效应对照 V1","",
        f"价格来源：{source['as_of']}；合格研究标的 {result['source_counts']['eligible_symbols']} 只；主题代理组 {result['source_counts']['current_proxy_count']}；行业组 {result['source_counts']['current_sector_count']}。",
        "","## 15 日重建事件，10 日次日开盘净收益（6bp/side）","",
        "| 候选池 | 验证期交易日 | 每日候选均值 | Top1 10日均值 | Top3 10日均值 | 日等权平均 |",
        "|---|---:|---:|---:|---:|---:|"]
    for name in VARIANTS:
        x=result["variants"][name]["selection"]["slope_delta"].get("VALID",{})
        if not x:continue
        lines.append(f"| {name} | {x['days']} | {x['per_day_candidates_mean']:.2f} | "+
           f"{x['top1']['average_pct']:+.3f}% | {x['top3']['average_pct']:+.3f}% | "+
           f"{x['daily_equal_weight']['average_pct']:+.3f}% |")
    lines+=["","## 同日匹配检验：相对于 ALL（Top1 按 slope_delta 排序）","",
            "| 收缩池 | 共同日期 | Top1 收益差 pp | 按月区块95%区间 |",
            "|---|---:|---:|---|"]
    for name,a in result["same_date_matched"]["slope_delta"].items():
        ci=a.get("top1_ci95_pp")
        lines.append(f"| {name} | {a['matched_days']} | {a.get('top1_diff_pp')} | {ci} |")
    lines+=["","## 结论边界","",*["- "+x for x in result["caveats"]]]
    path=Path(args.report);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("\n".join(lines),encoding="utf8")
    print("UNIVERSE_DEDUP_AUDIT_SUCCESS "+json.dumps({
      "source_counts":result["source_counts"],
      "train_valid":{k:result["variants"][k]["selection"]["slope_delta"] for k in VARIANTS},
      "matched":result["same_date_matched"]["slope_delta"]
    },ensure_ascii=False,default=str),flush=True)


if __name__=="__main__":
    main()
