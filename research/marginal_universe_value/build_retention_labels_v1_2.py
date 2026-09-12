#!/usr/bin/env python3
"""MUV retention labels V1.2: add counterfactual competition-path labels.

V1.1 established point-in-time own-state handling for occasional month-end
quote lags.  V1.2 leaves all portfolio return calculations unchanged and adds
label-side diagnostics describing *how* removing an incumbent changes the next
month's OLS competition / portfolio path.

These path fields are outcomes, not predictors.  They must never be included in
X at the same decision date.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

import build_retention_labels_v1 as v1
import build_retention_labels_v1_1 as v11

VERSION = "muv_retention_labels_v1_2_20260912"
EPS = 1e-12


def monthly_metrics_with_path(
    ranked: pd.Series,
    counts: pd.Series,
    oo: pd.DataFrame,
    calendar: pd.Index,
    label_period: pd.Period,
    initial_prev_target: str | None,
) -> dict:
    rows = []
    prev = initial_prev_target

    for i in range(len(calendar) - 2):
        signal = pd.Timestamp(calendar[i])
        exec_date = pd.Timestamp(calendar[i + 1])
        if exec_date.to_period("M") != label_period:
            continue

        raw = ranked.iloc[i]
        t = v1._target(raw)

        if t == prev:
            sides = 0
        elif prev is None or t is None:
            sides = 1
        else:
            sides = 2

        gross = 0.0
        missing = False
        if t is not None:
            try:
                gross = float(oo.at[signal, t])
                if not math.isfinite(gross):
                    gross = 0.0
                    missing = True
            except Exception:
                gross = 0.0
                missing = True

        net = (1.0 + gross) * (1.0 - v1.SIDE_COST * sides) - 1.0
        rows.append(
            {
                "date": exec_date,
                "signal_date": signal,
                "raw_top1": None if raw is None or pd.isna(raw) else str(raw),
                "target": t,
                "gross": gross,
                "net": net,
                "switch": int(t != prev),
                "sides": int(sides),
                "missing": bool(missing),
                "candidate_count": int(counts.iloc[i]),
            }
        )
        prev = t

    p = pd.DataFrame(rows)
    if p.empty:
        return {
            "total_return": np.nan,
            "max_drawdown": np.nan,
            "switches": 0,
            "turnover_sides": 0,
            "mean_top1_tenure": np.nan,
            "invested_ratio": np.nan,
            "missing_quote_days": 0,
            "candidate_mean": np.nan,
            "execution_days": 0,
            "_daily_path": [],
        }

    eq = (1.0 + p["net"]).cumprod()
    dd = eq / eq.cummax() - 1.0

    raw_nonnull = p["raw_top1"].dropna().astype(str)
    groups = (raw_nonnull != raw_nonnull.shift()).cumsum()
    runs = raw_nonnull.groupby(groups).size() if len(raw_nonnull) else pd.Series(dtype=float)

    path_cols = ["date", "raw_top1", "target", "net", "switch", "sides"]
    path = p[path_cols].copy()
    path["date"] = path["date"].astype(str)

    return {
        "total_return": float(eq.iloc[-1] - 1.0),
        "max_drawdown": float(dd.min()),
        "switches": int(p["switch"].sum()),
        "turnover_sides": int(p["sides"].sum()),
        "mean_top1_tenure": float(runs.mean()) if len(runs) else np.nan,
        "invested_ratio": float(p["target"].notna().mean()),
        "missing_quote_days": int(p["missing"].sum()),
        "candidate_mean": float(p["candidate_count"].mean()),
        "execution_days": int(len(p)),
        "_daily_path": path.to_dict(orient="records"),
    }


def _same_identity(a, b) -> bool:
    if a is None and b is None:
        return True
    return str(a) == str(b)


def _episodes(mask: list[bool]) -> int:
    n = 0
    prev = False
    for x in mask:
        if x and not prev:
            n += 1
        prev = x
    return n


def path_labels(symbol: str, base_metrics: dict, cf_metrics: dict) -> dict:
    bp = {str(r["date"]): r for r in base_metrics.get("_daily_path", [])}
    cp = {str(r["date"]): r for r in cf_metrics.get("_daily_path", [])}
    dates = sorted(set(bp) & set(cp))

    raw_changed = 0
    target_changed = 0
    switch_changed = 0
    net_changed = 0
    beneficial = 0
    harmful = 0
    changed_equal_net = 0
    direct_days = 0
    direct_raw_days = 0
    direct_beneficial = 0
    direct_harmful = 0
    spillover_changed = 0
    spillover_beneficial = 0
    spillover_harmful = 0
    cf_cash_on_changed = 0
    base_cash_on_changed = 0
    replacements: set[str] = set()
    direct_mask: list[bool] = []

    for d in dates:
        b = bp[d]
        c = cp[d]
        raw_diff = not _same_identity(b.get("raw_top1"), c.get("raw_top1"))
        target_diff = not _same_identity(b.get("target"), c.get("target"))
        switch_diff = int(b.get("switch", 0)) != int(c.get("switch", 0))
        net_delta = float(b.get("net", 0.0)) - float(c.get("net", 0.0))
        net_diff = abs(net_delta) > EPS
        is_direct = _same_identity(b.get("target"), symbol)
        is_direct_raw = _same_identity(b.get("raw_top1"), symbol)

        raw_changed += int(raw_diff)
        target_changed += int(target_diff)
        switch_changed += int(switch_diff)
        net_changed += int(net_diff)
        beneficial += int(net_delta > EPS)
        harmful += int(net_delta < -EPS)
        changed_equal_net += int(target_diff and not net_diff)
        direct_days += int(is_direct)
        direct_raw_days += int(is_direct_raw)
        direct_mask.append(bool(is_direct))

        if target_diff:
            if c.get("target") is None:
                cf_cash_on_changed += 1
            else:
                replacements.add(str(c.get("target")))
            if b.get("target") is None:
                base_cash_on_changed += 1

        if is_direct:
            direct_beneficial += int(net_delta > EPS)
            direct_harmful += int(net_delta < -EPS)
        elif target_diff:
            spillover_changed += 1
            spillover_beneficial += int(net_delta > EPS)
            spillover_harmful += int(net_delta < -EPS)

    n = len(dates)
    return {
        "path_observation_days": int(n),
        "path_raw_top1_changed_days": int(raw_changed),
        "path_target_changed_days": int(target_changed),
        "path_target_changed_fraction": float(target_changed / n) if n else np.nan,
        "path_switch_flag_changed_days": int(switch_changed),
        "path_net_changed_days": int(net_changed),
        "path_changed_target_equal_net_days": int(changed_equal_net),
        "path_beneficial_days": int(beneficial),
        "path_harmful_days": int(harmful),
        "path_direct_selection_days": int(direct_days),
        "path_direct_raw_top1_days": int(direct_raw_days),
        "path_direct_selection_episodes": int(_episodes(direct_mask)),
        "path_direct_beneficial_days": int(direct_beneficial),
        "path_direct_harmful_days": int(direct_harmful),
        "path_spillover_changed_days": int(spillover_changed),
        "path_spillover_beneficial_days": int(spillover_beneficial),
        "path_spillover_harmful_days": int(spillover_harmful),
        "path_cf_cash_on_changed_days": int(cf_cash_on_changed),
        "path_base_cash_on_changed_days": int(base_cash_on_changed),
        "path_replacement_unique_count": int(len(replacements)),
    }


def make_state_rows_v1_2(
    features: pd.DataFrame,
    score: pd.DataFrame,
    rank: pd.DataFrame,
    counts: pd.Series,
    ret: pd.DataFrame,
    baseline_ranked: pd.Series,
    asof: pd.Timestamp,
    label_period: pd.Period,
    base_metrics: dict,
    counterfactual_by_symbol: dict[str, dict],
) -> list[dict]:
    rows = v11.make_state_rows_latest_available(
        features,
        score,
        rank,
        counts,
        ret,
        baseline_ranked,
        asof,
        label_period,
        base_metrics,
        counterfactual_by_symbol,
    )
    for row in rows:
        sym = str(row["symbol"])
        row["dataset_version"] = VERSION
        row.update(path_labels(sym, base_metrics, counterfactual_by_symbol[sym]))
    return rows


def main() -> None:
    v1.VERSION = VERSION
    v1.monthly_metrics = monthly_metrics_with_path
    v1.make_state_rows = make_state_rows_v1_2
    v1.main()


if __name__ == "__main__":
    main()
