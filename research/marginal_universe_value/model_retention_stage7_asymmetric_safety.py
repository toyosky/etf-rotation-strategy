#!/usr/bin/env python3
"""MUV Stage 7: asymmetric retention safety policy.

Frozen before results in STAGE7_ASYMMETRIC_SAFETY_DESIGN_20260912.md.

The Stage-6 failure showed that ordinary sign accuracy is not the policy loss:
a single false removal of a large positive-retention-value ETF can dominate many
small correct removals. Stage 7 therefore adds a magnitude-weighted safety score
and calibrates a past-only protected region designed to cover a fixed share of
historical positive opportunity-regret mass.

No hyperparameter, feature, or policy-threshold search is performed here.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

LABELS = Path("muv-retention-labels-v1.parquet")
STAGE3 = Path("muv-retention-stage3-predictions.csv")
OUT_JSON = Path("muv-retention-stage7-report.json")
OUT_MONTHLY = Path("muv-retention-stage7-monthly-policy.csv")
OUT_RISK = Path("muv-retention-stage7-safety-predictions.csv")

EPS = 1e-12
SAFETY_PRED_START = "2022-01"
POLICY_START = "2023-01"
MIN_ACTIVE_TRAIN = 20
MIN_PRIOR_POSITIVE_EVENTS = 8
RANDOM_SEED = 20260912
RANDOM_DRAWS = 2000

PAIRWISE_FEATURES = [
    "pair_score_exact_gap_alt",
    "pair_r2_gap_alt",
    "pair_current_resid_gap_alt",
    "pair_ret10_gap_alt",
    "pair_ret20_gap_alt",
    "pair_efficiency10_gap_alt",
    "pair_vol20_gap_alt",
    "pair_ma10_dist_gap_alt",
    "pair_corr120_with_alt",
    "pair_top3_freq20_gap_alt",
]

REGIME_FEATURES = [
    "regime_risk_qualified_count",
    "regime_risk_ret20_positive_frac",
    "regime_risk_ret20_median",
]

FEATURE_SETS = {
    "pairwise": PAIRWISE_FEATURES,
    "pairwise_regime": PAIRWISE_FEATURES + REGIME_FEATURES,
}

POLICIES = {
    "primary_regime90": ("risk_pairwise_regime", 0.90),
    "regime80": ("risk_pairwise_regime", 0.80),
    "regime95": ("risk_pairwise_regime", 0.95),
    "pairwise90": ("risk_pairwise", 0.90),
}


def pipe_logit() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=1.0, max_iter=2000, solver="lbfgs")),
    ])


def auc(y, p):
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    ok = np.isfinite(p)
    y, p = y[ok], p[ok]
    if len(y) < 2 or len(np.unique(y)) < 2:
        return None
    return float(roc_auc_score(y, p))


def equity_metrics(returns: pd.Series) -> dict:
    r = pd.to_numeric(returns, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    if len(r) == 0:
        return {"months": 0, "total_return": None, "cagr": None,
                "monthly_equity_max_drawdown": None, "final_wealth": None}
    wealth = np.cumprod(1.0 + r)
    wealth0 = np.r_[1.0, wealth]
    peak = np.maximum.accumulate(wealth0)
    dd = wealth0 / peak - 1.0
    years = len(r) / 12.0
    final_wealth = float(wealth[-1])
    return {
        "months": int(len(r)),
        "total_return": float(final_wealth - 1.0),
        "cagr": float(final_wealth ** (1.0 / years) - 1.0) if years > 0 and final_wealth > 0 else None,
        "monthly_equity_max_drawdown": float(np.min(dd)),
        "mean_monthly_return": float(np.mean(r)),
        "monthly_return_std": float(np.std(r, ddof=1)) if len(r) > 1 else 0.0,
        "final_wealth": final_wealth,
    }


def build_safety_predictions(lab: pd.DataFrame) -> pd.DataFrame:
    months = sorted(m for m in lab.label_month.unique() if m >= SAFETY_PRED_START)
    outs = []
    for m in months:
        tr = lab[lab.label_month < m].copy()
        te = lab[lab.label_month == m].copy()
        atr = tr[tr.path_active].copy()
        if te.empty or len(atr) < MIN_ACTIVE_TRAIN:
            continue
        y = atr.delta_return.gt(EPS).astype(int)
        if y.nunique() < 2:
            continue

        mag = atr.delta_return.abs().to_numpy(dtype=float)
        mean_mag = float(np.mean(mag))
        if not np.isfinite(mean_mag) or mean_mag <= 0:
            continue
        weights = mag / mean_mag

        out = te[["label_month", "symbol", "delta_return", "path_active"]].copy()
        out["train_active_rows"] = int(len(atr))
        out["train_positive_rows"] = int(y.sum())
        out["train_mean_abs_delta"] = mean_mag

        for name, cols in FEATURE_SETS.items():
            mod = pipe_logit()
            mod.fit(atr[cols], y, model__sample_weight=weights)
            out[f"risk_{name}"] = mod.predict_proba(te[cols])[:, 1]

        outs.append(out)

    if not outs:
        raise RuntimeError("No Stage7 OOS safety predictions were produced")
    p = pd.concat(outs, ignore_index=True)
    p.to_csv(OUT_RISK, index=False)
    return p


def regret_cutoff(hist: pd.DataFrame, score_col: str, coverage: float) -> tuple[float, int, float]:
    z = hist[
        hist.path_active
        & hist.delta_return.gt(EPS)
        & hist[score_col].notna()
    ][[score_col, "delta_return"]].copy()
    n = int(len(z))
    total = float(z.delta_return.sum()) if n else 0.0
    if n < MIN_PRIOR_POSITIVE_EVENTS or total <= 0:
        return np.nan, n, total

    z = z.sort_values([score_col, "delta_return"], ascending=[False, False]).reset_index(drop=True)
    z["cum_share"] = z.delta_return.cumsum() / total
    hit = z[z.cum_share >= coverage]
    if hit.empty:
        return float(z[score_col].min()), n, total
    cutoff = float(hit.iloc[0][score_col])
    return cutoff, n, total


def apply_policy(month_rows: pd.DataFrame, hist_risk: pd.DataFrame,
                 score_col: str, coverage: float) -> dict:
    base = month_rows.iloc[0]
    cutoff, npos, prior_pos_mass = regret_cutoff(hist_risk, score_col, coverage)
    result = {
        "acted": False,
        "selected_symbol": None,
        "selected_pred_muv": None,
        "selected_safety_score": None,
        "safety_cutoff": cutoff if np.isfinite(cutoff) else None,
        "prior_positive_events": npos,
        "prior_positive_regret_mass": prior_pos_mass,
        "safe_negative_candidates": 0,
        "ret": float(base.base_return),
        "switches": int(base.base_switches),
        "turnover": int(base.base_turnover_sides),
        "mdd": float(base.base_max_drawdown),
        "improvement": 0.0,
        "selected_delta_return": 0.0,
    }
    if not np.isfinite(cutoff):
        return result

    z = month_rows[
        month_rows.muv_pairwise.notna()
        & month_rows[score_col].notna()
        & month_rows.muv_pairwise.lt(0.0)
        & month_rows[score_col].lt(cutoff)
    ].copy()
    result["safe_negative_candidates"] = int(len(z))
    if z.empty:
        return result

    cand = z.sort_values(["muv_pairwise", score_col, "symbol"]).iloc[0]
    result.update({
        "acted": True,
        "selected_symbol": str(cand.symbol),
        "selected_pred_muv": float(cand.muv_pairwise),
        "selected_safety_score": float(cand[score_col]),
        "ret": float(cand.cf_return),
        "switches": int(cand.cf_switches),
        "turnover": int(cand.cf_turnover_sides),
        "mdd": float(cand.cf_max_drawdown),
        "improvement": float(cand.cf_return - cand.base_return),
        "selected_delta_return": float(cand.delta_return),
    })
    return result


def summarize_policy(g: pd.DataFrame, policy: str) -> dict:
    ret_col = f"ret_{policy}"
    act_col = f"act_{policy}"
    imp_col = f"improvement_{policy}"
    drv_col = f"selected_delta_return_{policy}"
    selected = g[g[act_col]].copy()
    em = equity_metrics(g[ret_col])
    base = equity_metrics(g.base_return)
    positive_regrets = selected.loc[selected[drv_col] > EPS, drv_col]
    captured_negative = -selected.loc[selected[drv_col] < -EPS, drv_col]
    max_regret = float(positive_regrets.max()) if len(positive_regrets) else 0.0
    worst = None
    if len(positive_regrets):
        idx = positive_regrets.idxmax()
        worst = {
            "label_month": str(selected.loc[idx, "label_month"]),
            "symbol": str(selected.loc[idx, f"symbol_{policy}"]),
            "retention_value_lost": float(selected.loc[idx, drv_col]),
        }
    em.update({
        "action_months": int(selected.shape[0]),
        "action_rate": float(g[act_col].mean()),
        "realized_action_win_rate": float((selected[imp_col] > EPS).mean()) if len(selected) else None,
        "realized_action_harm_rate": float((selected[imp_col] < -EPS).mean()) if len(selected) else None,
        "mean_realized_improvement_when_acting": float(selected[imp_col].mean()) if len(selected) else None,
        "sum_realized_improvement_when_acting": float(selected[imp_col].sum()) if len(selected) else 0.0,
        "cumulative_false_removal_regret": float(positive_regrets.sum()) if len(positive_regrets) else 0.0,
        "captured_negative_retention_value": float(captured_negative.sum()) if len(captured_negative) else 0.0,
        "max_single_false_removal_regret": max_regret,
        "worst_false_removal": worst,
        "terminal_wealth_advantage_vs_keep_all": (
            float(em["final_wealth"] / base["final_wealth"] - 1.0)
            if em.get("final_wealth") is not None and base.get("final_wealth") not in (None, 0)
            else None
        ),
        "total_switches": int(g[f"switches_{policy}"].sum()),
        "total_turnover_sides": int(g[f"turnover_{policy}"].sum()),
        "mean_within_month_max_drawdown": float(g[f"mdd_{policy}"].mean()),
    })
    return em


def random_baseline(monthly_rows: dict[str, pd.DataFrame], action_months: list[str]) -> dict:
    rng = np.random.default_rng(RANDOM_SEED)
    months = sorted(monthly_rows)
    aset = set(action_months)
    base_returns = np.asarray([float(monthly_rows[m].iloc[0].base_return) for m in months])
    base_final = float(np.prod(1.0 + base_returns))
    totals, advantages = [], []
    for _ in range(RANDOM_DRAWS):
        rr = []
        for m in months:
            h = monthly_rows[m]
            if m not in aset:
                rr.append(float(h.iloc[0].base_return))
            else:
                j = int(rng.integers(0, len(h)))
                rr.append(float(h.iloc[j].cf_return))
        fw = float(np.prod(1.0 + np.asarray(rr)))
        totals.append(fw - 1.0)
        advantages.append(fw / base_final - 1.0)
    t = np.asarray(totals)
    a = np.asarray(advantages)
    return {
        "draws": RANDOM_DRAWS,
        "seed": RANDOM_SEED,
        "action_months_matched_to_primary_policy": int(len(action_months)),
        "total_return_mean": float(t.mean()),
        "total_return_p05": float(np.quantile(t, 0.05)),
        "total_return_p50": float(np.quantile(t, 0.50)),
        "total_return_p95": float(np.quantile(t, 0.95)),
        "terminal_wealth_advantage_vs_keep_all_mean": float(a.mean()),
        "terminal_wealth_advantage_vs_keep_all_p05": float(np.quantile(a, 0.05)),
        "terminal_wealth_advantage_vs_keep_all_p50": float(np.quantile(a, 0.50)),
        "terminal_wealth_advantage_vs_keep_all_p95": float(np.quantile(a, 0.95)),
        "prob_random_beats_keep_all": float(np.mean(a > 0.0)),
    }


def main() -> None:
    lab = pd.read_parquet(LABELS)
    s3 = pd.read_csv(STAGE3)
    lab["label_month"] = lab.label_month.astype(str)
    s3["label_month"] = s3.label_month.astype(str)
    lab["symbol"] = lab.symbol.astype(str).str.replace(r"\.0$", "", regex=True)
    s3["symbol"] = s3.symbol.astype(str).str.replace(r"\.0$", "", regex=True)
    lab["delta_return"] = pd.to_numeric(lab.delta_return, errors="coerce")
    lab["path_active"] = pd.to_numeric(lab.path_direct_selection_days, errors="coerce").fillna(0) > 0

    required = set(PAIRWISE_FEATURES + REGIME_FEATURES + [
        "base_return", "base_max_drawdown", "base_switches", "base_turnover_sides",
        "cf_return", "cf_max_drawdown", "cf_switches", "cf_turnover_sides",
        "delta_return", "path_direct_selection_days",
    ])
    missing = required - set(lab.columns)
    if missing:
        raise RuntimeError(f"Missing Stage7 label/features: {sorted(missing)}")
    if "muv_pairwise" not in s3.columns:
        raise RuntimeError("Stage3 muv_pairwise is missing")

    risk = build_safety_predictions(lab)

    # Evaluation rows use Stage3 OOS months only (2023 onward).
    risk_eval = risk[risk.label_month >= POLICY_START].copy()
    s3eval = s3[s3.label_month >= POLICY_START][
        ["label_month", "symbol", "muv_pairwise", "p_active", "p_positive_pairwise"]
    ].copy()
    outcomes = lab[[
        "label_month", "symbol", "base_return", "base_max_drawdown", "base_switches",
        "base_turnover_sides", "cf_return", "cf_max_drawdown", "cf_switches",
        "cf_turnover_sides", "delta_return",
    ]].copy()

    d = s3eval.merge(
        risk_eval[["label_month", "symbol", "risk_pairwise", "risk_pairwise_regime"]],
        on=["label_month", "symbol"], how="left", validate="one_to_one"
    ).merge(outcomes, on=["label_month", "symbol"], how="left", validate="one_to_one")
    if d.base_return.isna().any():
        raise RuntimeError("Stage7 evaluation merge produced missing outcomes")

    rows = []
    monthly_rows: dict[str, pd.DataFrame] = {}
    for m, h in d.groupby("label_month", sort=True):
        h = h.sort_values("symbol").copy()
        monthly_rows[str(m)] = h
        base = h.iloc[0]
        hist = risk[risk.label_month < str(m)].copy()
        out = {
            "label_month": str(m),
            "base_return": float(base.base_return),
            "base_switches": int(base.base_switches),
            "base_turnover_sides": int(base.base_turnover_sides),
            "base_max_drawdown": float(base.base_max_drawdown),
        }
        for pname, (score_col, coverage) in POLICIES.items():
            r = apply_policy(h, hist, score_col, coverage)
            out[f"act_{pname}"] = bool(r["acted"])
            out[f"symbol_{pname}"] = r["selected_symbol"]
            out[f"pred_muv_{pname}"] = r["selected_pred_muv"]
            out[f"safety_score_{pname}"] = r["selected_safety_score"]
            out[f"safety_cutoff_{pname}"] = r["safety_cutoff"]
            out[f"prior_positive_events_{pname}"] = r["prior_positive_events"]
            out[f"prior_positive_regret_mass_{pname}"] = r["prior_positive_regret_mass"]
            out[f"safe_negative_candidates_{pname}"] = r["safe_negative_candidates"]
            out[f"ret_{pname}"] = r["ret"]
            out[f"switches_{pname}"] = r["switches"]
            out[f"turnover_{pname}"] = r["turnover"]
            out[f"mdd_{pname}"] = r["mdd"]
            out[f"improvement_{pname}"] = r["improvement"]
            out[f"selected_delta_return_{pname}"] = r["selected_delta_return"]
        rows.append(out)

    monthly = pd.DataFrame(rows).sort_values("label_month").reset_index(drop=True)

    # Future-aware one-removal oracle, diagnostic upper bound only.
    oracle_ret, oracle_act = [], []
    for m in monthly.label_month:
        h = monthly_rows[m]
        cand = h.sort_values(["delta_return", "symbol"]).iloc[0]
        if float(cand.delta_return) < -EPS:
            oracle_ret.append(float(cand.cf_return))
            oracle_act.append(True)
        else:
            oracle_ret.append(float(cand.base_return))
            oracle_act.append(False)
    monthly["ret_oracle_one"] = oracle_ret
    monthly["act_oracle_one"] = oracle_act
    monthly.to_csv(OUT_MONTHLY, index=False)

    base_summary = equity_metrics(monthly.base_return)
    base_summary.update({
        "total_switches": int(monthly.base_switches.sum()),
        "total_turnover_sides": int(monthly.base_turnover_sides.sum()),
        "mean_within_month_max_drawdown": float(monthly.base_max_drawdown.mean()),
    })
    policy_summaries = {p: summarize_policy(monthly, p) for p in POLICIES}

    by_period = {}
    periods = {
        "2023-24": monthly[monthly.label_month.str[:4].astype(int) <= 2024],
        "2025-26": monthly[monthly.label_month.str[:4].astype(int) >= 2025],
    }
    for per, g in periods.items():
        by_period[per] = {
            "keep_all": equity_metrics(g.base_return),
            **{p: summarize_policy(g, p) for p in POLICIES},
        }

    by_year = {}
    for y, g in monthly.groupby(monthly.label_month.str[:4]):
        by_year[str(y)] = {
            "keep_all": equity_metrics(g.base_return),
            **{p: summarize_policy(g, p) for p in POLICIES},
        }

    oracle = equity_metrics(monthly.ret_oracle_one)
    oracle["action_months"] = int(monthly.act_oracle_one.sum())
    oracle["terminal_wealth_advantage_vs_keep_all"] = float(
        oracle["final_wealth"] / base_summary["final_wealth"] - 1.0
    )

    primary_actions = monthly.loc[monthly.act_primary_regime90, "label_month"].tolist()
    random = random_baseline(monthly_rows, primary_actions)

    # OOS safety-score diagnostics are secondary; policy regret is primary.
    active_risk = risk[risk.path_active].copy()
    risk_diag = {}
    for name in FEATURE_SETS:
        col = f"risk_{name}"
        risk_diag[name] = {
            "oos_active_rows": int(len(active_risk)),
            "ordinary_sign_auc": auc(active_risk.delta_return.gt(EPS).astype(int), active_risk[col]),
            "positive_regret_weighted_mean_score": (
                float(np.average(
                    active_risk.loc[active_risk.delta_return > EPS, col],
                    weights=active_risk.loc[active_risk.delta_return > EPS, "delta_return"]
                )) if (active_risk.delta_return > EPS).any() else None
            ),
            "negative_value_weighted_mean_score": (
                float(np.average(
                    active_risk.loc[active_risk.delta_return < -EPS, col],
                    weights=-active_risk.loc[active_risk.delta_return < -EPS, "delta_return"]
                )) if (active_risk.delta_return < -EPS).any() else None
            ),
        }

    report = {
        "design": {
            "dataset_version": str(lab.dataset_version.iloc[0]) if "dataset_version" in lab.columns else None,
            "safety_prediction_start": SAFETY_PRED_START,
            "policy_start": POLICY_START,
            "min_active_train": MIN_ACTIVE_TRAIN,
            "min_prior_positive_events": MIN_PRIOR_POSITIVE_EVENTS,
            "model": "L2 LogisticRegression C=1 fixed, active rows, |delta_return|-weighted and mean-normalized",
            "primary_features": FEATURE_SETS["pairwise_regime"],
            "ablation_features": FEATURE_SETS["pairwise"],
            "primary_policy": "primary_regime90",
            "primary_regret_coverage": 0.90,
            "sensitivities": {"regime80": 0.80, "regime95": 0.95, "pairwise90": 0.90},
            "max_removals_per_month": 1,
            "decision_rule": "muv_pairwise < 0 AND safety_score below past-only regret-coverage cutoff; choose most negative predicted MUV",
            "crowding_gate": None,
            "hyperparameter_search": False,
            "coverage_search": False,
        },
        "safety_model_diagnostics": risk_diag,
        "keep_all": base_summary,
        "policies": policy_summaries,
        "by_period": by_period,
        "by_year": by_year,
        "oracle_one_removal_upper_bound": oracle,
        "random_one_removal_baseline": random,
        "notes": [
            "Safety cutoffs use only earlier OOS safety predictions and realized positive retention values.",
            "Positive-RV opportunity-loss mass, not raw classification count, determines the protected score region.",
            "Stage3 expected MUV is not retuned; Stage7 only adds a veto-style removal safety guard.",
            "Primary policy is frozen at 90% regret coverage. 80%/95% are sensitivities and must not be selected after results.",
            "This remains one-removal-per-month. Multi-removal sequential retention is not justified unless the primary policy passes.",
        ],
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
