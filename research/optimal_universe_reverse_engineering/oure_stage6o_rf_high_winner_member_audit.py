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
from sklearn.ensemble import RandomForestRegressor
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage5_history_transfer as s5
import optimal_universe_reverse_engineering.oure_stage6c_fullmarket_2022_2024_k_frontier as s6c
import optimal_universe_reverse_engineering.oure_stage6f_rf_surrogate_value as s6g
import optimal_universe_reverse_engineering.oure_stage6k_adjacent_126_transfer as s6k
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

LOOKBACK = 126
FUTURE = 126
SEED = 20260914
RF_HIGH_FRAC = 0.20
GOOD_FRAC = 0.20
BAD_FRAC = 0.20
PRED_STRATA = 10
MIN_APPEAR = 20

FEATURES = [
    "singleton_log126",
    "elig_participation126",
    "score_last",
    "score_mean126",
    "score_p90_126",
    "score_recent_minus_prior21",
    "ret21",
    "ret63",
    "ret126",
    "vol21",
    "vol63",
    "vol126",
    "maxdd63",
    "maxdd126",
    "dist_high21",
    "dist_high63",
    "rfhigh_presence_rate",
    "rfhigh_mean_rf_pred_when_present",
    "rfhigh_mean_past126_set_when_present",
    "rfhigh_comember_corr_mean",
    "rfhigh_comember_hhi",
]

FAMILY = {
    "singleton_log126": "A",
    "elig_participation126": "B",
    "score_last": "B",
    "score_mean126": "B",
    "score_p90_126": "B",
    "score_recent_minus_prior21": "B",
    "ret21": "C",
    "ret63": "C",
    "ret126": "C",
    "vol21": "C",
    "vol63": "C",
    "vol126": "C",
    "maxdd63": "C",
    "maxdd126": "C",
    "dist_high21": "C",
    "dist_high63": "C",
    "rfhigh_presence_rate": "D",
    "rfhigh_mean_rf_pred_when_present": "D",
    "rfhigh_mean_past126_set_when_present": "D",
    "rfhigh_comember_corr_mean": "D",
    "rfhigh_comember_hhi": "D",
}

RF_MEMBER_PARAMS = dict(
    n_estimators=600,
    max_depth=5,
    min_samples_leaf=5,
    max_features="sqrt",
    random_state=20260915,
    n_jobs=4,
)

BASELINES = [
    "singleton_log126",
    "ret126",
    "elig_participation126",
    "rfhigh_mean_past126_set_when_present",
]


def rank_pct(s: pd.Series) -> pd.Series:
    return s6g.rank_pct(pd.Series(s, dtype=float))


def spearman(a, b) -> float:
    v = s6g.spearman(a, b)
    return float(v) if np.isfinite(v) else np.nan


def finite_mean(x) -> float:
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    return float(a.mean()) if len(a) else np.nan


def finite_quantile(x, q: float) -> float:
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    return float(np.quantile(a, q)) if len(a) else np.nan


def price_stats(close: pd.DataFrame, cal: pd.DatetimeIndex, d: int, symbol: str, w: int) -> tuple[float, float, float, float]:
    start = max(0, d - w - 1)
    dates = cal[start:d]
    x = close.loc[dates, symbol].astype(float).dropna()
    if len(x) < max(5, min(w, 10)):
        return np.nan, np.nan, np.nan, np.nan
    ret = float(x.iloc[-1] / x.iloc[0] - 1.0) if x.iloc[0] > 0 else np.nan
    dr = x.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    vol = float(dr.std(ddof=0) * math.sqrt(252.0)) if len(dr) >= 3 else np.nan
    rollmax = x.cummax()
    dd = x / rollmax - 1.0
    maxdd = float(dd.min()) if len(dd) else np.nan
    dist_high = float(x.iloc[-1] / x.max() - 1.0) if x.max() > 0 else np.nan
    return ret, vol, maxdd, dist_high


def score_stats(score: pd.DataFrame, past_dates: pd.DatetimeIndex, symbol: str) -> dict:
    s = score.loc[past_dates, symbol].astype(float)
    vals = s.to_numpy(dtype=float)
    finite = vals[np.isfinite(vals)]
    recent = s.iloc[-21:].to_numpy(dtype=float)
    prior = s.iloc[-42:-21].to_numpy(dtype=float)
    return {
        "elig_participation126": float(np.mean(np.isfinite(vals))),
        "score_last": float(vals[-1]) if len(vals) and np.isfinite(vals[-1]) else np.nan,
        "score_mean126": finite_mean(finite),
        "score_p90_126": finite_quantile(finite, 0.90),
        "score_recent_minus_prior21": finite_mean(recent) - finite_mean(prior)
        if np.isfinite(finite_mean(recent)) and np.isfinite(finite_mean(prior)) else np.nan,
    }


def conditional_future_marginal(high: pd.DataFrame, present: np.ndarray) -> tuple[float, int]:
    deltas = []
    weights = []
    for _, g in high.groupby("pred_stratum"):
        idx = g.index.to_numpy(dtype=int)
        p = present[idx]
        npres = int(p.sum())
        nabs = int((~p).sum())
        if npres < 3 or nabs < 3:
            continue
        y = g["future_log_growth"].to_numpy(dtype=float)
        delta = float(np.mean(y[p]) - np.mean(y[~p]))
        deltas.append(delta)
        weights.append(npres)
    if not deltas:
        return np.nan, 0
    return float(np.average(deltas, weights=weights)), int(np.sum(weights))


def member_rows_for_block(
    high: pd.DataFrame,
    decision_date: pd.Timestamp,
    cal: pd.DatetimeIndex,
    close: pd.DataFrame,
    score: pd.DataFrame,
    pool: list[str],
) -> pd.DataFrame:
    d = int(cal.get_indexer([decision_date])[0])
    past_dates = pd.DatetimeIndex(cal[d - LOOKBACK:d])
    ev = s6c.Eval(score, close / close.shift(1), past_dates, pool)

    members_lists = [tuple(str(x).split(",")) for x in high["members"]]
    all_members = sorted(set(s for m in members_lists for s in m))
    n = len(high)

    qgood = float(high["future_log_growth"].quantile(1.0 - GOOD_FRAC))
    qbad = float(high["future_log_growth"].quantile(BAD_FRAC))
    is_good = high["future_log_growth"].to_numpy(dtype=float) >= qgood
    is_bad = high["future_log_growth"].to_numpy(dtype=float) <= qbad

    # Past return-correlation matrix for co-member context.
    ret_hist = close.loc[past_dates, all_members].astype(float).pct_change().replace([np.inf, -np.inf], np.nan)
    corr = ret_hist.corr(min_periods=40)

    rows = []
    for sym in all_members:
        present = np.array([sym in m for m in members_lists], dtype=bool)
        cnt = int(present.sum())
        if cnt < MIN_APPEAR:
            continue

        cond, valid_n = conditional_future_marginal(high, present)
        p_all = cnt / n
        p_good = float(np.mean(present[is_good])) if is_good.sum() else np.nan
        p_bad = float(np.mean(present[is_bad])) if is_bad.sum() else np.nan

        st = score_stats(score, past_dates, sym)
        r21, v21, _, dh21 = price_stats(close, cal, d, sym, 21)
        r63, v63, md63, dh63 = price_stats(close, cal, d, sym, 63)
        r126, v126, md126, _ = price_stats(close, cal, d, sym, 126)

        # Singleton OLS value using the exact frozen evaluator semantics.
        try:
            singleton = float(ev.evaluate({sym})["log_growth"])
        except Exception:
            singleton = np.nan

        hp = high.loc[present]
        mean_rf = finite_mean(hp["rf_pred"].to_numpy(dtype=float))
        mean_past_set = finite_mean(hp["past126_log_growth"].to_numpy(dtype=float)) if "past126_log_growth" in hp.columns else np.nan

        co_counts = {}
        for m in np.array(members_lists, dtype=object)[present]:
            for other in m:
                if other != sym:
                    co_counts[other] = co_counts.get(other, 0) + 1
        total_co = sum(co_counts.values())
        hhi = float(sum((c / total_co) ** 2 for c in co_counts.values())) if total_co else np.nan
        corr_num = 0.0
        corr_den = 0.0
        for other, c in co_counts.items():
            if sym in corr.index and other in corr.columns:
                cv = corr.loc[sym, other]
                if np.isfinite(cv):
                    corr_num += float(cv) * c
                    corr_den += c
        co_corr = corr_num / corr_den if corr_den > 0 else np.nan

        rows.append({
            "symbol": sym,
            "appear_count": cnt,
            "conditional_valid_presence_n": valid_n,
            "winner_presence_rate": p_good,
            "loser_presence_rate": p_bad,
            "winner_enrichment": p_good - p_all if np.isfinite(p_good) else np.nan,
            "winner_minus_loser_presence": p_good - p_bad if np.isfinite(p_good) and np.isfinite(p_bad) else np.nan,
            "conditional_future_marginal": cond,
            "singleton_log126": singleton,
            **st,
            "ret21": r21,
            "ret63": r63,
            "ret126": r126,
            "vol21": v21,
            "vol63": v63,
            "vol126": v126,
            "maxdd63": md63,
            "maxdd126": md126,
            "dist_high21": dh21,
            "dist_high63": dh63,
            "rfhigh_presence_rate": p_all,
            "rfhigh_mean_rf_pred_when_present": mean_rf,
            "rfhigh_mean_past126_set_when_present": mean_past_set,
            "rfhigh_comember_corr_mean": co_corr,
            "rfhigh_comember_hhi": hhi,
        })
    out = pd.DataFrame(rows)
    if len(out):
        out["future_member_rank_pct"] = rank_pct(out["conditional_future_marginal"]).to_numpy()
    return out


def stable_effects(member_df: pd.DataFrame, target_blocks: list[str]) -> tuple[pd.DataFrame, list[str]]:
    effect_rows = []
    for b in target_blocks:
        g = member_df[member_df["target_block"] == b].copy()
        good = g[g["future_member_rank_pct"] >= 0.75]
        bad = g[g["future_member_rank_pct"] <= 0.25]
        for f in FEATURES:
            vals = g[f].to_numpy(dtype=float)
            sd = float(np.nanstd(vals, ddof=0))
            gm = finite_mean(good[f].to_numpy(dtype=float))
            bm = finite_mean(bad[f].to_numpy(dtype=float))
            eff = (gm - bm) / sd if np.isfinite(gm) and np.isfinite(bm) and np.isfinite(sd) and sd > 1e-12 else np.nan
            effect_rows.append({"target_block": b, "feature": f, "family": FAMILY[f], "std_effect": eff})
    effects = pd.DataFrame(effect_rows)

    stable = []
    for f, gf in effects.groupby("feature"):
        vals = gf.set_index("target_block")["std_effect"].reindex(target_blocks).to_numpy(dtype=float)
        finite = vals[np.isfinite(vals)]
        if len(finite) < 6:
            continue
        pos = int((finite > 0).sum())
        neg = int((finite < 0).sum())
        if max(pos, neg) < 6:
            continue
        if float(np.median(np.abs(finite))) < 0.15:
            continue
        stable.append(str(f))
    return effects, sorted(stable)


def eval_rule(test: pd.DataFrame, score_vals: np.ndarray, rule: str, test_block: str) -> dict:
    t = test.copy()
    t["pred_score"] = np.asarray(score_vals, dtype=float)
    t = t[np.isfinite(t["pred_score"]) & np.isfinite(t["future_member_rank_pct"])].copy()
    if not len(t):
        return {"test_block": test_block, "rule": rule}
    ic = spearman(t["pred_score"], t["future_member_rank_pct"])
    top = t.nlargest(min(10, len(t)), "pred_score")
    lift = float(top["conditional_future_marginal"].mean() - t["conditional_future_marginal"].mean())
    return {
        "test_block": test_block,
        "rule": rule,
        "n_members": int(len(t)),
        "spearman": ic,
        "positive_ic": bool(np.isfinite(ic) and ic > 0),
        "top10_mean_actual_percentile": float(top["future_member_rank_pct"].mean()),
        "top10_conditional_marginal_lift": lift,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage6o-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng)
    bars["symbol"] = bars["symbol"].astype(str)
    feat = build_features(bars)
    feat["symbol"] = feat["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)
    meta = pd.read_sql_query(text("""
        select symbol,has_daily_bars,leveraged_flag,inverse_flag
        from public.instrument_metadata_current
    """), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    # Regenerate strict Stage6K blocks exactly.
    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    rng = np.random.default_rng(SEED)
    frames = []
    b = 1
    pos = start0
    while True:
        pack = s6k.block_data(b, pos, cal, score, gross, close, meta, rng)
        if pack is None:
            break
        frames.append(pack[0])
        b += 1
        pos += FUTURE
    data = pd.concat(frames, ignore_index=True)
    block_ids = data[["block", "block_no"]].drop_duplicates().sort_values("block_no")["block"].astype(str).tolist()

    high_frames = []
    member_frames = []
    for j in range(1, len(block_ids)):
        prev_b = block_ids[j - 1]
        target_b = block_ids[j]
        train = data[data["block"] == prev_b].copy().reset_index(drop=True)
        test = data[data["block"] == target_b].copy().reset_index(drop=True)
        pred, _ = s6k.fit_rf(train, test)
        test["rf_pred"] = pred
        test["rf_pred_rank_pct"] = rank_pct(test["rf_pred"]).to_numpy()
        n_hi = max(1, int(math.ceil(len(test) * RF_HIGH_FRAC)))
        high = test.nlargest(n_hi, "rf_pred").copy().reset_index(drop=True)
        high["pred_stratum"] = pd.qcut(high["rf_pred_rank_pct"], q=PRED_STRATA, labels=False, duplicates="drop")
        high["target_block"] = target_b
        high_frames.append(high)

        decision_date = pd.Timestamp(high["decision_date"].iloc[0])
        d = int(cal.get_indexer([decision_date])[0])
        pool = s5.available_pool(close, meta, cal, d)
        mdf = member_rows_for_block(high, decision_date, cal, close, score, pool)
        mdf["target_block"] = target_b
        mdf["decision_date"] = str(decision_date.date())
        member_frames.append(mdf)

    high_all = pd.concat(high_frames, ignore_index=True)
    members = pd.concat(member_frames, ignore_index=True)
    target_blocks = block_ids[1:]

    high_all.to_csv(out / "stage6o_rf_high_sets.csv", index=False)
    members.to_csv(out / "stage6o_member_rows.csv", index=False)

    effects, stable = stable_effects(members, target_blocks)
    effects.to_csv(out / "stage6o_member_feature_effects.csv", index=False)

    # Descriptive per-block top/bottom member identities for audit only.
    desc_rows = []
    for b in target_blocks:
        g = members[members["target_block"] == b].copy()
        for side, gg in [("top", g.nlargest(10, "conditional_future_marginal")), ("bottom", g.nsmallest(10, "conditional_future_marginal"))]:
            for rank, (_, r) in enumerate(gg.iterrows(), start=1):
                desc_rows.append({
                    "target_block": b,
                    "side": side,
                    "rank": rank,
                    "symbol": r["symbol"],
                    "conditional_future_marginal": float(r["conditional_future_marginal"]),
                    "winner_enrichment": float(r["winner_enrichment"]),
                    "winner_minus_loser_presence": float(r["winner_minus_loser_presence"]),
                })
    pd.DataFrame(desc_rows).to_csv(out / "stage6o_member_extremes.csv", index=False)

    # Stage 2 chronological prediction.
    metric_rows = []
    pred_rows = []
    test_blocks = [b for b in ["B05", "B06", "B07", "B08", "B09"] if b in target_blocks]
    for tb in test_blocks:
        tno = int(tb[1:])
        train_blocks = [b for b in target_blocks if int(b[1:]) < tno]
        tr = members[members["target_block"].isin(train_blocks)].copy().reset_index(drop=True)
        te = members[members["target_block"] == tb].copy().reset_index(drop=True)
        med = tr[FEATURES].replace([np.inf, -np.inf], np.nan).median(axis=0)
        xtr = tr[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
        xte = te[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(med).fillna(0.0)
        ytr = tr["future_member_rank_pct"].astype(float)

        model = RandomForestRegressor(**RF_MEMBER_PARAMS)
        model.fit(xtr, ytr)
        pred = model.predict(xte)
        metric_rows.append(eval_rule(te, pred, "member_rf", tb))
        for bl in BASELINES:
            metric_rows.append(eval_rule(te, te[bl].to_numpy(dtype=float), bl, tb))
        for i, r in te.iterrows():
            pred_rows.append({
                "test_block": tb,
                "symbol": r["symbol"],
                "pred_member_rf": float(pred[i]),
                "future_member_rank_pct": float(r["future_member_rank_pct"]),
                "conditional_future_marginal": float(r["conditional_future_marginal"]),
                **{bl: float(r[bl]) if np.isfinite(r[bl]) else np.nan for bl in BASELINES},
            })

    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(out / "stage6o_chronological_metrics.csv", index=False)
    pd.DataFrame(pred_rows).to_csv(out / "stage6o_chronological_predictions.csv", index=False)

    summaries = {}
    for rule, g in metrics.groupby("rule"):
        summaries[rule] = {
            "test_n": int(len(g)),
            "median_spearman": float(g["spearman"].median()),
            "positive_ic_n": int((g["spearman"] > 0).sum()),
            "median_top10_actual_percentile": float(g["top10_mean_actual_percentile"].median()),
            "median_top10_conditional_marginal_lift": float(g["top10_conditional_marginal_lift"].median()),
        }

    member_rf = summaries.get("member_rf", {})
    best_baseline_ic = max((summaries.get(b, {}).get("median_spearman", -np.inf) for b in BASELINES), default=-np.inf)
    gates = {
        "median_ic_gt_0_10": bool(member_rf.get("median_spearman", -np.inf) > 0.10),
        "positive_ic_ge_4_of_5": bool(member_rf.get("positive_ic_n", 0) >= 4),
        "median_top10_pct_gt_0_60": bool(member_rf.get("median_top10_actual_percentile", -np.inf) > 0.60),
        "median_top10_marginal_lift_gt_0": bool(member_rf.get("median_top10_conditional_marginal_lift", -np.inf) > 0),
        "median_ic_beats_best_baseline_by_0_05": bool(member_rf.get("median_spearman", -np.inf) >= best_baseline_ic + 0.05),
    }

    stable_families = sorted(set(FAMILY[f] for f in stable))
    stage1_pass = bool(len(stable) >= 3 and len(stable_families) >= 2)
    stage2_pass = bool(all(gates.values()))

    stable_detail = []
    for f in stable:
        vals = effects[effects["feature"] == f].set_index("target_block")["std_effect"].reindex(target_blocks).to_numpy(dtype=float)
        finite = vals[np.isfinite(vals)]
        stable_detail.append({
            "feature": f,
            "family": FAMILY[f],
            "positive_blocks": int((finite > 0).sum()),
            "negative_blocks": int((finite < 0).sum()),
            "median_effect": float(np.median(finite)) if len(finite) else np.nan,
            "median_abs_effect": float(np.median(np.abs(finite))) if len(finite) else np.nan,
        })
    pd.DataFrame(stable_detail).to_csv(out / "stage6o_stable_member_traits.csv", index=False)

    summary = {
        "study": "OURE Stage6O RF-high winner-member audit and chronological admission test",
        "status": "completed",
        "target_blocks": target_blocks,
        "member_rows": int(len(members)),
        "stable_trait_n": int(len(stable)),
        "stable_trait_families": stable_families,
        "stable_traits": stable_detail,
        "stage1_mechanism_pass": stage1_pass,
        "chronological_test_blocks": test_blocks,
        "model_params": RF_MEMBER_PARAMS,
        "rule_summaries": summaries,
        "best_simple_baseline_median_ic": float(best_baseline_ic),
        "stage2_gates": gates,
        "stage2_predictive_pass": stage2_pass,
        "decision": (
            "member_traits_and_chronological_admission_supported" if stage1_pass and stage2_pass
            else "member_traits_exist_but_admission_not_oos_supported" if stage1_pass
            else "winner_member_traits_not_stable"
        ),
    }
    (out / "stage6o_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=float))


if __name__ == "__main__":
    main()
