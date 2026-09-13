#!/usr/bin/env python3
"""Build Stage19 candidate-pair reachability rows from frozen V1.6 labels.

The realized dominant replacement is label-side only. Candidate predictors use
only score/rank history available through the decision as-of close.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

import build_retention_labels_v1 as v1

LABELS = Path("muv-retention-labels-v1.parquet")
OUT = Path("muv-retention-stage19-pairs.parquet")
CASH = "__CASH__"
LOOKBACK_DAYS = 20
RISK_SYMBOLS = sorted(v1.FIXED15 - {v1.CASH_SIGNAL})


def _finite(x):
    try:
        z = float(x)
        return z if math.isfinite(z) else np.nan
    except Exception:
        return np.nan


def _slope(values: np.ndarray) -> float:
    mask = np.isfinite(values)
    if mask.sum() < 5:
        return np.nan
    x = np.arange(len(values), dtype=float)[mask]
    y = values[mask]
    if len(np.unique(x)) < 2:
        return np.nan
    return float(np.polyfit(x, y, 1)[0])


def _crossings(values: np.ndarray) -> float:
    z = values[np.isfinite(values)]
    if len(z) < 2:
        return np.nan
    s = np.sign(z)
    s = s[s != 0]
    if len(s) < 2:
        return 0.0
    return float(np.sum(s[1:] != s[:-1]))


def pair_features(score: pd.DataFrame, rank: pd.DataFrame, asof: pd.Timestamp, incumbent: str, candidate: str) -> dict:
    hist = score.index[score.index <= asof]
    win = hist[-LOOKBACK_DAYS:]
    si = pd.to_numeric(score.loc[win, incumbent], errors="coerce") if incumbent in score.columns else pd.Series(index=win, dtype=float)
    sj = pd.to_numeric(score.loc[win, candidate], errors="coerce") if candidate in score.columns else pd.Series(index=win, dtype=float)
    gap = (sj - si).to_numpy(dtype=float)
    both = np.isfinite(si.to_numpy(dtype=float)) & np.isfinite(sj.to_numpy(dtype=float))

    ri = pd.to_numeric(rank.loc[win, incumbent], errors="coerce") if incumbent in rank.columns else pd.Series(index=win, dtype=float)
    rj = pd.to_numeric(rank.loc[win, candidate], errors="coerce") if candidate in rank.columns else pd.Series(index=win, dtype=float)

    current_i = _finite(score.at[asof, incumbent]) if asof in score.index and incumbent in score.columns else np.nan
    current_j = _finite(score.at[asof, candidate]) if asof in score.index and candidate in score.columns else np.nan
    valid_gap = gap[np.isfinite(gap)]

    return {
        "x_pair_current_gap_j_minus_i": current_j - current_i if math.isfinite(current_i) and math.isfinite(current_j) else np.nan,
        "x_pair_i_qualified_now": float(math.isfinite(current_i)),
        "x_pair_j_qualified_now": float(math.isfinite(current_j)),
        "x_pair_i_qualified_frac20": float(np.isfinite(si.to_numpy(dtype=float)).mean()) if len(win) else np.nan,
        "x_pair_j_qualified_frac20": float(np.isfinite(sj.to_numpy(dtype=float)).mean()) if len(win) else np.nan,
        "x_pair_both_qualified_frac20": float(both.mean()) if len(win) else np.nan,
        "x_pair_gap_mean20": float(np.mean(valid_gap)) if len(valid_gap) else np.nan,
        "x_pair_gap_std20": float(np.std(valid_gap, ddof=0)) if len(valid_gap) else np.nan,
        "x_pair_gap_slope20": _slope(gap),
        "x_pair_gap_crossings20": _crossings(gap),
        "x_pair_j_beats_i_frac20": float(np.mean(gap[both] > 0)) if both.any() else np.nan,
        "x_pair_both_top3_frac20": float(((ri <= 3) & (rj <= 3)).fillna(False).mean()) if len(win) else np.nan,
        "x_pair_j_top1_frac20": float((rj == 1).fillna(False).mean()) if len(win) else np.nan,
        "x_pair_j_top3_frac20": float((rj <= 3).fillna(False).mean()) if len(win) else np.nan,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(LABELS))
    ap.add_argument("--output", default=str(OUT))
    args = ap.parse_args()

    labels = pd.read_parquet(args.labels)
    labels["asof_date"] = pd.to_datetime(labels["asof_date"])
    labels["label_month"] = labels["label_month"].astype(str)
    active = labels[pd.to_numeric(labels["disp_direct_days"], errors="coerce").fillna(0) > 0].copy()

    engine = create_engine(v1._db_url())
    bars = v1.load_fixed15_bars(engine)
    features = v1.build_features(bars)
    _, score, rank, _, _, _, _ = v1.prepare_wides(bars, features)

    rows = []
    event_id = 0
    for _, r in active.iterrows():
        incumbent = str(r["symbol"])
        dominant = r.get("disp_direct_dominant_replacement")
        if pd.isna(dominant):
            continue
        dominant = str(dominant)
        asof = pd.Timestamp(r["asof_date"])
        event_id += 1
        is_cash_event = dominant == CASH

        current_scores = score.loc[asof].drop(index=incumbent, errors="ignore") if asof in score.index else pd.Series(dtype=float)
        finite_static = current_scores.dropna().sort_values(ascending=False)
        static_rank_map = {str(sym): k + 1 for k, sym in enumerate(finite_static.index)}

        for candidate in RISK_SYMBOLS:
            if candidate == incumbent:
                continue
            out = {
                "event_id": event_id,
                "label_month": str(r["label_month"]),
                "asof_date": asof,
                "incumbent": incumbent,
                "candidate": candidate,
                "dominant_replacement": dominant,
                "is_cash_event": bool(is_cash_event),
                "y_is_dominant_replacement": int((not is_cash_event) and candidate == dominant),
                "static_score_rank": float(static_rank_map[candidate]) if candidate in static_rank_map else np.nan,
                "delta_return": _finite(r.get("delta_return")),
                "disp_direct_dominant_share": _finite(r.get("disp_direct_dominant_share")),
            }
            out.update(pair_features(score, rank, asof, incumbent, candidate))
            rows.append(out)

    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("Stage19 pair builder produced no rows")
    out.to_parquet(args.output, index=False)
    print({"rows": len(out), "events": int(out.event_id.nunique()), "cash_events": int(out.loc[out.is_cash_event, "event_id"].nunique())})


if __name__ == "__main__":
    main()
