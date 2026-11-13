#!/usr/bin/env python3
"""Research-only stability extension of the frozen V3.2 Top1 selection audit.

Replays identical original ALL/EXACT_PRE/QUALITY_PRE definitions over 2021-26.
P99 annual out-of-sample variant uses only prior calendar years' qualified
full-pool slopes to freeze each subsequent year's cap. 2021 has no trained cap.
This is NOT a point-in-time taxonomy or executable trading simulation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import audit_top1_extreme_quality_v1 as base

YEARS = tuple(range(2021, 2027))
SEED = 20261113
SOURCE_SHA = "9d55f6e0a511be72609e799b19d04c1b44e2555374298bceef102a0481a067fb"
PERIODS = {
    "2021-2024": (2021, 2024),
    "2025-2026": (2025, 2026),
    "2021-2026": (2021, 2026),
    "2022-2026": (2022, 2026),
    "2023-2024": (2023, 2024),
}

def prior_year_p99(qualified_all, exact):
    parts = []
    thresholds = {}
    for year in YEARS:
        if year == YEARS[0]:
            thresholds[str(year)] = None
            continue
        prior = qualified_all.loc[qualified_all.date < pd.Timestamp(year=year,month=1,day=1), 'slope'].dropna()
        cap = float(prior.quantile(.99))
        if not np.isfinite(cap) or cap <= 0 or len(prior) < 100:
            raise ValueError(f"Insufficient preceding years for {year} p99: {len(prior)}")
        thresholds[str(year)] = {"cap_slope_bps":round(cap*10000, 4),
                                 "prior_observations":int(len(prior))}
        cur=exact.loc[exact.date.dt.year==year]
        parts.append(cur.loc[cur.slope<=cap])
    return pd.concat(parts, ignore_index=True), thresholds

def selected(df):
    if df.empty:
        return df
    v=base.rank_top(df)
    return v.loc[v.net10.notna()].copy()

def describe(x):
    if x.empty:
        return {"days":0, "mean_pct":None,"median_pct":None,"p10_pct":None,"win_pct":None}
    r=x.net10.to_numpy(dtype=float)
    return {"days":int(len(x)),
            "mean_pct":round(float(r.mean()*100),4),
            "median_pct":round(float(np.median(r)*100),4),
            "p10_pct":round(float(np.quantile(r,.10)*100),4),
            "win_pct":round(float((r>0).mean()*100),2),
            "distinct_funds":int(x.symbol.nunique())}

def _period(df, lower, upper):
    return df.loc[df.date.dt.year.between(lower,upper)]

def paired(a,b,lower,upper):
    a=_period(a,lower,upper).set_index("date")
    b=_period(b,lower,upper).set_index("date")
    c=a[["net10","symbol"]].join(b[["net10","symbol"]],
            how="inner",lsuffix="_a",rsuffix="_b").dropna()
    if len(c)==0: return {"days":0}
    delta=c.net10_a-c.net10_b
    month=delta.groupby(delta.index.to_period("M")).agg(["sum","count"])
    sums=month["sum"].to_numpy(float); counts=month["count"].to_numpy(int)
    rng=np.random.default_rng(SEED)
    picks=rng.integers(0,len(sums),size=(3000,len(sums)))
    boots=100*sums[picks].sum(axis=1)/counts[picks].sum(axis=1)
    changed=c.symbol_a.ne(c.symbol_b)
    return {"days":int(len(c)),
            "diff_pp":round(float(delta.mean()*100),4),
            "ci95_pp":[round(float(v),4) for v in np.quantile(boots,[.025,.975])],
            "changed_days":int(changed.sum()),
            "same_fund_pct":round(float((~changed).mean()*100),2),
            "diff_on_changed_days_pp":round(float(delta[changed].mean()*100),4) if changed.any() else 0.0,
            "positive_diff_days_pct":round(float((delta>0).mean()*100),2)}

def test():
    train_days=pd.date_range("2021-01-04",periods=120,freq="B")
    dates=list(train_days)+[pd.Timestamp("2022-06-01"),pd.Timestamp("2023-06-01")]
    v=pd.DataFrame({"date":dates,
                    "symbol":["A"]*len(dates),
                    "slope":[.01]*len(dates), "r2":[.8]*len(dates),
                    "prior_amount":[10_000_000.0]*len(dates),
                    "net10":[.02]*len(dates)})
    wf, t=prior_year_p99(v,v)
    assert t["2021"] is None and t["2022"]["prior_observations"]==120
    assert wf.date.dt.year.min()==2022
    a=selected(v)
    z=paired(a,a,2021,2023)
    assert z["diff_pp"]==0 and z["changed_days"]==0
    assert describe(_period(a,2021,2021))["days"]==120
    print("SELF_TEST_PASS")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--bars",type=Path)
    parser.add_argument("--taxonomy",type=Path)
    parser.add_argument("--summary",type=Path)
    parser.add_argument("--baseline",type=Path)
    parser.add_argument("--out",type=Path,default=Path(
       "research/taxonomy_v3/output_v32/top1_stability_2021_v1.json"))
    parser.add_argument("--report",type=Path,default=Path(
       "research/taxonomy_v3/output_v32/top1_stability_2021_v1.md"))
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test: return test()
    if not all([args.bars,args.taxonomy,args.summary,args.baseline]):
        parser.error("--bars --taxonomy --summary --baseline are required")
    observed_sha=hashlib.sha256(args.bars.read_bytes()).hexdigest()
    src=json.loads(args.summary.read_text())
    if observed_sha!=SOURCE_SHA or src["archive_sha256"]!=SOURCE_SHA:
        raise ValueError("Frozen 2026-11-11 archive hash mismatch: "+observed_sha)
    bar=pd.read_parquet(args.bars,columns=["symbol","date","open","high","low","close","amount"])
    tax=pd.read_parquet(args.taxonomy)
    daily,skipped=base.qualified_daily(bar,tax)
    modes, original_threshold=base.pools(daily)
    baseline=json.loads(args.baseline.read_text())
    for name in ("ALL","EXACT_PRE","QUALITY_PRE","TRAIN_P99_CAP"):
        check=base.summarize(modes[name])
        expected=baseline["variants"][name]
        for field in ("days","top1_net10_mean_pct"):
            if check[field]!=expected[field]:
                raise AssertionError(f"2025-26 regression mismatch {name}.{field}: {check[field]} != {expected[field]}")
    if abs(original_threshold*10000-baseline["sample"]["train_p99_slope_bps"])>.001:
        raise AssertionError("Training threshold differs from frozen baseline")
    # Keep the original 2025-26 P99 cap unchanged. Apply annual ex-ante
    # growing-training cutoffs to 2022-24 and 2025-26 as a distinct variant.
    p99wf,thresh=prior_year_p99(modes["ALL"],modes["EXACT_PRE"])
    modes["P99_WALK_FORWARD"]=p99wf
    tops={k:selected(v) for k,v in modes.items()}
    variants=("ALL","EXACT_PRE","QUALITY_PRE","P99_WALK_FORWARD")
    annual={
      k:{str(year):describe(_period(tops[k],year,year)) if not
           (k=="P99_WALK_FORWARD" and year==2021) else {"days":0,"note":"no prior-year P99 training"}
          for year in YEARS}
      for k in variants}
    period_stats={k:{period:describe(_period(tops[k],*yrange))
               for period,yrange in PERIODS.items()} for k in variants}
    # P99 2025-26 is identical to the original TRAIN_P99_CAP; annual
    # dynamic threshold only makes historical pre-2025 expansion unbiased.
    p99_validation_equal=(tops["P99_WALK_FORWARD"].loc[
         tops["P99_WALK_FORWARD"].date.dt.year.ge(2025),["date","symbol"]].reset_index(drop=True)
        .equals(tops["TRAIN_P99_CAP"].loc[
         tops["TRAIN_P99_CAP"].date.dt.year.ge(2025),["date","symbol"]].reset_index(drop=True)))
    if not p99_validation_equal:
        raise AssertionError("2025-26 historical OOS P99 mismatch with original fixed cap")
    comparisons={"EXACT_PRE_vs_ALL":("EXACT_PRE","ALL"),
                 "QUALITY_PRE_vs_EXACT_PRE":("QUALITY_PRE","EXACT_PRE"),
                 "P99_WALK_FORWARD_vs_EXACT_PRE":("P99_WALK_FORWARD","EXACT_PRE")}
    compare={key:{"periods":{p:paired(tops[a],tops[b],*period) for p,period in PERIODS.items()},
                    "years":{str(y):paired(tops[a],tops[b],y,y) if not
                        (a=="P99_WALK_FORWARD" and y==2021) else {"days":0,"note":"no prior-year training"}
                        for y in YEARS}}
             for key,(a,b) in comparisons.items()}
    output={"contract":"ETF_TAXONOMY_TOP1_STABILITY_2021_V1",
            "research_only":True,"historical_taxonomy_pit":False,
            "not_funded_portfolio_backtest":True,
            "source":{"archive_sha256":observed_sha,
                      "last_data_date":str(bar.date.max()),
                      "source_rows":len(bar),
                      "taxonomy_snapshot":src["snapshot_date"]},
            "frozen_baseline_reproduced":True,
            "original_pre2025_p99_bps":round(original_threshold*10000,4),
            "annual_p99_thresholds":thresh,
            "eligible_funds":int(daily.symbol.nunique()),
            "annual":annual, "periods":period_stats,
            "paired":compare,
            "caveats":[
              "2026 taxonomy retrospectively assigned to 2021-2026; not historical PIT.",
              "Selected Top1 net10 is a daily overlapping event outcome, NOT a funded strategy.",
              "P99_WALK_FORWARD uses prior calendar years only; no P99 entry for 2021.",
              "The 2025-26 cutoffs exactly match prior 2021-24 TRAIN_P99_CAP.",
              "No point-in-time NAV premium, delisted funds, or intraday executable filters.",
              "Bootstrap resamples calendar month blocks; no multiple-test adjustment."]}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    lines=["# ETF Top1 去重、质量与P99过滤：2021—2026年稳定性检查",
           "",
           "**研究性质**：重放2026-11-12的静态分类，不是2021年的真实PIT；后10日收益窗口重叠，不是资金回测。",
           "与原2025—2026结果使用**相同旧版行情哈希**、相同斜率/质量规则；先断言旧表逐值复现才计算扩展。",
           "P99从每个验证年之前的完整年份训练；2021年没有训练史，记为不适用。2025/26与原固定2021—2024 P99完全相同。",
           "",
           "## 年度后10日平均净收益（%）",
           "",
           "| 年份 | ALL | 精确去重 | 去重+质量 | 去重+历年P99 |",
           "|---|---:|---:|---:|---:|"]
    for y in YEARS:
        r=annual
        def val(k):
            v=r[k][str(y)]["mean_pct"]
            return "—" if v is None else f"{v:+.3f}"
        lines.append(f"| {y} | {val('ALL')} | {val('EXACT_PRE')} | {val('QUALITY_PRE')} | {val('P99_WALK_FORWARD')} |")
    lines.extend(["","## 同日配对：每年平均收益差（百分点）","",
                  "| 年份 | 精确去重−ALL | 质量−去重 | P99−去重 |",
                  "|---|---:|---:|---:|"])
    for y in YEARS:
        def delta(k):
            s=compare[k]["years"][str(y)]
            return "—" if s["days"]==0 else f"{s['diff_pp']:+.3f} ({s['days']}日)"
        lines.append(f"| {y} | {delta('EXACT_PRE_vs_ALL')} | {delta('QUALITY_PRE_vs_EXACT_PRE')} | {delta('P99_WALK_FORWARD_vs_EXACT_PRE')} |")
    lines.extend(["","## 分阶段同日配对与月份区块95%置信区间",""])
    for pname in PERIODS:
        lines.append(f"**{pname}**")
        for label in comparisons:
            s=compare[label]["periods"][pname]
            if s["days"]==0:continue
            ci=s["ci95_pp"]
            lines.append(f"- {label}: n={s['days']}, Δ={s['diff_pp']:+.4f}pp, CI=[{ci[0]:+.4f},{ci[1]:+.4f}], 换标的日={s['changed_days']}（{100-s['same_fund_pct']:.2f}%）")
        lines.append("")
    lines.extend(["## 年度候选覆盖率（有Top1信号的日期数）","",
                  "| 年份 | ALL | 精确去重 | 去重+质量 | 去重+P99 |","|---|---:|---:|---:|---:|"])
    for y in YEARS:
        lines.append("| {} | {} | {} | {} | {} |".format(y,*[annual[k][str(y)]["days"] for k in variants]))
    lines.extend(["","## 训练期P99阈值",""])
    for yr,info in thresh.items():
        if info is None: continue
        lines.append(f"- {yr}年：阈值 {info['cap_slope_bps']:.4f} bps/交易日；此前合格观测 {info['prior_observations']}")
    lines.extend(["","## 主要限制","",*["- "+x for x in output["caveats"]],""])
    args.report.write_text("\n".join(lines))
    print("\n".join(lines))

if __name__=="__main__":
    main()
