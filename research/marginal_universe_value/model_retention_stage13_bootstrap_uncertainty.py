#!/usr/bin/env python3
"""Stage 13: month-cluster bootstrap uncertainty around frozen expected MUV.

Frozen in STAGE13_BOOTSTRAP_UNCERTAINTY_DESIGN_20260913.md.

No new predictive model family is introduced.  Each bootstrap draw resamples
prior months as clusters, then refits the exact Stage-A and Stage-3 pairwise
models and historical positive/negative active-delta means.  A removal is
called uncertainty-safe only when the bootstrap 90th percentile of expected
MUV remains below zero.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import model_retention_stage3_pairwise_sign as s3

LABELS = Path("muv-retention-labels-v1.parquet")
STAGE3 = Path("muv-retention-stage3-predictions.csv")
STAGE7_MONTHLY = Path("muv-retention-stage7-monthly-policy.csv")
OUT_JSON = Path("muv-retention-stage13-report.json")
OUT_PRED = Path("muv-retention-stage13-bootstrap-predictions.csv")
OUT_STAGE7 = Path("muv-retention-stage13-stage7-veto.csv")
OUT_UCB = Path("muv-retention-stage13-ucb-policy.csv")

START_TEST = "2023-01"
BOOT_DRAWS = 300
BOOT_Q_LO = 0.10
BOOT_Q_HI = 0.90
RANDOM_SEED = 20260913
EPS = 1e-10
TAIL_QUANTILE = 0.80


def _sym(v) -> str:
    s = str(v)
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(6)


def _wealth(r) -> float:
    a = pd.to_numeric(pd.Series(r), errors="coerce").fillna(0.0).to_numpy(dtype=float)
    return float(np.prod(1.0 + a))


def _period(month: str) -> str:
    return "2023-24" if int(str(month)[:4]) <= 2024 else "2025-26"


def _tail_cutoff(tr: pd.DataFrame) -> float:
    pos = pd.to_numeric(tr.loc[tr.delta_return > EPS, "delta_return"], errors="coerce").dropna()
    return float(pos.quantile(TAIL_QUANTILE)) if len(pos) else np.nan


def _cluster_bootstrap(tr: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    months = np.asarray(sorted(tr.label_month.unique()), dtype=object)
    sampled = rng.choice(months, size=len(months), replace=True)
    pieces = [tr[tr.label_month == m] for m in sampled]
    return pd.concat(pieces, ignore_index=True)


def bootstrap_month(tr: pd.DataFrame, te: pd.DataFrame, month: str) -> tuple[np.ndarray, int]:
    draws = []
    rng = np.random.default_rng(RANDOM_SEED + int(month.replace("-", "")))

    for _ in range(BOOT_DRAWS):
        b = _cluster_bootstrap(tr, rng)
        y_active = b.path_active.astype(int)
        if y_active.nunique() < 2:
            continue

        a = s3.pipe_logit()
        a.fit(b[s3.STAGE_A_FEATURES], y_active)
        p_active = a.predict_proba(te[s3.STAGE_A_FEATURES])[:, 1]

        atr = b[b.path_active].copy()
        if len(atr) < 40:
            continue
        y_sign = atr.delta_return.gt(EPS).astype(int)
        if y_sign.nunique() < 2:
            continue

        sm = s3.pipe_logit()
        sm.fit(atr[s3.PAIRWISE_FEATURES], y_sign)
        p_pos = sm.predict_proba(te[s3.PAIRWISE_FEATURES])[:, 1]

        pos = atr.loc[atr.delta_return > EPS, "delta_return"]
        neg = atr.loc[atr.delta_return < -EPS, "delta_return"]
        if len(pos) == 0 or len(neg) == 0:
            continue
        mean_pos = float(pos.mean())
        mean_neg = float(neg.mean())
        cond = p_pos * mean_pos + (1.0 - p_pos) * mean_neg
        draws.append(p_active * cond)

    if not draws:
        raise RuntimeError(f"No valid bootstrap draws for {month}")
    return np.vstack(draws), len(draws)


def build_predictions(df: pd.DataFrame, p3: pd.DataFrame) -> pd.DataFrame:
    outs = []
    months = sorted(m for m in df.label_month.unique() if m >= START_TEST)
    for month in months:
        tr = df[df.label_month < month].copy()
        te = df[df.label_month == month].copy()
        if te.empty:
            continue

        boot, n_valid = bootstrap_month(tr, te, month)
        q10 = np.quantile(boot, BOOT_Q_LO, axis=0)
        med = np.quantile(boot, 0.50, axis=0)
        q90 = np.quantile(boot, BOOT_Q_HI, axis=0)
        pneg = np.mean(boot < 0.0, axis=0)

        point = p3[p3.label_month == month][["symbol", "muv_pairwise", "p_active"]].copy()
        point["symbol"] = point.symbol.map(_sym)

        out = te[[
            "label_month", "asof_date", "symbol", "delta_return",
            "base_return", "cf_return"
        ]].copy()
        out["symbol"] = out.symbol.map(_sym)
        out = out.merge(point, on="symbol", how="left")
        out["boot_valid_draws"] = int(n_valid)
        out["muv_boot_q10"] = q10
        out["muv_boot_median"] = med
        out["muv_boot_q90"] = q90
        out["boot_prob_muv_negative"] = pneg
        out["boot_width_80"] = q90 - q10
        out["uncertainty_safe_remove"] = q90 < 0.0
        tail_cut = _tail_cutoff(tr)
        out["tail_delta_cutoff"] = tail_cut
        out["actual_tail"] = out.delta_return.ge(tail_cut) if np.isfinite(tail_cut) else False
        out["oos_period"] = _period(month)
        outs.append(out)

    p = pd.concat(outs, ignore_index=True)
    p.to_csv(OUT_PRED, index=False)
    return p


def stage7_veto(monthly: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in monthly.iterrows():
        month = str(r.label_month)
        acted = bool(r.act_primary_regime90)
        sym = _sym(r.symbol_primary_regime90) if acted and pd.notna(r.symbol_primary_regime90) else None
        h = p[(p.label_month == month) & (p.symbol == sym)] if sym else pd.DataFrame()
        safe = bool(h.iloc[0].uncertainty_safe_remove) if len(h) else False
        q90 = float(h.iloc[0].muv_boot_q90) if len(h) else np.nan
        veto = bool(acted and not safe)
        guarded_ret = float(r.base_return) if veto else float(r.ret_primary_regime90)
        rows.append({
            "label_month": month,
            "base_return": float(r.base_return),
            "stage7_return": float(r.ret_primary_regime90),
            "stage7_action": acted,
            "selected_symbol": sym,
            "selected_delta_return": float(r.selected_delta_return_primary_regime90),
            "muv_boot_q90": q90,
            "uncertainty_safe_remove": safe,
            "uncertainty_veto": veto,
            "stage7_uncertainty_return": guarded_ret,
        })
    out = pd.DataFrame(rows)
    out.to_csv(OUT_STAGE7, index=False)
    return out


def ucb_policy(p: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month, g in p.groupby("label_month", sort=True):
        base = g.iloc[0]
        cand = g[
            g.muv_pairwise.notna()
            & g.muv_pairwise.lt(0.0)
            & g.uncertainty_safe_remove
        ].sort_values(["muv_pairwise", "muv_boot_q90", "symbol"])
        if len(cand):
            c = cand.iloc[0]
            rows.append({
                "label_month": month,
                "acted": True,
                "selected_symbol": str(c.symbol),
                "pred_muv": float(c.muv_pairwise),
                "muv_boot_q90": float(c.muv_boot_q90),
                "selected_delta_return": float(c.delta_return),
                "return": float(c.cf_return),
            })
        else:
            rows.append({
                "label_month": month,
                "acted": False,
                "selected_symbol": None,
                "pred_muv": np.nan,
                "muv_boot_q90": np.nan,
                "selected_delta_return": 0.0,
                "return": float(base.base_return),
            })
    out = pd.DataFrame(rows)
    out.to_csv(OUT_UCB, index=False)
    return out


def diagnostics(p: pd.DataFrame) -> dict:
    pos = p[p.delta_return > EPS]
    neg = p[p.delta_return < -EPS]
    tail = p[p.actual_tail]
    hidden = tail[p.muv_pairwise < 0.0]
    ordinary = p[~p.actual_tail]

    named = {}
    for month, sym in [("2024-09", "159915"), ("2025-04", "518880")]:
        h = p[(p.label_month == month) & (p.symbol == sym)]
        if len(h):
            r = h.iloc[0]
            named[f"{month}_{sym}"] = {
                "delta_return": float(r.delta_return),
                "point_muv": float(r.muv_pairwise) if pd.notna(r.muv_pairwise) else None,
                "p_active": float(r.p_active) if pd.notna(r.p_active) else None,
                "boot_q10": float(r.muv_boot_q10),
                "boot_median": float(r.muv_boot_median),
                "boot_q90": float(r.muv_boot_q90),
                "boot_prob_negative": float(r.boot_prob_muv_negative),
                "boot_width_80": float(r.boot_width_80),
                "uncertainty_safe_remove": bool(r.uncertainty_safe_remove),
                "actual_tail": bool(r.actual_tail),
            }

    by_period = {}
    for per, g in p.groupby("oos_period"):
        t = g[g.actual_tail]
        n = g[g.delta_return < -EPS]
        by_period[per] = {
            "rows": int(len(g)),
            "tail_events": int(len(t)),
            "tail_false_safe_share": float(t.uncertainty_safe_remove.mean()) if len(t) else None,
            "negative_rv_safe_share": float(n.uncertainty_safe_remove.mean()) if len(n) else None,
        }

    return {
        "rows": int(len(p)),
        "months": int(p.label_month.nunique()),
        "positive_rv_rows": int(len(pos)),
        "positive_rv_false_safe_share": float(pos.uncertainty_safe_remove.mean()) if len(pos) else None,
        "negative_rv_rows": int(len(neg)),
        "negative_rv_safe_share": float(neg.uncertainty_safe_remove.mean()) if len(neg) else None,
        "tail_events": int(len(tail)),
        "tail_false_safe_share": float(tail.uncertainty_safe_remove.mean()) if len(tail) else None,
        "negative_point_muv_tail_events": int(len(hidden)),
        "negative_point_muv_tail_false_safe_share": float(hidden.uncertainty_safe_remove.mean()) if len(hidden) else None,
        "hidden_tail_median_width80": float(hidden.boot_width_80.median()) if len(hidden) else None,
        "ordinary_median_width80": float(ordinary.boot_width_80.median()) if len(ordinary) else None,
        "by_period": by_period,
        "named_audits": named,
    }


def main():
    df = pd.read_parquet(LABELS)
    df["label_month"] = df.label_month.astype(str)
    df["symbol"] = df.symbol.map(_sym)
    df["delta_return"] = pd.to_numeric(df.delta_return, errors="coerce")
    df["path_active"] = pd.to_numeric(df.path_direct_selection_days, errors="coerce").fillna(0) > 0

    req = set(s3.STAGE_A_FEATURES + s3.PAIRWISE_FEATURES)
    missing = req - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing Stage13 features: {sorted(missing)}")

    p3 = pd.read_csv(STAGE3)
    p3["label_month"] = p3.label_month.astype(str)
    p3["symbol"] = p3.symbol.map(_sym)
    monthly = pd.read_csv(STAGE7_MONTHLY)
    monthly["label_month"] = monthly.label_month.astype(str)

    p = build_predictions(df, p3)
    g7 = stage7_veto(monthly, p)
    ucb = ucb_policy(p)
    diag = diagnostics(p)

    report = {
        "version": "muv_stage13_bootstrap_uncertainty_20260913",
        "design": {
            "test_start": START_TEST,
            "bootstrap_unit": "prior label_month cluster",
            "bootstrap_draws": BOOT_DRAWS,
            "bootstrap_quantiles": [BOOT_Q_LO, BOOT_Q_HI],
            "safe_rule": "bootstrap MUV q90 < 0",
            "stage_a_features": s3.STAGE_A_FEATURES,
            "pairwise_features": s3.PAIRWISE_FEATURES,
            "model_specification_changed": False,
            "feature_search": False,
            "confidence_level_search": False,
        },
        "diagnostics": diag,
        "stage7_plus_uncertainty_veto": {
            "stage7_final_wealth": _wealth(g7.stage7_return),
            "guarded_final_wealth": _wealth(g7.stage7_uncertainty_return),
            "stage7_actions": int(g7.stage7_action.sum()),
            "vetoes": int(g7.uncertainty_veto.sum()),
            "prevented_positive_retention_regret": float(g7.loc[g7.uncertainty_veto & (g7.selected_delta_return > EPS), "selected_delta_return"].sum()),
            "sacrificed_correct_removal_value": float((-g7.loc[g7.uncertainty_veto & (g7.selected_delta_return < -EPS), "selected_delta_return"]).sum()),
        },
        "ucb_one_removal_diagnostic": {
            "final_wealth": _wealth(ucb["return"]),
            "actions": int(ucb.acted.sum()),
            "positive_retention_value_mistakes": int((ucb.selected_delta_return > EPS).sum()),
            "negative_retention_value_correct_removals": int((ucb.selected_delta_return < -EPS).sum()),
            "sum_positive_retention_regret": float(ucb.loc[ucb.selected_delta_return > EPS, "selected_delta_return"].sum()),
            "sum_negative_retention_value": float(ucb.loc[ucb.selected_delta_return < -EPS, "selected_delta_return"].sum()),
        },
        "notes": [
            "This stage estimates epistemic model uncertainty by resampling whole prior months; it does not add a new return predictor.",
            "The 90% one-sided upper bound was frozen before results and is not tuned.",
            "If large hidden winners remain uncertainty-safe, the hard one-removal cap is more defensible than deeper sequential deletion with the current feature/model family.",
        ],
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
