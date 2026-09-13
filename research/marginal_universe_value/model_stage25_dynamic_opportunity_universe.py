#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars

FEATURES = ["score", "r2", "score_delta", "current_resid", "efficiency20", "dist_high20"]
CASH = "511220"
TEST_START = "2023-01"
POSITIVE_FRACTION = 0.20
SECONDARY_FRACTION = 0.40
OUT = Path("muv-stage25-dou-report.json")
OUTM = Path("muv-stage25-dou-months.csv")


def add_fwd20(frame: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for _, g0 in frame.groupby("symbol", sort=False):
        g = g0.sort_values("date").copy()
        c = g["close"].astype(float).to_numpy()
        v = np.full(len(g), np.nan)
        if len(g) > 20:
            v[:-20] = c[20:] / c[:-20] - 1.0
        g["fwd20_close"] = v
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


def make_model() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(C=1, class_weight="balanced", max_iter=2000),
            ),
        ]
    )


def label_month(g: pd.DataFrame) -> pd.DataFrame:
    x = g.copy()
    n = len(x)
    k = max(1, int(math.ceil(POSITIVE_FRACTION * n)))
    order = x["fwd20_close"].rank(method="first", ascending=False)
    x["y"] = (order <= k).astype(int)
    return x


def recall_at_fraction(g: pd.DataFrame, rank_col: str, frac: float) -> float:
    n = len(g)
    k = max(1, int(math.ceil(frac * n)))
    selected = g.nsmallest(k, rank_col)
    positives = int(g["y"].sum())
    if positives <= 0:
        return float("nan")
    return float(selected["y"].sum() / positives)


def monthly_metrics(g: pd.DataFrame, score_col: str, rank_col: str) -> dict:
    y = g["y"].astype(int).to_numpy()
    s = pd.to_numeric(g[score_col], errors="coerce").astype(float).to_numpy()
    ap = float(average_precision_score(y, s)) if len(np.unique(y)) > 1 else float("nan")
    sp = float(pd.Series(s).corr(pd.Series(g["fwd20_close"].to_numpy()), method="spearman"))
    return {
        "ap": ap,
        "recall_at_20pct": recall_at_fraction(g, rank_col, POSITIVE_FRACTION),
        "recall_at_40pct": recall_at_fraction(g, rank_col, SECONDARY_FRACTION),
        "spearman_fwd20": sp,
    }


def summarize(months: pd.DataFrame, prefix: str) -> dict:
    if months.empty:
        return {"n_months": 0}
    cols = [
        f"{prefix}_ap",
        f"{prefix}_recall_at_20pct",
        f"{prefix}_recall_at_40pct",
        f"{prefix}_spearman_fwd20",
    ]
    return {
        "n_months": int(len(months)),
        "ap": float(months[cols[0]].mean()),
        "recall_at_20pct": float(months[cols[1]].mean()),
        "recall_at_40pct": float(months[cols[2]].mean()),
        "spearman_fwd20": float(months[cols[3]].mean()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    args = ap.parse_args()
    if not args.database_url:
        raise RuntimeError("ETF_DAILY_BARS_DATABASE_URL is required")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    f = add_fwd20(build_features(load_daily_bars(engine)))
    f["symbol"] = f["symbol"].astype(str)
    f["date"] = pd.to_datetime(f["date"])
    f["month"] = f["date"].dt.to_period("M").astype(str)

    month_ends = f[["date", "month"]].drop_duplicates().groupby("month")["date"].max()
    month_end_dates = set(pd.to_datetime(month_ends))

    data = f[
        f["date"].isin(month_end_dates)
        & f["trend_eligible"].fillna(False)
        & (f["symbol"] != CASH)
        & f["fwd20_close"].notna()
    ][["date", "month", "symbol", "fwd20_close", *FEATURES]].copy()

    labeled = []
    for _, g in data.groupby("month", sort=True):
        if len(g) < 5:
            continue
        labeled.append(label_month(g))
    data = pd.concat(labeled, ignore_index=True)

    monthly_rows = []
    for month in sorted(m for m in data["month"].unique() if m >= TEST_START):
        train = data[data["month"] < month].copy()
        test = data[data["month"] == month].copy()
        if train["month"].nunique() < 12 or train["y"].nunique() < 2 or test["y"].nunique() < 2:
            continue

        model = make_model()
        model.fit(train[FEATURES], train["y"])
        test["state_p"] = model.predict_proba(test[FEATURES])[:, 1]
        test["score_rank"] = test["score"].rank(method="first", ascending=False)
        test["state_rank"] = test["state_p"].rank(method="first", ascending=False)

        score_m = monthly_metrics(test, "score", "score_rank")
        state_m = monthly_metrics(test, "state_p", "state_rank")
        monthly_rows.append(
            {
                "month": month,
                "era": "2023-24" if int(month[:4]) < 2025 else "2025-26",
                "candidate_count": int(len(test)),
                "positive_count": int(test["y"].sum()),
                "positive_share": float(test["y"].mean()),
                **{f"score_{k}": v for k, v in score_m.items()},
                **{f"state_{k}": v for k, v in state_m.items()},
            }
        )

    months = pd.DataFrame(monthly_rows)
    months.to_csv(OUTM, index=False)

    score_all = summarize(months, "score")
    state_all = summarize(months, "state")

    by_era = {}
    era_primary_deltas = []
    for era, g in months.groupby("era", sort=True):
        sb = summarize(g, "score")
        st = summarize(g, "state")
        delta = {
            "ap": st["ap"] - sb["ap"],
            "recall_at_20pct": st["recall_at_20pct"] - sb["recall_at_20pct"],
            "recall_at_40pct": st["recall_at_40pct"] - sb["recall_at_40pct"],
            "spearman_fwd20": st["spearman_fwd20"] - sb["spearman_fwd20"],
        }
        by_era[era] = {"score_baseline": sb, "low_dof_state": st, "delta": delta}
        era_primary_deltas.append(delta)

    overall_ap_delta = state_all["ap"] - score_all["ap"]
    overall_recall_delta = state_all["recall_at_20pct"] - score_all["recall_at_20pct"]
    no_era_double_deterioration = all(
        not (d["ap"] < 0 and d["recall_at_20pct"] < 0) for d in era_primary_deltas
    )
    supported = bool(
        overall_ap_delta >= 0
        and overall_recall_delta >= 0
        and no_era_double_deterioration
        and (overall_ap_delta > 0 or overall_recall_delta > 0)
    )

    report = {
        "version": "muv_stage25_dynamic_opportunity_universe_identifiability_20260913",
        "design": {
            "candidate_universe": "full-market non-cash point-in-time trend-eligible ETFs",
            "label": "top 20% of cross-sectional next-20-trading-day close return",
            "positive_fraction": POSITIVE_FRACTION,
            "features": FEATURES,
            "split": "strict monthly expanding OOS",
            "feature_search": False,
            "hyperparameter_search": False,
            "topk_search": False,
            "threshold_search": False,
            "policy_backtest": False,
        },
        "coverage": {
            "oos_months": int(len(months)),
            "candidate_count_mean": float(months["candidate_count"].mean()),
            "positive_count_mean": float(months["positive_count"].mean()),
            "positive_share_mean": float(months["positive_share"].mean()),
        },
        "overall": {
            "score_baseline": score_all,
            "low_dof_state": state_all,
            "delta": {
                "ap": overall_ap_delta,
                "recall_at_20pct": overall_recall_delta,
                "recall_at_40pct": state_all["recall_at_40pct"] - score_all["recall_at_40pct"],
                "spearman_fwd20": state_all["spearman_fwd20"] - score_all["spearman_fwd20"],
            },
        },
        "by_era": by_era,
        "predeclared_interpretation": {
            "dynamic_opportunity_state_supported": supported,
            "rule": "State AP and Recall@20% must not deteriorate overall; neither era may deteriorate on both primary metrics; at least one overall primary metric must improve.",
        },
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
