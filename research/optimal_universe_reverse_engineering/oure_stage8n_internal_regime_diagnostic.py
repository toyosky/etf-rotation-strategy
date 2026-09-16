#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import cluster90_resistance_score_v1_test as v1lib
import optimal_universe_reverse_engineering.oure_stage8m_fixv2_v1_long_horizon as s8m
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

COST = 0.0006
HORIZONS = (5, 10, 20)
PCT_LOOKBACK = 252
PCT_MIN_HISTORY = 60
FEATURES = (
    "risk_churn20",
    "recent5_risk_episode_mean",
    "breadth",
    "median_signed_strength",
)
BAD_RULES = {
    "warn_high_churn": ("risk_churn20_pct252", ">=", 80.0),
    "warn_short_life": ("recent5_risk_episode_mean_pct252", "<=", 20.0),
    "warn_low_breadth": ("breadth_pct252", "<=", 20.0),
    "warn_weak_strength": ("median_signed_strength_pct252", "<=", 20.0),
}


def prior_percentile(s: pd.Series, lookback: int = PCT_LOOKBACK, min_hist: int = PCT_MIN_HISTORY) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce").to_numpy(float)
    out = np.full(len(x), np.nan, dtype=float)
    for i, cur in enumerate(x):
        if not np.isfinite(cur):
            continue
        hist = x[max(0, i - lookback):i]
        hist = hist[np.isfinite(hist)]
        if len(hist) >= min_hist:
            out[i] = 100.0 * float(np.mean(hist <= cur))
    return pd.Series(out, index=s.index, dtype=float)


def recent_episode_mean(raw_targets: pd.Series, n_recent: int = 5) -> pd.Series:
    vals = [None if pd.isna(v) else str(v) for v in raw_targets.tolist()]
    completed: list[int] = []
    out = np.full(len(vals), np.nan, dtype=float)
    prev = None
    run_len = 0
    for i, cur in enumerate(vals):
        if i == 0:
            prev, run_len = cur, 1
        elif cur == prev:
            run_len += 1
        else:
            if prev is not None:
                completed.append(int(run_len))
            prev, run_len = cur, 1
        if len(completed) >= n_recent:
            out[i] = float(np.mean(completed[-n_recent:]))
    return pd.Series(out, index=raw_targets.index, dtype=float)


def pivot_feature(feat: pd.DataFrame, cal: pd.DatetimeIndex, symbols: list[str], col: str) -> pd.DataFrame:
    z = feat[["date", "symbol", col]].copy()
    z["date"] = pd.to_datetime(z["date"])
    z["symbol"] = z["symbol"].astype(str).str.zfill(6)
    return z.pivot(index="date", columns="symbol", values=col).reindex(index=cal, columns=symbols)


def forward_mdd(r: np.ndarray) -> float:
    if len(r) == 0:
        return np.nan
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.r_[1.0, eq])[1:]
    return float(np.min(eq / peak - 1.0))


def add_forward_labels(z: pd.DataFrame) -> pd.DataFrame:
    out = z.copy()
    r = out["v1_net_ret"].to_numpy(float)
    for h in HORIZONS:
        fr = np.full(len(out), np.nan, dtype=float)
        fm = np.full(len(out), np.nan, dtype=float)
        for i in range(len(out)):
            if i + h <= len(out):
                w = r[i:i+h]
                fr[i] = float(np.prod(1.0 + w) - 1.0)
                fm[i] = forward_mdd(w)
        out[f"fwd_return_{h}"] = fr
        out[f"fwd_mdd_{h}"] = fm
    return out


def agg_outcome(g: pd.DataFrame, h: int) -> dict:
    r = pd.to_numeric(g[f"fwd_return_{h}"], errors="coerce")
    m = pd.to_numeric(g[f"fwd_mdd_{h}"], errors="coerce")
    ok = r.notna() & m.notna()
    r, m = r[ok], m[ok]
    if len(r) == 0:
        return {"n": 0, "mean_return": np.nan, "median_return": np.nan, "win_rate": np.nan,
                "q10_return": np.nan, "mean_fwd_mdd": np.nan, "median_fwd_mdd": np.nan}
    return {
        "n": int(len(r)), "mean_return": float(r.mean()), "median_return": float(r.median()),
        "win_rate": float((r > 0).mean()), "q10_return": float(r.quantile(0.10)),
        "mean_fwd_mdd": float(m.mean()), "median_fwd_mdd": float(m.median()),
    }


def build_quintiles(z: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for f in FEATURES:
        pcol = f + "_pct252"
        g0 = z.loc[z[pcol].notna()].copy()
        if g0.empty:
            continue
        g0["quintile"] = np.clip(np.floor(g0[pcol].astype(float) / 20.0).astype(int) + 1, 1, 5)
        for h in HORIZONS:
            for q, g in g0.groupby("quintile"):
                rows.append({"feature": f, "horizon": h, "quintile": int(q),
                             "mean_feature_pct": float(g[pcol].mean()), **agg_outcome(g, h)})
    return pd.DataFrame(rows)


def build_extremes(z: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for warn, (pcol, op, threshold) in BAD_RULES.items():
        g0 = z.loc[z[pcol].notna()].copy()
        if g0.empty:
            continue
        g0["warning"] = (g0[pcol] >= threshold) if op == ">=" else (g0[pcol] <= threshold)
        for h in HORIZONS:
            for state, g in g0.groupby("warning"):
                rows.append({"warning_name": warn, "feature_pct": pcol, "threshold": threshold,
                             "warning": bool(state), "horizon": h, **agg_outcome(g, h)})
    return pd.DataFrame(rows)


def build_bad_count(z: pd.DataFrame) -> pd.DataFrame:
    rows = []
    g0 = z.loc[z["bad_count"].notna()].copy()
    for h in HORIZONS:
        for k, g in g0.groupby("bad_count"):
            rows.append({"horizon": h, "bad_count": int(k), **agg_outcome(g, h)})
    return pd.DataFrame(rows)


def build_correlations(z: pd.DataFrame) -> pd.DataFrame:
    segments = {
        "FULL": pd.Series(True, index=z.index),
        "PRE2021": z["execution_date"] < pd.Timestamp("2021-01-01"),
        "POST2021": z["execution_date"] >= pd.Timestamp("2021-01-01"),
    }
    rows = []
    for sname, mask in segments.items():
        g = z.loc[mask].copy()
        for f in FEATURES:
            pcol = f + "_pct252"
            for h in HORIZONS:
                x = g[[pcol, f"fwd_return_{h}", f"fwd_mdd_{h}"]].dropna()
                if len(x) < 10:
                    cr = cm = np.nan
                else:
                    cr = float(x[pcol].corr(x[f"fwd_return_{h}"], method="spearman"))
                    cm = float(x[pcol].corr(x[f"fwd_mdd_{h}"], method="spearman"))
                rows.append({"segment": sname, "feature": f, "horizon": h, "n": int(len(x)),
                             "spearman_future_return": cr, "spearman_future_mdd": cm})
    return pd.DataFrame(rows)


def build_nonoverlap(z: pd.DataFrame) -> pd.DataFrame:
    pcols = [f + "_pct252" for f in FEATURES]
    g0 = z.dropna(subset=pcols + ["bad_count"]).copy().reset_index(drop=True)
    if g0.empty:
        return pd.DataFrame()
    g0 = g0.iloc[::20].copy()
    g0["bad_ge2"] = g0["bad_count"] >= 2
    return pd.DataFrame([{"bad_ge2": bool(state), **agg_outcome(g, 20)} for state, g in g0.groupby("bad_ge2")])


def summarize_window(g: pd.DataFrame, name: str) -> dict:
    rec = {"window": name, "n": int(len(g))}
    if g.empty:
        return rec
    rec.update({
        "start_execution": str(g["execution_date"].min().date()),
        "end_execution": str(g["execution_date"].max().date()),
        "strategy_compound": float(np.prod(1.0 + g["v1_net_ret"].to_numpy(float)) - 1.0),
        "risk_churn20_mean": float(g["risk_churn20"].mean()),
        "recent5_life_mean": float(g["recent5_risk_episode_mean"].mean()),
        "breadth_mean": float(g["breadth"].mean()),
        "median_signed_strength_mean": float(g["median_signed_strength"].mean()),
        "churn_pct_mean": float(g["risk_churn20_pct252"].mean()),
        "life_pct_mean": float(g["recent5_risk_episode_mean_pct252"].mean()),
        "breadth_pct_mean": float(g["breadth_pct252"].mean()),
        "strength_pct_mean": float(g["median_signed_strength_pct252"].mean()),
        "high_churn_rate": float(g["warn_high_churn"].mean()),
        "short_life_rate": float(g["warn_short_life"].mean()),
        "low_breadth_rate": float(g["warn_low_breadth"].mean()),
        "weak_strength_rate": float(g["warn_weak_strength"].mean()),
        "bad_count_mean": float(g["bad_count"].mean()),
        "bad_count_ge2_rate": float((g["bad_count"] >= 2).mean()),
    })
    return rec


def build_event_windows(z: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    defs = {
        "DD_2022": (pd.Timestamp("2022-03-09"), pd.Timestamp("2022-05-10")),
        "DD_2026": (pd.Timestamp("2026-06-03"), pd.Timestamp("2026-08-19")),
        "Y2020": (pd.Timestamp("2020-01-01"), pd.Timestamp("2020-12-31")),
        "Y2021": (pd.Timestamp("2021-01-01"), pd.Timestamp("2021-12-31")),
        "Y2025": (pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")),
    }
    rows, parts = [], []
    for name, (lo, hi) in defs.items():
        g = z.loc[(z["execution_date"] >= lo) & (z["execution_date"] <= hi)].copy()
        rows.append(summarize_window(g, name))
        if name.startswith("DD_") and not g.empty:
            start_idx = int(g.index.min())
            pre = z.loc[max(0, start_idx - 20): start_idx - 1].copy()
            pname = "PRE20_" + name.split("_", 1)[1]
            rows.append(summarize_window(pre, pname))
            pre["window"] = pname
            parts.append(pre)
        if not g.empty:
            g["window"] = name
            parts.append(g)
    return pd.DataFrame(rows), pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def build_annual_warning(z: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for y, g in z.groupby(z["execution_date"].dt.year):
        rows.append({
            "year": int(y), "sessions": int(len(g)),
            "strategy_return": float(np.prod(1.0 + g["v1_net_ret"].to_numpy(float)) - 1.0),
            "high_churn_rate": float(g["warn_high_churn"].mean()),
            "short_life_rate": float(g["warn_short_life"].mean()),
            "low_breadth_rate": float(g["warn_low_breadth"].mean()),
            "weak_strength_rate": float(g["warn_weak_strength"].mean()),
            "bad_count_mean": float(g["bad_count"].mean()),
            "bad_count_ge2_rate": float((g["bad_count"] >= 2).mean()),
            "risk_churn20_mean": float(g["risk_churn20"].mean()),
            "recent5_life_mean": float(g["recent5_risk_episode_mean"].mean()),
            "breadth_mean": float(g["breadth"].mean()),
            "median_signed_strength_mean": float(g["median_signed_strength"].mean()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage8n-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng)
    bars["symbol"] = bars["symbol"].astype(str).str.zfill(6)
    bars["date"] = pd.to_datetime(bars["date"])
    feat = build_features(bars)
    feat["symbol"] = feat["symbol"].astype(str).str.zfill(6)
    feat["date"] = pd.to_datetime(feat["date"])
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)

    cash_ok = score[s8m.CASH].notna() & np.isfinite(score[s8m.CASH]) & (score.index >= s8m.START_FLOOR)
    if not cash_ok.any():
        raise RuntimeError("cash comparator never becomes valid")
    first_signal = pd.Timestamp(score.index[cash_ok][0])
    start_i = int(cal.get_loc(first_signal)); last_i = len(cal) - 3

    raw = s8m.build_raw_targets(cal, score, s8m.MAIN_MEMBERS, start_i, last_i)
    symbols = list(score.columns.astype(str))
    raw_score = s8m.raw_score_wide(feat, cal, symbols)
    annual_w = pivot_feature(feat, cal, symbols, "annual")
    raw_r2_w = pivot_feature(feat, cal, symbols, "r2")
    signed_strength_w = annual_w * raw_r2_w
    raw_delta = raw_score.diff()

    needed = set(raw["target"].dropna().astype(str).unique())
    profiles_df = v1lib.build_needed_profiles(bars, needed)
    profiles = profiles_df.set_index(["date", "symbol"])["resistance_pct252"].to_dict()
    v1, events = s8m.build_v1_targets(raw, score, raw_delta, profiles, s8m.MAIN_MEMBERS, s8m.MAIN_THRESHOLD)
    v1 = s8m.attach_returns(v1, gross, COST)

    z = raw[["signal_pos", "signal_date", "execution_date", "return_end_date", "target"]].copy()
    z = z.rename(columns={"target": "raw_target"})
    z["v1_target"] = v1["target"].values
    z["v1_net_ret"] = v1["net_ret"].values
    z["v1_sides"] = v1["sides"].values

    raw_state = z["raw_target"].where(z["raw_target"].notna(), "__CASH__").astype(str)
    prev = raw_state.shift(1)
    risk_switch = (raw_state != prev) & (raw_state != "__CASH__") & prev.notna() & (prev != "__CASH__")
    total_switch = (raw_state != prev) & prev.notna()
    z["risk_switch"] = risk_switch.astype(int)
    z["total_state_switch"] = total_switch.astype(int)
    z["risk_churn20"] = z["risk_switch"].rolling(20, min_periods=20).sum()
    z["total_churn20"] = z["total_state_switch"].rolling(20, min_periods=20).sum()
    z["recent5_risk_episode_mean"] = recent_episode_mean(z["raw_target"], 5)

    breadth, strength, ready_n, positive_n = [], [], [], []
    risk_syms = [s for s in s8m.MAIN_RISK if s in raw_score.columns and s in score.columns]
    for r in z.itertuples(index=False):
        d = pd.Timestamp(r.signal_date)
        rawvals = raw_score.loc[d, risk_syms].astype(float)
        rawvals = rawvals[np.isfinite(rawvals)]
        available = list(rawvals.index.astype(str))
        ready_n.append(int(len(available)))
        if not available:
            breadth.append(np.nan); strength.append(np.nan); positive_n.append(0); continue
        poolvals = score.loc[d, available].astype(float)
        pos = np.isfinite(poolvals.to_numpy(float))
        positive_n.append(int(pos.sum()))
        breadth.append(float(pos.mean()))
        svals = signed_strength_w.loc[d, available].astype(float)
        svals = svals[np.isfinite(svals)]
        strength.append(float(np.median(svals.to_numpy(float))) if len(svals) else np.nan)
    z["ols_ready_risk_n"] = ready_n
    z["positive_trend_risk_n"] = positive_n
    z["breadth"] = breadth
    z["median_signed_strength"] = strength

    for f in FEATURES:
        z[f + "_pct252"] = prior_percentile(z[f])

    z["warn_high_churn"] = z["risk_churn20_pct252"] >= 80.0
    z["warn_short_life"] = z["recent5_risk_episode_mean_pct252"] <= 20.0
    z["warn_low_breadth"] = z["breadth_pct252"] <= 20.0
    z["warn_weak_strength"] = z["median_signed_strength_pct252"] <= 20.0
    pcols = [f + "_pct252" for f in FEATURES]
    all_ready = z[pcols].notna().all(axis=1)
    z["bad_count"] = np.where(all_ready, z[list(BAD_RULES.keys())].sum(axis=1).astype(float), np.nan)
    z = add_forward_labels(z)

    quint = build_quintiles(z)
    extremes = build_extremes(z)
    bad = build_bad_count(z)
    corr = build_correlations(z)
    nonov = build_nonoverlap(z)
    windows, window_daily = build_event_windows(z)
    annual = build_annual_warning(z)

    z.to_csv(out / "stage8n_daily.csv", index=False)
    quint.to_csv(out / "stage8n_feature_quintiles.csv", index=False)
    extremes.to_csv(out / "stage8n_extreme_states.csv", index=False)
    bad.to_csv(out / "stage8n_bad_count.csv", index=False)
    corr.to_csv(out / "stage8n_correlations.csv", index=False)
    nonov.to_csv(out / "stage8n_nonoverlap20.csv", index=False)
    windows.to_csv(out / "stage8n_event_windows.csv", index=False)
    window_daily.to_csv(out / "stage8n_event_window_daily.csv", index=False)
    annual.to_csv(out / "stage8n_annual_warning_rates.csv", index=False)

    summary = {
        "study": "OURE Stage8N internal regime diagnostic corrected",
        "status": "completed",
        "first_signal": str(first_signal.date()), "last_signal": str(z["signal_date"].max().date()),
        "sessions": int(len(z)), "fully_ready_sessions": int(all_ready.sum()),
        "features": list(FEATURES), "bad_rules": BAD_RULES,
        "event_windows": windows.to_dict(orient="records"),
        "nonoverlap20": nonov.to_dict(orient="records"),
    }
    (out / "stage8n_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print("\nBAD COUNT\n", bad.to_string(index=False))
    print("\nEVENT WINDOWS\n", windows.to_string(index=False))
    print("\nCORRELATIONS\n", corr.to_string(index=False))
    print("\nANNUAL\n", annual.to_string(index=False))


if __name__ == "__main__":
    main()
