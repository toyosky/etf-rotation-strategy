#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine, text
from xgboost import XGBRanker, XGBRegressor

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage5_history_transfer as s5
import optimal_universe_reverse_engineering.oure_stage6c_fullmarket_2022_2024_k_frontier as s6c
import optimal_universe_reverse_engineering.oure_stage6f_rf_surrogate_value as s6g
import optimal_universe_reverse_engineering.oure_stage6k_adjacent_126_transfer as s6k
import optimal_universe_reverse_engineering.oure_stage6l_rf_false_positive_structure as s6l
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

LOOKBACK = 126
FUTURE = 126
SEED = 20260915
RF_HIGH_FRAC = 0.20
TARGET_BLOCKS = ["B05", "B06", "B07", "B08", "B09"]

XGB_COMMON = dict(
    n_estimators=300,
    max_depth=3,
    learning_rate=0.03,
    min_child_weight=10,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=1.0,
    reg_lambda=10.0,
    n_jobs=4,
    random_state=SEED,
)


def rank_pct(s: pd.Series) -> pd.Series:
    return s6g.rank_pct(pd.Series(s, dtype=float))


def spearman(a, b) -> float:
    v = s6g.spearman(a, b)
    return float(v) if np.isfinite(v) else np.nan


def prepare_xy(train: pd.DataFrame, test: pd.DataFrame, features: list[str]):
    tr = train[features].replace([np.inf, -np.inf], np.nan)
    te = test[features].replace([np.inf, -np.inf], np.nan)
    med = tr.median(axis=0)
    tr = tr.fillna(med).fillna(0.0)
    te = te.fillna(med).fillna(0.0)
    return tr, te


def score_metrics(test: pd.DataFrame, score: np.ndarray, rule: str) -> dict:
    t = test.copy().reset_index(drop=True)
    t["model_score"] = np.asarray(score, dtype=float)
    ic = spearman(t["model_score"], t["future_rank_within_high"])
    n_top = min(50, len(t))
    top50 = t.nlargest(n_top, "model_score")
    dec_n = max(1, int(math.ceil(len(t) * 0.10)))
    topdec = t.nlargest(dec_n, "model_score")
    return {
        "target_block": str(t["target_block"].iloc[0]),
        "rule": rule,
        "sample_n": int(len(t)),
        "spearman_within_high": ic,
        "positive_ic": bool(np.isfinite(ic) and ic > 0),
        "top50_actual_percentile": float(top50["future_rank_within_high"].mean()),
        "top_decile_future_log_lift": float(topdec["future_log_growth"].mean() - t["future_log_growth"].mean()),
        "top_decile_mean_future_log": float(topdec["future_log_growth"].mean()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage6n-output")
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

    # Rebuild the exact strict Stage6K blocks.
    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    rng = np.random.default_rng(20260914)
    frames = []
    b = 1
    pos = start0
    while True:
        pack = s6k.block_data(b, pos, cal, score, gross, close, meta, rng)
        if pack is None:
            break
        frames.append(pack[0])
        b += 1
        pos += FUTURE
    data = pd.concat(frames, ignore_index=True)
    block_ids = data[["block", "block_no"]].drop_duplicates().sort_values("block_no")["block"].astype(str).tolist()

    # Rebuild Stage6L RF-high samples and the same 47 internal past-only features.
    high_frames = []
    internal_cols: list[str] | None = None
    for j in range(1, len(block_ids)):
        prev_b, target_b = block_ids[j - 1], block_ids[j]
        prev = data[data["block"] == prev_b].copy().reset_index(drop=True)
        test = data[data["block"] == target_b].copy().reset_index(drop=True)
        pred, _ = s6k.fit_rf(prev, test)
        test["rf_pred"] = pred
        test["rf_pred_rank_pct"] = rank_pct(test["rf_pred"]).to_numpy()
        test["residual_rank"] = test["future_rank_pct"].astype(float) - test["rf_pred_rank_pct"].astype(float)
        n_hi = max(1, int(math.ceil(len(test) * RF_HIGH_FRAC)))
        high = test.nlargest(n_hi, "rf_pred").copy().reset_index(drop=True)
        high["future_rank_within_high"] = rank_pct(high["future_log_growth"]).to_numpy()

        decision_date = pd.Timestamp(high["decision_date"].iloc[0])
        d = int(cal.get_indexer([decision_date])[0])
        pool = s5.available_pool(close, meta, cal, d)
        past_dates = pd.DatetimeIndex(cal[d - LOOKBACK:d])
        ev = s6c.Eval(score, gross, past_dates, pool)

        feats = []
        for _, row in high.iterrows():
            members = tuple(str(row["members"]).split(","))
            feats.append(s6l.internal_features(ev, members, score, gross, past_dates))
        fdf = pd.DataFrame(feats)
        if internal_cols is None:
            internal_cols = list(fdf.columns)
        high = pd.concat([high, fdf], axis=1)
        high["target_block"] = target_b
        high_frames.append(high)

    if internal_cols is None or len(internal_cols) != 47:
        raise RuntimeError(f"Expected 47 Stage6L internal features, got {0 if internal_cols is None else len(internal_cols)}")

    high_all = pd.concat(high_frames, ignore_index=True)
    high_all.to_csv(out / "stage6n_rf_high_internal_samples.csv", index=False)

    metrics = []
    pred_rows = []
    residual_rows = []

    for target_b in TARGET_BLOCKS:
        if target_b not in set(high_all["target_block"]):
            raise RuntimeError(f"Missing target block {target_b}")
        target_no = int(target_b[1:])
        train_blocks = [b for b in high_all["target_block"].drop_duplicates().tolist() if int(str(b)[1:]) < target_no]
        train = high_all[high_all["target_block"].isin(train_blocks)].copy().reset_index(drop=True)
        test = high_all[high_all["target_block"] == target_b].copy().reset_index(drop=True)
        if len(train_blocks) < 3:
            raise RuntimeError(f"{target_b} has too few training blocks: {train_blocks}")

        xtr, xte = prepare_xy(train, test, internal_cols)
        y_resid = train["residual_rank"].astype(float).to_numpy()

        # Baselines.
        metrics.append(score_metrics(test, test["rf_pred"].to_numpy(dtype=float), "first_layer_rf"))
        metrics.append(score_metrics(test, test["past126_log_growth"].to_numpy(dtype=float), "past126_log_growth"))

        # M0 Ridge47 residual baseline.
        scaler = StandardScaler()
        xtr_s = scaler.fit_transform(xtr)
        xte_s = scaler.transform(xte)
        ridge = Ridge(alpha=10.0)
        ridge.fit(xtr_s, y_resid)
        pred_ridge_resid = ridge.predict(xte_s)
        ridge_final = test["rf_pred_rank_pct"].to_numpy(dtype=float) + pred_ridge_resid
        metrics.append(score_metrics(test, ridge_final, "ridge47_residual"))
        residual_rows.append({
            "target_block": target_b,
            "rule": "ridge47_residual",
            "residual_spearman": spearman(pred_ridge_resid, test["residual_rank"]),
        })

        # M1 frozen XGBoost residual regression.
        xgbr = XGBRegressor(objective="reg:squarederror", **XGB_COMMON)
        xgbr.fit(xtr, y_resid, verbose=False)
        pred_xgb_resid = xgbr.predict(xte)
        xgb_final = test["rf_pred_rank_pct"].to_numpy(dtype=float) + pred_xgb_resid
        metrics.append(score_metrics(test, xgb_final, "xgb_residual"))
        residual_rows.append({
            "target_block": target_b,
            "rule": "xgb_residual",
            "residual_spearman": spearman(pred_xgb_resid, test["residual_rank"]),
        })

        # M2 frozen pairwise ranker. Sort historical rows by block so qid is nondecreasing.
        train_rank = train.copy().sort_values(["target_block", "family_id", "members"]).reset_index(drop=True)
        xtr_r, xte_r = prepare_xy(train_rank, test, internal_cols)
        qid_map = {b: i for i, b in enumerate(sorted(train_rank["target_block"].unique(), key=lambda z: int(str(z)[1:]))) }
        qid = train_rank["target_block"].map(qid_map).astype(int).to_numpy()
        y_rank = train_rank["future_rank_within_high"].astype(float).to_numpy()
        ranker = XGBRanker(objective="rank:pairwise", **XGB_COMMON)
        ranker.fit(xtr_r, y_rank, qid=qid, verbose=False)
        pred_rank = ranker.predict(xte_r)
        metrics.append(score_metrics(test, pred_rank, "xgb_pairwise_ranker"))

        for i, row in test.iterrows():
            pred_rows.append({
                "target_block": target_b,
                "family_id": row["family_id"],
                "members": row["members"],
                "future_log_growth": float(row["future_log_growth"]),
                "future_rank_within_high": float(row["future_rank_within_high"]),
                "residual_rank": float(row["residual_rank"]),
                "first_layer_rf": float(row["rf_pred"]),
                "ridge47_final": float(ridge_final[i]),
                "xgb_residual_final": float(xgb_final[i]),
                "xgb_pairwise_ranker": float(pred_rank[i]),
            })

    m = pd.DataFrame(metrics)
    r = pd.DataFrame(residual_rows)
    p = pd.DataFrame(pred_rows)
    m.to_csv(out / "stage6n_period_metrics.csv", index=False)
    r.to_csv(out / "stage6n_residual_metrics.csv", index=False)
    p.to_csv(out / "stage6n_predictions.csv", index=False)

    summary = {}
    for rule, g in m.groupby("rule"):
        summary[rule] = {
            "median_spearman_within_high": float(g["spearman_within_high"].median()),
            "positive_ic_n": int((g["spearman_within_high"] > 0).sum()),
            "median_top50_actual_percentile": float(g["top50_actual_percentile"].median()),
            "median_top_decile_future_log_lift": float(g["top_decile_future_log_lift"].median()),
        }
    for rule, g in r.groupby("rule"):
        summary.setdefault(rule, {})["median_residual_spearman"] = float(g["residual_spearman"].median())
        summary[rule]["positive_residual_ic_n"] = int((g["residual_spearman"] > 0).sum())

    base = summary["first_layer_rf"]
    m2 = summary["xgb_pairwise_ranker"]
    m1 = summary["xgb_residual"]
    m0 = summary["ridge47_residual"]

    m2_gates = {
        "median_ic_gt_0_10": bool(m2["median_spearman_within_high"] > 0.10),
        "positive_ic_ge_4_of_5": bool(m2["positive_ic_n"] >= 4),
        "median_top50_gain_vs_rf_ge_0_05": bool((m2["median_top50_actual_percentile"] - base["median_top50_actual_percentile"]) >= 0.05),
        "median_top_decile_lift_positive_and_gt_rf": bool(m2["median_top_decile_future_log_lift"] > 0 and m2["median_top_decile_future_log_lift"] > base["median_top_decile_future_log_lift"]),
    }
    m1_gates = {
        "median_residual_ic_gt_0_10": bool(m1.get("median_residual_spearman", np.nan) > 0.10),
        "positive_residual_ic_ge_4_of_5": bool(m1.get("positive_residual_ic_n", 0) >= 4),
        "median_top50_gain_vs_ridge_ge_0_05": bool((m1["median_top50_actual_percentile"] - m0["median_top50_actual_percentile"]) >= 0.05),
    }

    m2_pass = bool(all(m2_gates.values()))
    m1_signal = bool(all(m1_gates.values()))
    if m2_pass:
        decision = "pairwise_nonlinear_second_layer_supported"
    elif m1_signal:
        decision = "nonlinear_residual_signal_but_pairwise_primary_failed"
    else:
        decision = "xgboost_second_layer_not_supported"

    result = {
        "study": "OURE Stage6N frozen nonlinear second-layer test",
        "status": "completed",
        "target_blocks": TARGET_BLOCKS,
        "internal_feature_n": len(internal_cols),
        "xgb_common": XGB_COMMON,
        "rule_summary": summary,
        "m2_primary_gates": m2_gates,
        "m2_primary_pass": m2_pass,
        "m1_secondary_gates": m1_gates,
        "m1_secondary_signal": m1_signal,
        "decision": decision,
        "warning": "Frozen one-shot nonlinear model-class test; no hyperparameter/feature/window tuning permitted after outcome inspection.",
    }
    (out / "oure_stage6n_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
