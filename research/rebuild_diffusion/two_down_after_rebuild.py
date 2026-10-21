#!/usr/bin/env python3
"""Research: two successive DOWN days AFTER an observed R2 category rebuild.

Uses the already calculated daily, survivorship-biased CATEGORY ONSET leader
events, fixing the leader at T close (highest 60d amount, not chosen ex-post).
T+1 and T+2 must each close below preceding A-share-session close.
If triggered, enter at T+3 OPEN. Compare buying at T+1 OPEN.
Shared-exit comparison isolates execution-timing effect. Holding-based
comparison shows conditional forward returns from own entry date.
No fees/premium/new signal source or live trading code modified.
"""
import argparse
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd
from automation.build_fundamental_audit_trigger import calc_ols

HORIZONS=(5,10,20)
THRESHOLDS=(0.0,0.001,0.003) # each down >= 0, 0.1%, 0.3%

def summarize(a):
    a=np.asarray([float(x) for x in a if x is not None and np.isfinite(x)],dtype=float)
    if len(a)==0:
        return {"n":0,"mean_pct":None,"median_pct":None,"positive_pct":None,"p10_pct":None,
                "p90_pct":None}
    return {"n":len(a),"mean_pct":round(float(np.mean(a)*100),3),
            "median_pct":round(float(np.median(a)*100),3),
            "positive_pct":round(float(np.mean(a>0)*100),1),
            "p10_pct":round(float(np.quantile(a,.1)*100),3),
            "p90_pct":round(float(np.quantile(a,.9)*100),3)}

def entry_metrics(rows,label,h):
    return summarize([r.get(label,{}).get(str(h)) for r in rows])

def drawdown(g,start_date,end_date,entry):
    # Must use dated index, never global calendar index on individual ETF rows.
    if start_date not in g.index or end_date not in g.index:
        return None
    series=np.r_[entry,g.loc[start_date:end_date,"close"].to_numpy(dtype=float)]
    peak=np.maximum.accumulate(series)
    return float(np.min(series/peak-1))

def per_event(x,stocks,trading_dates,idx):
    sym=x["leader_symbol"]
    p=stocks.get(sym)
    t=idx.get(x["onset_date"])
    if p is None or t is None or t+23>=len(trading_dates):return None
    date0=trading_dates[t]
    ds=trading_dates[t:t+23]
    if not all(d in p.index for d in ds[:4]):return None
    c0=float(p.at[ds[0],"close"]);c1=float(p.at[ds[1],"close"]);c2=float(p.at[ds[2],"close"])
    open1=float(p.at[ds[1],"open"]);open3=float(p.at[ds[3],"open"])
    if min(c0,c1,c2,open1,open3)<=0:return None
    d1=c1/c0-1;d2=c2/c1-1
    trigger={str(th):bool(d1< -th and d2< -th) for th in THRESHOLDS}
    # State is recomputed at second-down close from prices known through T+2.
    prices_to_t2=p.loc[:ds[2],"close"].to_numpy(dtype=float)
    ann,r2=calc_ols(prices_to_t2)
    trend_alive=bool(np.isfinite(ann[-1]) and ann[-1]>0)
    trend_rebuild=bool(trend_alive and np.isfinite(r2[-1]) and np.isfinite(r2[-2])
                       and r2[-1]>r2[-2])
    delta_r2=float(r2[-1]-r2[-2]) if np.isfinite(r2[-1]) and np.isfinite(r2[-2]) else None
    ans={"category":x["category"],"onset_date":date0,"symbol":sym,
         "leader_onset_n":x["leaders_onset_n"],
         "leader_volume_3v20":x.get("leader_volume_3v20"),
         "d1_pct":round(d1*100,4),"d2_pct":round(d2*100,4),
         "two_day_pct":round((c2/c0-1)*100,4),
         "pattern":trigger,"annual_positive_after_two_down":trend_alive,
         "r2_still_improving_after_two_down":trend_rebuild,
         "r2_change_after_two_down":delta_r2,
         "buy_next_open":ds[1],"buy_after_two_down_open":ds[3],
         "buy_price_advantage_pct":round((1-open3/open1)*100,4),
         "same_exit_early":{},"same_exit_delayed":{},
         "entry_hold_early":{},"entry_hold_delayed":{},
         "mdd_hold_early":{},"mdd_hold_delayed":{}}
    for h in HORIZONS:
        end_same=t+h; end_e=t+h; end_d=t+2+h
        for name,pos,base,exitidx in [
            ("same_exit_early",t+1,open1,end_same),
            ("same_exit_delayed",t+3,open3,end_same),
            ("entry_hold_early",t+1,open1,end_e),
            ("entry_hold_delayed",t+3,open3,end_d)]:
            val=None
            if exitidx<len(trading_dates):
                end_date=trading_dates[exitidx]
                if end_date in p.index:
                    val=float(p.at[end_date,"close"])/base-1
            ans[name][str(h)]=val
        ans["mdd_hold_early"][str(h)]=(
            drawdown(p,ds[1],trading_dates[end_e],open1) if
            all(trading_dates[k] in p.index for k in range(t+1,min(end_e+1,len(trading_dates)))) else None)
        ans["mdd_hold_delayed"][str(h)]=(
            drawdown(p,ds[3],trading_dates[end_d],open3) if
            end_d<len(trading_dates) and
            all(trading_dates[k] in p.index for k in range(t+3,end_d+1)) else None)
    return ans

def aggregate(rows,pattern):
    def analyze(sub):
        result={"events":len(sub),"by_horizon":{}}
        for h in HORIZONS:
            m=str(h)
            a=[x["same_exit_early"][m] for x in sub]
            b=[x["same_exit_delayed"][m] for x in sub]
            paired=[(i,j) for i,j in zip(a,b) if i is not None and j is not None]
            result["by_horizon"][m]={
                "early_same_exit":summarize([i for i,j in paired]),
                "delayed_same_exit":summarize([j for i,j in paired]),
                "delay_minus_early_same_exit":summarize([j-i for i,j in paired]),
                "early_equal_hold":entry_metrics(sub,"entry_hold_early",h),
                "delayed_equal_hold":entry_metrics(sub,"entry_hold_delayed",h),
                "early_mdd":entry_metrics(sub,"mdd_hold_early",h),
                "delayed_mdd":entry_metrics(sub,"mdd_hold_delayed",h)}
        return result
    done=[x for x in rows if x["pattern"][str(pattern)]]
    failed=[x for x in rows if not x["pattern"][str(pattern)]]
    out={"population":len(rows),"triggered":len(done),
         "trigger_pct":round(100*len(done)/len(rows),1) if rows else None,
         "conditional_wait_trade":analyze(done),
         "no_trigger_early_trade":analyze(failed),
         "conditional_trend_alive":{
             "n":sum(x["annual_positive_after_two_down"] for x in done),
             "pct":round(100*sum(x["annual_positive_after_two_down"] for x in done)/len(done),1)
                   if done else None},
         "r2_still_improving":{
             "n":sum(x["r2_still_improving_after_two_down"] for x in done),
             "pct":round(100*sum(x["r2_still_improving_after_two_down"] for x in done)/len(done),1)
                   if done else None},
         "buy_price_advantage_pct":summarize([x["buy_price_advantage_pct"]/100 for x in done]),
         "conditional_buy_only_vs_always_early_at_fixed_signal_exit":{}}
    for h in HORIZONS:
        m=str(h)
        trigger_y=[x["same_exit_delayed"][m] for x in done]
        early_y=[x["same_exit_early"][m] for x in rows]
        # Each category episode equally weighted; non-trigger stays in cash
        out["conditional_buy_only_vs_always_early_at_fixed_signal_exit"][m]={
            "conditional_no_trade_cash_return_pct":round(100*sum(y or 0 for y in trigger_y)/len(rows),3)
                                                      if rows else None,
            "always_early_mean_pct":summarize(early_y)["mean_pct"],
            "note":"Nontrigger episodes earn 0 in cash, but opportunity cost and capital deployment differ."}
    alive=[x for x in done if x["annual_positive_after_two_down"]]
    dead=[x for x in done if not x["annual_positive_after_two_down"]]
    out["trigger_and_annual_positive"]=analyze(alive)
    out["trigger_and_annual_nonpositive"]=analyze(dead)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--parquet",required=True)
    ap.add_argument("--events",default="research/rebuild_diffusion/historical_diffusion_results.json")
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    original=json.loads(Path(args.events).read_text())
    if original.get("summary",{}).get("episode_count",0)<100:
        raise RuntimeError("Insufficient historical events")
    events=original["events"]
    codes=sorted(set(x["leader_symbol"] for x in events))
    data=pd.read_parquet(args.parquet,columns=["symbol","date","open","close"])
    data["symbol"]=data.symbol.astype(str).str.zfill(6)
    data=data[data.symbol.isin(codes)].copy()
    data["date"]=pd.to_datetime(data.date).dt.strftime("%Y-%m-%d")
    data=data.sort_values(["symbol","date"]).drop_duplicates(["symbol","date"],keep="last")
    # Pooled A-share trading calendar; no cross-border index synchronized here.
    cal=sorted(set(data.date.values))
    dates={d:i for i,d in enumerate(cal)}
    stocks={k:v.set_index("date")[["open","close"]] for k,v in data.groupby("symbol")}
    rows=[per_event(x,stocks,cal,dates) for x in events]
    valid=[x for x in rows if x is not None]
    group=defaultdict(list)
    for x in valid:group[x["category"]].append(x)
    result={"version":"post_rebuild_two_down_v1",
       "as_of":"2026-10-20",
       "population":"Historical category first-rebuild leader (one ETF per category episode; not all ETF signals)",
       "entry":"Signal T close; early buy T+1 open; if close T+1 < close T AND close T+2 < close T+1, delayed buy T+3 open",
       "down_return_thresholds":THRESHOLDS,
       "exit_comparisons":"same onset-relative T+5/10/20 close AND equal 5/10/20-session entry-based horizon",
       "dataset":"current listed 336 classified ETFs; current metadata creates survivor bias",
       "limitations":["No premiums, transaction fees, execution slippage or HK underlying market calendar confirmation",
            "Daily HFQ prices may be rounded to 0.01; use thresholds 0.1/0.3% as robustness checks",
            "Classifications can be broad and correlated; one leading ETF selected at T by 60d liquidity",
            "All paired comparisons conditional on two future DOWN days and are NOT an ex-ante choice at T",
            "For an actual deferred trade, decision only occurs after T+2 close",
            "No optimize/test split; descriptive historical exploration; not executable recommendation"],
       "population_events":len(events),"eligible_complete_events":len(valid),
       "excluded_missing_or_recent":len(events)-len(valid),
       "summary":{str(t):aggregate(valid,t) for t in THRESHOLDS},
       "by_category":{cat:{str(t):aggregate(g,t) for t in THRESHOLDS}
                      for cat,g in group.items()},
       "by_year":{year:{str(t):aggregate([x for x in valid if x["onset_date"].startswith(year)],t)
                        for t in THRESHOLDS}
                  for year in sorted(set(x["onset_date"][:4] for x in valid))},
       "events":valid}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps({"status":"OK","events":len(valid),
        "threshold0":{k:result["summary"]["0.0"][k] for k in ("population","triggered","trigger_pct","conditional_trend_alive","r2_still_improving")},
        "horizons":result["summary"]["0.0"]["conditional_wait_trade"]["by_horizon"]},ensure_ascii=False))

if __name__=="__main__":
    main()
