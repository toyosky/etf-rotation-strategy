#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage5_history_transfer as s5
import optimal_universe_reverse_engineering.oure_stage6c_fullmarket_2022_2024_k_frontier as s6c
import optimal_universe_reverse_engineering.oure_stage6f_rf_surrogate_value as s6g
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

SEED = 20260914
H = 126
TRAIN_BLOCKS = 3
K = 30


def rank_pct(x: pd.Series) -> pd.Series:
    return s6g.rank_pct(pd.Series(x, dtype=float))


def spearman(a, b) -> float:
    v = s6g.spearman(a, b)
    return float(v) if np.isfinite(v) else np.nan


def robust_score_from_cols(df: pd.DataFrame, cols: list[str]) -> np.ndarray:
    rv = df[cols].to_numpy(float)
    med = np.median(rv, axis=1)
    q25 = np.quantile(rv, 0.25, axis=1)
    return 0.5 * med + 0.5 * q25


def block_starts(cal: pd.DatetimeIndex, start0: int):
    out = []
    b = 1
    pos = int(start0)
    while pos + H <= len(cal) - 2:
        out.append((b, pos))
        b += 1
        pos += H
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage7d-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng); bars["symbol"] = bars["symbol"].astype(str)
    feat = build_features(bars); feat["symbol"] = feat["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)
    meta = pd.read_sql_query(text("select symbol,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    starts = block_starts(cal, start0)
    common_start = start0 + 3 * H
    common_end = start0 + 9 * H

    corr_rows = []
    metric_rows = []
    loo_rows = []
    winner_rows = []
    candidate_rows = []

    for ti in range(TRAIN_BLOCKS, len(starts)):
        bno, pos = starts[ti]
        if pos < common_start or pos + H > common_end:
            continue
        hist = starts[ti-TRAIN_BLOCKS:ti]
        involved = hist + [starts[ti]]
        pools = [set(s5.available_pool(close, meta, cal, int(p))) for _, p in involved]
        common = sorted(set.intersection(*pools))
        if len(common) < K:
            raise RuntimeError(f"B{bno:02d}: common pool too small {len(common)}")

        recent_dates = pd.DatetimeIndex(cal[pos-H:pos])
        fut_dates = pd.DatetimeIndex(cal[pos:pos+H])
        recent_ev = s6c.Eval(score, gross, recent_dates, common)
        future_ev = s6c.Eval(score, gross, fut_dates, common)
        rng = np.random.default_rng(SEED + bno * 1009)
        combo_family, _, _ = s6g.build_family_library(recent_ev, common, rng)
        combos = list(combo_family.keys())

        hist_evs = []
        for _, hp in hist:
            hdates = pd.DatetimeIndex(cal[hp:hp+H])
            hist_evs.append(s6c.Eval(score, gross, hdates, common))

        rows = []
        for u in combos:
            hlogs = [float(ev.evaluate(u)["log_growth"]) for ev in hist_evs]
            fut = future_ev.evaluate(u)
            row = {
                "block": f"B{bno:02d}",
                "block_no": int(bno),
                "decision_date": str(pd.Timestamp(cal[pos]).date()),
                "end_date": str(pd.Timestamp(fut_dates[-1]).date()),
                "members": ",".join(u),
                "future_log_growth": float(fut["log_growth"]),
                "future_total_return": float(fut["total_return"]),
            }
            for j, val in enumerate(hlogs, 1):
                row[f"hist{j}_log_growth"] = val
            rows.append(row)
        df = pd.DataFrame(rows)
        df["future_rank_pct"] = rank_pct(df["future_log_growth"]).to_numpy()
        rcols = []
        for j in range(1, 4):
            rc = f"r{j}"
            df[rc] = rank_pct(df[f"hist{j}_log_growth"]).to_numpy()
            rcols.append(rc)

        df["rank_mean"] = df[rcols].mean(axis=1)
        df["rank_std"] = df[rcols].std(axis=1, ddof=0)
        df["rank_range"] = df[rcols].max(axis=1) - df[rcols].min(axis=1)
        df["robust_score"] = robust_score_from_cols(df, rcols)

        # Cross-block persistence across all candidate Universes.
        pair_corrs = {
            "r1_r2": spearman(df["r1"], df["r2"]),
            "r2_r3": spearman(df["r2"], df["r3"]),
            "r1_r3": spearman(df["r1"], df["r3"]),
        }
        corr_rows.append({
            "block": f"B{bno:02d}",
            "decision_date": str(pd.Timestamp(cal[pos]).date()),
            **pair_corrs,
            "median_pair_corr": float(np.nanmedian(list(pair_corrs.values()))),
        })

        # Future predictive diagnostics for each component and aggregation.
        specs = {
            "r1": df["r1"], "r2": df["r2"], "r3": df["r3"],
            "rank_mean": df["rank_mean"],
            "neg_rank_std": -df["rank_std"],
            "neg_rank_range": -df["rank_range"],
            "robust_score": df["robust_score"],
        }
        for name, s in specs.items():
            metric_rows.append({
                "block": f"B{bno:02d}",
                "decision_date": str(pd.Timestamp(cal[pos]).date()),
                "signal": name,
                "future_spearman": spearman(s, df["future_log_growth"]),
            })

        full_top50 = set(df.nlargest(min(50, len(df)), "robust_score")["members"])
        winner = df.nlargest(1, "robust_score").iloc[0]
        win_member = str(winner["members"])
        win_prof = [float(winner[f"r{j}"]) for j in range(1,4)]
        winner_rows.append({
            "block": f"B{bno:02d}",
            "decision_date": str(pd.Timestamp(cal[pos]).date()),
            "members": win_member,
            "r1": win_prof[0], "r2": win_prof[1], "r3": win_prof[2],
            "rank_mean": float(winner["rank_mean"]),
            "rank_std": float(winner["rank_std"]),
            "rank_range": float(winner["rank_range"]),
            "robust_score": float(winner["robust_score"]),
            "future_rank_pct": float(winner["future_rank_pct"]),
            "future_total_return": float(winner["future_total_return"]),
            "all_three_above_median": bool(all(x >= 0.5 for x in win_prof)),
            "two_of_three_above_median": bool(sum(x >= 0.5 for x in win_prof) >= 2),
            "min_hist_rank": float(min(win_prof)),
        })

        for omit in (1,2,3):
            kept = [f"r{j}" for j in (1,2,3) if j != omit]
            loo_col = f"loo{omit}"
            df[loo_col] = robust_score_from_cols(df, kept)
            loo_top50 = set(df.nlargest(min(50, len(df)), loo_col)["members"])
            denom = len(full_top50 | loo_top50)
            jacc = len(full_top50 & loo_top50) / denom if denom else np.nan
            win_row = df.loc[df["members"] == win_member].iloc[0]
            loo_pct = float(rank_pct(df[loo_col]).loc[win_row.name])
            loo_rows.append({
                "block": f"B{bno:02d}",
                "decision_date": str(pd.Timestamp(cal[pos]).date()),
                "omitted_hist_block": omit,
                "score_spearman_full_vs_loo": spearman(df["robust_score"], df[loo_col]),
                "top50_jaccard_full_vs_loo": float(jacc),
                "winner_in_loo_top50": bool(win_member in loo_top50),
                "winner_loo_rank_pct": loo_pct,
                "future_spearman_loo": spearman(df[loo_col], df["future_log_growth"]),
            })

        candidate_rows.append(df[["block","members","future_rank_pct","r1","r2","r3","rank_mean","rank_std","rank_range","robust_score"]])

    corrs = pd.DataFrame(corr_rows)
    metrics = pd.DataFrame(metric_rows)
    loo = pd.DataFrame(loo_rows)
    winners = pd.DataFrame(winner_rows)
    candidates = pd.concat(candidate_rows, ignore_index=True)

    corrs.to_csv(out / "stage7d_cross_block_persistence.csv", index=False)
    metrics.to_csv(out / "stage7d_future_signal_metrics.csv", index=False)
    loo.to_csv(out / "stage7d_loo_sensitivity.csv", index=False)
    winners.to_csv(out / "stage7d_winner_profiles.csv", index=False)
    candidates.to_csv(out / "stage7d_candidate_diagnostics.csv", index=False)

    signal_summary = metrics.groupby("signal")["future_spearman"].agg(["median","mean",lambda x: int((x>0).sum()),"count"]).reset_index()
    signal_summary.columns = ["signal","median_future_spearman","mean_future_spearman","positive_n","n"]
    signal_summary.to_csv(out / "stage7d_signal_summary.csv", index=False)

    med_pair_corr = float(corrs["median_pair_corr"].median())
    med_full_loo_corr = float(loo["score_spearman_full_vs_loo"].median())
    med_loo_jacc = float(loo["top50_jaccard_full_vs_loo"].median())
    winner_loo_share = float(loo["winner_in_loo_top50"].mean())
    robust_med = float(signal_summary.loc[signal_summary["signal"]=="robust_score","median_future_spearman"].iloc[0])
    indiv = signal_summary[signal_summary["signal"].isin(["r1","r2","r3"])]
    best_indiv_med = float(indiv["median_future_spearman"].max())
    mean_med = float(signal_summary.loc[signal_summary["signal"]=="rank_mean","median_future_spearman"].iloc[0])

    # Conservative mechanism classification; thresholds are fixed ex ante here.
    persistence_strong = med_pair_corr >= 0.25
    loo_stable = med_full_loo_corr >= 0.80 and med_loo_jacc >= 0.50 and winner_loo_share >= 2/3
    aggregation_gain = robust_med >= best_indiv_med + 0.03
    if persistence_strong and loo_stable and not aggregation_gain:
        verdict = "persistent_quality"
    elif (not persistence_strong) and loo_stable and aggregation_gain:
        verdict = "variance_reduction"
    elif loo_stable and (persistence_strong or aggregation_gain):
        verdict = "mixed"
    else:
        verdict = "unresolved"

    summary = {
        "study": "OURE Stage7D long-history mechanism audit",
        "status": "completed",
        "verdict": verdict,
        "target_blocks": int(len(corrs)),
        "median_cross_block_pair_spearman": med_pair_corr,
        "median_full_vs_loo_score_spearman": med_full_loo_corr,
        "median_full_vs_loo_top50_jaccard": med_loo_jacc,
        "winner_in_loo_top50_share": winner_loo_share,
        "robust_score_median_future_spearman": robust_med,
        "best_individual_block_median_future_spearman": best_indiv_med,
        "rank_mean_median_future_spearman": mean_med,
        "winner_all_three_above_median_share": float(winners["all_three_above_median"].mean()),
        "winner_two_of_three_above_median_share": float(winners["two_of_three_above_median"].mean()),
        "median_winner_min_hist_rank": float(winners["min_hist_rank"].median()),
        "rules": {
            "persistence_strong": bool(persistence_strong),
            "loo_stable": bool(loo_stable),
            "aggregation_gain": bool(aggregation_gain),
            "persistence_threshold": 0.25,
            "loo_score_corr_threshold": 0.80,
            "loo_top50_jaccard_threshold": 0.50,
            "winner_loo_share_threshold": 2/3,
            "aggregation_gain_threshold": 0.03,
        },
    }
    (out / "stage7d_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
