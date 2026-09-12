#!/usr/bin/env python3
"""MUV Stage 6: crowding-aware one-step retention policy walk-forward.

Purpose
-------
Translate already-frozen Stage-3 OOS MUV predictions and Stage-5 point-in-time
crowding diagnostics into a conservative, executable retention policy.

This stage deliberately caps removals at ONE incumbent per month.  Remove-one
counterfactual labels are not additive, so allowing multiple simultaneous
removals without recomputing the universe would be methodologically invalid.
A successful result here can justify a later true sequential recomputation.

No model is re-fit here and no threshold is optimized on realized outcomes.
Three predeclared policies are reported:

1. pairwise_no_gate: remove the most negative predicted-MUV ETF when min MUV < 0.
2. crowding_lt_2_3: same, but only if crowding score < 2/3.  This is the primary
   policy because Stage 5 used fixed prior-history terciles before seeing Stage 6
   strategy results.
3. crowding_lt_1_3: stricter sensitivity version; only low-crowding months act.

Crowding score is the equal-weight mean of PRIOR-HISTORY percentiles for:
- number of qualified risk competitors,
- fraction of risk ETFs with positive 20d return,
- median 20d return across risk ETFs.

The natural retention cutoff is predicted MUV < 0: negative retention value
means the model expects the portfolio to benefit from excluding the ETF.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

LABELS = Path("muv-retention-labels-v1.parquet")
PRED = Path("muv-retention-stage3-predictions.csv")
REGIMES = Path("muv-retention-stage5-monthly-regimes.csv")
OUT_JSON = Path("muv-retention-stage6-report.json")
OUT_MONTHLY = Path("muv-retention-stage6-monthly-policy.csv")

EPS = 1e-12
RANDOM_SEED = 20260912
RANDOM_DRAWS = 2000

CROWDING_PCTS = [
    "regime_risk_qualified_count__pct_prior",
    "regime_risk_ret20_positive_frac__pct_prior",
    "regime_risk_ret20_median__pct_prior",
]

POLICIES = {
    "pairwise_no_gate": None,
    "crowding_lt_2_3": 2.0 / 3.0,
    "crowding_lt_1_3": 1.0 / 3.0,
}


def equity_metrics(returns: pd.Series) -> dict:
    r = pd.to_numeric(returns, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    if len(r) == 0:
        return {
            "months": 0,
            "total_return": None,
            "cagr": None,
            "monthly_equity_max_drawdown": None,
            "mean_monthly_return": None,
            "monthly_return_std": None,
        }
    wealth = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.r_[1.0, wealth])
    wealth0 = np.r_[1.0, wealth]
    dd = wealth0 / peak - 1.0
    years = len(r) / 12.0
    total = float(wealth[-1] - 1.0)
    final_wealth = float(wealth[-1])
    cagr = float(final_wealth ** (1.0 / years) - 1.0) if years > 0 and final_wealth > 0 else None
    return {
        "months": int(len(r)),
        "total_return": total,
        "cagr": cagr,
        "monthly_equity_max_drawdown": float(np.min(dd)),
        "mean_monthly_return": float(np.mean(r)),
        "monthly_return_std": float(np.std(r, ddof=1)) if len(r) > 1 else 0.0,
        "final_wealth": final_wealth,
    }


def summarize_policy(g: pd.DataFrame, policy: str) -> dict:
    ret_col = f"ret_{policy}"
    act_col = f"act_{policy}"
    improvement_col = f"improvement_{policy}"
    selected = g[g[act_col]].copy()
    em = equity_metrics(g[ret_col])
    base = equity_metrics(g["base_return"])
    em.update({
        "action_months": int(g[act_col].sum()),
        "action_rate": float(g[act_col].mean()),
        "realized_action_win_rate": float((selected[improvement_col] > EPS).mean()) if len(selected) else None,
        "realized_action_harm_rate": float((selected[improvement_col] < -EPS).mean()) if len(selected) else None,
        "mean_realized_improvement_when_acting": float(selected[improvement_col].mean()) if len(selected) else None,
        "median_realized_improvement_when_acting": float(selected[improvement_col].median()) if len(selected) else None,
        "sum_realized_improvement_when_acting": float(selected[improvement_col].sum()) if len(selected) else 0.0,
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


def apply_policy(month_rows: pd.DataFrame, crowding: float, gate: float | None) -> dict:
    # The only ranking signal is the already-OOS Stage-3 pairwise expected MUV.
    z = month_rows.dropna(subset=["muv_pairwise"]).copy()
    base = month_rows.iloc[0]
    result = {
        "acted": False,
        "selected_symbol": None,
        "selected_pred_muv": None,
        "ret": float(base.base_return),
        "switches": int(base.base_switches),
        "turnover": int(base.base_turnover_sides),
        "mdd": float(base.base_max_drawdown),
        "improvement": 0.0,
    }
    if z.empty:
        return result
    if gate is not None and (not np.isfinite(crowding) or crowding >= gate):
        return result

    cand = z.sort_values(["muv_pairwise", "symbol"]).iloc[0]
    pred = float(cand.muv_pairwise)
    if not np.isfinite(pred) or pred >= 0.0:
        return result

    result.update({
        "acted": True,
        "selected_symbol": str(cand.symbol),
        "selected_pred_muv": pred,
        "ret": float(cand.cf_return),
        "switches": int(cand.cf_switches),
        "turnover": int(cand.cf_turnover_sides),
        "mdd": float(cand.cf_max_drawdown),
        # improvement from removing = cf - keep = -retention delta
        "improvement": float(cand.cf_return - cand.base_return),
    })
    return result


def random_baseline(monthly_rows: dict[str, pd.DataFrame], action_months: list[str]) -> dict:
    rng = np.random.default_rng(RANDOM_SEED)
    months = sorted(monthly_rows)
    action_set = set(action_months)
    totals = []
    advantages = []
    base_returns = np.array([float(monthly_rows[m].iloc[0].base_return) for m in months])
    base_final = float(np.prod(1.0 + base_returns))

    for _ in range(RANDOM_DRAWS):
        rr = []
        for m in months:
            h = monthly_rows[m]
            if m not in action_set:
                rr.append(float(h.iloc[0].base_return))
                continue
            j = int(rng.integers(0, len(h)))
            rr.append(float(h.iloc[j].cf_return))
        fw = float(np.prod(1.0 + np.asarray(rr, dtype=float)))
        totals.append(fw - 1.0)
        advantages.append(fw / base_final - 1.0 if base_final != 0 else np.nan)

    a = np.asarray(advantages, dtype=float)
    t = np.asarray(totals, dtype=float)
    return {
        "draws": RANDOM_DRAWS,
        "seed": RANDOM_SEED,
        "action_months_matched_to_primary_policy": int(len(action_months)),
        "total_return_mean": float(np.mean(t)),
        "total_return_p05": float(np.quantile(t, 0.05)),
        "total_return_p50": float(np.quantile(t, 0.50)),
        "total_return_p95": float(np.quantile(t, 0.95)),
        "terminal_wealth_advantage_vs_keep_all_mean": float(np.mean(a)),
        "terminal_wealth_advantage_vs_keep_all_p05": float(np.quantile(a, 0.05)),
        "terminal_wealth_advantage_vs_keep_all_p50": float(np.quantile(a, 0.50)),
        "terminal_wealth_advantage_vs_keep_all_p95": float(np.quantile(a, 0.95)),
        "prob_random_beats_keep_all": float(np.mean(a > 0.0)),
    }


def main() -> None:
    lab = pd.read_parquet(LABELS)
    pred = pd.read_csv(PRED)
    reg = pd.read_csv(REGIMES)

    for d in (lab, pred, reg):
        d["label_month"] = d.label_month.astype(str)
    lab["symbol"] = lab.symbol.astype(str).str.replace(r"\.0$", "", regex=True)
    pred["symbol"] = pred.symbol.astype(str).str.replace(r"\.0$", "", regex=True)

    needed_lab = [
        "label_month", "symbol", "base_return", "base_max_drawdown", "base_switches",
        "base_turnover_sides", "cf_return", "cf_max_drawdown", "cf_switches",
        "cf_turnover_sides", "delta_return",
    ]
    missing_lab = set(needed_lab) - set(lab.columns)
    if missing_lab:
        raise RuntimeError(f"Missing label columns: {sorted(missing_lab)}")
    if "muv_pairwise" not in pred.columns:
        raise RuntimeError("Stage3 prediction column muv_pairwise is missing")
    missing_reg = set(CROWDING_PCTS) - set(reg.columns)
    if missing_reg:
        raise RuntimeError(f"Missing Stage5 crowding percentile columns: {sorted(missing_reg)}")

    p = pred[["label_month", "symbol", "muv_pairwise", "p_active", "p_positive_pairwise"]].copy()
    d = p.merge(lab[needed_lab], on=["label_month", "symbol"], how="left", validate="one_to_one")
    if d["base_return"].isna().any():
        raise RuntimeError("Prediction/label merge produced missing outcomes")

    reg2 = reg[["label_month"] + CROWDING_PCTS].copy()
    reg2["crowding_score"] = reg2[CROWDING_PCTS].mean(axis=1, skipna=False)
    d = d.merge(reg2, on="label_month", how="left", validate="many_to_one")

    rows = []
    monthly_rows: dict[str, pd.DataFrame] = {}
    for m, h in d.groupby("label_month", sort=True):
        h = h.sort_values("symbol").copy()
        monthly_rows[str(m)] = h
        crowd = float(h.crowding_score.iloc[0]) if pd.notna(h.crowding_score.iloc[0]) else np.nan
        base = h.iloc[0]
        out = {
            "label_month": str(m),
            "crowding_score": crowd,
            "base_return": float(base.base_return),
            "base_switches": int(base.base_switches),
            "base_turnover_sides": int(base.base_turnover_sides),
            "base_max_drawdown": float(base.base_max_drawdown),
        }
        for name, gate in POLICIES.items():
            r = apply_policy(h, crowd, gate)
            out[f"act_{name}"] = bool(r["acted"])
            out[f"symbol_{name}"] = r["selected_symbol"]
            out[f"pred_muv_{name}"] = r["selected_pred_muv"]
            out[f"ret_{name}"] = r["ret"]
            out[f"switches_{name}"] = r["switches"]
            out[f"turnover_{name}"] = r["turnover"]
            out[f"mdd_{name}"] = r["mdd"]
            out[f"improvement_{name}"] = r["improvement"]
        rows.append(out)

    monthly = pd.DataFrame(rows).sort_values("label_month").reset_index(drop=True)

    # One-removal oracle upper bound: future-aware, diagnostic only.
    oracle_ret = []
    oracle_action = []
    for m in monthly.label_month:
        h = monthly_rows[m]
        cand = h.sort_values(["delta_return", "symbol"]).iloc[0]
        if float(cand.delta_return) < -EPS:
            oracle_ret.append(float(cand.cf_return))
            oracle_action.append(True)
        else:
            oracle_ret.append(float(cand.base_return))
            oracle_action.append(False)
    monthly["ret_oracle_one"] = oracle_ret
    monthly["act_oracle_one"] = oracle_action

    monthly.to_csv(OUT_MONTHLY, index=False)

    base_summary = equity_metrics(monthly.base_return)
    base_summary.update({
        "total_switches": int(monthly.base_switches.sum()),
        "total_turnover_sides": int(monthly.base_turnover_sides.sum()),
        "mean_within_month_max_drawdown": float(monthly.base_max_drawdown.mean()),
    })

    policy_summaries = {name: summarize_policy(monthly, name) for name in POLICIES}

    by_period = {}
    periods = {
        "2023-24": monthly[monthly.label_month.str[:4].astype(int) <= 2024],
        "2025-26": monthly[monthly.label_month.str[:4].astype(int) >= 2025],
    }
    for per, g in periods.items():
        by_period[per] = {
            "keep_all": equity_metrics(g.base_return),
            **{name: summarize_policy(g, name) for name in POLICIES},
        }

    by_year = {}
    for y, g in monthly.groupby(monthly.label_month.str[:4]):
        by_year[str(y)] = {
            "keep_all": equity_metrics(g.base_return),
            **{name: summarize_policy(g, name) for name in POLICIES},
        }

    oracle = equity_metrics(monthly.ret_oracle_one)
    oracle["action_months"] = int(monthly.act_oracle_one.sum())
    oracle["terminal_wealth_advantage_vs_keep_all"] = float(
        oracle["final_wealth"] / base_summary["final_wealth"] - 1.0
    )

    primary_actions = monthly.loc[monthly.act_crowding_lt_2_3, "label_month"].tolist()
    random = random_baseline(monthly_rows, primary_actions)

    # Action-symbol diagnostics for the primary policy.
    acts = monthly[monthly.act_crowding_lt_2_3].copy()
    selected_counts = (
        acts.symbol_crowding_lt_2_3.value_counts().to_dict() if len(acts) else {}
    )

    report = {
        "design": {
            "dataset_version": str(lab.dataset_version.iloc[0]) if "dataset_version" in lab.columns else None,
            "test_months": [str(monthly.label_month.min()), str(monthly.label_month.max())],
            "oos_source": "Stage3 monthly expanding predictions; no refit in Stage6",
            "max_removals_per_month": 1,
            "decision_rule": "choose minimum OOS muv_pairwise; remove only if predicted MUV < 0",
            "primary_crowding_gate": "equal-weight prior-percentile crowding score < 2/3",
            "crowding_features": CROWDING_PCTS,
            "crowding_weights": "equal; fixed, not optimized",
            "threshold_search": False,
            "policy_search": False,
            "sensitivity_policies": list(POLICIES),
            "important_limitation": "This is one-step sequential retention. Multiple removals require recomputing universe-dependent features after each removal.",
        },
        "keep_all": base_summary,
        "policies": policy_summaries,
        "by_period": by_period,
        "by_year": by_year,
        "oracle_one_removal_upper_bound": oracle,
        "random_one_removal_baseline": random,
        "primary_policy_selected_symbol_counts": selected_counts,
        "notes": [
            "All realized policy outcomes use the exact remove-one counterfactual for the single selected ETF; no additive approximation is used.",
            "The oracle is future-aware and is reported only as an upper bound on what one-removal-per-month could have achieved.",
            "Random baseline matches the primary policy's action months but chooses a random incumbent, isolating whether model selection adds value beyond merely shrinking the universe.",
            "Monthly-equity MDD is computed from chained monthly returns; within-month MDD is reported separately as a mean, because exact daily chaining for changing universes is not reconstructed in Stage6.",
            "2023-2026 history has already informed prior research stages, so this is chronological OOS relative to each model fit, not a pristine untouched final test set.",
        ],
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
