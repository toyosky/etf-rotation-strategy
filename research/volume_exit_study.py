#!/usr/bin/env python3
from __future__ import annotations
import os
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

import sys
RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))
from full_market_ols_storage import _db_url, load_daily_bars, feature_one_symbol

RISK_POOL = ["159934","159985","161226","513100","159957","159509","513290","159529","159981","501018","513530","511380","164824"]
CASH = "511220"
POOL = RISK_POOL + [CASH]
START = pd.Timestamp("2021-01-01")
OUT = Path("research/volume_exit_study_20260930.md")

def fmt(x):
    return "NA" if pd.isna(x) else f"{100*x:+.2f}%"

def main():
    raw = os.environ["ETF_DAILY_BARS_DATABASE_URL"]
    eng = create_engine(_db_url(raw))
    bars = load_daily_bars(eng)
    bars = bars[bars.symbol.astype(str).str.zfill(6).isin(POOL)].copy()
    bars["symbol"] = bars.symbol.astype(str).str.zfill(6)

    parts=[]
    for sym,g in bars.groupby("symbol",sort=False):
        f=feature_one_symbol(g)
        # Production fixed-pool eligibility: positive weighted OLS and no 3-day <-3% event.
        f["eligible_prod"]=(f["annual"]>0)&(f["r2"]>0)&(f["score"]>0)&(~f["recent_drop3"].fillna(False))
        f["amount20_prev"]=f["amount"].shift(1).rolling(20,min_periods=20).mean()
        f["vol_ratio20"]=f["amount"]/f["amount20_prev"]
        f["high_close_dd"]=1-f["close"]/f["high"]
        for h in (1,3,5,10):
            f[f"fwd{h}"]=f["close"].shift(-h)/f["close"]-1
        parts.append(f)
    f=pd.concat(parts,ignore_index=True)

    cash=f[f.symbol==CASH][["date","score","close"]+[f"fwd{h}" for h in (1,3,5,10)]].copy()
    cash=cash.rename(columns={"score":"cash_score","close":"cash_close",**{f"fwd{h}":f"cash_fwd{h}" for h in (1,3,5,10)}})

    risk=f[(f.symbol.isin(RISK_POOL)) & f.eligible_prod].copy()
    risk["rank"]=risk.groupby("date")["score"].rank(method="first",ascending=False)
    top=risk[risk["rank"]==1].merge(cash,on="date",how="left")
    top=top[(top.date>=START)&(top.score>top.cash_score.fillna(0))].sort_values("date").copy()

    # Episode / held-profit state for the raw OLS leader.
    top["switch"]=top.symbol.ne(top.symbol.shift(1)) | (top.date.diff().dt.days>7)
    top["episode"]=top["switch"].cumsum()
    top["episode_entry_close"]=top.groupby("episode")["close"].transform("first")
    top["episode_gain"]=top["close"]/top["episode_entry_close"]-1
    top["hold_day"]=top.groupby("episode").cumcount()+1
    top["score_delta1"]=top.groupby("symbol")["score"].diff()

    for h in (1,3,5,10):
        top[f"excess_cash{h}"]=top[f"fwd{h}"]-top[f"cash_fwd{h}"]

    top["period"]=np.where(top.date.dt.year<=2024,"2021-2024","2025-2026")
    top["vol_bin"]=pd.cut(top.vol_ratio20,[-np.inf,1,1.5,2,3,np.inf],
                          labels=["<1.0x","1.0-1.5x","1.5-2.0x","2.0-3.0x",">=3.0x"],right=False)

    def summarize(df,label):
        rows=[]
        for period,g in list(df.groupby("period"))+[("ALL",df)]:
            rows.append({
                "sample":label,"period":period,"n":len(g),
                "f1":g.fwd1.mean(),"f3":g.fwd3.mean(),"f5":g.fwd5.mean(),"f10":g.fwd10.mean(),
                "xc3":g.excess_cash3.mean(),"xc5":g.excess_cash5.mean(),
                "win5":(g.fwd5>0).mean() if len(g) else np.nan,
                "epgain":g.episode_gain.mean(),
            })
        return rows

    rows=[]
    rows+=summarize(top,"All held Top1 days")
    for name,mask in [
        ("Vol>=1.5x",top.vol_ratio20>=1.5),
        ("Vol>=2.0x",top.vol_ratio20>=2.0),
        ("DD>=1%",top.high_close_dd>=.01),
        ("DD>=2%",top.high_close_dd>=.02),
        ("Vol>=1.5x & DD>=1%",(top.vol_ratio20>=1.5)&(top.high_close_dd>=.01)),
        ("Vol>=2.0x & DD>=1%",(top.vol_ratio20>=2)&(top.high_close_dd>=.01)),
        ("Vol>=1.5x & DD>=2%",(top.vol_ratio20>=1.5)&(top.high_close_dd>=.02)),
        ("Vol>=2.0x & DD>=2%",(top.vol_ratio20>=2)&(top.high_close_dd>=.02)),
        ("Vol>=1.5x & DD>=1% & profit>0",(top.vol_ratio20>=1.5)&(top.high_close_dd>=.01)&(top.episode_gain>0)),
        ("Vol>=2.0x & DD>=1% & profit>0",(top.vol_ratio20>=2)&(top.high_close_dd>=.01)&(top.episode_gain>0)),
        ("Vol>=1.5x & DD>=1% & profit>=3%",(top.vol_ratio20>=1.5)&(top.high_close_dd>=.01)&(top.episode_gain>=.03)),
        ("Vol>=2.0x & DD>=1% & profit>=3%",(top.vol_ratio20>=2)&(top.high_close_dd>=.01)&(top.episode_gain>=.03)),
    ]:
        rows+=summarize(top[mask],name)
    s=pd.DataFrame(rows)

    # Coarse 2D matrix, no threshold optimization.
    matrix=[]
    for vb,vg in top.groupby("vol_bin",observed=True):
        for dd_label,lo,hi in [("<0.5%",0,.005),("0.5-1%",.005,.01),("1-2%",.01,.02),(">=2%",.02,np.inf)]:
            g=vg[(vg.high_close_dd>=lo)&(vg.high_close_dd<hi)]
            if len(g):
                matrix.append((str(vb),dd_label,len(g),g.fwd3.mean(),g.fwd5.mean(),g.excess_cash5.mean()))
    m=pd.DataFrame(matrix,columns=["Volume20","HighCloseDD","n","Fwd3","Fwd5","Fwd5_vs_cash"])

    # Best-supported predeclared candidate = compare fixed simple rules; require >=20 events overall and both eras present.
    candidates=[]
    for vr in (1.5,2.0,2.5):
        for dd in (.005,.01,.015,.02):
            mask=(top.vol_ratio20>=vr)&(top.high_close_dd>=dd)&(top.episode_gain>0)
            g=top[mask]
            old=g[g.period=="2021-2024"]; new=g[g.period=="2025-2026"]
            candidates.append({
                "vr":vr,"dd":dd,"n":len(g),"n_old":len(old),"n_new":len(new),
                "f5":g.fwd5.mean(),"xc5":g.excess_cash5.mean(),
                "old_f5":old.fwd5.mean(),"new_f5":new.fwd5.mean(),
            })
    c=pd.DataFrame(candidates)
    c["robust"]=(c.n>=20)&(c.n_old>=8)&(c.n_new>=8)&(c.old_f5<0)&(c.new_f5<0)&(c.xc5<0)

    lines=[]
    lines.append("# Volume-based exit / take-profit event study — 2026-09-30")
    lines.append("")
    lines.append("## Design")
    lines.append("")
    lines.append("- Universe: current FixV2 13 risk assets + 511220 comparator.")
    lines.append("- OLS: frozen 26-price weighted log-price OLS, half-life 10, annualization 250.")
    lines.append("- Held-day sample: daily raw risk Top1 is production-eligible and score > 511220 score.")
    lines.append("- VolumeRatio20 = current turnover amount / mean turnover amount of the strictly prior 20 sessions.")
    lines.append("- HighCloseDD = 1 - close/high. This is a daily proxy for intraday high drawdown, not a 14:05 executable minute signal.")
    lines.append("- Take-profit subsets additionally require current raw-Top1 episode gain > 0 or >=3%.")
    lines.append("- Outcomes: same asset future close-to-close 1/3/5/10d return and excess versus holding 511220.")
    lines.append("- Thresholds are a coarse predeclared grid; no in-sample optimum is promoted as a rule.")
    lines.append("")
    lines.append(f"Sample: {len(top)} held Top1-days, {top.date.min().date()} to {top.date.max().date()}.")
    lines.append("")
    lines.append("## Key cuts")
    lines.append("")
    lines.append("| Signal | Period | n | Fwd1 | Fwd3 | Fwd5 | Fwd10 | Fwd5 vs cash | Win5 | Avg episode gain |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    show=s[s["sample"].isin(["All held Top1 days","Vol>=1.5x","Vol>=2.0x","DD>=1%","DD>=2%","Vol>=1.5x & DD>=1%","Vol>=2.0x & DD>=1%","Vol>=1.5x & DD>=1% & profit>0","Vol>=2.0x & DD>=1% & profit>0","Vol>=1.5x & DD>=1% & profit>=3%","Vol>=2.0x & DD>=1% & profit>=3%"])]
    for _,r in show.iterrows():
        lines.append(f"| {r['sample']} | {r['period']} | {int(r.n)} | {fmt(r.f1)} | {fmt(r.f3)} | {fmt(r.f5)} | {fmt(r.f10)} | {fmt(r.xc5)} | {r.win5:.1%} | {fmt(r.epgain)} |")
    lines.append("")
    lines.append("## 2D event matrix")
    lines.append("")
    lines.append("| VolumeRatio20 | High→Close DD | n | Fwd3 | Fwd5 | Fwd5 vs cash |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for _,r in m.iterrows():
        lines.append(f"| {r.Volume20} | {r.HighCloseDD} | {int(r.n)} | {fmt(r.Fwd3)} | {fmt(r.Fwd5)} | {fmt(r.Fwd5_vs_cash)} |")
    lines.append("")
    lines.append("## Robustness screen for take-profit candidates")
    lines.append("")
    lines.append("A candidate passes only if: n>=20, each era has >=8 events, 5d future return is negative in both 2021-24 and 2025-26, and overall 5d excess vs 511220 is negative.")
    lines.append("")
    lines.append("| Vol threshold | DD threshold | n | 2021-24 n/Fwd5 | 2025-26 n/Fwd5 | All Fwd5 | Fwd5 vs cash | Pass |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|:---:|")
    for _,r in c.iterrows():
        lines.append(f"| {r.vr:.1f}x | {r.dd:.1%} | {int(r.n)} | {int(r.n_old)} / {fmt(r.old_f5)} | {int(r.n_new)} / {fmt(r.new_f5)} | {fmt(r.f5)} | {fmt(r.xc5)} | {'YES' if r.robust else 'NO'} |")
    lines.append("")
    passed=c[c.robust]
    lines.append("## Machine conclusion")
    lines.append("")
    if passed.empty:
        lines.append("No coarse candidate passes the cross-era robustness screen. Do not add a volume-based hard exit rule from daily data yet.")
    else:
        p=passed.sort_values(["xc5","n"],ascending=[True,False]).iloc[0]
        lines.append(f"At least one coarse candidate passes. Most defensive passing candidate by 5d excess-vs-cash: VolumeRatio20 >= {p.vr:.1f}x AND HighCloseDD >= {p.dd:.1%}, conditional on episode profit > 0. Treat as a research candidate, not production, pending minute-level execution validation.")
    lines.append("")
    lines.append("## Limitation")
    lines.append("")
    lines.append("Historical minute coverage is insufficient for a full 14:05 high-drawdown backtest. The daily High→Close proxy can establish whether the economic mechanism exists; executable intraday timing must be validated prospectively with minute bars.")
    OUT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))

if __name__=="__main__":
    main()
