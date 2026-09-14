#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage5_history_transfer as s5
import optimal_universe_reverse_engineering.oure_stage6c_fullmarket_2022_2024_k_frontier as s6c
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

CASH = "511220"
K = 30
LOOKBACK = 126
FUTURE = 126
SHORTLIST_N = 140
GREEDY_SEEDS = 6
LOCAL_N = 220
SHORT_RANDOM_N = 200
FULL_RANDOM_N = 150
JACCARD_MAX = 0.90
SEED = 20260914
TOP_N = 50

FEATURES = [
    "past126_log_growth",
    "past126_max_drawdown",
    "invested_ratio",
    "coverage_share",
    "mean_eligible_count",
    "mean_competitors_when_covered",
    "coverage_efficiency",
    "leader_switch_rate",
    "mean_top1_tenure",
    "median_top1_tenure",
    "short_run_le2_share",
    "top1_top2_gap_median",
    "active_leader_count",
    "leader_hhi",
    "effective_leader_count",
    "mean_pair_trend_jaccard",
    "max_pair_trend_jaccard",
    "productive_switch_share",
    "switch_counterfactual_gain_mean",
]


def keyify(xs) -> tuple[str, ...]:
    return tuple(sorted(set(str(x) for x in xs if str(x) != CASH)))


def spearman(x, y) -> float:
    a = pd.Series(np.asarray(x, dtype=float))
    b = pd.Series(np.asarray(y, dtype=float))
    m = a.notna() & b.notna() & np.isfinite(a) & np.isfinite(b)
    if int(m.sum()) < 3:
        return np.nan
    return float(a[m].rank(method="average").corr(b[m].rank(method="average")))


def rank_pct(vals: pd.Series) -> pd.Series:
    r = vals.rank(method="average", ascending=True)
    n = len(r)
    if n <= 1:
        return pd.Series(np.ones(n), index=vals.index)
    return (r - 1.0) / (n - 1.0)


def jaccard(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    sa, sb = set(a), set(b)
    u = len(sa | sb)
    return float(len(sa & sb) / u) if u else 1.0


def greedy_to_k(ev: s6c.Eval, seed: str, shortlist: list[str]) -> tuple[str, ...]:
    cur = {seed}
    while len(cur) < K:
        best_y = None
        best_v = -np.inf
        for y in shortlist:
            if y in cur:
                continue
            v = ev.quick_add_log(cur, y)
            if v > best_v + 1e-12 or (abs(v - best_v) <= 1e-12 and (best_y is None or y < best_y)):
                best_v, best_y = v, y
        if best_y is None:
            break
        cur.add(best_y)
    return keyify(cur)


def mutate(base: tuple[str, ...], source: list[str], nswap: int, rng: np.random.Generator) -> tuple[str, ...]:
    cur = set(base)
    outside = [x for x in source if x not in cur]
    nswap = min(nswap, len(cur), len(outside))
    if nswap <= 0:
        return keyify(cur)
    outs = rng.choice(sorted(cur), size=nswap, replace=False).tolist()
    ins = rng.choice(outside, size=nswap, replace=False).tolist()
    for x in outs:
        cur.remove(str(x))
    for x in ins:
        cur.add(str(x))
    return keyify(cur)


def build_library(ev: s6c.Eval, pool: list[str], rng: np.random.Generator) -> tuple[list[tuple[str, ...]], pd.DataFrame]:
    singles = []
    for sym in pool:
        singles.append((sym, ev.evaluate({sym})["log_growth"]))
    single = pd.DataFrame(singles, columns=["symbol", "past_singleton_log"]).sort_values(
        ["past_singleton_log", "symbol"], ascending=[False, True]
    )
    shortlist = single.head(min(SHORTLIST_N, len(single)))["symbol"].astype(str).tolist()
    if len(shortlist) < K:
        raise RuntimeError(f"shortlist smaller than K: {len(shortlist)}")

    lib: set[tuple[str, ...]] = set()
    greedy = []
    for seed in shortlist[:min(GREEDY_SEEDS, len(shortlist))]:
        u = greedy_to_k(ev, seed, shortlist)
        if len(u) == K:
            greedy.append(u); lib.add(u)
    if not greedy:
        raise RuntimeError("no K30 greedy seeds")
    greedy = sorted(greedy, key=lambda u: (-ev.evaluate(u)["log_growth"], u))

    # Local hard controls around the strongest past-only K30s.
    for _ in range(LOCAL_N):
        base = greedy[int(rng.integers(0, len(greedy)))]
        nswap = int(rng.integers(1, 6))
        u = mutate(base, shortlist, nswap, rng)
        if len(u) == K:
            lib.add(u)

    # Plausible same-K controls from the past singleton shortlist.
    for _ in range(SHORT_RANDOM_N * 8):
        u = keyify(rng.choice(shortlist, size=K, replace=False).tolist())
        lib.add(u)
        if len(lib) >= len(greedy) + LOCAL_N + SHORT_RANDOM_N:
            break

    # Broader same-K controls from the full point-in-time pool.
    target = len(lib) + FULL_RANDOM_N
    for _ in range(FULL_RANDOM_N * 12):
        u = keyify(rng.choice(pool, size=K, replace=False).tolist())
        lib.add(u)
        if len(lib) >= target:
            break

    # Near-duplicate de-dup using only past ranking for order.
    ordered = sorted(lib, key=lambda u: (-ev.evaluate(u)["log_growth"], u))
    kept: list[tuple[str, ...]] = []
    for u in ordered:
        if all(jaccard(u, v) <= JACCARD_MAX for v in kept):
            kept.append(u)
    if len(kept) < 120:
        # Preserve analyzable library size without changing threshold: add full-pool random sets that pass the same gate.
        tries = 0
        while len(kept) < 180 and tries < 10000:
            tries += 1
            u = keyify(rng.choice(pool, size=K, replace=False).tolist())
            if all(jaccard(u, v) <= JACCARD_MAX for v in kept):
                kept.append(u)
    return kept, single


def top_gap_median(ev: s6c.Eval, members: tuple[str, ...]) -> float:
    ids = [ev.idx[s] for s in members if s in ev.idx]
    if len(ids) < 2:
        return np.nan
    sm = ev.score[:, ids]
    vals = []
    for row in sm:
        rr = row[np.isfinite(row)]
        if len(rr) >= 2:
            p = np.partition(rr, -2)
            vals.append(float(p[-1] - p[-2]))
    return float(np.median(vals)) if vals else np.nan


def feature_row(ev: s6c.Eval, u: tuple[str, ...]) -> dict:
    d = ev.diagnostics(u)
    return {
        "past126_log_growth": float(d.get("log_growth", np.nan)),
        "past126_max_drawdown": float(d.get("max_drawdown", np.nan)),
        "invested_ratio": float(d.get("invested_ratio", np.nan)),
        "coverage_share": float(d.get("coverage_share", np.nan)),
        "mean_eligible_count": float(d.get("mean_eligible_count", np.nan)),
        "mean_competitors_when_covered": float(d.get("mean_competitors_when_covered", np.nan)),
        "coverage_efficiency": float(d.get("coverage_efficiency", np.nan)),
        "leader_switch_rate": float(d.get("switch_rate", np.nan)),
        "mean_top1_tenure": float(d.get("mean_top1_tenure", np.nan)),
        "median_top1_tenure": float(d.get("median_top1_tenure", np.nan)),
        "short_run_le2_share": float(d.get("short_run_le2_share", np.nan)),
        "top1_top2_gap_median": top_gap_median(ev, u),
        "active_leader_count": float(d.get("active_leader_count", np.nan)),
        "leader_hhi": float(d.get("leader_hhi", np.nan)),
        "effective_leader_count": float(d.get("effective_leader_count", np.nan)),
        "mean_pair_trend_jaccard": float(d.get("mean_pair_trend_jaccard", np.nan)),
        "max_pair_trend_jaccard": float(d.get("max_pair_trend_jaccard", np.nan)),
        "productive_switch_share": float(d.get("productive_switch_share", np.nan)),
        "switch_counterfactual_gain_mean": float(d.get("switch_counterfactual_gain_mean", np.nan)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage6e-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng); bars["symbol"] = bars["symbol"].astype(str)
    feat = build_features(bars); feat["symbol"] = feat["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)
    meta = pd.read_sql_query(text("""
        select symbol,has_daily_bars,leveraged_flag,inverse_flag
        from public.instrument_metadata_current
    """), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    decision_pos = s5.decision_indices(cal)
    rng = np.random.default_rng(SEED)
    all_rows: list[dict] = []
    period_meta: list[dict] = []

    for pidx, d in enumerate(decision_pos):
        decision_date = pd.Timestamp(cal[d])
        if d < LOOKBACK:
            continue
        pool = s5.available_pool(close, meta, cal, d)
        if len(pool) < K:
            continue
        past_dates = pd.DatetimeIndex(cal[d-LOOKBACK:d])
        future_end_pos = min(d + FUTURE, len(cal) - 2)
        future_dates = pd.DatetimeIndex(cal[d:future_end_pos])
        complete = bool((future_end_pos - d) >= FUTURE)
        if len(future_dates) == 0:
            continue

        past_ev = s6c.Eval(score, gross, past_dates, pool)
        future_ev = s6c.Eval(score, gross, future_dates, pool)
        library, singles = build_library(past_ev, pool, rng)

        rows = []
        for u in library:
            fr = feature_row(past_ev, u)
            fut = future_ev.evaluate(u)
            rows.append({
                "decision_date": str(decision_date.date()),
                "future_end_date": str(pd.Timestamp(future_dates[-1]).date()),
                "complete_future_126": complete,
                "era": "2022_2024" if decision_date < pd.Timestamp("2025-01-01") else "2025_2026",
                "pool_n": len(pool),
                "members": ",".join(u),
                "future_log_growth": float(fut["log_growth"]),
                "future_total_return": float(fut["total_return"]),
                **fr,
            })
        df = pd.DataFrame(rows)
        df["future_rank_pct"] = rank_pct(df["future_log_growth"])
        n_top = min(TOP_N, len(df))
        cutoff = df["future_log_growth"].nlargest(n_top).min()
        df["future_top50"] = (df["future_log_growth"] >= cutoff).astype(int)
        all_rows.extend(df.to_dict(orient="records"))
        period_meta.append({
            "decision_date": str(decision_date.date()),
            "future_end_date": str(pd.Timestamp(future_dates[-1]).date()),
            "complete_future_126": complete,
            "era": "2022_2024" if decision_date < pd.Timestamp("2025-01-01") else "2025_2026",
            "pool_n": len(pool),
            "library_n": len(df),
            "top_n": n_top,
        })

    data = pd.DataFrame(all_rows)
    data.to_csv(out / "rf_k30_dataset.csv", index=False)
    pd.DataFrame(period_meta).to_csv(out / "rf_k30_periods.csv", index=False)

    decisions = sorted(pd.to_datetime(data.loc[data["complete_future_126"], "decision_date"].unique()))
    oos_rows = []
    pred_rows = []
    imp_rows = []

    for test_date in decisions:
        test_key = str(pd.Timestamp(test_date).date())
        test = data[(data["decision_date"] == test_key) & data["complete_future_126"]].copy()
        # Training labels must be fully realized before test decision date.
        train = data[
            data["complete_future_126"]
            & (pd.to_datetime(data["future_end_date"]) < pd.Timestamp(test_date))
        ].copy()
        train_periods = sorted(train["decision_date"].unique())
        if len(train_periods) < 2 or len(test) < 50:
            continue

        med = train[FEATURES].replace([np.inf, -np.inf], np.nan).median(axis=0)
        Xtr = train[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
        Xte = test[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
        ytr = train["future_rank_pct"].astype(float)

        rf = RandomForestRegressor(
            n_estimators=500,
            max_depth=5,
            min_samples_leaf=20,
            max_features="sqrt",
            bootstrap=True,
            random_state=SEED,
            n_jobs=-1,
        )
        rf.fit(Xtr, ytr)
        pred = rf.predict(Xte)
        test = test.copy(); test["rf_pred"] = pred
        ic = spearman(test["rf_pred"], test["future_rank_pct"])
        n_top = min(TOP_N, len(test))
        ptop = test.nlargest(n_top, "rf_pred")
        atop = test.nlargest(n_top, "future_rank_pct")
        capture = len(set(ptop["members"]) & set(atop["members"])) / max(1, n_top)
        model_best = test.sort_values(["rf_pred", "members"], ascending=[False, True]).iloc[0]
        past_best = test.sort_values(["past126_log_growth", "members"], ascending=[False, True]).iloc[0]
        era = str(test["era"].iloc[0])
        oos_rows.append({
            "test_decision_date": test_key,
            "era": era,
            "train_period_n": len(train_periods),
            "train_row_n": len(train),
            "test_row_n": len(test),
            "rank_ic": ic,
            "pred_top50_mean_actual_percentile": float(ptop["future_rank_pct"].mean()),
            "top50_capture": float(capture),
            "model_top1_actual_percentile": float(model_best["future_rank_pct"]),
            "model_top1_future_log": float(model_best["future_log_growth"]),
            "model_top1_future_return": float(model_best["future_total_return"]),
            "past126_winner_actual_percentile": float(past_best["future_rank_pct"]),
            "past126_winner_future_log": float(past_best["future_log_growth"]),
            "past126_winner_future_return": float(past_best["future_total_return"]),
        })
        for f, v in zip(FEATURES, rf.feature_importances_):
            imp_rows.append({"test_decision_date": test_key, "era": era, "feature": f, "importance": float(v)})
        for _, r in test.iterrows():
            pred_rows.append({
                "test_decision_date": test_key,
                "era": era,
                "members": r["members"],
                "rf_pred": float(r["rf_pred"]),
                "future_rank_pct": float(r["future_rank_pct"]),
                "future_log_growth": float(r["future_log_growth"]),
                "past126_log_growth": float(r["past126_log_growth"]),
            })

    oos = pd.DataFrame(oos_rows)
    oos.to_csv(out / "rf_oos_period_metrics.csv", index=False)
    pd.DataFrame(pred_rows).to_csv(out / "rf_oos_predictions.csv", index=False)
    imp = pd.DataFrame(imp_rows)
    imp.to_csv(out / "rf_feature_importance_by_fold.csv", index=False)
    if len(imp):
        imp.groupby("feature", as_index=False)["importance"].agg(["mean", "median"]).reset_index().to_csv(
            out / "rf_feature_importance_summary.csv", index=False
        )

    if len(oos):
        med_ic = float(oos["rank_ic"].median())
        pos_share = float((oos["rank_ic"] > 0).mean())
        med_top = float(oos["pred_top50_mean_actual_percentile"].median())
        era_medians = {str(k): float(g["rank_ic"].median()) for k, g in oos.groupby("era") if len(g) >= 2}
        gate1 = med_ic > 0.10
        gate2 = pos_share >= 0.60
        gate3 = med_top > 0.60
        gate4 = bool(era_medians) and all(v > 0 for v in era_medians.values())
    else:
        med_ic = pos_share = med_top = np.nan; era_medians = {}
        gate1 = gate2 = gate3 = gate4 = False

    summary = {
        "study": "OURE Stage6E random-forest direct K30 set ranking",
        "status": "completed",
        "feature_count": len(FEATURES),
        "features": FEATURES,
        "rf": {"n_estimators":500,"max_depth":5,"min_samples_leaf":20,"max_features":"sqrt","bootstrap":True,"random_state":SEED},
        "formal_oos_periods": int(len(oos)),
        "median_oos_rank_ic": med_ic,
        "positive_ic_share": pos_share,
        "median_pred_top50_actual_percentile": med_top,
        "era_median_rank_ic": era_medians,
        "gates": {
            "median_rank_ic_gt_0p10": bool(gate1),
            "positive_ic_share_ge_0p60": bool(gate2),
            "median_pred_top50_pct_gt_0p60": bool(gate3),
            "era_median_ic_positive": bool(gate4),
        },
        "primary_gate_pass": bool(gate1 and gate2 and gate3 and gate4),
        "warning": "finite past-generated K30 libraries; no hyperparameter tuning; current metadata survivorship caveat",
    }
    (out / "oure_stage6e_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
