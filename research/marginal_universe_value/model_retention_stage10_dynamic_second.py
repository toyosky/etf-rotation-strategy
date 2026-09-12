#!/usr/bin/env python3
"""MUV Stage 10: dynamic second-removal transport test.

Frozen in STAGE10_DYNAMIC_SECOND_REMOVAL_DESIGN_20260912.md.

First removal = frozen Stage7 primary action.
Second step recomputes universe-dependent features after that first removal, but
reuses the exact historical Stage3 expected-MUV and Stage7 asymmetric-safety
model specifications trained only on earlier original Fixed15 labels.

No reduced-universe outcome is used in training or threshold calibration.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_retention_labels_v1 as v1
import build_retention_labels_v1_3 as v13
import model_retention_stage3_pairwise_sign as s3
import model_retention_stage7_asymmetric_safety as s7
from full_market_ols_storage import _db_url, build_features
from universe.oracle_replacement_v1 import FIXED15, CASH_SIGNAL

LABELS = Path("muv-retention-labels-v1.parquet")
STAGE7_MONTHLY = Path("muv-retention-stage7-monthly-policy.csv")
STAGE7_RISK = Path("muv-retention-stage7-safety-predictions.csv")
STAGE9 = Path("muv-retention-stage9-report.json")
OUT = Path("muv-retention-stage10-report.json")
OUT_MONTHLY = Path("muv-retention-stage10-dynamic-second.csv")

EPS = 1e-12
RANDOM_SEED = 20260912
RANDOM_DRAWS = 5000

PAIRWISE_FEATURES = s3.PAIRWISE_FEATURES
STAGE_A_FEATURES = s3.STAGE_A_FEATURES
SAFETY_FEATURES = s7.FEATURE_SETS["pairwise_regime"]


def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else np.nan
    except Exception:
        return np.nan


def _symbol(v) -> str:
    s = str(v)
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(6)


def wealth(r) -> float:
    a = np.asarray(r, dtype=float)
    return float(np.prod(1.0 + a))


def month_setup(calendar: pd.Index, baseline_ranked: pd.Series, label_period: pd.Period):
    dates = calendar[
        pd.Index([pd.Timestamp(d).to_period("M") == label_period for d in calendar])
    ]
    if len(dates) == 0:
        raise RuntimeError(f"No dates for {label_period}")
    first_exec = pd.Timestamp(dates[0])
    first_pos = int(calendar.get_loc(first_exec))
    if first_pos == 0:
        raise RuntimeError(f"No prior date for {label_period}")
    asof = pd.Timestamp(calendar[first_pos - 1])
    prev_signal_pos = first_pos - 2
    initial_prev = v1._target(baseline_ranked.iloc[prev_signal_pos]) if prev_signal_pos >= 0 else None
    return asof, initial_prev


def reduced_feature_frame(
    universe: set[str],
    asof: pd.Timestamp,
    features: pd.DataFrame,
    score: pd.DataFrame,
    ret: pd.DataFrame,
) -> pd.DataFrame:
    """Build only the X columns used by Stage3/Stage7 under current universe."""
    asof = pd.Timestamp(asof)
    cols = sorted(universe)
    su = score.loc[:, [c for c in cols if c in score.columns]].copy()
    rank_u = su.rank(axis=1, method="min", ascending=False)
    hist_dates = su.index[su.index <= asof]
    d20 = hist_dates[-20:]
    d120 = hist_dates[-120:]

    current = su.loc[asof].dropna().sort_values(ascending=False) if asof in su.index else pd.Series(dtype=float)
    top1_score = _num(current.iloc[0]) if len(current) else np.nan

    # Reduced-universe regime breadth. Own return states remain point-in-time.
    risk_symbols = sorted(universe - {CASH_SIGNAL})
    ret20_vals = []
    for rs in risk_symbols:
        state, _, _ = v13._latest_state(features, rs, asof)
        if state is not None:
            x = _num(state.get("ret20"))
            if math.isfinite(x):
                ret20_vals.append(x)
    qualified = current.drop(index=CASH_SIGNAL, errors="ignore")
    reg_qualified_count = int(len(qualified))
    reg_ret20_median = float(np.median(ret20_vals)) if ret20_vals else np.nan
    reg_ret20_positive_frac = float(np.mean(np.asarray(ret20_vals) > 0)) if ret20_vals else np.nan

    corr120 = (
        ret.loc[d120].corr(min_periods=min(60, max(2, len(d120) // 2)))
        if len(d120) >= 20 else pd.DataFrame()
    )

    rows = []
    for sym in risk_symbols:
        own, _, _ = v13._latest_state(features, sym, asof)
        if own is None:
            continue

        own_exact = _num(su.at[asof, sym]) if sym in su.columns and asof in su.index else np.nan
        own_ratio = (
            own_exact / top1_score
            if math.isfinite(own_exact) and math.isfinite(top1_score) and top1_score != 0
            else np.nan
        )
        top3 = (
            float((rank_u.loc[d20, sym] <= 3).mean())
            if sym in rank_u.columns and len(d20) else np.nan
        )
        days1 = v13._days_since_rank1(rank_u, sym, hist_dates)

        alternatives = current.drop(index=sym, errors="ignore")
        alt = str(alternatives.index[0]) if len(alternatives) else None
        alt_exact = _num(alternatives.iloc[0]) if len(alternatives) else np.nan
        alt_state, _, _ = v13._latest_state(features, alt, asof) if alt is not None else (None, None, None)
        alt_top3 = (
            float((rank_u.loc[d20, alt] <= 3).mean())
            if alt is not None and alt in rank_u.columns and len(d20) else np.nan
        )

        corr_alt = np.nan
        if alt is not None and not corr120.empty and sym in corr120.index and alt in corr120.columns:
            corr_alt = _num(corr120.at[sym, alt])

        def gap(col):
            ov = _num(own.get(col)) if own is not None else np.nan
            av = _num(alt_state.get(col)) if alt_state is not None else np.nan
            return ov - av if math.isfinite(ov) and math.isfinite(av) else np.nan

        row = {
            "symbol": sym,
            "alt_symbol_asof": alt,
            "own_score_ratio_top1": own_ratio,
            "top3_freq20": top3,
            "days_since_top1": days1,
            "x_score": _num(own.get("score")),
            "x_r2": _num(own.get("r2")),
            "x_score_delta": _num(own.get("score_delta")),
            "pair_score_exact_gap_alt": (
                own_exact - alt_exact
                if math.isfinite(own_exact) and math.isfinite(alt_exact) else np.nan
            ),
            "pair_r2_gap_alt": gap("r2"),
            "pair_current_resid_gap_alt": gap("current_resid"),
            "pair_ret10_gap_alt": gap("ret10"),
            "pair_ret20_gap_alt": gap("ret20"),
            "pair_efficiency10_gap_alt": gap("efficiency10"),
            "pair_vol20_gap_alt": gap("vol20"),
            "pair_ma10_dist_gap_alt": gap("ma10_dist"),
            "pair_corr120_with_alt": corr_alt,
            "pair_top3_freq20_gap_alt": (
                top3 - alt_top3
                if math.isfinite(_num(top3)) and math.isfinite(_num(alt_top3)) else np.nan
            ),
            "regime_risk_qualified_count": reg_qualified_count,
            "regime_risk_ret20_positive_frac": reg_ret20_positive_frac,
            "regime_risk_ret20_median": reg_ret20_median,
        }
        rows.append(row)

    return pd.DataFrame(rows)


def fit_predict_second(lab: pd.DataFrame, risk_hist: pd.DataFrame, month: str, x: pd.DataFrame):
    tr = lab[lab.label_month < month].copy()
    if tr.empty or x.empty:
        return x.assign(p_active=np.nan, p_positive=np.nan, muv=np.nan, safety=np.nan), np.nan

    # Stage A relevance.
    a = s3.pipe_logit()
    a.fit(tr[STAGE_A_FEATURES], tr.path_active.astype(int))
    p_active = a.predict_proba(x[STAGE_A_FEATURES])[:, 1]

    # Stage B conditional sign; magnitude stays expanding historical means.
    atr = tr[tr.path_active].copy()
    y = atr.delta_return.gt(EPS).astype(int)
    if len(atr) < s7.MIN_ACTIVE_TRAIN or y.nunique() < 2:
        return x.assign(p_active=p_active, p_positive=np.nan, muv=np.nan, safety=np.nan), np.nan

    b = s3.pipe_logit()
    b.fit(atr[PAIRWISE_FEATURES], y)
    p_positive = b.predict_proba(x[PAIRWISE_FEATURES])[:, 1]
    pos = atr.loc[atr.delta_return > EPS, "delta_return"]
    neg = atr.loc[atr.delta_return < -EPS, "delta_return"]
    mean_pos = float(pos.mean()) if len(pos) else 0.0
    mean_neg = float(neg.mean()) if len(neg) else 0.0
    cond = p_positive * mean_pos + (1.0 - p_positive) * mean_neg
    muv = p_active * cond

    # Asymmetric safety model, unchanged specification.
    mag = atr.delta_return.abs().to_numpy(dtype=float)
    mean_mag = float(np.mean(mag))
    weights = mag / mean_mag
    sm = s7.pipe_logit()
    sm.fit(atr[SAFETY_FEATURES], y, model__sample_weight=weights)
    safety = sm.predict_proba(x[SAFETY_FEATURES])[:, 1]

    cutoff, _, _ = s7.regret_cutoff(
        risk_hist[risk_hist.label_month < month], "risk_pairwise_regime", 0.90
    )

    out = x.copy()
    out["p_active"] = p_active
    out["p_positive"] = p_positive
    out["muv"] = muv
    out["safety"] = safety
    return out, cutoff


def main() -> None:
    db = os.getenv("ETF_DAILY_BARS_DATABASE_URL")
    if not db:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    lab = pd.read_parquet(LABELS)
    monthly = pd.read_csv(STAGE7_MONTHLY)
    risk = pd.read_csv(STAGE7_RISK)
    with open(STAGE9, encoding="utf-8") as f:
        stage9 = json.load(f)

    lab["label_month"] = lab.label_month.astype(str)
    lab["delta_return"] = pd.to_numeric(lab.delta_return, errors="coerce")
    lab["path_active"] = pd.to_numeric(lab.path_direct_selection_days, errors="coerce").fillna(0) > 0
    monthly["label_month"] = monthly.label_month.astype(str)
    risk["label_month"] = risk.label_month.astype(str)
    if risk.path_active.dtype != bool:
        risk["path_active"] = risk.path_active.astype(str).str.lower().eq("true")
    risk["delta_return"] = pd.to_numeric(risk.delta_return, errors="coerce")

    engine = create_engine(_db_url(db), pool_pre_ping=True)
    bars = v1.load_fixed15_bars(engine)
    features = build_features(bars)
    calendar, score, _, _, oo, _, ret = v1.prepare_wides(bars, features)
    baseline_ranked, _ = v1.rank_pool(score, set(FIXED15))

    action_months = monthly[monthly.act_primary_regime90].copy()
    details = []
    random_outcomes = {}
    max_first_diff = 0.0

    for _, mr in action_months.iterrows():
        mo = str(mr.label_month)
        lp = pd.Period(mo, freq="M")
        first = _symbol(mr.symbol_primary_regime90)
        asof, initial_prev = month_setup(calendar, baseline_ranked, lp)
        u1 = set(FIXED15) - {first}

        rank1, count1 = v1.rank_pool(score, u1)
        met1 = v1.monthly_metrics(rank1, count1, oo, calendar, lp, initial_prev)
        max_first_diff = max(max_first_diff, abs(float(met1["total_return"]) - float(mr.ret_primary_regime90)))

        x = reduced_feature_frame(u1, asof, features, score, ret)
        pred, cutoff = fit_predict_second(lab, risk, mo, x)
        cand = pred[
            pred.muv.notna()
            & pred.safety.notna()
            & pred.muv.lt(0.0)
            & pred.safety.lt(cutoff)
        ].sort_values(["muv", "safety", "symbol"])

        second = None
        selected_pred_muv = np.nan
        selected_safety = np.nan
        ret2 = float(met1["total_return"])
        met2 = met1
        if np.isfinite(cutoff) and len(cand):
            c = cand.iloc[0]
            second = str(c.symbol)
            selected_pred_muv = float(c.muv)
            selected_safety = float(c.safety)
            rank2, count2 = v1.rank_pool(score, u1 - {second})
            met2 = v1.monthly_metrics(rank2, count2, oo, calendar, lp, initial_prev)
            ret2 = float(met2["total_return"])

        # Exact outcomes for random-second control on months where the model acts.
        if second is not None:
            opts = []
            for rs in sorted(u1 - {CASH_SIGNAL}):
                r2, c2 = v1.rank_pool(score, u1 - {rs})
                mm = v1.monthly_metrics(r2, c2, oo, calendar, lp, initial_prev)
                opts.append((rs, float(mm["total_return"])))
            random_outcomes[mo] = opts

        details.append({
            "label_month": mo,
            "asof_date": str(asof.date()),
            "first_removed_stage7": first,
            "stage7_return": float(met1["total_return"]),
            "second_action": bool(second is not None),
            "second_removed_stage10": second,
            "second_pred_muv": selected_pred_muv,
            "second_safety_score": selected_safety,
            "safety_cutoff": float(cutoff) if np.isfinite(cutoff) else np.nan,
            "safe_negative_candidates": int(len(cand)) if np.isfinite(cutoff) else 0,
            "stage10_return": ret2,
            "second_realized_improvement": float(ret2 - met1["total_return"]),
            "second_realized_retention_value": float(met1["total_return"] - ret2),
            "stage10_switches": int(met2["switches"]),
            "stage10_turnover_sides": int(met2["turnover_sides"]),
            "stage10_max_drawdown": float(met2["max_drawdown"]),
        })

    if max_first_diff > 1e-10:
        raise RuntimeError(f"Stage10 failed to reproduce Stage7 first-removal returns: {max_first_diff}")

    d = pd.DataFrame(details).sort_values("label_month").reset_index(drop=True)
    d.to_csv(OUT_MONTHLY, index=False)

    path = monthly[["label_month", "base_return", "ret_primary_regime90"]].merge(
        d[["label_month", "second_action", "stage10_return"]],
        on="label_month", how="left", validate="one_to_one"
    )
    path["ret_stage10"] = path.ret_primary_regime90
    m2 = path.second_action.fillna(False)
    path.loc[m2, "ret_stage10"] = path.loc[m2, "stage10_return"]

    fw_base = wealth(path.base_return)
    fw7 = wealth(path.ret_primary_regime90)
    fw10 = wealth(path.ret_stage10)

    acted = d[d.second_action].copy()
    pos_gain = acted.loc[acted.second_realized_improvement > EPS, "second_realized_improvement"]
    harms = -acted.loc[acted.second_realized_improvement < -EPS, "second_realized_improvement"]

    # Random second removal on exactly the Stage10 second-action months.
    rng = np.random.default_rng(RANDOM_SEED)
    rand_adv = []
    for _ in range(RANDOM_DRAWS):
        rr = path.ret_primary_regime90.to_numpy(dtype=float).copy()
        for i, mo in enumerate(path.label_month):
            if mo not in random_outcomes:
                continue
            opts = random_outcomes[mo]
            j = int(rng.integers(0, len(opts)))
            rr[i] = opts[j][1]
        fw = wealth(rr)
        rand_adv.append(fw / fw7 - 1.0)
    rand_adv = np.asarray(rand_adv, dtype=float)
    stage10_inc = float(fw10 / fw7 - 1.0)

    periods = {}
    for name, mask in {
        "2023-24": path.label_month.str[:4].astype(int).le(2024),
        "2025-26": path.label_month.str[:4].astype(int).ge(2025),
    }.items():
        g = path[mask]
        dm = d[d.label_month.isin(g.label_month)]
        f7 = wealth(g.ret_primary_regime90)
        f10 = wealth(g.ret_stage10)
        periods[name] = {
            "first_action_months": int(len(dm)),
            "second_action_months": int(dm.second_action.sum()),
            "incremental_terminal_wealth_vs_stage7": float(f10 / f7 - 1.0),
            "sum_second_realized_improvement": float(dm.loc[dm.second_action, "second_realized_improvement"].sum()),
            "second_false_removal_regret": float((-dm.loc[dm.second_realized_improvement < -EPS, "second_realized_improvement"]).sum()),
        }

    oracle_headroom_sum = float(stage9["headroom"]["sum_additional_monthly_return"])
    oracle_inc_wealth = float(stage9["wealth"]["incremental_terminal_wealth_vs_stage7"])

    report = {
        "design": {
            "first_removal": "frozen Stage7 primary action",
            "second_model": "transport same Stage3/Stage7 specifications from earlier Fixed15 labels to reduced Fixed15-1 X state",
            "safety_coverage": 0.90,
            "max_second_removals": 1,
            "feature_search": False,
            "threshold_search": False,
            "reduced_universe_training_labels": False,
        },
        "sanity": {
            "first_action_months": int(len(d)),
            "max_abs_reproduced_stage7_return_diff": float(max_first_diff),
        },
        "policy": {
            "second_action_months": int(d.second_action.sum()),
            "second_action_rate_given_first": float(d.second_action.mean()),
            "beneficial_second_actions": int((acted.second_realized_improvement > EPS).sum()),
            "harmful_second_actions": int((acted.second_realized_improvement < -EPS).sum()),
            "zero_effect_second_actions": int((acted.second_realized_improvement.abs() <= EPS).sum()),
            "sum_second_realized_improvement": float(acted.second_realized_improvement.sum()),
            "captured_negative_second_retention_value": float(pos_gain.sum()) if len(pos_gain) else 0.0,
            "cumulative_second_false_removal_regret": float(harms.sum()) if len(harms) else 0.0,
            "max_single_second_false_removal_regret": float(harms.max()) if len(harms) else 0.0,
        },
        "wealth": {
            "keep_all_final_wealth": fw_base,
            "stage7_final_wealth": fw7,
            "stage10_final_wealth": fw10,
            "stage7_relative_vs_keep_all": float(fw7 / fw_base - 1.0),
            "stage10_relative_vs_keep_all": float(fw10 / fw_base - 1.0),
            "stage10_incremental_terminal_wealth_vs_stage7": stage10_inc,
        },
        "oracle_capture": {
            "stage9_sum_additional_monthly_return_headroom": oracle_headroom_sum,
            "stage10_sum_realized_second_improvement": float(acted.second_realized_improvement.sum()),
            "ratio_sum_monthly_improvement_to_oracle_headroom": (
                float(acted.second_realized_improvement.sum() / oracle_headroom_sum)
                if oracle_headroom_sum > 0 else None
            ),
            "stage9_oracle_incremental_terminal_wealth_vs_stage7": oracle_inc_wealth,
            "stage10_incremental_terminal_wealth_vs_stage7": stage10_inc,
        },
        "random_second_control": {
            "draws": RANDOM_DRAWS,
            "second_action_months_matched": int(len(random_outcomes)),
            "incremental_vs_stage7_mean": float(rand_adv.mean()),
            "incremental_vs_stage7_median": float(np.median(rand_adv)),
            "incremental_vs_stage7_p05": float(np.quantile(rand_adv, 0.05)),
            "incremental_vs_stage7_p95": float(np.quantile(rand_adv, 0.95)),
            "prob_random_second_beats_stage7": float(np.mean(rand_adv > 0.0)),
            "prob_random_matches_or_beats_stage10": float(np.mean(rand_adv >= stage10_inc)),
            "stage10_percentile_among_random": float(np.mean(rand_adv <= stage10_inc)),
        },
        "by_period": periods,
        "second_action_details": acted.to_dict(orient="records"),
        "notes": [
            "This is the first predictive reduced-universe transport test; no reduced-universe labels train the model.",
            "The first Stage7 removal is frozen and reproduced exactly.",
            "A failure must not be rescued by tuning a new second-step threshold on these results.",
            "Stage9 Oracle remains future-aware upper-bound headroom only.",
        ],
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
