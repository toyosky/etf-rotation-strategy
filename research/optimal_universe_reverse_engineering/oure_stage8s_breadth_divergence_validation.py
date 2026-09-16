#!/usr/bin/env python3
from __future__ import annotations

import json, os, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
import optimal_universe_reverse_engineering.oure_stage8r_breadth_divergence as s8r

THRESHOLD = 80.0
HORIZON = 20
MIN_GAP = 20
SEGMENTS = {
    "PRE2021": (None, "2020-12-31"),
    "2021_2022": ("2021-01-01", "2022-12-31"),
    "POST2023": ("2023-01-01", None),
}


def summarize(g: pd.DataFrame, label: str) -> dict:
    r = pd.to_numeric(g[f"fwd_return_{HORIZON}"], errors="coerce")
    m = pd.to_numeric(g[f"fwd_mdd_{HORIZON}"], errors="coerce")
    x = pd.DataFrame({"r": r, "m": m}).dropna()
    if x.empty:
        return {"group": label, "n": 0}
    return {
        "group": label,
        "n": int(len(x)),
        "mean_return": float(x.r.mean()),
        "median_return": float(x.r.median()),
        "win_rate": float((x.r > 0).mean()),
        "q10_return": float(x.r.quantile(.10)),
        "mean_mdd": float(x.m.mean()),
        "median_mdd": float(x.m.median()),
    }


def fixed_grid(z: pd.DataFrame, offset: int = 0) -> pd.DataFrame:
    g = z.dropna(subset=["breadth_divergence_pct252", f"fwd_return_{HORIZON}", f"fwd_mdd_{HORIZON}"]).reset_index(drop=True)
    if g.empty:
        return pd.DataFrame()
    return g.iloc[offset::HORIZON].copy()


def event_onsets(z: pd.DataFrame) -> pd.DataFrame:
    g = z.dropna(subset=["breadth_divergence_pct252", f"fwd_return_{HORIZON}", f"fwd_mdd_{HORIZON}"]).copy().reset_index(drop=True)
    high = g["breadth_divergence_pct252"] >= THRESHOLD
    onset = high & ~high.shift(1, fill_value=False)
    chosen = []
    last = -10**9
    for i in np.flatnonzero(onset.to_numpy()):
        if i - last >= MIN_GAP:
            chosen.append(i); last = i
    return g.iloc[chosen].copy() if chosen else pd.DataFrame(columns=g.columns)


def segment_mask(d: pd.Series, lo, hi):
    m = pd.Series(True, index=d.index)
    if lo: m &= d >= pd.Timestamp(lo)
    if hi: m &= d <= pd.Timestamp(hi)
    return m


def grid_robustness(z: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    # Check every possible 20-day grid offset; a robust result should not depend on arbitrary phase.
    for off in range(HORIZON):
        g=fixed_grid(z,off)
        if g.empty: continue
        g["high"] = g.breadth_divergence_pct252 >= THRESHOLD
        for seg,(lo,hi) in {"FULL":(None,None), **SEGMENTS}.items():
            x=g.loc[segment_mask(g.signal_date,lo,hi)].copy()
            for state,y in x.groupby("high"):
                rec=summarize(y,"HIGH" if state else "NOT_HIGH")
                rec.update({"offset":off,"segment":seg,"high":bool(state)})
                rows.append(rec)
    return pd.DataFrame(rows)


def offset_effect_summary(grid: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for seg,g in grid.groupby("segment"):
        piv=g.pivot(index="offset",columns="high",values=["mean_return","win_rate","mean_mdd","n"])
        valid=[i for i in piv.index if ("mean_return",True) in piv.columns and ("mean_return",False) in piv.columns and pd.notna(piv.loc[i,("mean_return",True)]) and pd.notna(piv.loc[i,("mean_return",False)])]
        diffs=[]
        for i in valid:
            diffs.append({
                "ret_diff":float(piv.loc[i,("mean_return",True)]-piv.loc[i,("mean_return",False)]),
                "win_diff":float(piv.loc[i,("win_rate",True)]-piv.loc[i,("win_rate",False)]),
                "mdd_diff":float(piv.loc[i,("mean_mdd",True)]-piv.loc[i,("mean_mdd",False)]),
            })
        if not diffs: continue
        d=pd.DataFrame(diffs)
        rows.append({"segment":seg,"offsets":len(d),
                     "ret_diff_mean":float(d.ret_diff.mean()),"ret_diff_median":float(d.ret_diff.median()),
                     "ret_diff_negative_share":float((d.ret_diff<0).mean()),
                     "win_diff_mean":float(d.win_diff.mean()),"win_diff_negative_share":float((d.win_diff<0).mean()),
                     "mdd_diff_mean":float(d.mdd_diff.mean())})
    return pd.DataFrame(rows)


def onset_table(z: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    on=event_onsets(z)
    rows=[]
    if on.empty: return on,pd.DataFrame()
    for seg,(lo,hi) in {"FULL":(None,None), **SEGMENTS}.items():
        x=on.loc[segment_mask(on.signal_date,lo,hi)]
        rec=summarize(x,"HIGH_DIVERGENCE_ONSET"); rec.update({"segment":seg}); rows.append(rec)
    return on,pd.DataFrame(rows)


def annual(z: pd.DataFrame) -> pd.DataFrame:
    g=fixed_grid(z,0)
    if g.empty: return pd.DataFrame()
    g["high"]=g.breadth_divergence_pct252>=THRESHOLD
    rows=[]
    for y,x in g.groupby(g.signal_date.dt.year):
        a=x[x.high]; b=x[~x.high]
        sa=summarize(a,"HIGH"); sb=summarize(b,"NOT_HIGH")
        rows.append({"year":int(y),"n_high":sa.get("n",0),"n_not_high":sb.get("n",0),
                     "high_mean_return":sa.get("mean_return",np.nan),"not_high_mean_return":sb.get("mean_return",np.nan),
                     "return_diff":sa.get("mean_return",np.nan)-sb.get("mean_return",np.nan) if sa.get("n",0) and sb.get("n",0) else np.nan,
                     "high_win_rate":sa.get("win_rate",np.nan),"not_high_win_rate":sb.get("win_rate",np.nan)})
    return pd.DataFrame(rows)


def bootstrap_diff(g: pd.DataFrame, reps=5000, seed=20260916):
    x=g.dropna(subset=["breadth_divergence_pct252",f"fwd_return_{HORIZON}"]).copy()
    x["high"]=x.breadth_divergence_pct252>=THRESHOLD
    a=x.loc[x.high,f"fwd_return_{HORIZON}"].to_numpy(float); b=x.loc[~x.high,f"fwd_return_{HORIZON}"].to_numpy(float)
    if len(a)<3 or len(b)<3: return {}
    rng=np.random.default_rng(seed); diffs=np.empty(reps)
    for i in range(reps):
        diffs[i]=rng.choice(a,len(a),replace=True).mean()-rng.choice(b,len(b),replace=True).mean()
    return {"observed_diff":float(a.mean()-b.mean()),"ci2_5":float(np.quantile(diffs,.025)),"ci97_5":float(np.quantile(diffs,.975)),"p_diff_ge0":float((diffs>=0).mean()),"n_high":len(a),"n_not_high":len(b)}


def main():
    db=os.getenv("ETF_DAILY_BARS_DATABASE_URL")
    if not db: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(os.getenv("OUTPUT_DIR","stage8s-breadth-divergence-validation-output")); out.mkdir(parents=True,exist_ok=True)
    eng=create_engine(_db_url(db),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars.symbol.astype(str).str.zfill(6); bars["date"]=pd.to_datetime(bars.date)
    feat=build_features(bars); feat["symbol"]=feat.symbol.astype(str).str.zfill(6); feat["date"]=pd.to_datetime(feat.date)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    labels=s8r.fixed_strategy_labels(cal,score,gross,feat,bars)
    z=s8r.build_panel(cal,feat,labels)

    grid=grid_robustness(z); eff=offset_effect_summary(grid); on,on_sum=onset_table(z); ann=annual(z)
    base=fixed_grid(z,0); boot=bootstrap_diff(base)

    grid.to_csv(out/"stage8s_grid_offsets.csv",index=False)
    eff.to_csv(out/"stage8s_offset_effect_summary.csv",index=False)
    on.to_csv(out/"stage8s_high_divergence_onsets.csv",index=False)
    on_sum.to_csv(out/"stage8s_onset_summary.csv",index=False)
    ann.to_csv(out/"stage8s_annual.csv",index=False)
    summary={"study":"OURE Stage8S breadth divergence validation","frozen_threshold_pct252":THRESHOLD,
             "horizon":HORIZON,"nonoverlap_gap":MIN_GAP,"offset_effect_summary":eff.to_dict(orient="records"),
             "bootstrap_offset0":boot,"onset_summary":on_sum.to_dict(orient="records"),
             "decision_rule":"Promote only if high divergence shows directionally weaker forward return across most grid offsets and multiple time segments; otherwise keep diagnostic only."}
    (out/"stage8s_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    md=["# Stage8S — Breadth Divergence Validation","",f"Frozen rule: divergence percentile >= {THRESHOLD:.0f}%; horizon={HORIZON} sessions.","",
        "## Offset robustness","",eff.to_markdown(index=False),"","## Onset events","",on_sum.to_markdown(index=False),"","## Annual fixed-grid","",ann.to_markdown(index=False),"","## Bootstrap (offset 0)","",f"`{boot}`"]
    (out/"stage8s_summary.md").write_text("\n".join(md),encoding="utf-8")
    print("\n".join(md))

if __name__=="__main__": main()
