#!/usr/bin/env python3
"""Stage 12: direct tail-winner risk model and fixed protective guard.

Frozen in STAGE12_TAIL_WINNER_GUARD_DESIGN_20260913.md.

The target is not ordinary positive MUV.  For each OOS month, a tail winner is
an ETF whose realized positive retention value is at or above the 80th
percentile of *prior* positive retention values.  The model is trained directly
on all prior month x ETF rows, bypassing multiplication by Stage-A p(active).

No feature search, model tuning, or global threshold fitting is performed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

import model_retention_stage3_pairwise_sign as s3
import model_retention_stage7_asymmetric_safety as s7

LABELS = Path("muv-retention-labels-v1.parquet")
STAGE3 = Path("muv-retention-stage3-predictions.csv")
STAGE7_RISK = Path("muv-retention-stage7-safety-predictions.csv")
STAGE7_MONTHLY = Path("muv-retention-stage7-monthly-policy.csv")
STAGE10 = Path("muv-retention-stage10-dynamic-second.csv")
OUT_JSON = Path("muv-retention-stage12-report.json")
OUT_PRED = Path("muv-retention-stage12-tail-predictions.csv")
OUT_STAGE7 = Path("muv-retention-stage12-stage7-guard.csv")
OUT_STAGE10 = Path("muv-retention-stage12-stage10-guard.csv")

EPS = 1e-10
START_TEST = "2023-01"
TAIL_QUANTILE = 0.80
REGRET_COVERAGE = 0.90
MIN_TAIL_TRAIN_EVENTS = 8
MIN_PRIOR_OOS_TAIL_EVENTS = 8

TAIL_FEATURES = list(dict.fromkeys(
    s3.STAGE_A_FEATURES + s3.PAIRWISE_FEATURES + s7.REGIME_FEATURES
))


def _auc(y, p):
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    ok = np.isfinite(p)
    y, p = y[ok], p[ok]
    if len(y) < 2 or len(np.unique(y)) < 2:
        return None
    return float(roc_auc_score(y, p))


def _ap(y, p):
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    ok = np.isfinite(p)
    y, p = y[ok], p[ok]
    if len(y) < 2 or int(y.sum()) == 0:
        return None
    return float(average_precision_score(y, p))


def _wealth(r) -> float:
    a = pd.to_numeric(pd.Series(r), errors="coerce").fillna(0.0).to_numpy(dtype=float)
    return float(np.prod(1.0 + a))


def _period(month: str) -> str:
    return "2023-24" if int(str(month)[:4]) <= 2024 else "2025-26"


def tail_cutoff_from_training(tr: pd.DataFrame) -> float:
    pos = pd.to_numeric(tr.loc[tr.delta_return > EPS, "delta_return"], errors="coerce").dropna()
    if len(pos) < MIN_TAIL_TRAIN_EVENTS:
        return np.nan
    return float(pos.quantile(TAIL_QUANTILE))


def protective_score_cutoff(hist_pred: pd.DataFrame) -> tuple[float, int, float]:
    """High p_tail is risky. Return minimum score protecting 90% tail-regret mass."""
    z = hist_pred[
        hist_pred.actual_tail
        & hist_pred.p_tail.notna()
        & hist_pred.delta_return.gt(EPS)
    ][["p_tail", "delta_return"]].copy()
    n = int(len(z))
    total = float(z.delta_return.sum()) if n else 0.0
    if n < MIN_PRIOR_OOS_TAIL_EVENTS or total <= 0:
        return np.nan, n, total
    z = z.sort_values(["p_tail", "delta_return"], ascending=[False, False]).reset_index(drop=True)
    z["cum_share"] = z.delta_return.cumsum() / total
    hit = z[z.cum_share >= REGRET_COVERAGE]
    cutoff = float(hit.iloc[0].p_tail) if len(hit) else float(z.p_tail.min())
    return cutoff, n, total


def build_predictions(df: pd.DataFrame) -> pd.DataFrame:
    months = sorted(m for m in df.label_month.unique() if m >= START_TEST)
    outs = []
    prior_oos = []

    for month in months:
        tr = df[df.label_month < month].copy()
        te = df[df.label_month == month].copy()
        if te.empty:
            continue

        tail_delta_cutoff = tail_cutoff_from_training(tr)
        if not np.isfinite(tail_delta_cutoff):
            continue

        y = tr.delta_return.ge(tail_delta_cutoff).astype(int)
        if int(y.sum()) < MIN_TAIL_TRAIN_EVENTS or y.nunique() < 2:
            continue

        mod = s3.pipe_logit()
        mod.fit(tr[TAIL_FEATURES], y)
        p_tail = mod.predict_proba(te[TAIL_FEATURES])[:, 1]

        current = te[["label_month", "asof_date", "symbol", "delta_return"]].copy()
        current["tail_delta_cutoff"] = tail_delta_cutoff
        current["actual_tail"] = current.delta_return.ge(tail_delta_cutoff)
        current["p_tail"] = p_tail
        current["train_rows"] = int(len(tr))
        current["train_tail_events"] = int(y.sum())
        current["oos_period"] = _period(month)
        current["month_tail_rank_pct"] = current.p_tail.rank(pct=True, method="average")

        hist = pd.concat(prior_oos, ignore_index=True) if prior_oos else pd.DataFrame()
        if len(hist):
            score_cutoff, n_tail, tail_mass = protective_score_cutoff(hist)
        else:
            score_cutoff, n_tail, tail_mass = np.nan, 0, 0.0
        current["tail_guard_cutoff"] = score_cutoff
        current["prior_oos_tail_events"] = n_tail
        current["prior_oos_tail_regret_mass"] = tail_mass
        current["tail_protected"] = (
            current.p_tail.ge(score_cutoff) if np.isfinite(score_cutoff) else False
        )

        outs.append(current)
        prior_oos.append(current.copy())

    if not outs:
        raise RuntimeError("No Stage12 OOS predictions produced")
    p = pd.concat(outs, ignore_index=True)
    p.to_csv(OUT_PRED, index=False)
    return p


def stage7_guard(monthly: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    z = monthly.copy()
    z["label_month"] = z.label_month.astype(str)
    pp = p[["label_month", "symbol", "p_tail", "tail_guard_cutoff", "tail_protected", "actual_tail"]].copy()

    rows = []
    for _, r in z.iterrows():
        acted = bool(r.act_primary_regime90)
        sym = None
        if acted and pd.notna(r.symbol_primary_regime90):
            sym = str(int(float(r.symbol_primary_regime90))).zfill(6)
        hit = pp[(pp.label_month == r.label_month) & (pp.symbol.astype(str).str.zfill(6) == sym)] if sym else pd.DataFrame()
        protected = bool(hit.iloc[0].tail_protected) if len(hit) else False
        tail_prob = float(hit.iloc[0].p_tail) if len(hit) else np.nan
        cutoff = float(hit.iloc[0].tail_guard_cutoff) if len(hit) and pd.notna(hit.iloc[0].tail_guard_cutoff) else np.nan

        veto = bool(acted and protected)
        guarded_ret = float(r.base_return) if veto else float(r.ret_primary_regime90)
        rows.append({
            "label_month": r.label_month,
            "base_return": float(r.base_return),
            "stage7_return": float(r.ret_primary_regime90),
            "stage7_action": acted,
            "selected_symbol": sym,
            "selected_delta_return": float(r.selected_delta_return_primary_regime90),
            "tail_probability": tail_prob,
            "tail_guard_cutoff": cutoff,
            "tail_veto": veto,
            "stage7_tail_guard_return": guarded_ret,
        })
    out = pd.DataFrame(rows)
    out.to_csv(OUT_STAGE7, index=False)
    return out


def stage10_guard(stage10: pd.DataFrame, p: pd.DataFrame, stage7_monthly: pd.DataFrame) -> pd.DataFrame:
    m7 = stage7_monthly[["label_month", "base_return", "ret_primary_regime90"]].copy()
    m7["label_month"] = m7.label_month.astype(str)
    s10 = stage10.copy()
    s10["label_month"] = s10.label_month.astype(str)
    psmall = p[["label_month", "symbol", "p_tail", "tail_guard_cutoff", "tail_protected"]].copy()

    rows = []
    for _, r in s10.iterrows():
        second_action = bool(r.second_action)
        sym = None
        if second_action and pd.notna(r.second_removed_stage10):
            sym = str(int(float(r.second_removed_stage10))).zfill(6)
        hit = psmall[(psmall.label_month == r.label_month) & (psmall.symbol.astype(str).str.zfill(6) == sym)] if sym else pd.DataFrame()
        protected = bool(hit.iloc[0].tail_protected) if len(hit) else False
        tail_prob = float(hit.iloc[0].p_tail) if len(hit) else np.nan
        cutoff = float(hit.iloc[0].tail_guard_cutoff) if len(hit) and pd.notna(hit.iloc[0].tail_guard_cutoff) else np.nan
        veto = bool(second_action and protected)
        guarded = float(r.stage7_return) if veto else float(r.stage10_return)
        rows.append({
            "label_month": r.label_month,
            "first_removed_stage7": str(r.first_removed_stage7),
            "stage7_return": float(r.stage7_return),
            "second_action": second_action,
            "second_removed_stage10": sym,
            "second_realized_retention_value": float(r.second_realized_retention_value),
            "tail_probability": tail_prob,
            "tail_guard_cutoff": cutoff,
            "tail_veto": veto,
            "stage10_return": float(r.stage10_return),
            "stage10_tail_guard_return": guarded,
        })
    out = pd.DataFrame(rows)
    out.to_csv(OUT_STAGE10, index=False)
    return out


def summarize_predictions(p: pd.DataFrame, p3: pd.DataFrame, risk: pd.DataFrame, monthly: pd.DataFrame) -> dict:
    q = p.merge(
        p3[["label_month", "symbol", "muv_pairwise", "p_active"]],
        on=["label_month", "symbol"], how="left"
    ).merge(
        risk[["label_month", "symbol", "risk_pairwise_regime"]],
        on=["label_month", "symbol"], how="left"
    )
    mm = monthly[["label_month", "safety_cutoff_primary_regime90"]].copy()
    mm["label_month"] = mm.label_month.astype(str)
    q = q.merge(mm, on="label_month", how="left")
    q["stage7_safety_protected"] = q.risk_pairwise_regime.ge(q.safety_cutoff_primary_regime90)

    tail = q[q.actual_tail].copy()
    neg_tail = tail[tail.muv_pairwise < 0].copy()

    named = {}
    for month, sym in [("2024-09", "159915"), ("2025-04", "518880")]:
        h = q[(q.label_month == month) & (q.symbol.astype(str).str.zfill(6) == sym)]
        if len(h):
            r = h.iloc[0]
            named[f"{month}_{sym}"] = {
                "delta_return": float(r.delta_return),
                "tail_delta_cutoff": float(r.tail_delta_cutoff),
                "actual_tail": bool(r.actual_tail),
                "p_active": float(r.p_active) if pd.notna(r.p_active) else None,
                "muv_pairwise": float(r.muv_pairwise) if pd.notna(r.muv_pairwise) else None,
                "stage7_safety_risk": float(r.risk_pairwise_regime) if pd.notna(r.risk_pairwise_regime) else None,
                "stage7_safety_protected": bool(r.stage7_safety_protected),
                "p_tail": float(r.p_tail),
                "tail_rank_pct": float(r.month_tail_rank_pct),
                "tail_guard_cutoff": float(r.tail_guard_cutoff) if pd.notna(r.tail_guard_cutoff) else None,
                "tail_protected": bool(r.tail_protected),
            }

    return {
        "overall": {
            "rows": int(len(q)),
            "months": int(q.label_month.nunique()),
            "tail_events": int(q.actual_tail.sum()),
            "tail_auc": _auc(q.actual_tail.astype(int), q.p_tail),
            "tail_average_precision": _ap(q.actual_tail.astype(int), q.p_tail),
            "tail_base_rate": float(q.actual_tail.mean()),
            "tail_mean_month_rank_pct": float(tail.month_tail_rank_pct.mean()) if len(tail) else None,
            "tail_median_month_rank_pct": float(tail.month_tail_rank_pct.median()) if len(tail) else None,
        },
        "by_period": {
            per: {
                "rows": int(len(g)),
                "tail_events": int(g.actual_tail.sum()),
                "auc": _auc(g.actual_tail.astype(int), g.p_tail),
                "average_precision": _ap(g.actual_tail.astype(int), g.p_tail),
            }
            for per, g in q.groupby("oos_period")
        },
        "negative_muv_tail_failures": {
            "events": int(len(neg_tail)),
            "stage7_safety_protected_share": float(neg_tail.stage7_safety_protected.mean()) if len(neg_tail) else None,
            "tail_guard_protected_share": float(neg_tail.tail_protected.mean()) if len(neg_tail) else None,
            "mean_tail_rank_pct": float(neg_tail.month_tail_rank_pct.mean()) if len(neg_tail) else None,
        },
        "named_audits": named,
    }


def main():
    df = pd.read_parquet(LABELS)
    df["label_month"] = df.label_month.astype(str)
    df["symbol"] = df.symbol.astype(str).str.zfill(6)
    df["delta_return"] = pd.to_numeric(df.delta_return, errors="coerce")

    missing = set(TAIL_FEATURES) - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing Stage12 features: {sorted(missing)}")

    p3 = pd.read_csv(STAGE3)
    risk = pd.read_csv(STAGE7_RISK)
    monthly = pd.read_csv(STAGE7_MONTHLY)
    s10 = pd.read_csv(STAGE10)
    for x in [p3, risk, monthly, s10]:
        x["label_month"] = x.label_month.astype(str)
    for x in [p3, risk]:
        x["symbol"] = x.symbol.astype(str).str.replace(".0", "", regex=False).str.zfill(6)

    p = build_predictions(df)
    p["symbol"] = p.symbol.astype(str).str.zfill(6)
    g7 = stage7_guard(monthly, p)
    g10 = stage10_guard(s10, p, monthly)
    pred_summary = summarize_predictions(p, p3, risk, monthly)

    stage7_summary = {
        "stage7_final_wealth": _wealth(g7.stage7_return),
        "stage7_tail_guard_final_wealth": _wealth(g7.stage7_tail_guard_return),
        "tail_vetoes": int(g7.tail_veto.sum()),
        "vetoed_positive_retention_value": float(g7.loc[g7.tail_veto & (g7.selected_delta_return > EPS), "selected_delta_return"].sum()),
        "vetoed_negative_retention_value": float(g7.loc[g7.tail_veto & (g7.selected_delta_return < -EPS), "selected_delta_return"].sum()),
    }

    path = monthly[["label_month", "ret_primary_regime90"]].merge(
        g10[["label_month", "stage10_return", "stage10_tail_guard_return"]],
        on="label_month", how="left"
    )
    path["stage10_return"] = path.stage10_return.fillna(path.ret_primary_regime90)
    path["stage10_tail_guard_return"] = path.stage10_tail_guard_return.fillna(path.ret_primary_regime90)
    stage10_summary = {
        "stage7_final_wealth": _wealth(path.ret_primary_regime90),
        "stage10_final_wealth": _wealth(path.stage10_return),
        "stage10_tail_guard_final_wealth": _wealth(path.stage10_tail_guard_return),
        "second_actions": int(g10.second_action.sum()),
        "tail_vetoes": int(g10.tail_veto.sum()),
        "vetoed_false_removal_regret": float(g10.loc[g10.tail_veto & (g10.second_realized_retention_value > EPS), "second_realized_retention_value"].sum()),
        "vetoed_correct_removal_value": float((-g10.loc[g10.tail_veto & (g10.second_realized_retention_value < -EPS), "second_realized_retention_value"]).sum()),
    }

    report = {
        "version": "muv_stage12_tail_winner_guard_20260913",
        "design": {
            "test_start": START_TEST,
            "tail_definition": "delta_return >= expanding prior positive-delta 80th percentile",
            "tail_quantile": TAIL_QUANTILE,
            "features": TAIL_FEATURES,
            "model": "L2 logistic C=1 fixed; direct all-row tail classification",
            "stage_a_probability_used_in_prediction": False,
            "guard_calibration": "prior OOS tail events only; protect 90% realized tail-regret mass",
            "min_tail_train_events": MIN_TAIL_TRAIN_EVENTS,
            "min_prior_oos_tail_events_for_guard": MIN_PRIOR_OOS_TAIL_EVENTS,
            "feature_search": False,
            "threshold_search": False,
        },
        "prediction": pred_summary,
        "stage7_plus_tail_guard": stage7_summary,
        "stage10_plus_tail_guard_diagnostic": stage10_summary,
        "notes": [
            "Stage7 remains the production research baseline unless the fixed tail guard improves asymmetric regret without excessive opportunity sacrifice.",
            "Stage10 remains rejected; its guarded result is diagnostic only.",
            "The 80th percentile tail definition and 90% regret coverage were frozen before this run and are never optimized against final wealth.",
        ],
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
