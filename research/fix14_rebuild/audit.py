#!/usr/bin/env python3
"""Fixed 14 OLS-universe rebuild independent-value audit, frozen original RISK_POOL.
Research only. Never changes production selection, holdings, scheduler or database.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from research.full_market_rebuild.fullmarket_window_backtest_v1 import ols_arrays

FIX14 = (
    "159934","159985","161226","513100","159957","159509","513290",
    "159529","159981","501018","513530","511380","164824","512800",
)
GROUP = {
    "159934":"metals","161226":"metals",
    "159985":"commodity","159981":"commodity","501018":"commodity",
    "513100":"US","159509":"US","513290":"US","159529":"US",
    "159957":"A_equity","512800":"A_equity",
    "511380":"bond_convertible","513530":"HK_equity","164824":"India",
}
BENCH = "511220"
HORIZONS = (5,10,20)
FIRST = pd.Timestamp("2021-01-01")
LAST = pd.Timestamp("2026-10-13")
FEE = 0.0006
CALIPER = np.array([0.03,0.05,0.08])
SEED=20261113


def load_panel(file):
    sha=hashlib.sha256(Path(file).read_bytes()).hexdigest()
    bars=pd.read_parquet(file,columns=["symbol","date","open","close","amount"])
    rows,total=int(len(bars)),int(bars.symbol.nunique())
    bars["symbol"]=bars.symbol.astype(str).str.zfill(6)
    bars=bars[bars.symbol.isin(FIX14+(BENCH,))].copy()
    bars["date"]=pd.to_datetime(bars.date).dt.normalize()
    for c in ("open","close","amount"):
        bars[c]=pd.to_numeric(bars[c],errors="coerce")
    bars=bars[(bars.open>0)&(bars.close>0)].copy()
    bars=bars.sort_values(["symbol","date"]).drop_duplicates(["symbol","date"],keep="last").reset_index(drop=True)
    calendar=np.sort(bars.date.unique())
    bars["tid"]=np.searchsorted(calendar,bars.date.to_numpy(dtype="datetime64[ns]"))
    bars["group"]=bars.symbol.map(GROUP)
    cols=["ret5","ret10","ret26","slope","r2","ann","score","rebuild",
          "last_signal_age","net5","net10","net20"]
    for col in cols:bars[col]=np.nan
    bars["rebuild"]=False
    coverage={}
    event_variant={}
    for sym,g in bars.groupby("symbol",sort=False):
        p=g.index.to_numpy()
        close=g.close.to_numpy(float)
        op=g.open.to_numpy(float)
        tid=g.tid.to_numpy(int)
        n=len(g)
        coverage[sym]={"rows":int(n),"first":str(g.date.iloc[0].date()),
                       "last":str(g.date.iloc[-1].date())}
        slope,r2=ols_arrays(close,26)
        annual=np.expm1(np.clip(slope*250,-700,700))
        bars.loc[p,"slope"]=slope
        bars.loc[p,"ann"]=annual
        bars.loc[p,"r2"]=r2
        bars.loc[p,"score"]=np.where(annual>0,annual*r2,0)
        for h in (5,10,26):
            ret=np.full(n,np.nan)
            if n>h:
                good=tid[h:]-tid[:-h]==h
                ret[h:]=np.where(good,close[h:]/close[:-h]-1,np.nan)
            bars.loc[p,f"ret{h}"]=ret
        for h in HORIZONS:
            ret=np.full(n,np.nan)
            k=h+1
            if n>k:
                good=tid[k:]-tid[:-k]==k
                # T+1 open buy and T+h+1 open sell, net of 6bp each side.
                ret[:n-k]=np.where(good,op[k:]/op[1:n-h]*(1-FEE)/(1+FEE)-1,np.nan)
            bars.loc[p,f"net{h}"]=ret
        if sym==BENCH:continue
        signals=[]
        crossed=np.flatnonzero((slope[1:]>1e-8)&(slope[:-1]<=1e-8))+1
        for i in crossed:
            for q in range(i+1,min(i+4,n)):
                if (slope[q]>1e-8 and np.isfinite(r2[q-1]) and
                    r2[q]>r2[q-1]+1e-12 and r2[q]>r2[i]+1e-12):
                    signals.append(q);break
        event_variant[sym]={"all_crossings":int(len(crossed)),
                            "qualified_no_cooldown":int(len(signals))}
        event=np.zeros(n,dtype=bool)
        event[signals]=True
        bars.loc[p,"rebuild"]=event
        recent=np.maximum.accumulate(np.where(event,tid,-100000))
        bars.loc[p,"last_signal_age"]=tid-recent
    # Valid observation is one with full 26-trading-day historical return,
    # valid forward 20, plus T+1 open.  Excludes 511220 from signals.
    bars=bars[(bars.date>=FIRST)&(bars.date<=LAST)].copy()
    required=["ret5","ret10","ret26","net5","net10","net20"]
    bars=bars[bars[required].notna().all(axis=1)].copy()
    risk=bars[bars.symbol.isin(FIX14)].copy()
    cash=bars[bars.symbol.eq(BENCH)].copy()
    if len(risk.symbol.unique())!=14:raise RuntimeError("Missing risk ETF(s)")
    if cash.empty:raise RuntimeError("No cash benchmark")
    info={"file_sha256":sha,"archive_all_symbols":total,"archive_all_rows":rows,
          "pool":list(FIX14),"cash_comparator":BENCH,
          "coverage":coverage,"panel_risk_rows":len(risk),
          "panel_dates":int(risk.date.nunique()),"signal_raw":int(risk.rebuild.sum()),
          "signal_first":str(risk.loc[risk.rebuild,"date"].min().date()),
          "signal_last":str(risk.loc[risk.rebuild,"date"].max().date()),
          "signals_by_symbol":event_variant}
    return risk,cash,info


def select_events(risk, cooldown=20):
    # Qualification events are already unique per crossing, but two crossings
    # might be very close. Apply optional cooldown on each symbol's valid dates.
    g=risk.sort_values(["symbol","tid"])
    pieces=[]
    for sym, sub in g.groupby("symbol",sort=True):
        prior=-100000
        for r in sub[sub.rebuild].itertuples(index=False):
            if r.tid-prior<cooldown:continue
            prior=r.tid
            pieces.append({"symbol":sym,"date":r.date,"tid":int(r.tid),
                           "group":r.group,"score":float(r.score),
                           "ret5":float(r.ret5),"ret10":float(r.ret10),"ret26":float(r.ret26),
                           **{f"net{h}":float(getattr(r,f"net{h}")) for h in HORIZONS}})
    return pd.DataFrame(pieces)


def make_panel(events,risk,cash):
    # Event-level cross-section outcomes: mean of every contemporaneous
    # other active risk ETF (excluding the event ETF), and 511220.
    sorted_r=risk.sort_values(["date","symbol"])
    bydate={d:g for d,g in sorted_r.groupby("date")}
    bycash=cash.set_index("date")
    out=[]
    for t in events.itertuples(index=False):
        crowd=bydate[t.date]
        others=crowd[crowd.symbol.ne(t.symbol)]
        if len(others)<3 or t.date not in bycash.index:continue
        baseline=bycash.loc[t.date]
        row=dict(date=str(t.date.date()),year=t.date.year,month=str(t.date)[:7],
                 symbol=t.symbol, group=t.group,score=t.score, alternative_n=len(others))
        for h in HORIZONS:
            y=float(getattr(t,f"net{h}"))
            row.update({f"signal{h}":y,
                        f"peers{h}":float(others[f"net{h}"].mean()),
                        f"cash{h}":float(baseline[f"net{h}"]),
                        f"excess_peers{h}":y-float(others[f"net{h}"].mean()),
                        f"excess_cash{h}":y-float(baseline[f"net{h}"])})
        out.append(row)
    return pd.DataFrame(out)


def matched(events,risk,group_only=False,caliper=True):
    # Same-date event vs one eligible non-rebuild control.
    # Control must not have qualified within past 20 sessions.
    # Distance in historical 5/10/26-day returns; no future feature.
    controls=risk[~risk.rebuild & (risk.last_signal_age>20)].copy()
    bydate={d:g for d,g in controls.groupby("date")}
    matched=[]
    for d, eg in events.groupby("date"):
        pool=bydate.get(d)
        if pool is None:continue
        used=set()
        for t in eg.sort_values(["score","symbol"],ascending=[False,True]).itertuples(index=False):
            c=pool[pool.symbol.ne(t.symbol)&~pool.symbol.isin(used)].copy()
            if group_only:c=c[c.group.eq(t.group)]
            if c.empty:continue
            dif=np.abs(c[["ret5","ret10","ret26"]].to_numpy(float)-
                       np.array([t.ret5,t.ret10,t.ret26]))
            eligible=np.all(dif<=CALIPER,axis=1) if caliper else np.ones(len(c),dtype=bool)
            if not eligible.any():continue
            dist=(dif / CALIPER)**2
            dist=dist.sum(axis=1)
            dist[~eligible]=np.inf
            ix=int(np.argmin(dist))
            peer=c.iloc[ix]
            used.add(peer.symbol)
            row=dict(date=str(d.date()),month=str(d)[:7],year=int(d.year),
                     symbol=t.symbol,control=peer.symbol,group=t.group,
                     distance=float(dist[ix]),
                     d_ret5=float(dif[ix,0]),d_ret10=float(dif[ix,1]),d_ret26=float(dif[ix,2]))
            for h in HORIZONS:
                row.update({f"signal{h}":float(getattr(t,f"net{h}")),
                            f"control{h}":float(peer[f"net{h}"]),
                            f"excess{h}":float(getattr(t,f"net{h}")-peer[f"net{h}"])})
            matched.append(row)
    return pd.DataFrame(matched)


def monthly_ci(frame,key,seed=SEED,n=2000):
    if frame.empty:return None
    groups=frame.groupby("month")[key].agg(["sum","count"])[["sum","count"]].to_numpy(float)
    rng=np.random.default_rng(seed)
    idx=rng.integers(0,len(groups),size=(n,len(groups)))
    means=groups[idx,0].sum(axis=1)/groups[idx,1].sum(axis=1)
    return [round(float(x)*100,3) for x in np.quantile(means,[.025,.975])]


def stats(frame,style="peers",paired=False):
    if frame.empty:return {"n":0}
    out={"n":int(len(frame)), "dates":int(frame.date.nunique()),
         "months":int(frame.month.nunique()),"symbols":int(frame.symbol.nunique())}
    for h in HORIZONS:
        base = f"control{h}" if paired else f"{style}{h}"
        excess = f"excess{h}" if paired else f"excess_{style}{h}"
        s=frame[f"signal{h}"];b=frame[base];e=frame[excess]
        temp=frame.groupby(["date","month"],as_index=False)[excess].mean()
        out[str(h)]={"signal_mean_pct":round(float(s.mean()*100),3),
                     "baseline_mean_pct":round(float(b.mean()*100),3),
                     "excess_mean_pp":round(float(e.mean()*100),3),
                     "excess_median_pp":round(float(e.median()*100),3),
                     "signal_win_rate_pct":round(float((s>0).mean()*100),1),
                     "beat_baseline_pct":round(float((e>0).mean()*100),1),
                     "ci95_month_pp":monthly_ci(frame,excess,seed=SEED+h),
                     "day_equal_excess_pp":round(float(temp[excess].mean()*100),3),
                     "day_equal_ci95_pp":monthly_ci(temp,excess,seed=SEED+100+h)}
    return out


def segments(frame,style="peers",paired=False):
    if frame.empty:return {"all":{"n":0}}
    return {"all":stats(frame,style,paired),
            "train_2021_24":stats(frame[frame.year<=2024],style,paired),
            "test_2025_26":stats(frame[frame.year>=2025],style,paired),
            "years":{str(yr):stats(x,style,paired) for yr,x in frame.groupby("year")}}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--parquet",required=True)
    parser.add_argument("--out",default="research/fix14_rebuild/output")
    args=parser.parse_args()
    dest=Path(args.out);dest.mkdir(parents=True,exist_ok=True)
    risk,cash,info=load_panel(args.parquet)
    events=select_events(risk,cooldown=20)
    zero=select_events(risk,cooldown=0)
    observations=make_panel(events,risk,cash)
    observations.to_csv(dest/"events_with_alternatives.csv.gz",compression="gzip",index=False)
    result={"run":"fix14_original_wols26_20261113","source":info,
            "definition":"26 weighted OLS close crossing from <=0 to >0, first D1-D3 R2 rising above prior day and crossing date, 20 same-symbol cooldown",
            "transaction":"T close signal, T+1 open to T+(H+1) open, 0.06% per side",
            "risk_baseline":"same-date equal-weight other currently trading eligible fixed-pool members (net fee for each carrier)",
            "cash_baseline":"511220 risk-free/protection comparator, net same fees",
            "unmatched_limits":"2021-2026 current fixed pool retrospectively applied; assumes future bars for evaluation; no QDII NAV premiums, delisted correction or actual intraday execution",
            "no_cooldown_signal_count":len(zero),
            "cooldown_events":len(events),
            "baseline_peers":segments(observations),
            "baseline_cash":segments(observations,"cash"),
            "rank1_on_signal_dates":{},
            "matched":{}}
    # If multiple newly qualified on same date, preselect highest contemporary score.
    top=events.sort_values(["date","score","symbol"],ascending=[True,False,True]).drop_duplicates("date")
    result["rank1_on_signal_dates"] = segments(make_panel(top,risk,cash))
    for label,grp,cal in [("nearest_any_14",False,False),
                          ("momentum_caliper",False,True),
                          ("risk_group_only",True,False),
                          ("risk_group_and_caliper",True,True)]:
        m=matched(events,risk,grp,cal)
        if len(m):
            m.to_csv(dest/(label+".csv.gz"),compression="gzip",index=False)
        rec={"match_rate":round(len(m)/len(events),3) if len(events) else 0,
             "results":segments(m,paired=True)}
        if len(m):
            rec["avg_abs_past_momentum_gap_pp"]={
                f"ret{k}":round(float(m[f"d_ret{k}"].mean()*100),3) for k in (5,10,26)}
        result["matched"][label]=rec
    # Stress check for 2026 splice window, and removing first year.
    no_seam=observations[~observations.date.between("2026-06-01","2026-09-01")]
    result["exclude_2026_seam"]=segments(no_seam)
    # Raw event replay without arbitrary 20d suppression.
    result["no_cooldown"]=segments(make_panel(zero,risk,cash))
    result["per_symbol"]={sym:stats(g) for sym,g in observations.groupby("symbol")}
    (dest/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    lines=["# 固定14只OLS风险资产的原始重建信号独立价值检验", "",
           "正式名单来自 `strategy/main.py:RISK_POOL`（14只）；不含511220城投债与513500 Carrier，亦不含巴西。",
           "2021-01-01至2026-10-13信号，价格数据冻结至2026-11-11；信号后第1个交易日开盘买入，持有5/10/20交易日后开盘卖出。",
           "26日加权OLS，D0 annual由非正转正，D1-D3首个R²较前日及D0改善信号；同基金间隔至少20日。",
           "按每边0.06%交易费；仅事件平均，不等于并行资金分配组合收益。", ""]
    lines.extend([f"源文件SHA256: {info['file_sha256']}",
                  f"14只池内有效信号 {len(events)}，无冷却 {len(zero)}，首次/最后 {info['signal_first']} / {info['signal_last']}。",""])
    def fmt(label,item):
        lines.extend(["## "+label,""])
        for seg in ["all","train_2021_24","test_2025_26"]:
            z=item[seg];lines.append(f"### {seg} (n={z['n']})")
            if not z["n"]:continue
            for h in HORIZONS:
                p=z[str(h)]
                lines.append(
                    f"- {h}日：重建 {p['signal_mean_pct']:+.3f}%，对照 {p['baseline_mean_pct']:+.3f}%，差 {p['excess_mean_pp']:+.3f}pp，95%月区块CI {p['ci95_month_pp']}，打败对照 {p['beat_baseline_pct']:.1f}%；日等权差 {p['day_equal_excess_pp']:+.3f}pp")
        lines.append("按年度10日： "+"；".join(
            f"{y} n={r['n']} 重建 {r['10']['signal_mean_pct']:+.3f}%，超额 {r['10']['excess_mean_pp']:+.3f}pp"
            for y,r in item["years"].items() if r["n"])+"")
        lines.append("")
    fmt("同日其余13只等权风险基准",result["baseline_peers"])
    fmt("511220城投债比较器",result["baseline_cash"])
    fmt("当天有多只新重建时只选score最高一只",result["rank1_on_signal_dates"])
    for name,record in result["matched"].items():
        lines.extend([f"## 控制组匹配：{name}，匹配率{record['match_rate']:.1%}", ""])
        if record["results"]["all"]["n"]:fmt(name,record["results"])
    fmt("无20日冷却（每次新翻正都可触发）",result["no_cooldown"])
    fmt("排除2026-06-01至09-01拼接可疑窗口",result["exclude_2026_seam"])
    lines.extend(["## 局限与解释",
       "- 固定2026池回溯2021；部分ETF当时尚未上市，样本数量和风险暴露随年份变化；这不是同时可用14只的无前视建池实盘。",
       "- 同日其余基金等权是市场基线，不是交易信号；其中可包含尚未重建或已经成熟的趋势。",
       "- 14只横跨A股、美股、黄金、商品、印度与转债，同日最近动量配对可能跨资产；同风险组匹配样本少、结果可能不稳定。",
       "- 月区块bootstrap不能完全去除重叠事件的截面相关性。严格执行应补缺失NAV溢价、开盘风险与停牌。",
       "- 本测试不改变原Top1系统策略，也不将重建结果视为自动买入许可。"])
    (dest/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf8")
    print("AUDIT_DONE",json.dumps({"pool":list(FIX14),"event_count":len(events),
                                "baseline_test_10":result["baseline_peers"]["test_2025_26"]["10"],
                                "matched_test_10":result["matched"]["momentum_caliper"]["results"]["test_2025_26"].get("10")},
                                ensure_ascii=False),flush=True)

if __name__=="__main__":main()
