#!/usr/bin/env python3
"""Retrospective cash-flow factor study BEFORE the Oct 16-20 ETF R2 onset.

Use close/amount only through 2026-10-20. Three verified index families each
receive ONE equal vote, independently of the number of funds in that family.
ETF prices are price PROXIES (not underlying index levels nor fund flows).
Outputs historical returns vs wide-market, finance, growth and consumer ETF
benchmarks. No trading/ranking rule modified. No survivorship correction.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd
from automation.build_fundamental_audit_trigger import calc_ols

ASOF="2026-10-20"
BEGIN="2026-05-01"
GROUPS={
    "CSI800_CASHFLOW":["159119","159229","516460","563580","563680","563990"],
    "GUOZHENG_CASHFLOW":["159201","159222","159276"],
    "FTSE_A_CASHFLOW":["159399"],
}
BENCHMARKS={
    "CSI300_510300":"510300",
    "CSI500_510500":"510500",
    "CSI800_515800":"515800",
    "DIVIDEND_510880":"510880",
    "BANKS_512800":"512800",
    "CONSUMER_159928":"159928",
    "GROWTH_159915":"159915",
    "GROWTH_159957":"159957",
    "TECH_588000":"588000",
}
POINTS=["2026-06-01","2026-07-01","2026-08-03","2026-08-17",
        "2026-09-01","2026-09-15","2026-09-30","2026-10-09",
        "2026-10-15","2026-10-16","2026-10-19","2026-10-20"]
WINDOWS=[("JUL1_TO_AUG3","2026-07-01","2026-08-03"),
         ("AUG3_TO_SEP1","2026-08-03","2026-09-01"),
         ("SEP1_TO_SEP30","2026-09-01","2026-09-30"),
         ("JUL1_TO_SEP30","2026-07-01","2026-09-30"),
         ("SEP30_TO_OCT15","2026-09-30","2026-10-15"),
         ("OCT9_TO_OCT15","2026-10-09","2026-10-15"),
         ("OCT15_TO_OCT20","2026-10-15","2026-10-20"),
         ("AUG3_TO_OCT15","2026-08-03","2026-10-15"),
         ("JUL1_TO_OCT15","2026-07-01","2026-10-15")]
def num(x,n=3):
    try:return round(float(x),n) if np.isfinite(x) else None
    except (ValueError,TypeError):return None

def stats_ols(s):
    x=s.dropna().astype(float)
    if len(x)<30:return {"last_annual":None,"last_r2":None,"cross_dates":[],"qualification_dates":[]}
    annual,r2=calc_ols(x.to_numpy(dtype=float))
    cross=np.flatnonzero((annual[1:]>1e-8)&(annual[:-1]<=1e-8))+1
    qualified=[]
    for i in cross:
        for k in range(i+1,min(i+4,len(x))):
            if (annual[k]>0 and r2[k]>r2[k-1]+1e-12
                    and r2[k]>r2[i]+1e-12):
                qualified.append({"first_qualified_date":str(x.index[k].date()),"cross_date":str(x.index[i].date()),"r2":num(r2[k],4),"annual":num(annual[k],4)})
                break
    return {"last_annual":num(annual[-1],5),"last_r2":num(r2[-1],5),
            "cross_dates":[str(x.index[i].date()) for i in cross],
            "qualification_events":qualified}

def at_or_before(x,date):
    q=x.loc[x.index<=pd.Timestamp(date)].dropna()
    return (q.index[-1],float(q.iloc[-1])) if len(q) else (None,None)

def perf(x,date_a,date_b):
    da,a=at_or_before(x,date_a)
    db,b=at_or_before(x,date_b)
    if a is None or b is None or da>=db or a<=0:return None
    return {"start":str(da.date()),"end":str(db.date()),"return_pct":num(100*(b/a-1))}

def rolling_rel(a,b,window):
    r=np.log(a/a.shift(1))-np.log(b/b.shift(1))
    return r.rolling(window,min_periods=window).sum()

def pick_relative_lead(series, benchmark):
    """Date-detected relative 20-session alpha vs CSI300, using data as of each date.
    At each date, alpha20 = cashflow return20 - market ETF return20 (arithmetic pct).
    Lists sustained outperformance periods; threshold fixed a priori at >1 pct.
    """
    z=pd.concat({"factor":series,"base":benchmark},axis=1).dropna()
    if len(z)<40:return {}
    alpha20=(z.factor/z.factor.shift(20)-z.base/z.base.shift(20))*100
    ret20_factor=(z.factor/z.factor.shift(20)-1)*100
    s=alpha20.loc[(alpha20.index>="2026-06-01") & (alpha20.index<=ASOF)]
    positions=[]
    for i in range(len(s)):
        if s.iloc[i]>1 and (i==0 or s.iloc[i-1]<=1):
            positions.append({"date":str(s.index[i].date()),"alpha20_pp":num(s.iloc[i]),
                              "factor20_pct":num(ret20_factor.loc[s.index[i]])})
    rows=[{"date":str(d.date()),"alpha20_pp":num(v),
           "factor20_pct":num(ret20_factor.loc[d])}
          for d,v in s.items() if d.strftime("%Y-%m-%d") in POINTS]
    return {"cross_above_1pp":positions,"checkpoints":rows,
            "first_5_sessions_above_1pp":next((str(s.index[i].date()) for i in range(4,len(s))
                if all(s.iloc[i-j]>1 for j in range(5))),None)}

# Executable shadow representatives fixed by index family before reviewing
# the episode's outcome. Index-family median price generates the SIGNAL,
# one ETF OPEN price determines the ENTRY and EXIT execution proxy.
REPRESENTATIVES={
    "CSI800_CASHFLOW":"159229",
    "GUOZHENG_CASHFLOW":"159201",
    "FTSE_A_CASHFLOW":"159399",
}
COST_PER_SIDE=0.0006

def trend_episodes(level_series, representative_open, representative_close):
    """First qualified after each annual cross; exit first annual<=0.

    Signal at close T; buy T+1 open. Exit at next open after annual<=0.
    No 20-day cap and no arbitrary R2 exit. Strictly chronological.
    Right-censored episodes marked to most recent close with NO unrealized
    liquidation cost. Synthetic index-family price is not itself tradable.
    """
    level_series=level_series.dropna().astype(float)
    if len(level_series)<30:return []
    annual,r2=calc_ols(level_series.to_numpy(dtype=float))
    dates=list(level_series.index)
    cross=np.zeros(len(dates),dtype=bool)
    cross[1:]=(annual[1:]>1e-8)&(annual[:-1]<=1e-8)
    pending_cross=None
    own_open=representative_open.reindex(dates)
    own_close=representative_close.reindex(dates)
    trades=[]
    active=None
    for i in range(len(dates)):
        # At the day's open, execute PREVIOUS close's orders. No same-day fill.
        if active is not None and active.get("pending_exit"):
            px=own_open.iloc[i]
            if pd.notna(px) and px>0:
                active["exit_date"]=str(dates[i].date())
                active["exit_price"]=float(px)
                active["exit_reason"]="annual_nonpositive"
                active["exit_annual"]=active.pop("pending_exit_annual",None)
                active.pop("pending_exit",None)
                active["status"]="closed"
                trades.append(active)
                active=None
        if active is not None and active.get("pending_entry"):
            px=own_open.iloc[i]
            if pd.notna(px) and px>0:
                active["entry_date"]=str(dates[i].date())
                active["entry_price"]=float(px)
                active.pop("pending_entry",None)
        # Observe close and compute today's signal AFTER open execution.
        if active is not None and "entry_date" in active and np.isfinite(annual[i]) and annual[i]<=0:
            active["pending_exit"]=True
            active["pending_exit_annual"]=num(annual[i],5)
            active["failure_date"]=str(dates[i].date())
        if cross[i]:
            pending_cross=i
        if active is None and pending_cross is not None and i>pending_cross and i<=pending_cross+3:
            if (annual[i]>1e-8 and np.isfinite(r2[i]) and r2[i]>r2[i-1]+1e-12
                    and r2[i]>r2[pending_cross]+1e-12):
                active={"cross_date":str(dates[pending_cross].date()),
                        "qualified_date":str(dates[i].date()),
                        "entry_annual":num(annual[i],5),
                        "entry_r2":num(r2[i],5),
                        "pending_entry":True}
                pending_cross=None
        if pending_cross is not None and (i>pending_cross+3 or annual[i]<=0):
            pending_cross=None
    if active is not None:
        if "entry_date" in active:
            # Exit order from latest signal cannot fill until next session.
            mark=own_close.iloc[-1]
            active["exit_date"]=str(dates[-1].date())
            active["exit_price"]=float(mark) if pd.notna(mark) else None
            active["exit_reason"]="right_censored_mark_to_market"
            active["status"]="open"
            active.pop("pending_entry",None)
            active.pop("pending_exit",None)
            active.pop("pending_exit_annual",None)
            trades.append(active)
    for x in trades:
        a=x["entry_price"];b=x.get("exit_price")
        x["gross_return_pct"]=num((b/a-1)*100) if b is not None else None
        x["return_after_cost_pct"]=num(100*((b/a-1)-COST_PER_SIDE*(1 if x["status"]=="open" else 2))) if b is not None else None
        x["trading_days_held"]=None
        enter=pd.Timestamp(x["entry_date"])
        end=pd.Timestamp(x["exit_date"])
        if enter in own_close.index and end in own_close.index:
            series=own_close.loc[enter:end].dropna().to_numpy(dtype=float)
            if len(series):
                curve=np.r_[float(a),series]
                x["max_drawdown_pct"]=num(100*np.min(curve/np.maximum.accumulate(curve)-1))
            x["trading_days_held"]=len(own_close.loc[enter:end])
    return trades

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--parquet",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    codes=set(s for members in GROUPS.values() for s in members)|set(BENCHMARKS.values())
    raw=pd.read_parquet(args.parquet,columns=["symbol","date","open","close","amount"])
    raw["symbol"]=raw.symbol.astype(str).str.zfill(6)
    raw["date"]=pd.to_datetime(raw.date)
    raw=raw[raw.symbol.isin(codes)&(raw.date>=pd.Timestamp(BEGIN))&(raw.date<=pd.Timestamp(ASOF))].copy()
    raw["close"]=pd.to_numeric(raw.close,errors="coerce")
    raw["amount"]=pd.to_numeric(raw.amount,errors="coerce")
    raw=raw.dropna(subset=["close"])
    raw=raw[raw.close>0]
    raw=raw.sort_values(["symbol","date"]).drop_duplicates(["symbol","date"],keep="last")
    close=raw.pivot(index="date",columns="symbol",values="close")
    amounts=raw.pivot(index="date",columns="symbol",values="amount")
    open_prices=raw.pivot(index="date",columns="symbol",values="open")
    if len(close)<60:raise RuntimeError("Too few market data dates")
    # For ETFs sharing one actual index, median of their daily percentage returns,
    # capped to 0 when no fresh price; no forward fill. This suppresses 0.001 ticks.
    # Take one equal vote per verified index family, rather than per fund code.
    group_ret={}
    group_coverage={}
    group_amt={}
    for key,ss in GROUPS.items():
        available=[s for s in ss if s in close.columns]
        if not available:raise RuntimeError(f"No prices for verified group {key}")
        daily=close[available].pct_change(fill_method=None)
        # require at least 1 ETF present, use median within index family
        group_ret[key]=daily.median(axis=1,skipna=True)
        group_coverage[key]={
            "expected_symbols":ss,
            "available_symbols":available,
            "last_data_date":str(close[available].dropna(how="all").index[-1].date()),
            "individual_date_counts":{s:int(close[s].notna().sum()) for s in available},
        }
        # normalize turnover per fund against its own preceding 20 sessions
        # to prevent the 6+3+1 family imbalance in group-level amount comparisons.
        a=amounts[available].where(amounts[available]>0)
        avg20=a.shift(5).rolling(20,min_periods=20).mean()
        ratio=(a.rolling(5,min_periods=5).mean()/avg20)
        group_amt[key]=ratio.median(axis=1,skipna=True)
    # Group-specific index-price proxy and composite with exactly one equal
    # vote per index family; avoid ETF count bias.
    ret=pd.DataFrame(group_ret)
    # Require ALL three families to quote at both dates to compute composite.
    ret["CASHFLOW_3_INDEX_EQUAL"]=ret.dropna(how="any").mean(axis=1)
    for name,sym in BENCHMARKS.items():
        if sym in close:
            ret[name]=close[sym].pct_change(fill_method=None)
    level=(1+ret.fillna(0)).cumprod()*100
    level.loc[:level.index[0],:]=100
    # Cumulative index levels are only valid if coverage is good; report count.
    valid_days={k:int(v.notna().sum()) for k,v in ret.items()}
    out={"as_of":ASOF,"begin":BEGIN,"data_source":"archived Tencent-adjusted fullmarket ETF daily parquet",
         "definitions":{"index_family":"each known underlying tracked index counts once; group daily median ETF percentage return",
           "composite":"equal mean of 3 index-family daily return proxies, each 1/3",
           "benchmark":"ETF price proxies, not official index level or underlying constituent returns",
           "relative_excess":"window cashflow ETF return minus window selected broad-market ETF return in percentage points",
           "risk":"adjusted price rounding and fund inception/survivorship, missing observations, no flows/official index NAV"},
         "coverage":{"symbols":[{"symbol":s,"n_days":int(close[s].notna().sum()),
             "first":str(close[s].dropna().index.min().date()),
             "last":str(close[s].dropna().index.max().date()),
             "same_close_pct":num(100*(close[s].dropna().diff()==0).iloc[1:].mean(),1)}
             for s in sorted(codes) if s in close.columns],
             "missing_symbols":sorted(codes-set(close.columns)),
             "valid_days_by_series":valid_days,"index_families":group_coverage},
         "period_returns":{},
         "relative_20d_leading":{},
         "ols_rebuild_timing":{},
         "turnover_5v20_by_family":{},
         "levels_at_checkpoints":{},
         "price_curve":[],
        "trend_episode_replay":{},
        "episode_contract":{"signal":"26-day weighted OLS annual crosses positive, first R2 improvement qualified within 1-3 sessions",
           "entry":"qualify T close -> T+1 representative ETF open",
           "exit":"first annual<=0 at close -> next day representative ETF open; no 20-session limit",
           "reentry":"new annual nonpositive-to-positive crossing and subsequent qualification after exit",
           "cash":"0 return while out of market, no opportunity-cost benchmark",
           "reference_etfs":REPRESENTATIVES,
           "trade_fee_each_side":COST_PER_SIDE,
           "price_signal_warning":"median group ETF return reconstructed into synthetic NAV-100 signal; actual underlying index not available",
           "right_censored":"current open positions marked at 2026-10-20 close, gross return and one-sided cost only"},
    }
    for label,start,end in WINDOWS:
        benchmarks={}
        f=perf(level["CASHFLOW_3_INDEX_EQUAL"],start,end)
        for key in list(GROUPS)+["CASHFLOW_3_INDEX_EQUAL"]+list(BENCHMARKS):
            if key in level:
                a=perf(level[key],start,end)
                benchmarks[key]=a
        ex={}
        for key in BENCHMARKS:
            if key in benchmarks and benchmarks[key] and f:
                ex[key]=num(f["return_pct"]-benchmarks[key]["return_pct"])
        out["period_returns"][label]={"start":start,"end":end,
            "returns":benchmarks,"cashflow_excess_pp":ex}
    for key in list(GROUPS)+["CASHFLOW_3_INDEX_EQUAL"]:
        if key in level:
            out["ols_rebuild_timing"][key]=stats_ols(level[key])
            out["relative_20d_leading"][key]=pick_relative_lead(
                level[key],level["CSI300_510300"]) if "CSI300_510300" in level else {}
        if key in group_amt:
            s=group_amt[key]
            out["turnover_5v20_by_family"][key]={
                date:{"asof":str(at_or_before(s,date)[0].date()) if at_or_before(s,date)[0] is not None else None,
                      "ratio":num(at_or_before(s,date)[1])}
                for date in POINTS}
    for family,representative in REPRESENTATIVES.items():
        if family in level and representative in open_prices and representative in close:
            out["trend_episode_replay"][family]=trend_episodes(
                level[family],open_prices[representative],close[representative])
    # Synthetic 3-factor composite executed as a price PROXY using one third
    # capital in each known representative. Each family has its own onset dates;
    # this is just composite signal execution and not independently tradable.
    synthetic_open=pd.DataFrame({k:open_prices[rep].pct_change(fill_method=None)
                                 for k,rep in REPRESENTATIVES.items()}).mean(axis=1)
    # Do not synthesize a misleading open basket: compare signal episodes
    # using the most liquid observed underlying ETF carrier only, separately.
    out["trend_episode_replay"]["CASHFLOW_3_INDEX_EQUAL_SIGNAL_ONLY"]=stats_ols(level["CASHFLOW_3_INDEX_EQUAL"])
    for date in POINTS:
        r={}
        for key in level:
            q=at_or_before(level[key],date)
            r[key]={"asof":str(q[0].date()) if q[0] is not None else None,
                     "level":num(q[1])}
        out["levels_at_checkpoints"][date]=r
    for date,record in level.iterrows():
        ds=str(date.date())
        if ds<"2026-06-01":continue
        row={"date":ds}
        for key in list(GROUPS)+["CASHFLOW_3_INDEX_EQUAL"]+list(BENCHMARKS):
            if key in level:
                row[key]=num(record[key],4)
        out["price_curve"].append(row)
    Path(args.out).parent.mkdir(parents=True,exist_ok=True)
    Path(args.out).write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf8")
    print(json.dumps({"status":"ok","as_of":ASOF,"coverage":out["coverage"],
             "period_returns":out["period_returns"],
             "ols_rebuild_timing":out["ols_rebuild_timing"],
             "relative_20d_leading":out["relative_20d_leading"]},ensure_ascii=False))
if __name__=="__main__":main()
