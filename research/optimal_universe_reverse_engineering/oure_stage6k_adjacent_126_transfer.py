#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
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


def spearman(a, b) -> float:
    v = s6g.spearman(a, b)
    return float(v) if np.isfinite(v) else np.nan


def rank_pct(s: pd.Series) -> pd.Series:
    return s6g.rank_pct(s.astype(float))


def fit_rf(train: pd.DataFrame, test: pd.DataFrame):
    med = train[s6g.FEATURES].replace([np.inf, -np.inf], np.nan).median(axis=0)
    xtr = train[s6g.FEATURES].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
    xte = test[s6g.FEATURES].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
    ytr = train["future_log_growth"].astype(float)
    rf = RandomForestRegressor(**s6g.RF_PARAMS)
    rf.fit(xtr, ytr)
    return rf.predict(xte), rf


def block_data(
    block_no: int,
    start_pos: int,
    cal: pd.DatetimeIndex,
    score: pd.DataFrame,
    gross: pd.DataFrame,
    close: pd.DataFrame,
    meta: pd.DataFrame,
    rng: np.random.Generator,
):
    d = int(start_pos)
    if d < max(252, LOOKBACK):
        raise RuntimeError("insufficient prehistory")
    if d + FUTURE > len(cal) - 2:
        return None

    decision_date = pd.Timestamp(cal[d])
    pool = s5.available_pool(close, meta, cal, d)
    if len(pool) < s6g.K:
        raise RuntimeError(f"too few candidates at {decision_date.date()}: {len(pool)}")

    past_dates = pd.DatetimeIndex(cal[d-LOOKBACK:d])
    future_dates = pd.DatetimeIndex(cal[d:d+FUTURE])
    past_ev = s6c.Eval(score, gross, past_dates, pool)
    future_ev = s6c.Eval(score, gross, future_dates, pool)
    combo_family, singles, families = s6g.build_family_library(past_ev, pool, rng)

    bid = f"B{block_no:02d}"
    rows = []
    for u, fam in combo_family.items():
        fr = s6e.feature_row(past_ev, u)
        fut = future_ev.evaluate(u)
        rows.append({
            "block": bid,
            "block_no": block_no,
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
    df["future_rank_pct"] = rank_pct(df["future_log_growth"])
    families["block"] = bid
    families["decision_date"] = str(decision_date.date())
    singles["block"] = bid
    singles["decision_date"] = str(decision_date.date())
    return df, families, singles


def evaluate_scores(test: pd.DataFrame, pred: np.ndarray, rule: str, train_blocks: str) -> dict:
    t = test.copy()
    t["pred"] = np.asarray(pred, dtype=float)
    ic = spearman(t["pred"], t["future_log_growth"])
    n_top = min(50, len(t))
    ptop = t.nlargest(n_top, "pred")
    dec_n = max(1, int(np.ceil(len(t) * 0.10)))
    pdec = t.nlargest(dec_n, "pred")
    return {
        "test_block": str(t["block"].iloc[0]),
        "test_decision_date": str(t["decision_date"].iloc[0]),
        "rule": rule,
        "train_blocks": train_blocks,
        "train_block_n": len(train_blocks.split(",")) if train_blocks else 0,
        "test_n": int(len(t)),
        "spearman": ic,
        "positive_ic": bool(np.isfinite(ic) and ic > 0),
        "pred_top50_mean_actual_percentile": float(ptop["future_rank_pct"].mean()),
        "pred_top_decile_log_lift": float(pdec["future_log_growth"].mean() - t["future_log_growth"].mean()),
        "pred_top_decile_mean_future_log": float(pdec["future_log_growth"].mean()),
        "test_mean_future_log": float(t["future_log_growth"].mean()),
    }


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

    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    if start0 < 252:
        raise RuntimeError("insufficient 2022 prehistory")

    rng = np.random.default_rng(SEED)
    frames = []
    fam_frames = []
    single_frames = []
    b = 1
    pos = start0
    while True:
        pack = block_data(b, pos, cal, score, gross, close, meta, rng)
        if pack is None:
            break
        df, fam, single = pack
        frames.append(df)
        fam_frames.append(fam)
        single_frames.append(single)
        b += 1
        pos += FUTURE

    if len(frames) < 4:
        raise RuntimeError(f"too few complete blocks: {len(frames)}")

    data = pd.concat(frames, ignore_index=True)
    pd.concat(fam_frames, ignore_index=True).to_csv(out / "stage6k_family_bases.csv", index=False)
    pd.concat(single_frames, ignore_index=True).to_csv(out / "stage6k_singletons.csv", index=False)
    data.to_csv(out / "stage6k_k30_samples.csv", index=False)

    block_ids = [str(x) for x in data[["block", "block_no"]].drop_duplicates().sort_values("block_no")["block"]]
    metrics = []
    preds = []
    imps = []

    for j in range(1, len(block_ids)):
        prev_b = block_ids[j-1]
        test_b = block_ids[j]
        prev = data[data["block"] == prev_b].copy().reset_index(drop=True)
        test = data[data["block"] == test_b].copy().reset_index(drop=True)

        # PRIMARY: immediately previous fully completed block only.
        pred_prev, rf_prev = fit_rf(prev, test)
        metrics.append(evaluate_scores(test, pred_prev, "previous_block_rf", prev_b))
        for f, v in zip(s6g.FEATURES, rf_prev.feature_importances_):
            imps.append({"test_block": test_b, "rule": "previous_block_rf", "feature": f, "importance": float(v)})

        # Secondary: expanding fully completed history.
        hist_ids = block_ids[:j]
        hist = data[data["block"].isin(hist_ids)].copy().reset_index(drop=True)
        pred_exp, _ = fit_rf(hist, test)
        metrics.append(evaluate_scores(test, pred_exp, "expanding_history_rf", ",".join(hist_ids)))

        # Secondary simple current X<=t benchmark.
        pred_past = test["past126_log_growth"].astype(float).to_numpy()
        metrics.append(evaluate_scores(test, pred_past, "current_past126_log_rank", ""))

        for i, r in test.iterrows():
            preds.append({
                "test_block": test_b,
                "decision_date": r["decision_date"],
                "family_id": r["family_id"],
                "members": r["members"],
                "future_log_growth": float(r["future_log_growth"]),
                "future_rank_pct": float(r["future_rank_pct"]),
                "previous_block_rf": float(pred_prev[i]),
                "expanding_history_rf": float(pred_exp[i]),
                "current_past126_log_growth": float(pred_past[i]),
            })

    m = pd.DataFrame(metrics)
    m.to_csv(out / "stage6k_transfer_metrics.csv", index=False)
    pd.DataFrame(preds).to_csv(out / "stage6k_predictions.csv", index=False)
    pd.DataFrame(imps).to_csv(out / "stage6k_feature_importance.csv", index=False)

    block_meta = (
        data.groupby(["block", "block_no", "decision_date", "future_end_date"], as_index=False)
        .agg(sample_n=("members", "size"), pool_n=("pool_n", "first"), family_n=("family_id", "nunique"))
        .sort_values("block_no")
    )
    block_meta.to_csv(out / "stage6k_blocks.csv", index=False)

    primary = m[m["rule"] == "previous_block_rf"].copy()
    med_ic = float(primary["spearman"].median())
    pos_share = float((primary["spearman"] > 0).mean())
    med_top = float(primary["pred_top50_mean_actual_percentile"].median())
    med_lift = float(primary["pred_top_decile_log_lift"].median())
    gates = {
        "median_ic_gt_0_10": bool(med_ic > 0.10),
        "positive_ic_share_ge_2_of_3": bool(pos_share >= (2.0 / 3.0)),
        "median_top50_pct_gt_0_60": bool(med_top > 0.60),
        "median_top_decile_lift_gt_0": bool(med_lift > 0),
    }
    passed = bool(all(gates.values()))

    rule_summary = {}
    for rule, g in m.groupby("rule"):
        rule_summary[rule] = {
            "transition_n": int(len(g)),
            "median_spearman": float(g["spearman"].median()),
            "positive_ic_share": float((g["spearman"] > 0).mean()),
            "median_top50_actual_percentile": float(g["pred_top50_mean_actual_percentile"].median()),
            "median_top_decile_log_lift": float(g["pred_top_decile_log_lift"].median()),
        }

    summary = {
        "study": "OURE Stage6K strict adjacent 126-to-126 RF transfer",
        "status": "completed",
        "block_count": int(len(block_ids)),
        "transition_count": int(len(primary)),
        "rf_params": s6g.RF_PARAMS,
        "feature_count": len(s6g.FEATURES),
        "primary_rule": "previous_block_rf",
        "primary_metrics": {
            "median_spearman": med_ic,
            "positive_ic_share": pos_share,
            "median_pred_top50_actual_percentile": med_top,
            "median_top_decile_log_lift": med_lift,
        },
        "gates": gates,
        "gate_pass": passed,
        "decision": "adjacent_mapping_transfer_supported" if passed else "adjacent_mapping_transfer_not_supported",
        "rule_summary": rule_summary,
        "warning": "Strict non-overlapping 126-session blocks; prior-block labels are fully realized before next decision. No tuning after preregistration.",
    }
    (out / "oure_stage6k_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
