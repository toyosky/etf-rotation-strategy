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
from sklearn.model_selection import GroupKFold
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage5_history_transfer as s5
import optimal_universe_reverse_engineering.oure_stage6c_fullmarket_2022_2024_k_frontier as s6c
import optimal_universe_reverse_engineering.oure_stage6e_rf_k30_rank as s6e
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

CASH = "511220"
K = 30
LOOKBACK = 126
SHORTLIST_N = 160
GREEDY_SEEDS = 8
FAMILY_TARGET = 26
MUTATIONS_PER_FAMILY = 70
BROAD_RANDOM_N = 650
BASE_JACCARD_MAX = 0.55
SEED = 20260914
TOP_N = 50

RF_PARAMS = dict(
    n_estimators=800,
    max_depth=7,
    min_samples_leaf=10,
    max_features="sqrt",
    bootstrap=True,
    random_state=SEED,
    n_jobs=-1,
)

ERAS = [
    ("2022_2024", pd.Timestamp("2022-01-01"), pd.Timestamp("2024-12-31")),
    ("2025_2026", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-09-09")),
]

FEATURES = list(s6e.FEATURES)


def spearman(x, y) -> float:
    a = pd.Series(np.asarray(x, dtype=float))
    b = pd.Series(np.asarray(y, dtype=float))
    m = a.notna() & b.notna() & np.isfinite(a) & np.isfinite(b)
    if int(m.sum()) < 3:
        return np.nan
    return float(a[m].rank(method="average").corr(b[m].rank(method="average")))


def rank_pct(s: pd.Series) -> pd.Series:
    r = s.rank(method="average", ascending=True)
    if len(r) <= 1:
        return pd.Series(np.ones(len(r)), index=s.index)
    return (r - 1.0) / (len(r) - 1.0)


def keyify(xs) -> tuple[str, ...]:
    return s6e.keyify(xs)


def jaccard(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    return s6e.jaccard(a, b)


def random_k30(source: list[str], rng: np.random.Generator) -> tuple[str, ...]:
    return keyify(rng.choice(source, size=K, replace=False).tolist())


def build_family_library(
    past_ev: s6c.Eval,
    pool: list[str],
    rng: np.random.Generator,
) -> tuple[dict[tuple[str, ...], str], pd.DataFrame, pd.DataFrame]:
    singles = []
    for sym in pool:
        singles.append((sym, past_ev.evaluate({sym})["log_growth"]))
    single = pd.DataFrame(singles, columns=["symbol", "past_singleton_log"]).sort_values(
        ["past_singleton_log", "symbol"], ascending=[False, True]
    )
    shortlist = single.head(min(SHORTLIST_N, len(single)))["symbol"].astype(str).tolist()
    if len(shortlist) < K:
        raise RuntimeError("shortlist smaller than K")

    candidate_bases: list[tuple[str, ...]] = []
    for seed in shortlist[:min(GREEDY_SEEDS, len(shortlist))]:
        u = s6e.greedy_to_k(past_ev, seed, shortlist)
        if len(u) == K:
            candidate_bases.append(u)

    # Plenty of past-only random bases; future outcomes are never used here.
    for _ in range(4000):
        src = shortlist if rng.random() < 0.5 else pool
        candidate_bases.append(random_k30(src, rng))
        if len(candidate_bases) >= 4500:
            break

    # Order only by past126 set value, then enforce family-base diversity.
    candidate_bases = sorted(set(candidate_bases), key=lambda u: (-past_ev.evaluate(u)["log_growth"], u))
    bases: list[tuple[str, ...]] = []
    for u in candidate_bases:
        if all(jaccard(u, v) <= BASE_JACCARD_MAX for v in bases):
            bases.append(u)
        if len(bases) >= FAMILY_TARGET:
            break
    if len(bases) < 10:
        raise RuntimeError(f"too few diverse family bases: {len(bases)}")

    combo_family: dict[tuple[str, ...], str] = {}
    family_rows = []
    for fi, base in enumerate(bases):
        fam = f"family_{fi:03d}"
        combo_family.setdefault(base, fam)
        family_rows.append({
            "family_id": fam,
            "base_members": ",".join(base),
            "base_past126_log": float(past_ev.evaluate(base)["log_growth"]),
        })
        # Earlier families are often stronger past-only bases; mutation source alternates so families do not all live in one shortlist ecology.
        src = shortlist if fi % 2 == 0 else pool
        for _ in range(MUTATIONS_PER_FAMILY * 5):
            nswap = int(rng.integers(1, 7))
            u = s6e.mutate(base, src, nswap, rng)
            if len(u) != K:
                continue
            combo_family.setdefault(u, fam)
            if sum(1 for x in combo_family.values() if x == fam) >= MUTATIONS_PER_FAMILY + 1:
                break

    # Broad random controls are singleton groups. Their pair overlap is naturally low and they stop the task becoming merely “mutations around strong past sets”.
    added = 0
    tries = 0
    while added < BROAD_RANDOM_N and tries < BROAD_RANDOM_N * 20:
        tries += 1
        u = random_k30(pool, rng)
        if u in combo_family:
            continue
        fam = f"random_{added:04d}"
        combo_family[u] = fam
        added += 1

    return combo_family, single, pd.DataFrame(family_rows)


def era_data(
    era: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    cal: pd.DatetimeIndex,
    score: pd.DataFrame,
    gross: pd.DataFrame,
    close: pd.DataFrame,
    meta: pd.DataFrame,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    d = int(cal.searchsorted(start, side="left"))
    if d < 252:
        raise RuntimeError(f"not enough history for {era}")
    pool = s5.available_pool(close, meta, cal, d)
    if len(pool) < K:
        raise RuntimeError(f"too few candidates for {era}: {len(pool)}")

    past_dates = pd.DatetimeIndex(cal[d-LOOKBACK:d])
    positions = np.flatnonzero((cal >= start) & (cal <= end))
    positions = positions[positions < len(cal) - 2]
    future_dates = pd.DatetimeIndex(cal[positions])
    if len(future_dates) < 100:
        raise RuntimeError(f"future era too short for {era}: {len(future_dates)}")

    past_ev = s6c.Eval(score, gross, past_dates, pool)
    future_ev = s6c.Eval(score, gross, future_dates, pool)
    combo_family, singles, families = build_family_library(past_ev, pool, rng)

    rows = []
    for u, fam in combo_family.items():
        fr = s6e.feature_row(past_ev, u)
        fut = future_ev.evaluate(u)
        rows.append({
            "era": era,
            "start_date": str(pd.Timestamp(future_dates[0]).date()),
            "end_date": str(pd.Timestamp(future_dates[-1]).date()),
            "pool_n": len(pool),
            "family_id": fam,
            "members": ",".join(u),
            "future_log_growth": float(fut["log_growth"]),
            "future_total_return": float(fut["total_return"]),
            **fr,
        })
    df = pd.DataFrame(rows)
    df["future_rank_pct"] = rank_pct(df["future_log_growth"])
    families["era"] = era
    singles["era"] = era
    return df, families, singles


def fit_predict_fold(train: pd.DataFrame, valid: pd.DataFrame) -> tuple[np.ndarray, RandomForestRegressor]:
    med = train[FEATURES].replace([np.inf, -np.inf], np.nan).median(axis=0)
    Xtr = train[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
    Xva = valid[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
    ytr = train["future_log_growth"].astype(float)
    rf = RandomForestRegressor(**RF_PARAMS)
    rf.fit(Xtr, ytr)
    return rf.predict(Xva), rf


def group_cv(df: pd.DataFrame, era: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    groups = df["family_id"].astype(str)
    if groups.nunique() < 5:
        raise RuntimeError(f"too few groups for {era}")
    gkf = GroupKFold(n_splits=5)
    metrics = []
    preds = []
    imps = []
    Xdummy = np.zeros((len(df), 1))
    for fold, (tr, va) in enumerate(gkf.split(Xdummy, groups=groups), start=1):
        train = df.iloc[tr].copy(); valid = df.iloc[va].copy()
        pred, rf = fit_predict_fold(train, valid)
        valid["rf_pred"] = pred
        ic = spearman(valid["rf_pred"], valid["future_log_growth"])
        n_top = min(TOP_N, len(valid))
        ptop = valid.nlargest(n_top, "rf_pred")
        atop = valid.nlargest(n_top, "future_log_growth")
        capture = len(set(ptop["members"]) & set(atop["members"])) / max(1, n_top)
        dec_n = max(1, int(np.ceil(len(valid) * 0.10)))
        pdec = valid.nlargest(dec_n, "rf_pred")
        lift = float(pdec["future_log_growth"].mean() - valid["future_log_growth"].mean())
        metrics.append({
            "era": era,
            "fold": fold,
            "train_n": len(train),
            "valid_n": len(valid),
            "train_group_n": train["family_id"].nunique(),
            "valid_group_n": valid["family_id"].nunique(),
            "spearman": ic,
            "pred_top50_mean_actual_percentile": float(ptop["future_rank_pct"].mean()),
            "top50_capture": float(capture),
            "pred_top_decile_log_lift": lift,
            "pred_top_decile_mean_future_log": float(pdec["future_log_growth"].mean()),
            "valid_mean_future_log": float(valid["future_log_growth"].mean()),
        })
        for f, v in zip(FEATURES, rf.feature_importances_):
            imps.append({"era": era, "fold": fold, "feature": f, "importance": float(v)})
        for _, r in valid.iterrows():
            preds.append({
                "era": era,
                "fold": fold,
                "family_id": r["family_id"],
                "members": r["members"],
                "rf_pred": float(r["rf_pred"]),
                "future_log_growth": float(r["future_log_growth"]),
                "future_rank_pct": float(r["future_rank_pct"]),
            })
    return pd.DataFrame(metrics), pd.DataFrame(preds), pd.DataFrame(imps)


def cross_era_transfer(train: pd.DataFrame, test: pd.DataFrame, train_era: str, test_era: str) -> dict:
    pred, _ = fit_predict_fold(train, test)
    return {
        "train_era": train_era,
        "test_era": test_era,
        "spearman": spearman(pred, test["future_log_growth"]),
        "n_train": len(train),
        "n_test": len(test),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage6f-output")
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

    rng = np.random.default_rng(SEED)
    era_frames = []
    fam_frames = []
    single_frames = []
    for era, start, end in ERAS:
        df, fam, single = era_data(era, start, end, cal, score, gross, close, meta, rng)
        era_frames.append(df); fam_frames.append(fam); single_frames.append(single)

    data = pd.concat(era_frames, ignore_index=True)
    families = pd.concat(fam_frames, ignore_index=True)
    singles = pd.concat(single_frames, ignore_index=True)
    data.to_csv(out / "stage6f_k30_samples.csv", index=False)
    families.to_csv(out / "stage6f_family_bases.csv", index=False)
    singles.to_csv(out / "stage6f_singletons.csv", index=False)

    cv_frames = []; pred_frames = []; imp_frames = []
    gates = {}; era_summary = {}
    for era, g in data.groupby("era", sort=False):
        cv, pred, imp = group_cv(g.reset_index(drop=True), era)
        cv_frames.append(cv); pred_frames.append(pred); imp_frames.append(imp)
        med_ic = float(cv["spearman"].median())
        pos_n = int((cv["spearman"] > 0).sum())
        med_top = float(cv["pred_top50_mean_actual_percentile"].median())
        med_lift = float(cv["pred_top_decile_log_lift"].median())
        passed = bool(med_ic > 0.15 and pos_n >= 4 and med_top > 0.65 and med_lift > 0)
        gates[era] = passed
        era_summary[era] = {
            "sample_n": int(len(g)),
            "family_n": int(g["family_id"].nunique()),
            "median_fold_spearman": med_ic,
            "positive_fold_n": pos_n,
            "median_pred_top50_actual_percentile": med_top,
            "median_top_decile_log_lift": med_lift,
            "gate_pass": passed,
        }

    cv_all = pd.concat(cv_frames, ignore_index=True)
    pred_all = pd.concat(pred_frames, ignore_index=True)
    imp_all = pd.concat(imp_frames, ignore_index=True)
    cv_all.to_csv(out / "stage6f_cv_metrics.csv", index=False)
    pred_all.to_csv(out / "stage6f_cv_predictions.csv", index=False)
    imp_all.to_csv(out / "stage6f_feature_importance_by_fold.csv", index=False)
    if len(imp_all):
        imp_all.groupby(["era", "feature"], as_index=False)["importance"].agg(["mean", "median"]).reset_index().to_csv(
            out / "stage6f_feature_importance_summary.csv", index=False
        )

    a = data[data["era"] == "2022_2024"].reset_index(drop=True)
    b = data[data["era"] == "2025_2026"].reset_index(drop=True)
    transfers = [
        cross_era_transfer(a, b, "2022_2024", "2025_2026"),
        cross_era_transfer(b, a, "2025_2026", "2022_2024"),
    ]
    pd.DataFrame(transfers).to_csv(out / "stage6f_cross_era_transfer.csv", index=False)

    pass_count = int(sum(bool(v) for v in gates.values()))
    decision = "both_eras_learnable" if pass_count == 2 else ("era_specific_learnability" if pass_count == 1 else "not_learnable_from_frozen_X")
    summary = {
        "study": "OURE Stage6F RF surrogate value function for K30",
        "status": "completed",
        "decision": decision,
        "features": FEATURES,
        "rf": RF_PARAMS,
        "era_summary": era_summary,
        "gates": gates,
        "cross_era_transfer_secondary": transfers,
        "warning": "within-era grouped validation is a mechanism/learnability test, not chronological OOS; current metadata survivorship caveat remains",
    }
    (out / "oure_stage6f_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
