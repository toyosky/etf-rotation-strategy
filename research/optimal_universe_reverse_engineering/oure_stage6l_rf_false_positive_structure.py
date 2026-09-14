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
from sklearn.linear_model import Ridge
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
PRED_STRATA = 10
ALPHA = 10.0

QMAP = [(0.10, "p10"), (0.25, "p25"), (0.50, "p50"), (0.75, "p75"), (0.90, "p90")]


def rank_pct(s: pd.Series) -> pd.Series:
    return s6g.rank_pct(pd.Series(s, dtype=float))


def spearman(a, b) -> float:
    v = s6g.spearman(a, b)
    return float(v) if np.isfinite(v) else np.nan


def qstats(vals, prefix: str) -> dict:
    x = np.asarray(vals, dtype=float)
    x = x[np.isfinite(x)]
    out = {}
    if len(x) == 0:
        for _, n in QMAP:
            out[f"{prefix}_{n}"] = np.nan
        return out
    for q, n in QMAP:
        out[f"{prefix}_{n}"] = float(np.quantile(x, q))
    return out


def gini_nonnegative(x) -> float:
    a = np.asarray(x, dtype=float)
    a = np.where(np.isfinite(a), a, 0.0)
    a = np.maximum(a, 0.0)
    if a.sum() <= 0:
        return 0.0
    a = np.sort(a)
    n = len(a)
    return float((2.0 * np.sum((np.arange(1, n + 1)) * a) / (n * a.sum())) - (n + 1.0) / n)


def component_stats(corr: np.ndarray, threshold: float = 0.85) -> tuple[int, float]:
    n = corr.shape[0]
    parent = list(range(n))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    for i in range(n):
        for j in range(i + 1, n):
            if np.isfinite(corr[i, j]) and corr[i, j] > threshold:
                union(i, j)
    counts = {}
    for i in range(n):
        r = find(i)
        counts[r] = counts.get(r, 0) + 1
    return len(counts), float(max(counts.values()) / n) if n else np.nan


def internal_features(ev: s6c.Eval, members: tuple[str, ...], score_df: pd.DataFrame,
                      gross_df: pd.DataFrame, past_dates: pd.DatetimeIndex) -> dict:
    mem = list(members)
    out = {}

    # A: member singleton harvestability.
    sing = np.array([ev.evaluate({s})["log_growth"] for s in mem], dtype=float)
    out.update(qstats(sing, "member_singleton_log"))
    out["member_singleton_iqr"] = float(np.quantile(sing, 0.75) - np.quantile(sing, 0.25))
    out["member_singleton_std"] = float(np.std(sing))
    out["member_singleton_positive_frac"] = float(np.mean(sing > 0))

    # B: member eligibility participation.
    smdf = score_df.loc[past_dates, mem]
    sm = smdf.to_numpy(dtype=float)
    elig = np.isfinite(sm)
    ep = elig.mean(axis=0)
    out.update(qstats(ep, "elig_participation"))
    out["elig_participation_iqr"] = float(np.quantile(ep, 0.75) - np.quantile(ep, 0.25))
    out["elig_participation_std"] = float(np.std(ep))
    out["elig_participation_ge50_frac"] = float(np.mean(ep >= 0.50))

    # C: leader participation shape.
    _, target = ev.target_state(mem)
    invested = target[target >= 0]
    shares = np.zeros(len(mem), dtype=float)
    if len(invested):
        idx_to_local = {ev.idx[s]: i for i, s in enumerate(mem)}
        for x, cnt in zip(*np.unique(invested, return_counts=True)):
            if int(x) in idx_to_local:
                shares[idx_to_local[int(x)]] = cnt / len(invested)
    desc = np.sort(shares)[::-1]
    nz = shares[shares > 0]
    out["leader_share_top1"] = float(desc[0]) if len(desc) else 0.0
    out["leader_share_top3"] = float(desc[:3].sum())
    out["leader_share_top5"] = float(desc[:5].sum())
    out["leader_share_nonzero_median"] = float(np.median(nz)) if len(nz) else 0.0
    out["leader_member_active_frac"] = float(np.mean(shares > 0))
    out["leader_share_gini"] = gini_nonnegative(shares)

    # D: pair geometry.
    counts = elig.sum(axis=0).astype(float)
    inter = elig.astype(np.int16).T @ elig.astype(np.int16)
    union = counts[:, None] + counts[None, :] - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        jac = inter / union
    iu = np.triu_indices(len(mem), 1)
    jvals = jac[iu]
    out.update(qstats(jvals, "pair_elig_jaccard"))

    score_corr = smdf.corr(min_periods=20).to_numpy(dtype=float)
    scvals = score_corr[iu]
    out.update(qstats(scvals, "pair_score_corr"))

    grdf = gross_df.loc[past_dates, mem]
    ret_corr = grdf.corr(min_periods=40).to_numpy(dtype=float)
    rcvals = ret_corr[iu]
    out.update(qstats(rcvals, "pair_return_corr"))
    cc, largest = component_stats(ret_corr, 0.85)
    out["ret_cluster_component_count"] = float(cc)
    out["ret_cluster_largest_share"] = largest

    # E: leave-one-out robustness.
    base = float(ev.evaluate(mem)["log_growth"])
    damage = []
    sset = set(mem)
    for s in mem:
        lg = float(ev.evaluate(sset - {s})["log_growth"])
        damage.append(base - lg)
    damage = np.asarray(damage, dtype=float)
    out.update(qstats(damage, "loo_damage"))
    out["loo_damage_max"] = float(np.max(damage))
    out["loo_damage_std"] = float(np.std(damage))
    out["loo_delete_improves_frac"] = float(np.mean(damage < 0))
    return out


def feature_family(f: str) -> str:
    if f.startswith("member_singleton_"):
        return "A"
    if f.startswith("elig_participation_"):
        return "B"
    if f.startswith("leader_"):
        return "C"
    if f.startswith("pair_") or f.startswith("ret_cluster_"):
        return "D"
    if f.startswith("loo_"):
        return "E"
    return "?"


def make_matches(high: pd.DataFrame) -> pd.DataFrame:
    h = high.copy()
    h["pred_stratum"] = pd.qcut(h["rf_pred_rank_pct"], q=PRED_STRATA, labels=False, duplicates="drop")
    pairs = []
    pid = 0
    for st, g in h.groupby("pred_stratum"):
        if len(g) < 8:
            continue
        q25 = g["residual_rank"].quantile(0.25)
        q75 = g["residual_rank"].quantile(0.75)
        goods = g[g["residual_rank"] >= q75].sort_values("rf_pred_rank_pct")
        bads = g[g["residual_rank"] <= q25].copy()
        avail = list(bads.index)
        for gi, gr in goods.iterrows():
            if not avail:
                break
            bi = min(avail, key=lambda ix: abs(float(h.loc[ix, "rf_pred_rank_pct"]) - float(gr["rf_pred_rank_pct"])))
            avail.remove(bi)
            pid += 1
            pairs.append({
                "pair_id": pid,
                "stratum": int(st),
                "good_index": int(gi),
                "bad_index": int(bi),
                "pred_rank_gap": abs(float(h.loc[gi, "rf_pred_rank_pct"]) - float(h.loc[bi, "rf_pred_rank_pct"])),
            })
    return pd.DataFrame(pairs)


def stable_features(effect_df: pd.DataFrame, periods: list[str], proportional: bool) -> list[str]:
    sub = effect_df[effect_df["target_block"].isin(periods)]
    n = len(periods)
    if n == 0:
        return []
    if proportional:
        need = int(math.ceil(0.75 * n))
        finite_need = need
    else:
        need = 6
        finite_need = 6
    keep = []
    for f, g in sub.groupby("feature"):
        vals = g.set_index("target_block")["std_effect"].reindex(periods).to_numpy(dtype=float)
        finite = vals[np.isfinite(vals)]
        if len(finite) < finite_need:
            continue
        pos = int(np.sum(finite > 0)); neg = int(np.sum(finite < 0))
        if max(pos, neg) < need:
            continue
        if float(np.median(np.abs(finite))) < 0.15:
            continue
        keep.append(str(f))
    return sorted(keep)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage6l-output")
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

    # Regenerate strict Stage6K blocks exactly.
    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    rng = np.random.default_rng(SEED)
    frames = []
    b = 1; pos = start0
    while True:
        pack = s6k.block_data(b, pos, cal, score, gross, close, meta, rng)
        if pack is None:
            break
        frames.append(pack[0]); b += 1; pos += FUTURE
    data = pd.concat(frames, ignore_index=True)
    block_ids = data[["block", "block_no"]].drop_duplicates().sort_values("block_no")["block"].astype(str).tolist()

    high_frames = []
    pair_frames = []
    effect_rows = []
    internal_cols = None

    for j in range(1, len(block_ids)):
        prev_b, target_b = block_ids[j-1], block_ids[j]
        train = data[data["block"] == prev_b].copy().reset_index(drop=True)
        test = data[data["block"] == target_b].copy().reset_index(drop=True)
        pred, _ = s6k.fit_rf(train, test)
        test["rf_pred"] = pred
        test["rf_pred_rank_pct"] = rank_pct(test["rf_pred"]).to_numpy()
        test["residual_rank"] = test["future_rank_pct"].astype(float) - test["rf_pred_rank_pct"].astype(float)
        n_hi = max(1, int(math.ceil(len(test) * RF_HIGH_FRAC)))
        high = test.nlargest(n_hi, "rf_pred").copy().reset_index(drop=True)
        high["future_rank_within_high"] = rank_pct(high["future_log_growth"]).to_numpy()

        decision_date = pd.Timestamp(high["decision_date"].iloc[0])
        d = int(cal.get_indexer([decision_date])[0])
        pool = s5.available_pool(close, meta, cal, d)
        past_dates = pd.DatetimeIndex(cal[d-LOOKBACK:d])
        ev = s6c.Eval(score, gross, past_dates, pool)

        feats = []
        for _, r in high.iterrows():
            members = tuple(str(r["members"]).split(","))
            feats.append(internal_features(ev, members, score, gross, past_dates))
        fdf = pd.DataFrame(feats)
        if internal_cols is None:
            internal_cols = list(fdf.columns)
        high = pd.concat([high.reset_index(drop=True), fdf.reset_index(drop=True)], axis=1)
        high["target_block"] = target_b
        high_frames.append(high)

        pairs = make_matches(high)
        if not pairs.empty:
            pairs["target_block"] = target_b
            pair_frames.append(pairs)
            for f in internal_cols:
                diffs = []
                for _, pr in pairs.iterrows():
                    gv = float(high.loc[int(pr["good_index"]), f])
                    bv = float(high.loc[int(pr["bad_index"]), f])
                    if np.isfinite(gv) and np.isfinite(bv):
                        diffs.append(gv - bv)
                sd = float(high[f].std(ddof=0))
                eff = float(np.mean(diffs) / sd) if diffs and np.isfinite(sd) and sd > 1e-12 else np.nan
                effect_rows.append({
                    "target_block": target_b,
                    "feature": f,
                    "family": feature_family(f),
                    "pair_n": len(diffs),
                    "mean_good_minus_bad": float(np.mean(diffs)) if diffs else np.nan,
                    "rfhigh_sd": sd,
                    "std_effect": eff,
                })

    high_all = pd.concat(high_frames, ignore_index=True)
    pairs_all = pd.concat(pair_frames, ignore_index=True) if pair_frames else pd.DataFrame()
    effects = pd.DataFrame(effect_rows)
    target_blocks = block_ids[1:]

    high_all.to_csv(out / "stage6l_rf_high_samples.csv", index=False)
    pairs_all.to_csv(out / "stage6l_matched_pairs.csv", index=False)
    effects.to_csv(out / "stage6l_matched_effects.csv", index=False)

    stable = stable_features(effects, target_blocks, proportional=False)
    fams = sorted(set(feature_family(f) for f in stable))
    stage1_pass = bool(len(stable) >= 3 and len(fams) >= 2)

    stage2_metrics = []
    selection_rows = []
    if stage1_pass:
        for test_b in target_blocks[3:]:  # B05 onward: three earlier target blocks minimum
            test_no = target_blocks.index(test_b)
            hist_blocks = target_blocks[:test_no]
            selected = stable_features(effects, hist_blocks, proportional=True)
            selection_rows.append({
                "test_block": test_b,
                "history_blocks": ",".join(hist_blocks),
                "selected_n": len(selected),
                "selected_features": ",".join(selected),
            })
            tr = high_all[high_all["target_block"].isin(hist_blocks)].copy()
            te = high_all[high_all["target_block"] == test_b].copy()
            if len(selected) < 2:
                pred2 = np.zeros(len(te), dtype=float)
            else:
                mu = tr[selected].replace([np.inf, -np.inf], np.nan).mean(axis=0)
                sd = tr[selected].replace([np.inf, -np.inf], np.nan).std(axis=0).replace(0, 1.0)
                xtr = tr[selected].replace([np.inf, -np.inf], np.nan).fillna(mu)
                xte = te[selected].replace([np.inf, -np.inf], np.nan).fillna(mu)
                xtr = (xtr - mu) / sd
                xte = (xte - mu) / sd
                counts = tr.groupby("target_block")["target_block"].transform("size").astype(float)
                weights = 1.0 / counts
                model = Ridge(alpha=ALPHA, fit_intercept=True)
                model.fit(xtr, tr["residual_rank"].astype(float), sample_weight=weights)
                pred2 = model.predict(xte)
            te = te.copy()
            te["second_score"] = pred2
            residual_ic = spearman(te["second_score"], te["residual_rank"])
            n_top = min(50, len(te))
            sec_top = te.nlargest(n_top, "second_score")
            rf_top = te.nlargest(n_top, "rf_pred")
            past_top = te.nlargest(n_top, "past126_log_growth")
            sec_pct = float(sec_top["future_rank_within_high"].mean())
            rf_pct = float(rf_top["future_rank_within_high"].mean())
            past_pct = float(past_top["future_rank_within_high"].mean())
            stage2_metrics.append({
                "test_block": test_b,
                "selected_n": len(selected),
                "residual_spearman": residual_ic,
                "positive_residual_ic": bool(np.isfinite(residual_ic) and residual_ic > 0),
                "second_top50_future_pct_within_high": sec_pct,
                "rf_top50_future_pct_within_high": rf_pct,
                "past126_top50_future_pct_within_high": past_pct,
                "second_minus_rf_top50_pct": sec_pct - rf_pct,
            })

    pd.DataFrame(selection_rows).to_csv(out / "stage6l_chrono_feature_selection.csv", index=False)
    m2 = pd.DataFrame(stage2_metrics)
    m2.to_csv(out / "stage6l_second_layer_metrics.csv", index=False)

    if stage1_pass and len(m2) == 5:
        med_ic = float(m2["residual_spearman"].median())
        pos_n = int((m2["residual_spearman"] > 0).sum())
        med_top = float(m2["second_top50_future_pct_within_high"].median())
        med_gain = float(m2["second_minus_rf_top50_pct"].median())
        gates2 = {
            "median_residual_ic_gt_0_10": med_ic > 0.10,
            "positive_residual_ic_ge_4_of_5": pos_n >= 4,
            "median_second_top50_pct_gt_0_60": med_top > 0.60,
            "median_top50_gain_vs_rf_ge_0_05": med_gain >= 0.05,
        }
        stage2_pass = bool(all(gates2.values()))
    else:
        med_ic = med_top = med_gain = np.nan
        pos_n = 0
        gates2 = {}
        stage2_pass = False

    stable_table = []
    for f in stable:
        vals = effects[effects["feature"] == f].set_index("target_block")["std_effect"].reindex(target_blocks).to_numpy(dtype=float)
        finite = vals[np.isfinite(vals)]
        stable_table.append({
            "feature": f,
            "family": feature_family(f),
            "positive_blocks": int(np.sum(finite > 0)),
            "negative_blocks": int(np.sum(finite < 0)),
            "median_std_effect": float(np.median(finite)) if len(finite) else np.nan,
            "median_abs_std_effect": float(np.median(np.abs(finite))) if len(finite) else np.nan,
        })
    pd.DataFrame(stable_table).to_csv(out / "stage6l_stable_traits.csv", index=False)

    if not stage1_pass:
        decision = "no_stable_internal_false_positive_structure"
    elif not stage2_pass:
        decision = "stable_internal_structure_but_second_layer_not_oos_supported"
    else:
        decision = "second_layer_internal_quality_supported"

    summary = {
        "study": "OURE Stage6L RF false-positive matched structural audit",
        "status": "completed",
        "rf_high_fraction": RF_HIGH_FRAC,
        "target_blocks": target_blocks,
        "internal_feature_n": len(internal_cols or []),
        "stable_trait_n": len(stable),
        "stable_trait_families": fams,
        "stable_traits": stable,
        "stage1_gate_pass": stage1_pass,
        "stage2_run": bool(stage1_pass),
        "stage2_metrics": {
            "median_residual_spearman": None if not np.isfinite(med_ic) else med_ic,
            "positive_residual_ic_n": pos_n,
            "median_second_top50_future_pct_within_high": None if not np.isfinite(med_top) else med_top,
            "median_top50_gain_vs_rf": None if not np.isfinite(med_gain) else med_gain,
        },
        "stage2_gates": gates2,
        "stage2_gate_pass": stage2_pass,
        "decision": decision,
        "warning": "One-shot preregistered stage. Future outcomes only define residual/good-bad labels; all structural X is past-only. No search authorization follows automatically.",
    }
    (out / "oure_stage6l_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
