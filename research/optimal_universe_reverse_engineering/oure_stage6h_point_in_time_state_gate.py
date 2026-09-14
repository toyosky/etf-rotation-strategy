#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import optimal_universe_reverse_engineering.oure_stage5_history_transfer as s5
from optimal_universe_reverse_engineering.oure_stage6_transfer_regime import risk_leader_stats, spearman_no_scipy
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

SEED = 20260914
LOOKBACK_STATE = 126
MIN_PRIOR_STATES = 3
VOTE_THRESHOLD = 3
SPLIT = pd.Timestamp("2025-01-01")


def bootstrap_mean_diff(on: np.ndarray, off: np.ndarray, n_boot: int = 20000) -> dict:
    on = np.asarray(on, dtype=float)
    off = np.asarray(off, dtype=float)
    on = on[np.isfinite(on)]
    off = off[np.isfinite(off)]
    if len(on) == 0 or len(off) == 0:
        return {"mean_diff": np.nan, "ci_low": np.nan, "ci_high": np.nan, "n_boot": n_boot}
    rng = np.random.default_rng(SEED)
    vals = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        a = rng.choice(on, size=len(on), replace=True)
        b = rng.choice(off, size=len(off), replace=True)
        vals[i] = float(np.mean(a) - np.mean(b))
    return {
        "mean_diff": float(np.mean(on) - np.mean(off)),
        "ci_low": float(np.quantile(vals, 0.025)),
        "ci_high": float(np.quantile(vals, 0.975)),
        "n_boot": int(n_boot),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage6h-output")
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

    dec = s5.decision_indices(cal)
    rows: list[dict] = []
    prior_states: list[dict] = []

    for pi, d in enumerate(dec):
        next_d = dec[pi + 1] if pi + 1 < len(dec) else min(len(cal) - 2, d + 126)
        if next_d <= d:
            continue
        decision_date = pd.Timestamp(cal[d])
        future_end = pd.Timestamp(cal[next_d - 1])
        partial = bool(pi + 1 >= len(dec) and (next_d - d) < 110)
        pool = s5.available_pool(close, meta, cal, d)
        if len(pool) < 30:
            raise RuntimeError(f"too few candidates {decision_date.date()}: {len(pool)}")
        if d < LOOKBACK_STATE:
            continue

        # X<=t state: trailing 126 sessions strictly before the decision date.
        state_dates = pd.DatetimeIndex(cal[d - LOOKBACK_STATE:d])
        state = risk_leader_stats(score, state_dates, pool)
        current = {
            "eligible_fraction": float(state.get("eligible_fraction", np.nan)),
            "top1_top2_gap_median": float(state.get("top1_top2_gap_median", np.nan)),
            "leader_switch_rate": float(state.get("leader_switch_rate", np.nan)),
            "mean_leader_tenure": float(state.get("mean_leader_tenure", np.nan)),
        }

        thresholds = {k: np.nan for k in current}
        votes = {k: np.nan for k in current}
        transfer_on = np.nan
        vote_count = np.nan
        if len(prior_states) >= MIN_PRIOR_STATES:
            hist = pd.DataFrame(prior_states)
            for k in current:
                thresholds[k] = float(hist[k].median())
            votes["eligible_fraction"] = bool(current["eligible_fraction"] >= thresholds["eligible_fraction"])
            votes["top1_top2_gap_median"] = bool(current["top1_top2_gap_median"] >= thresholds["top1_top2_gap_median"])
            votes["leader_switch_rate"] = bool(current["leader_switch_rate"] >= thresholds["leader_switch_rate"])
            votes["mean_leader_tenure"] = bool(current["mean_leader_tenure"] <= thresholds["mean_leader_tenure"])
            vote_count = int(sum(bool(v) for v in votes.values()))
            transfer_on = bool(vote_count >= VOTE_THRESHOLD)

        # Future target: exactly the frozen Stage6 library-transfer definition.
        evals = {}
        libs = {}
        for L in s5.LOOKBACKS:
            ev = s5.WindowEvaluator(score, gross, cal, pool, d - L, d)
            lib, _ = s5.search_library(ev, pool)
            evals[L] = ev
            libs[L] = lib
        union = sorted(set().union(*libs.values()))
        chosen, robust_scores, _ = s5.choose_rules(evals, libs)
        future = s5.WindowEvaluator(score, gross, cal, pool, d, next_d)
        past6 = {u: evals[126].evaluate(u).log_growth for u in union}
        fut = {u: future.evaluate(u).log_growth for u in union}
        robust_min = {u: float(robust_scores[u][0]) for u in union}
        past6_future = spearman_no_scipy(list(past6.values()), [fut[u] for u in past6])
        robust_future = spearman_no_scipy([robust_min[u] for u in union], [fut[u] for u in union])

        row = {
            "decision_date": str(decision_date.date()),
            "future_end_date": str(future_end.date()),
            "era": "2022_2024" if decision_date < SPLIT else "2025_2026",
            "partial_final_period": partial,
            "pool_n": len(pool),
            "library_n": len(union),
            "n_prior_states": len(prior_states),
            "evaluable": bool(len(prior_states) >= MIN_PRIOR_STATES and not partial),
            "state_vote_count": vote_count,
            "transfer_on": transfer_on,
            "robust_future_spearman": robust_future,
            "past6_future_spearman": past6_future,
        }
        for k, v in current.items():
            row[f"state_{k}_126"] = v
            row[f"threshold_{k}"] = thresholds[k]
            row[f"vote_{k}"] = votes[k]
        rows.append(row)
        prior_states.append(current)

    periods = pd.DataFrame(rows)
    periods.to_csv(out / "stage6h_period_state_gate.csv", index=False)

    ev = periods[periods["evaluable"]].copy()
    if ev.empty:
        raise RuntimeError("No evaluable completed periods after burn-in")
    ev["transfer_on"] = ev["transfer_on"].astype(bool)
    on = ev[ev["transfer_on"]]
    off = ev[~ev["transfer_on"]]

    robust_sign_accuracy = float(((ev["robust_future_spearman"] > 0) == ev["transfer_on"]).mean())
    past6_sign_accuracy = float(((ev["past6_future_spearman"] > 0) == ev["transfer_on"]).mean())
    on_robust_median = float(on["robust_future_spearman"].median()) if len(on) else np.nan
    off_robust_median = float(off["robust_future_spearman"].median()) if len(off) else np.nan
    robust_median_diff = float(on_robust_median - off_robust_median) if len(on) and len(off) else np.nan
    on_past6_median = float(on["past6_future_spearman"].median()) if len(on) else np.nan
    off_past6_median = float(off["past6_future_spearman"].median()) if len(off) else np.nan

    gate1 = bool(len(on) >= 2 and len(off) >= 2)
    gate2 = bool(robust_sign_accuracy > 0.60)
    gate3 = bool(len(on) and len(off) and on_robust_median > 0 and off_robust_median <= 0)
    gate4 = bool(np.isfinite(robust_median_diff) and robust_median_diff >= 0.20)
    primary_pass = bool(gate1 and gate2 and gate3 and gate4)

    boot = bootstrap_mean_diff(on["robust_future_spearman"].to_numpy(), off["robust_future_spearman"].to_numpy())
    era_diag = {}
    for era, g in ev.groupby("era"):
        era_diag[era] = {
            "n": int(len(g)),
            "transfer_on_n": int(g["transfer_on"].sum()),
            "median_robust_future_spearman": float(g["robust_future_spearman"].median()),
            "median_past6_future_spearman": float(g["past6_future_spearman"].median()),
            "sign_accuracy": float(((g["robust_future_spearman"] > 0) == g["transfer_on"]).mean()),
        }

    payload = {
        "study": "OURE Stage6H point-in-time transfer-state gate",
        "status": "completed",
        "frozen_rule": {
            "lookback_sessions": LOOKBACK_STATE,
            "min_prior_states": MIN_PRIOR_STATES,
            "vote_threshold": VOTE_THRESHOLD,
            "directions": {
                "eligible_fraction": "greater_equal_expanding_median",
                "top1_top2_gap_median": "greater_equal_expanding_median",
                "leader_switch_rate": "greater_equal_expanding_median",
                "mean_leader_tenure": "less_equal_expanding_median",
            },
        },
        "n_evaluable": int(len(ev)),
        "transfer_on_n": int(len(on)),
        "transfer_off_n": int(len(off)),
        "robust_sign_accuracy": robust_sign_accuracy,
        "past6_sign_accuracy_secondary": past6_sign_accuracy,
        "transfer_on_median_robust_future_spearman": on_robust_median,
        "transfer_off_median_robust_future_spearman": off_robust_median,
        "on_minus_off_median_robust_spearman": robust_median_diff,
        "transfer_on_median_past6_future_spearman_secondary": on_past6_median,
        "transfer_off_median_past6_future_spearman_secondary": off_past6_median,
        "bootstrap_mean_difference": boot,
        "gates": {
            "both_states_at_least_2": gate1,
            "robust_sign_accuracy_gt_0_60": gate2,
            "on_positive_off_nonpositive_medians": gate3,
            "on_off_median_gap_ge_0_20": gate4,
        },
        "primary_gate_pass": primary_pass,
        "era_diagnostics": era_diag,
        "note": "If failed, do not tune state variables, 126-session lookback, expanding-median comparisons, or 3-of-4 vote rule.",
    }
    (out / "oure_stage6h_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
