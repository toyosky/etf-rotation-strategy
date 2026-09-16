#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
import optimal_universe_reverse_engineering.oure_stage8m_fixv2_v1_long_horizon as s8m
import optimal_universe_reverse_engineering.oure_stage8n_internal_regime_diagnostic as s8n
import cluster90_resistance_score_v1_test as v1lib

BASELINE = "511220"
RISK = tuple(s8m.MAIN_RISK)
COMPARATORS = {
    "511220": "城投债ETF海富通",
    "511010": "国债ETF国泰",
    "511260": "十年国债ETF国泰",
    "511360": "短融ETF海富通",
    "511520": "政金债ETF富国",
    "511580": "国债政金债ETF招商",
}
HISTORY = 252
HORIZONS = (5, 10, 20)
COST = 0.0006


def percentile_from_history(values: pd.Series, lookback: int = HISTORY) -> pd.Series:
    x = pd.to_numeric(values, errors="coerce").to_numpy(float)
    out = np.full(len(x), np.nan)
    hist: deque[float] = deque(maxlen=lookback)
    for i, v in enumerate(x):
        if np.isfinite(v):
            hist.append(float(v))
            out[i] = 100.0 * sum(h <= v for h in hist) / len(hist)
    return pd.Series(out, index=values.index)


def quadrant(breadth_pct: float, gap_pct: float) -> str | None:
    if not np.isfinite(breadth_pct) or not np.isfinite(gap_pct):
        return None
    if breadth_pct >= 50.0 and gap_pct >= 50.0:
        return "TREND_EXPANSION"
    if breadth_pct >= 50.0:
        return "ROTATION_CROWDING"
    if gap_pct >= 50.0:
        return "NARROW_LEADERSHIP"
    return "DEFENSIVE_VOID"


def fixed_strategy_labels(cal, score, gross, feat, bars):
    cash_ok = score[BASELINE].notna() & np.isfinite(score[BASELINE]) & (score.index >= s8m.START_FLOOR)
    first = pd.Timestamp(score.index[cash_ok][0])
    start_i = int(cal.get_loc(first)); last_i = len(cal) - 3
    raw = s8m.build_raw_targets(cal, score, s8m.MAIN_MEMBERS, start_i, last_i)
    raw_score = s8m.raw_score_wide(feat, cal, list(score.columns.astype(str)))
    raw_delta = raw_score.diff()
    needed = set(raw["target"].dropna().astype(str).unique())
    profiles_df = v1lib.build_needed_profiles(bars, needed)
    profiles = profiles_df.set_index(["date", "symbol"])["resistance_pct252"].to_dict()
    v1, _ = s8m.build_v1_targets(raw, score, raw_delta, profiles, s8m.MAIN_MEMBERS, s8m.MAIN_THRESHOLD)
    v1 = s8m.attach_returns(v1, gross, COST)
    z = raw[["signal_date", "execution_date", "return_end_date"]].copy()
    z["v1_net_ret"] = v1["net_ret"].to_numpy(float)
    return s8n.add_forward_labels(z)


def build_map_panel(cal, score, feat, strategy_labels):
    # IMPORTANT: the website map uses raw 26-day OLS scores, not pool_score.
    # Therefore no recent_drop3/trend-eligibility mask is allowed here.
    raw_score = s8m.raw_score_wide(feat, cal, list(score.columns.astype(str)))
    rows = []
    for d in cal:
        d = pd.Timestamp(d)
        vals = raw_score.loc[d, list(RISK)].astype(float)
        available = vals[np.isfinite(vals)].index.astype(str).tolist()
        if len(available) < 2:
            continue
        ranked_vals = raw_score.loc[d, available].astype(float)
        ranked_vals = ranked_vals[np.isfinite(ranked_vals)].sort_values(ascending=False)
        if len(ranked_vals) < 2:
            continue
        top1 = str(ranked_vals.index[0]); top2 = str(ranked_vals.index[1])
        gap_raw = max(float(ranked_vals.iloc[0] - ranked_vals.iloc[1]), 0.0)
        rec = {"signal_date": d, "ready_n": len(available), "top1": top1, "top2": top2, "gap_raw": gap_raw}
        for c in COMPARATORS:
            cv = raw_score.at[d, c] if c in raw_score.columns else np.nan
            if pd.isna(cv) or not np.isfinite(cv):
                rec[f"breadth_{c}"] = np.nan
                rec[f"breadth_count_{c}"] = np.nan
                rec[f"comparator_score_{c}"] = np.nan
            else:
                count = int(sum(float(ranked_vals.get(s, -np.inf)) > float(cv) for s in available))
                rec[f"breadth_count_{c}"] = count
                rec[f"breadth_{c}"] = 100.0 * count / len(RISK)
                rec[f"comparator_score_{c}"] = float(cv)
        rows.append(rec)
    z = pd.DataFrame(rows)
    z["gap_percentile"] = percentile_from_history(z["gap_raw"], HISTORY)
    for c in COMPARATORS:
        z[f"quadrant_{c}"] = [quadrant(b, g) for b, g in zip(z[f"breadth_{c}"], z["gap_percentile"])]
    z = z.merge(strategy_labels, on="signal_date", how="left")
    return z


def agreement_stats(z, comparator, window_name, lo=None):
    g = z.copy()
    if lo is not None:
        g = g[g.signal_date >= pd.Timestamp(lo)]
    cols = [f"breadth_{BASELINE}", f"breadth_{comparator}", f"quadrant_{BASELINE}", f"quadrant_{comparator}"]
    g = g.dropna(subset=cols)
    if g.empty:
        return None
    b0 = g[f"breadth_{BASELINE}"].astype(float)
    bc = g[f"breadth_{comparator}"].astype(float)
    q0 = g[f"quadrant_{BASELINE}"].astype(str)
    qc = g[f"quadrant_{comparator}"].astype(str)
    trans0 = q0 != q0.shift(1)
    transc = qc != qc.shift(1)
    return {
        "window": window_name,
        "comparator": comparator,
        "name": COMPARATORS[comparator],
        "n": int(len(g)),
        "breadth_pearson": float(b0.corr(bc)) if len(g) > 2 else np.nan,
        "breadth_spearman": float(b0.corr(bc, method="spearman")) if len(g) > 2 else np.nan,
        "breadth_mae_pp": float((b0 - bc).abs().mean()),
        "breadth_sign50_agreement": float(((b0 >= 50) == (bc >= 50)).mean()),
        "quadrant_agreement": float((q0 == qc).mean()),
        "transition_indicator_agreement": float((trans0.fillna(False) == transc.fillna(False)).mean()),
        "baseline_transition_rate": float(trans0.iloc[1:].mean()) if len(g) > 1 else np.nan,
        "candidate_transition_rate": float(transc.iloc[1:].mean()) if len(g) > 1 else np.nan,
    }


def predictive_stats(z, comparator, segment, lo=None):
    g = z.copy()
    if lo is not None:
        g = g[g.signal_date >= pd.Timestamp(lo)]
    rows = []
    for h in HORIZONS:
        cols = [f"breadth_{comparator}", f"fwd_return_{h}", f"fwd_mdd_{h}"]
        x = g[cols].dropna()
        if len(x) < 10:
            rr = rm = np.nan
        else:
            rr = float(x[cols[0]].corr(x[cols[1]], method="spearman"))
            rm = float(x[cols[0]].corr(x[cols[2]], method="spearman"))
        rows.append({"segment": segment, "comparator": comparator, "name": COMPARATORS[comparator],
                     "horizon": h, "n": int(len(x)), "spearman_future_return": rr,
                     "spearman_future_mdd": rm})
    return rows


def latest_rows(z):
    out = []
    for c in COMPARATORS:
        g = z.dropna(subset=[f"breadth_{c}", f"quadrant_{c}"])
        if g.empty:
            continue
        r = g.iloc[-1]
        out.append({"comparator": c, "name": COMPARATORS[c], "date": str(pd.Timestamp(r.signal_date).date()),
                    "breadth_pct": float(r[f"breadth_{c}"]), "breadth_count": int(r[f"breadth_count_{c}"]),
                    "comparator_score": float(r[f"comparator_score_{c}"]), "gap_percentile": float(r.gap_percentile),
                    "quadrant": str(r[f"quadrant_{c}"]), "top1": str(r.top1), "top2": str(r.top2)})
    return pd.DataFrame(out)


def main():
    db = os.getenv("ETF_DAILY_BARS_DATABASE_URL")
    if not db:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(os.getenv("OUTPUT_DIR", "stage8q-map-comparator-output")); out.mkdir(parents=True, exist_ok=True)
    eng = create_engine(_db_url(db), pool_pre_ping=True)
    bars = load_daily_bars(eng); bars["symbol"] = bars["symbol"].astype(str).str.zfill(6); bars["date"] = pd.to_datetime(bars["date"])
    feat = build_features(bars); feat["symbol"] = feat["symbol"].astype(str).str.zfill(6); feat["date"] = pd.to_datetime(feat["date"])
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat); cal = pd.DatetimeIndex(cal)
    raw_score = s8m.raw_score_wide(feat, cal, list(score.columns.astype(str)))
    missing = [s for s in list(RISK) + list(COMPARATORS) if s not in raw_score.columns]
    if missing:
        raise RuntimeError(f"missing symbols: {missing}")
    labels = fixed_strategy_labels(cal, score, gross, feat, bars)
    z = build_map_panel(cal, score, feat, labels)
    z.to_csv(out / "stage8q_daily_map_comparators.csv", index=False)

    ag = []
    for c in COMPARATORS:
        for w, lo in (("FULL_COMMON", None), ("POST2023", "2023-01-01")):
            rec = agreement_stats(z, c, w, lo)
            if rec: ag.append(rec)
    agreement = pd.DataFrame(ag)
    agreement.to_csv(out / "stage8q_map_agreement.csv", index=False)

    pr = []
    for c in COMPARATORS:
        pr += predictive_stats(z, c, "FULL", None)
        pr += predictive_stats(z, c, "POST2023", "2023-01-01")
    predictive = pd.DataFrame(pr)
    predictive.to_csv(out / "stage8q_predictive_utility.csv", index=False)

    latest = latest_rows(z); latest.to_csv(out / "stage8q_latest_states.csv", index=False)

    common_rows = []
    for c in COMPARATORS:
        g = z.dropna(subset=[f"breadth_{BASELINE}", f"breadth_{c}", f"quadrant_{BASELINE}", f"quadrant_{c}"]).copy()
        if g.empty: continue
        for name, mask in {
            "ALL_COMMON": pd.Series(True, index=g.index),
            "POST2023": g.signal_date >= pd.Timestamp("2023-01-01"),
            "DD2022": (g.signal_date >= pd.Timestamp("2022-03-09")) & (g.signal_date <= pd.Timestamp("2022-05-10")),
            "DD2026": (g.signal_date >= pd.Timestamp("2026-06-03")) & (g.signal_date <= pd.Timestamp("2026-08-19")),
        }.items():
            x = g.loc[mask]
            if x.empty: continue
            common_rows.append({"window": name, "comparator": c, "name": COMPARATORS[c], "n": len(x),
                                "baseline_breadth_mean": float(x[f"breadth_{BASELINE}"].mean()),
                                "candidate_breadth_mean": float(x[f"breadth_{c}"].mean()),
                                "breadth_delta_mean_pp": float((x[f"breadth_{c}"]-x[f"breadth_{BASELINE}"]).mean()),
                                "quadrant_agreement": float((x[f"quadrant_{c}"]==x[f"quadrant_{BASELINE}"]).mean()),
                                "defensive_void_rate_baseline": float((x[f"quadrant_{BASELINE}"]=="DEFENSIVE_VOID").mean()),
                                "defensive_void_rate_candidate": float((x[f"quadrant_{c}"]=="DEFENSIVE_VOID").mean())})
    event = pd.DataFrame(common_rows); event.to_csv(out / "stage8q_event_windows.csv", index=False)

    summary = {"study":"OURE Stage8Q map comparator robustness (website raw-score definition)", "baseline":BASELINE,
               "definition":"breadth = fixed-13 share of raw risky OLS scores above raw comparator OLS score; quadrant threshold breadth=50%, gap percentile=50%",
               "comparators":COMPARATORS,
               "latest":latest.to_dict(orient="records"),
               "post2023_agreement":agreement[agreement.window=="POST2023"].to_dict(orient="records"),
               "interpretation":"Diagnostic only; comparator replacement requires robustness, not same-sample winner selection."}
    (out / "stage8q_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    md = ["# Stage8Q — Market Regime Map Comparator Robustness", "",
          "Baseline: 511220. Uses the website's raw 26-day OLS map definition (no recent_drop3 eligibility mask).", "",
          "## Post-2023 agreement versus 511220", "",
          agreement[agreement.window=="POST2023"].to_markdown(index=False), "",
          "## Latest states", "", latest.to_markdown(index=False), "",
          "## Predictive utility", "", predictive.to_markdown(index=False), "",
          "Same-sample comparison is diagnostic only; no replacement is promoted by this stage."]
    (out / "stage8q_summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))

if __name__ == "__main__":
    main()
