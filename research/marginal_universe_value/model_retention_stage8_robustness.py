#!/usr/bin/env python3
"""MUV Stage 8: robustness diagnostics for the frozen Stage-7 primary policy.

This stage DOES NOT alter the model, coverage target, features, or action rule.
It only asks whether the observed Stage-7 benefit is concentrated in one month,
one symbol, or a lucky random deletion path.

These diagnostics are designed after Stage-7 results and therefore are not a
new untouched validation set. They are stress/concentration diagnostics only.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

LABELS = Path("muv-retention-labels-v1.parquet")
MONTHLY = Path("muv-retention-stage7-monthly-policy.csv")
OUT = Path("muv-retention-stage8-report.json")

RANDOM_SEED = 20260912
RANDOM_DRAWS = 10000
EPS = 1e-12


def wealth(ret: pd.Series | np.ndarray) -> float:
    r = np.asarray(ret, dtype=float)
    return float(np.prod(1.0 + r))


def rel_vs_base(ret: pd.Series | np.ndarray, base_ret: pd.Series | np.ndarray) -> float:
    b = wealth(base_ret)
    p = wealth(ret)
    return float(p / b - 1.0)


def main() -> None:
    m = pd.read_csv(MONTHLY)
    lab = pd.read_parquet(LABELS)
    m["label_month"] = m.label_month.astype(str)
    lab["label_month"] = lab.label_month.astype(str)
    lab["symbol"] = lab.symbol.astype(str).str.replace(r"\.0$", "", regex=True)

    act = m[m.act_primary_regime90].copy()
    primary_rel = rel_vs_base(m.ret_primary_regime90, m.base_return)
    primary_fw = wealth(m.ret_primary_regime90)
    base_fw = wealth(m.base_return)

    # 1) Adversarially remove the largest realized beneficial actions from the
    # observed policy path by reverting those months to keep-all.
    winners = act[act.improvement_primary_regime90 > EPS].sort_values(
        "improvement_primary_regime90", ascending=False
    )
    winner_ablation = []
    for k in [1, 2, 3, 5]:
        ret = m.ret_primary_regime90.copy()
        months = winners.head(k).label_month.tolist()
        ret.loc[m.label_month.isin(months)] = m.loc[m.label_month.isin(months), "base_return"]
        winner_ablation.append({
            "reverted_top_wins": int(min(k, len(winners))),
            "months_reverted": months,
            "final_wealth": wealth(ret),
            "relative_terminal_wealth_vs_keep_all": rel_vs_base(ret, m.base_return),
        })

    # 2) Remove dependence on any one selected symbol by reverting every action
    # involving that symbol to keep-all.
    symbol_ablation = []
    selected_symbols = sorted(
        act.symbol_primary_regime90.dropna().astype(str).str.replace(r"\.0$", "", regex=True).unique()
    )
    for sym in selected_symbols:
        ret = m.ret_primary_regime90.copy()
        chosen = m.symbol_primary_regime90.astype(str).str.replace(r"\.0$", "", regex=True).eq(sym)
        ret.loc[chosen] = m.loc[chosen, "base_return"]
        symbol_ablation.append({
            "symbol": sym,
            "actions_reverted": int((chosen & m.act_primary_regime90).sum()),
            "final_wealth": wealth(ret),
            "relative_terminal_wealth_vs_keep_all": rel_vs_base(ret, m.base_return),
        })
    symbol_ablation.sort(key=lambda x: x["relative_terminal_wealth_vs_keep_all"])

    # 3) Larger matched random-removal baseline. Same action months as primary,
    # but random incumbent is removed. This isolates selection skill from the
    # generic effect of shrinking the universe.
    action_months = set(act.label_month.tolist())
    months = m.label_month.tolist()
    by_month = {mo: h.reset_index(drop=True) for mo, h in lab.groupby("label_month") if mo in set(months)}
    rng = np.random.default_rng(RANDOM_SEED)
    rand_rel = np.empty(RANDOM_DRAWS, dtype=float)
    rand_fw = np.empty(RANDOM_DRAWS, dtype=float)
    for draw in range(RANDOM_DRAWS):
        rr = []
        for mo in months:
            h = by_month[mo]
            if mo in action_months:
                j = int(rng.integers(0, len(h)))
                rr.append(float(h.iloc[j].cf_return))
            else:
                rr.append(float(h.iloc[0].base_return))
        fw = wealth(rr)
        rand_fw[draw] = fw
        rand_rel[draw] = fw / base_fw - 1.0

    random_diag = {
        "draws": RANDOM_DRAWS,
        "action_months": int(len(action_months)),
        "relative_advantage_mean": float(rand_rel.mean()),
        "relative_advantage_median": float(np.median(rand_rel)),
        "relative_advantage_p05": float(np.quantile(rand_rel, 0.05)),
        "relative_advantage_p95": float(np.quantile(rand_rel, 0.95)),
        "relative_advantage_p99": float(np.quantile(rand_rel, 0.99)),
        "prob_random_beats_keep_all": float(np.mean(rand_rel > 0)),
        "prob_random_matches_or_beats_primary": float(np.mean(rand_rel >= primary_rel)),
        "primary_percentile_among_random": float(np.mean(rand_rel <= primary_rel)),
    }

    # 4) Performance concentration among the nonzero actions.
    nonzero = act[act.improvement_primary_regime90.abs() > EPS].copy()
    pos = nonzero[nonzero.improvement_primary_regime90 > EPS].sort_values(
        "improvement_primary_regime90", ascending=False
    )
    pos_sum = float(pos.improvement_primary_regime90.sum())
    concentration = {
        "actions": int(len(act)),
        "nonzero_actions": int(len(nonzero)),
        "positive_actions": int((nonzero.improvement_primary_regime90 > EPS).sum()),
        "harmful_actions": int((nonzero.improvement_primary_regime90 < -EPS).sum()),
        "zero_effect_actions": int(len(act) - len(nonzero)),
        "positive_improvement_sum": pos_sum,
        "harm_sum": float(nonzero.loc[nonzero.improvement_primary_regime90 < -EPS, "improvement_primary_regime90"].sum()),
        "top1_positive_share": float(pos.head(1).improvement_primary_regime90.sum() / pos_sum) if pos_sum > 0 else None,
        "top2_positive_share": float(pos.head(2).improvement_primary_regime90.sum() / pos_sum) if pos_sum > 0 else None,
        "top3_positive_share": float(pos.head(3).improvement_primary_regime90.sum() / pos_sum) if pos_sum > 0 else None,
    }

    # 5) Fixed calendar slices; no selection.
    periods = {}
    for name, mask in {
        "2023-24": m.label_month.str[:4].astype(int).le(2024),
        "2025-26": m.label_month.str[:4].astype(int).ge(2025),
    }.items():
        g = m[mask]
        periods[name] = {
            "months": int(len(g)),
            "relative_terminal_wealth_vs_keep_all": rel_vs_base(g.ret_primary_regime90, g.base_return),
            "actions": int(g.act_primary_regime90.sum()),
        }

    report = {
        "design": {
            "policy": "frozen Stage7 primary_regime90; no refit or policy changes",
            "random_draws": RANDOM_DRAWS,
            "random_seed": RANDOM_SEED,
            "diagnostic_only": True,
            "warning": "Stage8 is designed after Stage7 results and is not an untouched validation set.",
        },
        "baseline": {"final_wealth": base_fw},
        "primary": {
            "final_wealth": primary_fw,
            "relative_terminal_wealth_vs_keep_all": primary_rel,
            "actions": int(len(act)),
        },
        "adversarial_top_win_ablation": winner_ablation,
        "leave_one_selected_symbol_out": symbol_ablation,
        "random_matched_action_months": random_diag,
        "action_concentration": concentration,
        "fixed_periods": periods,
        "notes": [
            "Winner ablation deliberately removes realized beneficial actions; it is a stress test, not a tradable rule.",
            "Symbol ablation reverts all primary actions involving one selected symbol and checks whether the policy remains positive versus keep-all.",
            "Random controls use the exact same action months as Stage7 primary; only the removed incumbent is randomized.",
            "No Stage8 diagnostic is allowed to change the frozen Stage7 policy.",
        ],
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
