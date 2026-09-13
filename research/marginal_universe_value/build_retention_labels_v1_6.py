#!/usr/bin/env python3
"""MUV retention V1.6: explicit path-displacement label diagnostics.

Adds label-side diagnostics describing which counterfactual target replaces an
incumbent on days when the incumbent is directly selected by the baseline path.
Future replacement identity is outcome-only and must never enter X.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

import build_retention_labels_v1 as v1
import build_retention_labels_v1_2 as v12
import build_retention_labels_v1_5 as v15

VERSION = "muv_retention_labels_v1_6_displacement_20260913"
CASH = "__CASH__"


def _same(a, b):
    if a is None and b is None:
        return True
    return str(a) == str(b)


def displacement_labels(symbol: str, base_metrics: dict, cf_metrics: dict) -> dict:
    bp = {str(r["date"]): r for r in base_metrics.get("_daily_path", [])}
    cp = {str(r["date"]): r for r in cf_metrics.get("_daily_path", [])}
    dates = sorted(set(bp) & set(cp))

    repl = []
    direct_deltas = []
    spill_deltas = []

    for d in dates:
        b = bp[d]
        c = cp[d]
        btarget = b.get("target")
        ctarget = c.get("target")
        net_delta = float(b.get("net", 0.0)) - float(c.get("net", 0.0))

        is_direct = _same(btarget, symbol)
        target_changed = not _same(btarget, ctarget)

        if is_direct:
            repl.append(CASH if ctarget is None else str(ctarget))
            direct_deltas.append(net_delta)
        elif target_changed:
            spill_deltas.append(net_delta)

    counts = Counter(repl)
    if counts:
        dominant, dominant_n = counts.most_common(1)[0]
        dominance = dominant_n / len(repl)
    else:
        dominant, dominant_n, dominance = None, 0, np.nan

    noncash = [x for x in repl if x != CASH]
    return {
        "disp_direct_days": int(len(repl)),
        "disp_direct_replacement_unique_count": int(len(counts)),
        "disp_direct_dominant_replacement": dominant,
        "disp_direct_dominant_replacement_days": int(dominant_n),
        "disp_direct_dominant_share": float(dominance) if pd.notna(dominance) else np.nan,
        "disp_direct_cash_days": int(sum(x == CASH for x in repl)),
        "disp_direct_noncash_days": int(len(noncash)),
        "disp_direct_net_delta_sum": float(np.sum(direct_deltas)) if direct_deltas else 0.0,
        "disp_direct_net_delta_mean": float(np.mean(direct_deltas)) if direct_deltas else np.nan,
        "disp_spillover_net_delta_sum": float(np.sum(spill_deltas)) if spill_deltas else 0.0,
        "disp_spillover_changed_days": int(len(spill_deltas)),
    }


def make_state_rows_displacement(
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
    rows = v15.make_state_rows_local_relational(
        features, score, rank, counts, ret, baseline_ranked,
        asof, label_period, base_metrics, counterfactual_by_symbol,
    )
    for row in rows:
        sym = str(row["symbol"])
        row["dataset_version"] = VERSION
        row.update(displacement_labels(sym, base_metrics, counterfactual_by_symbol[sym]))

        dom = row.get("disp_direct_dominant_replacement")
        local = [row.get(f"local_alt{k}_symbol") for k in (1, 2, 3)]
        row["disp_dominant_matches_asof_alt1"] = bool(dom is not None and dom == local[0])
        row["disp_dominant_in_asof_top3"] = bool(dom is not None and dom in set(x for x in local if x is not None))
    return rows


def main() -> None:
    v1.VERSION = VERSION
    v1.monthly_metrics = v12.monthly_metrics_with_path
    v1.make_state_rows = make_state_rows_displacement
    v1.main()


if __name__ == "__main__":
    main()
