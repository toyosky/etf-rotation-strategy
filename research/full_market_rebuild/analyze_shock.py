#!/usr/bin/env python3
"""Research-only shock-vs-gradual comparison for independently qualified rebuild signals.

Uses ONLY information through signal-date close to classify events. Outcomes use
the next observed symbol open. This is an event study, NOT a portfolio backtest.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from automation.build_fundamental_audit_trigger import db_url, calc_ols

HORIZONS = (5, 10, 20, 40)
SHOCK_RULES = {
    "primary_10_8": (0.10, 0.08),
    "sensitivity_8_6": (0.08, 0.06),
    "sensitivity_12_10": (0.12, 0.10),
}

def classify(r2, max1, rule):
    cumulative, daily = rule
    return bool(r2 >= cumulative or max1 >= daily)

def load_bars():
    raw = os.environ.get("ETF_DAILY_BARS_DATABASE_URL")
    if not raw:
        raise RuntimeError("ETF_DAILY_BARS_DATABASE_URL required")
    engine = create_engine(db_url(raw), pool_pre_ping=True)
    with engine.connect() as conn:
        df = pd.read_sql_query(text(
            "select symbol,date,open,high,low,close,amount from public.daily_bars order by symbol,date"
        ), conn, parse_dates=["date"])
    df["symbol"] = df.symbol.astype(str).str.zfill(6)
    if df.duplicated(["symbol", "date"]).any():
        raise RuntimeError("Duplicate (symbol,date) in daily_bars")
    if df[["close","open"]].isna().any().any() or (df[["close","open"]] <= 0).any().any():
        raise RuntimeError("Missing/invalid open or close")
    return {sym: g.reset_index(drop=True) for sym, g in df.groupby("symbol", sort=True)}

def label(events, groups):
    if events.duplicated(["symbol", "signal_date"]).any():
        raise RuntimeError("Repeated signal day: investigate episode extraction")
    labeled = []
    unmatched = []
    disagreements = []
    for event in events.to_dict("records"):
        sym = str(event["symbol"]).zfill(6)
        g = groups.get(sym)
        if g is None:
            unmatched.append((sym, event["signal_date"]))
            continue
        loc = pd.Index(g.date).get_indexer([pd.Timestamp(event["signal_date"])])[0]
        if loc < 3:
            unmatched.append((sym, event["signal_date"]))
            continue
        c = g.close.to_numpy(dtype=float)
        o = g.open.to_numpy(dtype=float)
        a = g.amount.to_numpy(dtype=float)
        ret2 = float(c[loc] / c[loc-2] - 1)
        max1 = max(float(c[k] / c[k-1] - 1) for k in range(loc-2, loc+1))
        rec = dict(event)
        rec["ret1_pre"] = float(c[loc] / c[loc-1] - 1)
        rec["ret2_pre"] = ret2
        rec["ret3_pre"] = float(c[loc] / c[loc-3] - 1)
        rec["ret5_pre"] = float(c[loc] / c[loc-5] - 1) if loc >= 5 else None
        rec["max_daily_ret3"] = max1
        rec["signal_open_gap"] = float(o[loc] / c[loc-1] - 1)
        if loc >= 10:
            prior = a[loc-10:loc]
            rec["amount_ratio10"] = float(a[loc] / prior.mean()) if np.isfinite(prior).all() and prior.mean() > 0 else None
        else:
            rec["amount_ratio10"] = None
        for key, rule in SHOCK_RULES.items():
            rec[key] = classify(ret2, max1, rule)
        rec["type"] = "SHOCK" if rec["primary_10_8"] else "GRADUAL"
        for h in HORIZONS:
            end = loc + h
            if loc + 1 >= len(g) or end >= len(g):
                rec["mae_close_"+str(h)] = None
                rec["mfe_close_"+str(h)] = None
                continue
            f = c[loc+1:end+1] / o[loc+1] - 1
            rec["mae_close_"+str(h)] = float(f.min())
            rec["mfe_close_"+str(h)] = float(f.max())
            expected = float(c[end] / o[loc+1] - 1)
            prior_r = event.get("return_"+str(h)+"d")
            if pd.notna(prior_r) and abs(expected-float(prior_r)) > 1e-9:
                disagreements.append((sym, event["signal_date"], h))
        if loc + 1 < len(g) and abs(float(event["entry_open"]) - o[loc+1]) > 1e-9:
            disagreements.append((sym,event["signal_date"],"entry_open"))
        labeled.append(rec)
    if unmatched or disagreements:
        raise RuntimeError("Event join/return mismatch: unmatched="+str(unmatched[:5])+" differences="+str(disagreements[:5]))
    return pd.DataFrame(labeled)

def statistics(frame):
    out = {"events": int(len(frame)), "symbols": int(frame.symbol.nunique())}
    for h in HORIZONS:
        series = pd.to_numeric(frame["return_"+str(h)+"d"], errors="coerce").dropna()
        mae = pd.to_numeric(frame["mae_close_"+str(h)],errors="coerce").dropna()
        tag = str(h)+"d"
        out[tag] = {
            "n": int(len(series)),
            "mean": float(series.mean()) if len(series) else None,
            "median": float(series.median()) if len(series) else None,
            "win_rate": float((series > 0).mean()) if len(series) else None,
            "p10": float(series.quantile(.1)) if len(series) else None,
            "mean_mae_close": float(mae.mean()) if len(mae) else None,
            "mae_below_minus3": float((mae <= -0.03).mean()) if len(mae) else None,
        }
    out["median_signal_ret2"] = float(frame.ret2_pre.median()) if len(frame) else None
    out["median_r2"] = float(frame.r2.median()) if len(frame) else None
    return out

def cluster_bootstrap(frame, h, seed=20261020, draws=1500):
    """Symbol-level cluster resampling; wide uncertainty expected with 19 ETFs."""
    col = "return_"+str(h)+"d"
    sub = frame.dropna(subset=[col])
    symbols = sorted(sub.symbol.unique())
    if len(symbols) < 3 or sub.primary_10_8.sum() < 3 or (~sub.primary_10_8).sum() < 3:
        return {"n_valid_resamples": 0, "ci95": None}
    rng = np.random.default_rng(seed + h)
    buckets = [sub[sub.symbol == s] for s in symbols]
    diffs = []
    for _ in range(draws):
        sample = pd.concat([buckets[i] for i in rng.integers(0, len(buckets), size=len(buckets))], ignore_index=True)
        x = sample[sample.primary_10_8][col]
        y = sample[~sample.primary_10_8][col]
        if len(x) and len(y):
            diffs.append(float(x.mean() - y.mean()))
    return {"n_valid_resamples": len(diffs),
            "ci95": [float(np.quantile(diffs, .025)), float(np.quantile(diffs, .975))] if len(diffs) >= 100 else None}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--events", default="research/full_market_rebuild/output/events.csv")
    p.add_argument("--out", default="research/full_market_rebuild/output")
    a = p.parse_args()
    events = pd.read_csv(a.events, dtype={"symbol": str})
    groups = load_bars()
    result = label(events, groups)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    result.to_csv(out/"events_labeled.csv", index=False)
    result["year"] = result.signal_date.str[:4].astype(int)
    summaries = {}
    comparisons = {}
    windows = {
        "full_2013_2026": result,
        "study_2021_2026": result[result.year >= 2021],
        "discovery_2021_2024": result[result.year.between(2021,2024)],
        "recent_2025_2026": result[result.year >= 2025],
    }
    for key, sample in windows.items():
        summaries[key] = {
            "total": statistics(sample),
            "SHOCK": statistics(sample[sample.primary_10_8]),
            "GRADUAL": statistics(sample[~sample.primary_10_8])
        }
        comparisons[key] = {}
        for h in HORIZONS:
            shock = sample[sample.primary_10_8]["return_"+str(h)+"d"].dropna()
            gradual = sample[~sample.primary_10_8]["return_"+str(h)+"d"].dropna()
            comparisons[key][str(h)+"d"] = {
                "mean_diff_shock_minus_gradual": float(shock.mean()-gradual.mean()) if len(shock) and len(gradual) else None,
                "symbol_cluster_bootstrap": cluster_bootstrap(sample, h),
            }
    sensitivities = {}
    test=result[result.year>=2021]
    for name in SHOCK_RULES:
        mask = test[name]
        sensitivities[name] = {
            "shock_events": int(mask.sum()), "gradual_events": int((~mask).sum()),
            "shock_mean20": float(test.loc[mask,"return_20d"].mean()) if mask.any() else None,
            "gradual_mean20": float(test.loc[~mask,"return_20d"].mean()) if (~mask).any() else None,
        }
    by_symbol = result[result.year>=2021].groupby(["symbol","type"],as_index=False).agg(
        events=("signal_date","size"),mean20=("return_20d","mean"),mean40=("return_40d","mean"))
    by_symbol.to_csv(out/"by_symbol.csv",index=False)
    report = {
        "status":"exploratory_event_study_only", "data_as_of":str(max(g.date.max() for g in groups.values()).date()),
        "source":"Supabase public.daily_bars, 18 risk-asset symbols after excluding cash proxy 511220",
        "events_input":str(a.events), "signal":"frozen OLS 26 sessions, half-life 10; annual cross; R2 recovery within 1-3 days",
        "classification":{"asof":"signal close only","primary":"last 2 close-to-close sessions >= +10% OR max single day close-to-close in last 3 >= +8%",
                          "sensitivity":{"8_6":"2d>=8% or max1d>=6%","12_10":"2d>=12% or max1d>=10%"}},
        "future_return":"signal day j, entry day j+1 open, exit j+h close; gross; 5/10/20/40",
        "risk":"MAE is minimum close mark from entry open to j+h, not intraday max drawdown",
        "summaries":summaries, "comparisons":comparisons, "sensitivity":sensitivities,
        "critical_limitations":[
            "18 existing/surviving risk assets only; not whole market nor survivorship-bias-free",
            "candidate universe and weighting not PIT reconstructed",
            "classification thresholds informed by Oct 2026 Brazil event; 2025-26 is not uncontaminated out-of-sample validation",
            "overlapping correlated events; bootstrap resamples symbols, not independent trade outcomes; 6 shock events only",
            "no commissions/slippage/premium filters, no portfolio capital allocation or top1 benchmark",
            "historical adjusted price lineage/price-as-of validation not finished",
            "right censoring: incomplete forward horizons excluded per metric",
        ]
    }
    (out/"shock_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({"study":summaries["study_2021_2026"],"recent":summaries["recent_2025_2026"],
                      "sensitivity":sensitivities},ensure_ascii=False))
if __name__=="__main__":main()
