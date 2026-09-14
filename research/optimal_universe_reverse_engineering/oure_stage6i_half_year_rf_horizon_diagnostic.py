#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage5_history_transfer as s5
import optimal_universe_reverse_engineering.oure_stage6c_fullmarket_2022_2024_k_frontier as s6c
import optimal_universe_reverse_engineering.oure_stage6f_rf_surrogate_value as s6g
import optimal_universe_reverse_engineering.oure_stage6e_rf_k30_rank as s6e
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

LOOKBACK = 126
FUTURE = 126
SEED = 20260914
OLD_LONG_HORIZON_IC = 0.0129


def period_name(ts: pd.Timestamp) -> str:
    return f"{ts.year}H{1 if ts.month < 7 else 2}"


def period_data(
    decision_pos: int,
    cal: pd.DatetimeIndex,
    score: pd.DataFrame,
    gross: pd.DataFrame,
    close: pd.DataFrame,
    meta: pd.DataFrame,
    rng: np.random.Generator,
):
    d = int(decision_pos)
    decision_date = pd.Timestamp(cal[d])
    if d < max(252, LOOKBACK):
        raise RuntimeError(f"insufficient history at {decision_date.date()}")
    if d + FUTURE > len(cal) - 2:
        return None

    pool = s5.available_pool(close, meta, cal, d)
    if len(pool) < s6g.K:
        raise RuntimeError(f"too few candidates at {decision_date.date()}: {len(pool)}")

    past_dates = pd.DatetimeIndex(cal[d-LOOKBACK:d])
    future_dates = pd.DatetimeIndex(cal[d:d+FUTURE])
    past_ev = s6c.Eval(score, gross, past_dates, pool)
    future_ev = s6c.Eval(score, gross, future_dates, pool)
    combo_family, singles, families = s6g.build_family_library(past_ev, pool, rng)

    rows = []
    for u, fam in combo_family.items():
        fr = s6e.feature_row(past_ev, u)
        fut = future_ev.evaluate(u)
        rows.append({
            "period": period_name(decision_date),
            "decision_date": str(decision_date.date()),
            "future_end_date": str(pd.Timestamp(future_dates[-1]).date()),
            "pool_n": len(pool),
            "family_id": fam,
            "members": ",".join(u),
            "future_log_growth": float(fut["log_growth"]),
            "future_total_return": float(fut["total_return"]),
            **fr,
        })
    df = pd.DataFrame(rows)
    df["future_rank_pct"] = s6g.rank_pct(df["future_log_growth"])
    families["period"] = period_name(decision_date)
    families["decision_date"] = str(decision_date.date())
    singles["period"] = period_name(decision_date)
    singles["decision_date"] = str(decision_date.date())
    return df, families, singles


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage6i-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng)
    bars["symbol"] = bars["symbol"].astype(str)
    feat = build_features(bars)
    feat["symbol"] = feat["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)
    meta = pd.read_sql_query(text("""
        select symbol,has_daily_bars,leveraged_flag,inverse_flag
        from public.instrument_metadata_current
    """), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    rng = np.random.default_rng(SEED)
    dec = s5.decision_indices(cal)
    data_frames = []
    family_frames = []
    singleton_frames = []
    period_rows = []
    cv_frames = []
    pred_frames = []
    imp_frames = []

    for d in dec:
        dt = pd.Timestamp(cal[d])
        if dt < pd.Timestamp("2022-01-01") or dt >= pd.Timestamp("2026-07-01"):
            continue
        pdout = period_data(d, cal, score, gross, close, meta, rng)
        if pdout is None:
            continue
        df, families, singles = pdout
        p = str(df["period"].iloc[0])
        data_frames.append(df)
        family_frames.append(families)
        singleton_frames.append(singles)

        cv, pred, imp = s6g.group_cv(df.reset_index(drop=True), p)
        cv["period"] = p
        pred["period"] = p
        imp["period"] = p
        cv_frames.append(cv)
        pred_frames.append(pred)
        imp_frames.append(imp)

        med_ic = float(cv["spearman"].median())
        pos_fold_n = int((cv["spearman"] > 0).sum())
        med_top = float(cv["pred_top50_mean_actual_percentile"].median())
        med_lift = float(cv["pred_top_decile_log_lift"].median())
        strong = bool(med_ic > 0.15 and pos_fold_n >= 4 and med_top > 0.65 and med_lift > 0)
        period_rows.append({
            "period": p,
            "decision_date": str(dt.date()),
            "era": "2022_2024" if dt < pd.Timestamp("2025-01-01") else "2025_2026",
            "sample_n": int(len(df)),
            "family_n": int(df["family_id"].nunique()),
            "pool_n": int(df["pool_n"].iloc[0]),
            "median_fold_spearman": med_ic,
            "positive_fold_n": pos_fold_n,
            "median_pred_top50_actual_percentile": med_top,
            "median_top_decile_log_lift": med_lift,
            "learnable_strong": strong,
        })

    if not period_rows:
        raise RuntimeError("no completed half-year periods")

    data = pd.concat(data_frames, ignore_index=True)
    families = pd.concat(family_frames, ignore_index=True)
    singles = pd.concat(singleton_frames, ignore_index=True)
    cv_all = pd.concat(cv_frames, ignore_index=True)
    pred_all = pd.concat(pred_frames, ignore_index=True)
    imp_all = pd.concat(imp_frames, ignore_index=True)
    periods = pd.DataFrame(period_rows).sort_values("decision_date")

    data.to_csv(out / "stage6i_k30_samples.csv", index=False)
    families.to_csv(out / "stage6i_family_bases.csv", index=False)
    singles.to_csv(out / "stage6i_singletons.csv", index=False)
    cv_all.to_csv(out / "stage6i_cv_metrics.csv", index=False)
    pred_all.to_csv(out / "stage6i_cv_predictions.csv", index=False)
    imp_all.to_csv(out / "stage6i_feature_importance_by_fold.csv", index=False)
    periods.to_csv(out / "stage6i_period_summary.csv", index=False)

    imp_summary = (
        imp_all.groupby(["period", "feature"], as_index=False)["importance"]
        .agg(mean="mean", median="median")
    )
    imp_summary.to_csv(out / "stage6i_feature_importance_summary.csv", index=False)

    old = periods[periods["era"] == "2022_2024"].copy()
    new = periods[periods["era"] == "2025_2026"].copy()
    if len(old) != 6:
        raise RuntimeError(f"expected six 2022-24 half-years, got {len(old)}")

    old_med_ic = float(old["median_fold_spearman"].median())
    old_pos_periods = int((old["median_fold_spearman"] > 0).sum())
    gate1 = bool(old_med_ic > 0.10)
    gate2 = bool(old_pos_periods >= 4)
    gate3 = bool((old_med_ic - OLD_LONG_HORIZON_IC) >= 0.10)
    gate_count = int(gate1) + int(gate2) + int(gate3)
    if gate_count == 3:
        decision = "strong_horizon_mismatch_support"
    elif gate_count == 2:
        decision = "partial_horizon_mismatch_support"
    else:
        decision = "horizon_mismatch_insufficient"

    summary = {
        "study": "OURE Stage6I half-year RF horizon diagnostic",
        "status": "completed",
        "rf_params": s6g.RF_PARAMS,
        "feature_count": len(s6g.FEATURES),
        "period_count": int(len(periods)),
        "old_period_count": int(len(old)),
        "new_period_count": int(len(new)),
        "old_median_period_ic": old_med_ic,
        "old_positive_period_n": old_pos_periods,
        "old_long_horizon_stage6g_ic": OLD_LONG_HORIZON_IC,
        "old_halfyear_minus_longhorizon_ic": float(old_med_ic - OLD_LONG_HORIZON_IC),
        "new_median_period_ic": float(new["median_fold_spearman"].median()) if len(new) else None,
        "new_positive_period_n": int((new["median_fold_spearman"] > 0).sum()) if len(new) else 0,
        "strong_learnable_periods": periods.loc[periods["learnable_strong"], "period"].tolist(),
        "gates": {
            "old_median_ic_positive": gate1,
            "old_positive_period_breadth": gate2,
            "old_horizon_improvement": gate3,
        },
        "gate_count": gate_count,
        "decision": decision,
        "warning": "mechanism diagnostic only; current metadata survivorship caveat; no RF or feature tuning",
    }
    (out / "oure_stage6i_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
