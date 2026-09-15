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


def block_starts(cal: pd.DatetimeIndex, start0: int):
    out, b, pos = [], 1, int(start0)
    while pos + H <= len(cal) - 2:
        out.append((b, pos)); b += 1; pos += H
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage7e-output")
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

    candidate_frames, signal_rows, align_rows, block_support_rows = [], [], [], []

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
        hist_evs = [s6c.Eval(score, gross, pd.DatetimeIndex(cal[hp:hp+H]), common) for _, hp in hist]

        rows = []
        for u in combos:
            hlogs = [float(ev.evaluate(u)["log_growth"]) for ev in hist_evs]
            fut = future_ev.evaluate(u)
            rows.append({
                "block": f"B{bno:02d}",
                "decision_date": str(pd.Timestamp(cal[pos]).date()),
                "members": ",".join(u),
                "future_log_growth": float(fut["log_growth"]),
                "future_total_return": float(fut["total_return"]),
                "hist1_log_growth": hlogs[0], "hist2_log_growth": hlogs[1], "hist3_log_growth": hlogs[2],
            })
        df = pd.DataFrame(rows)
        df["future_rank_pct"] = rank_pct(df["future_log_growth"]).to_numpy()
        for j in (1,2,3):
            df[f"r{j}"] = rank_pct(df[f"hist{j}_log_growth"]).to_numpy()
        rv = df[["r1","r2","r3"]].to_numpy(float)
        df["rank_mean"] = rv.mean(axis=1)
        df["min_rank"] = rv.min(axis=1)
        df["q25_rank"] = np.quantile(rv, 0.25, axis=1)
        df["second_worst_rank"] = np.median(rv, axis=1)
        df["all3_strength"] = np.exp(np.log(np.clip(rv, 1e-6, 1.0)).mean(axis=1))
        df["robust_score"] = 0.5 * df["second_worst_rank"] + 0.5 * df["q25_rank"]
        # Fixed within-block deciles of weakest historical rank.
        p = rank_pct(df["min_rank"]).to_numpy()
        df["min_rank_decile"] = np.minimum(10, np.maximum(1, np.ceil(p * 10).astype(int)))
        df["future_top_decile"] = df["future_rank_pct"] >= 0.90

        specs = ["robust_score","rank_mean","min_rank","q25_rank","second_worst_rank","all3_strength"]
        for name in specs:
            top50 = df.nlargest(min(50, len(df)), name)
            topdec = df.nlargest(max(1, int(np.ceil(len(df)*0.10))), name)
            win = df.nlargest(1, name).iloc[0]
            signal_rows.append({
                "block": f"B{bno:02d}", "signal": name,
                "future_spearman": spearman(df[name], df["future_log_growth"]),
                "top50_mean_future_pct": float(top50["future_rank_pct"].mean()),
                "topdec_mean_future_pct": float(topdec["future_rank_pct"].mean()),
                "selected_top1_future_pct": float(win["future_rank_pct"]),
            })

        robust_top50 = set(df.nlargest(min(50, len(df)), "robust_score")["members"])
        min_top50 = set(df.nlargest(min(50, len(df)), "min_rank")["members"])
        robust_win = df.nlargest(1, "robust_score").iloc[0]
        min_topdec = set(df.nlargest(max(1, int(np.ceil(len(df)*0.10))), "min_rank")["members"])
        align_rows.append({
            "block": f"B{bno:02d}",
            "robust_vs_min_spearman": spearman(df["robust_score"], df["min_rank"]),
            "top50_jaccard": len(robust_top50 & min_top50) / len(robust_top50 | min_top50),
            "robust_winner_min_rank_pct": float(rank_pct(df["min_rank"]).loc[robust_win.name]),
            "robust_top50_in_min_topdec_share": float(len(robust_top50 & min_topdec) / len(robust_top50)),
        })
        block_support_rows.append({
            "block": f"B{bno:02d}",
            "min_rank_future_spearman": spearman(df["min_rank"], df["future_log_growth"]),
        })
        candidate_frames.append(df)

    candidates = pd.concat(candidate_frames, ignore_index=True)
    signals = pd.DataFrame(signal_rows)
    align = pd.DataFrame(align_rows)
    block_support = pd.DataFrame(block_support_rows)

    dec = candidates.groupby(["block","min_rank_decile"], as_index=False).agg(
        mean_future_rank_pct=("future_rank_pct","mean"),
        median_future_rank_pct=("future_rank_pct","median"),
        mean_future_log_growth=("future_log_growth","mean"),
        future_top_decile_share=("future_top_decile","mean"),
        n=("members","size"),
    )
    dec_agg = dec.groupby("min_rank_decile", as_index=False).agg(
        mean_future_rank_pct=("mean_future_rank_pct","mean"),
        median_future_rank_pct=("median_future_rank_pct","mean"),
        mean_future_log_growth=("mean_future_log_growth","mean"),
        future_top_decile_share=("future_top_decile_share","mean"),
    )

    candidates.to_csv(out / "stage7e_candidate_diagnostics.csv", index=False)
    signals.to_csv(out / "stage7e_signal_metrics.csv", index=False)
    align.to_csv(out / "stage7e_robust_alignment.csv", index=False)
    block_support.to_csv(out / "stage7e_block_support.csv", index=False)
    dec.to_csv(out / "stage7e_deciles_by_block.csv", index=False)
    dec_agg.to_csv(out / "stage7e_deciles_aggregate.csv", index=False)

    sig_summary = signals.groupby("signal", as_index=False).agg(
        median_future_spearman=("future_spearman","median"),
        mean_top50_future_pct=("top50_mean_future_pct","mean"),
        mean_topdec_future_pct=("topdec_mean_future_pct","mean"),
        median_selected_top1_future_pct=("selected_top1_future_pct","median"),
        positive_ic_n=("future_spearman", lambda x: int((x>0).sum())),
        n=("future_spearman","size"),
    )
    sig_summary.to_csv(out / "stage7e_signal_summary.csv", index=False)

    d1 = dec_agg.loc[dec_agg["min_rank_decile"]==1].iloc[0]
    d10 = dec_agg.loc[dec_agg["min_rank_decile"]==10].iloc[0]
    c1 = spearman(dec_agg["min_rank_decile"], dec_agg["mean_future_rank_pct"]) > 0
    c2 = float(d10["mean_future_rank_pct"]) > float(d1["mean_future_rank_pct"])
    c3 = float(d10["future_top_decile_share"]) > float(d1["future_top_decile_share"])
    pos_blocks = int((block_support["min_rank_future_spearman"] > 0).sum())
    c4 = pos_blocks >= 4
    passed = int(c1) + int(c2) + int(c3) + int(c4)
    verdict = "tail_consensus_supported" if passed == 4 else "partial_support" if passed >= 2 else "not_supported"

    summary = {
        "study": "OURE Stage7E tail-consensus mechanism test",
        "status": "completed",
        "verdict": verdict,
        "support_criteria_passed": passed,
        "decile_spearman": spearman(dec_agg["min_rank_decile"], dec_agg["mean_future_rank_pct"]),
        "d1_mean_future_rank_pct": float(d1["mean_future_rank_pct"]),
        "d10_mean_future_rank_pct": float(d10["mean_future_rank_pct"]),
        "d1_future_top_decile_share": float(d1["future_top_decile_share"]),
        "d10_future_top_decile_share": float(d10["future_top_decile_share"]),
        "positive_min_rank_ic_blocks": pos_blocks,
        "target_blocks": int(len(block_support)),
        "median_robust_vs_min_spearman": float(align["robust_vs_min_spearman"].median()),
        "median_robust_winner_min_rank_pct": float(align["robust_winner_min_rank_pct"].median()),
        "criteria": {"positive_decile_gradient": bool(c1), "d10_beats_d1": bool(c2), "d10_topdec_hit_beats_d1": bool(c3), "positive_blocks_at_least_4_of_6": bool(c4)},
    }
    (out / "stage7e_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
