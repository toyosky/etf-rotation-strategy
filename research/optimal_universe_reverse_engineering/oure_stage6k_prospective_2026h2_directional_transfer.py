#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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
import optimal_universe_reverse_engineering.oure_stage6e_rf_k30_rank as s6e
import optimal_universe_reverse_engineering.oure_stage6f_rf_surrogate_value as s6g
import optimal_universe_reverse_engineering.oure_stage6i_half_year_rf_horizon_diagnostic as s6i
import optimal_universe_reverse_engineering.oure_stage6j_chronological_mapping_transfer as s6j
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

SEED = 20260914
LOOKBACK = 126
HIST_PERIODS = ["2025H1", "2025H2", "2026H1"]
TARGET_START = pd.Timestamp("2026-07-01")


def current_library(d: int, cal, score, gross, close, meta, rng):
    decision_date = pd.Timestamp(cal[d])
    pool = s5.available_pool(close, meta, cal, d)
    if len(pool) < s6g.K:
        raise RuntimeError(f"too few candidates at {decision_date.date()}: {len(pool)}")
    past_dates = pd.DatetimeIndex(cal[d-LOOKBACK:d])
    past_ev = s6c.Eval(score, gross, past_dates, pool)
    combo_family, singles, families = s6g.build_family_library(past_ev, pool, rng)
    rows = []
    for u, fam in combo_family.items():
        fr = s6e.feature_row(past_ev, u)
        rows.append({
            "period": "2026H2",
            "decision_date": str(decision_date.date()),
            "pool_n": len(pool),
            "family_id": fam,
            "members": ",".join(u),
            **fr,
        })
    return pd.DataFrame(rows), families, singles


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage6k-output")
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
    hist_frames = {}

    # Reproduce Stage6I chronological RNG consumption exactly through 2026H1.
    for d in s5.decision_indices(cal):
        dt = pd.Timestamp(cal[d])
        if dt < pd.Timestamp("2022-01-01") or dt >= pd.Timestamp("2026-07-01"):
            continue
        pack = s6i.period_data(d, cal, score, gross, close, meta, rng)
        if pack is None:
            continue
        df, _, _ = pack
        p = str(df["period"].iloc[0])
        if p in HIST_PERIODS:
            hist_frames[p] = df.reset_index(drop=True)

    missing = [p for p in HIST_PERIODS if p not in hist_frames]
    if missing:
        raise RuntimeError(f"missing completed historical periods: {missing}")

    d_target = int(cal.searchsorted(TARGET_START, side="left"))
    if d_target <= LOOKBACK:
        raise RuntimeError("insufficient target history")
    target_date = pd.Timestamp(cal[d_target])
    current, families, singles = current_library(d_target, cal, score, gross, close, meta, rng)

    # PRIMARY: exact Stage6J unanimous-direction rule, using 2025H1/H2/2026H1 only.
    hist3 = [hist_frames[p] for p in HIST_PERIODS]
    primary_score, signs, rhos = s6j.directional_score(hist3, current)
    current["primary_unanimous_direction_score"] = primary_score
    current["primary_rank_pct"] = s6g.rank_pct(pd.Series(primary_score)).to_numpy(dtype=float)

    # Frozen secondary benchmark: previous-period RF trained only on 2026H1.
    prev_pred = s6j.fit_rf_predict(hist_frames["2026H1"], current)
    current["secondary_previous_period_rf"] = prev_pred
    current["secondary_previous_period_rf_rank_pct"] = s6g.rank_pct(pd.Series(prev_pred)).to_numpy(dtype=float)

    # Save feature correlations used to lock signs.
    diag_rows = []
    for f in s6g.FEATURES:
        vals = rhos.get(f, [])
        diag_rows.append({
            "feature": f,
            "rho_2025H1": vals[0] if len(vals) > 0 else np.nan,
            "rho_2025H2": vals[1] if len(vals) > 1 else np.nan,
            "rho_2026H1": vals[2] if len(vals) > 2 else np.nan,
            "retained": f in signs,
            "frozen_sign": signs.get(f, np.nan),
        })

    pred_path = out / "stage6k_2026H2_locked_predictions.csv"
    current.to_csv(pred_path, index=False)
    pd.DataFrame(diag_rows).to_csv(out / "stage6k_2026H2_feature_sign_lock.csv", index=False)
    families.to_csv(out / "stage6k_2026H2_family_bases.csv", index=False)
    singles.to_csv(out / "stage6k_2026H2_singletons.csv", index=False)

    # Check whether the prospective future label is already complete, but never evaluate it here.
    available_after = int((cal >= target_date).sum())
    future126_complete_now = bool(available_after >= 126)

    lock = {
        "study": "OURE Stage6K prospective 2026H2 directional transfer lock",
        "status": "prediction_locked_awaiting_future126",
        "decision_date": str(target_date.date()),
        "historical_mapping_periods": HIST_PERIODS,
        "candidate_n": int(len(current)),
        "family_n": int(current["family_id"].nunique()),
        "pool_n": int(current["pool_n"].iloc[0]),
        "feature_count": len(s6g.FEATURES),
        "retained_feature_n": int(len(signs)),
        "retained_features": sorted(signs.keys()),
        "frozen_signs": signs,
        "predictions_sha256": sha256_file(pred_path),
        "future126_complete_at_lock_time": future126_complete_now,
        "available_calendar_sessions_from_decision_at_lock_time": available_after,
        "primary_future_gate": {
            "spearman_gt": 0.10,
            "pred_top50_actual_percentile_gt": 0.55,
            "top_decile_log_lift_gt": 0.0,
            "all_required": True,
        },
        "secondary_previous_period_rf_cannot_rescue": True,
        "warning": "Do not regenerate or alter the stored candidate/prediction file when future labels become complete.",
    }
    (out / "oure_stage6k_prediction_lock.json").write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(lock, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
