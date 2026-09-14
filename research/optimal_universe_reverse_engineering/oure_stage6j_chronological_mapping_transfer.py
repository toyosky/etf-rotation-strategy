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
import optimal_universe_reverse_engineering.oure_stage6f_rf_surrogate_value as s6g
import optimal_universe_reverse_engineering.oure_stage6i_half_year_rf_horizon_diagnostic as s6i
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

SEED = 20260914
PRIMARY_TARGETS = ["2023H2", "2024H1", "2024H2", "2025H1", "2025H2", "2026H1"]
EARLY_TARGETS = {"2023H2", "2024H1", "2024H2"}
LATE_TARGETS = {"2025H1", "2025H2", "2026H1"}


def rank_pct(s: pd.Series) -> pd.Series:
    return s6g.rank_pct(s.astype(float))


def spearman(a, b) -> float:
    v = s6g.spearman(a, b)
    return float(v) if np.isfinite(v) else np.nan


def prepare_xy(train: pd.DataFrame, valid: pd.DataFrame):
    med = train[s6g.FEATURES].replace([np.inf, -np.inf], np.nan).median(axis=0)
    xtr = train[s6g.FEATURES].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
    xva = valid[s6g.FEATURES].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
    ytr = train["future_log_growth"].astype(float)
    return xtr, ytr, xva


def fit_rf_predict(train: pd.DataFrame, valid: pd.DataFrame) -> np.ndarray:
    xtr, ytr, xva = prepare_xy(train, valid)
    rf = RandomForestRegressor(**s6g.RF_PARAMS)
    rf.fit(xtr, ytr)
    return rf.predict(xva)


def directional_score(history: list[pd.DataFrame], valid: pd.DataFrame):
    signs = {}
    rhos = {}
    for f in s6g.FEATURES:
        vals = []
        for h in history:
            rho = spearman(h[f], h["future_log_growth"])
            vals.append(rho)
        rhos[f] = vals
        finite = [x for x in vals if np.isfinite(x) and x != 0]
        if len(finite) == len(history) and len(finite) > 0:
            sg = np.sign(finite)
            if np.all(sg > 0):
                signs[f] = 1.0
            elif np.all(sg < 0):
                signs[f] = -1.0

    if not signs:
        return np.zeros(len(valid), dtype=float), signs, rhos

    parts = []
    for f, sg in signs.items():
        x = valid[f].replace([np.inf, -np.inf], np.nan)
        fill = float(x.median()) if x.notna().any() else 0.0
        rp = rank_pct(x.fillna(fill)) - 0.5
        parts.append(sg * rp.to_numpy(dtype=float))
    score = np.vstack(parts).mean(axis=0)
    return score, signs, rhos


def evaluate_rule(period: str, rule: str, score: np.ndarray, target: pd.DataFrame) -> dict:
    t = target.copy()
    t["pred_score"] = np.asarray(score, dtype=float)
    ic = spearman(t["pred_score"], t["future_log_growth"])
    n_top = min(50, len(t))
    top = t.nlargest(n_top, "pred_score")
    dec_n = max(1, int(np.ceil(len(t) * 0.10)))
    dec = t.nlargest(dec_n, "pred_score")
    return {
        "period": period,
        "rule": rule,
        "sample_n": int(len(t)),
        "spearman": ic,
        "positive_ic": bool(np.isfinite(ic) and ic > 0),
        "pred_top50_mean_actual_percentile": float(top["future_rank_pct"].mean()),
        "pred_top_decile_log_lift": float(dec["future_log_growth"].mean() - t["future_log_growth"].mean()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage6j-output")
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

    # Regenerate Stage6I half-year libraries deterministically, in chronological order.
    rng = np.random.default_rng(SEED)
    period_frames: dict[str, pd.DataFrame] = {}
    for d in s5.decision_indices(cal):
        dt = pd.Timestamp(cal[d])
        if dt < pd.Timestamp("2022-01-01") or dt >= pd.Timestamp("2026-07-01"):
            continue
        pack = s6i.period_data(d, cal, score, gross, close, meta, rng)
        if pack is None:
            continue
        df, _, _ = pack
        p = str(df["period"].iloc[0])
        period_frames[p] = df.reset_index(drop=True)

    periods = sorted(period_frames.keys(), key=lambda p: (int(p[:4]), int(p[-1])))
    missing = [p for p in PRIMARY_TARGETS if p not in period_frames]
    if missing:
        raise RuntimeError(f"missing primary target periods: {missing}")

    rows = []
    diagnostics = []
    prediction_rows = []

    for target_p in PRIMARY_TARGETS:
        idx = periods.index(target_p)
        if idx < 3:
            raise RuntimeError(f"target {target_p} has fewer than 3 prior periods")
        hist3_names = periods[idx-3:idx]
        hist3 = [period_frames[p] for p in hist3_names]
        target = period_frames[target_p].copy()

        # R1: previous-period RF.
        pred_prev = fit_rf_predict(hist3[-1], target)
        r1 = evaluate_rule(target_p, "previous_period_rf", pred_prev, target)
        rows.append(r1)

        # R2 PRIMARY: equal-weight rank ensemble of three separately fitted historical RFs.
        pred_ranks = []
        component_pred = []
        for hp, hdf in zip(hist3_names, hist3):
            pr = fit_rf_predict(hdf, target)
            component_pred.append(pr)
            pred_ranks.append(rank_pct(pd.Series(pr)).to_numpy(dtype=float))
        pred_ens = np.vstack(pred_ranks).mean(axis=0)
        r2row = evaluate_rule(target_p, "last3_rf_rank_ensemble", pred_ens, target)
        rows.append(r2row)

        # R3: unanimous directional sub-mapping across the same previous three periods.
        pred_dir, signs, rhos = directional_score(hist3, target)
        r3 = evaluate_rule(target_p, "last3_unanimous_direction", pred_dir, target)
        r3["retained_feature_n"] = int(len(signs))
        r3["retained_features"] = ",".join(sorted(signs.keys()))
        rows.append(r3)

        diagnostics.append({
            "period": target_p,
            "history_periods": ",".join(hist3_names),
            "retained_feature_n": int(len(signs)),
            "retained_features": ",".join(sorted(signs.keys())),
            "feature_signs_json": json.dumps(signs, ensure_ascii=False, sort_keys=True),
            "feature_rhos_json": json.dumps(rhos, ensure_ascii=False, sort_keys=True),
        })

        for i, rec in target.reset_index(drop=True).iterrows():
            prediction_rows.append({
                "period": target_p,
                "family_id": rec["family_id"],
                "members": rec["members"],
                "future_log_growth": float(rec["future_log_growth"]),
                "future_rank_pct": float(rec["future_rank_pct"]),
                "previous_period_rf": float(pred_prev[i]),
                "last3_rf_rank_ensemble": float(pred_ens[i]),
                "last3_unanimous_direction": float(pred_dir[i]),
            })

    metrics = pd.DataFrame(rows)
    metrics.to_csv(out / "stage6j_period_rule_metrics.csv", index=False)
    pd.DataFrame(diagnostics).to_csv(out / "stage6j_directional_diagnostics.csv", index=False)
    pd.DataFrame(prediction_rows).to_csv(out / "stage6j_predictions.csv", index=False)

    primary = metrics[metrics["rule"] == "last3_rf_rank_ensemble"].copy()
    if len(primary) != 6:
        raise RuntimeError(f"expected 6 primary OOS periods, got {len(primary)}")

    early = primary[primary["period"].isin(EARLY_TARGETS)]
    late = primary[primary["period"].isin(LATE_TARGETS)]
    med_ic = float(primary["spearman"].median())
    pos_n = int((primary["spearman"] > 0).sum())
    med_top50 = float(primary["pred_top50_mean_actual_percentile"].median())
    early_ic = float(early["spearman"].median())
    late_ic = float(late["spearman"].median())

    gates = {
        "median_ic_gt_0_10": bool(med_ic > 0.10),
        "positive_periods_ge_4_of_6": bool(pos_n >= 4),
        "median_top50_pct_gt_0_55": bool(med_top50 > 0.55),
        "early_block_median_ic_positive": bool(early_ic > 0),
        "late_block_median_ic_positive": bool(late_ic > 0),
    }
    passed = bool(all(gates.values()))

    rule_summary = {}
    for rule, g in metrics.groupby("rule"):
        rule_summary[rule] = {
            "median_spearman": float(g["spearman"].fillna(0).median()),
            "positive_period_n": int((g["spearman"].fillna(0) > 0).sum()),
            "median_top50_actual_percentile": float(g["pred_top50_mean_actual_percentile"].median()),
            "median_top_decile_log_lift": float(g["pred_top_decile_log_lift"].median()),
        }

    summary = {
        "study": "OURE Stage6J chronological mapping transfer",
        "status": "completed",
        "primary_rule": "last3_rf_rank_ensemble",
        "primary_target_periods": PRIMARY_TARGETS,
        "rf_params": s6g.RF_PARAMS,
        "feature_count": len(s6g.FEATURES),
        "primary_metrics": {
            "median_period_spearman": med_ic,
            "positive_period_n": pos_n,
            "median_pred_top50_actual_percentile": med_top50,
            "early_2023H2_2024H2_median_ic": early_ic,
            "late_2025H1_2026H1_median_ic": late_ic,
        },
        "gates": gates,
        "gate_pass": passed,
        "decision": "chronological_mapping_transfer_supported" if passed else "chronological_mapping_transfer_not_supported",
        "rule_summary": rule_summary,
        "warning": "No current-period future label enters fitting/feature selection/weights. R1/R3 are diagnostics and cannot rescue primary R2.",
    }
    (out / "oure_stage6j_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
