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
import optimal_universe_reverse_engineering.oure_stage6e_rf_k30_rank as s6e
import optimal_universe_reverse_engineering.oure_stage6f_rf_surrogate_value as s6g
import optimal_universe_reverse_engineering.oure_stage6k_adjacent_126_transfer as s6k
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

LOOKBACK = 126
FUTURE = 126
SEED = 20260914
TRAIN_BLOCKS = 3
RANDOM_PATHS = 10000


def rank_pct(x: pd.Series) -> pd.Series:
    return s6g.rank_pct(pd.Series(x, dtype=float))


def spearman(a, b) -> float:
    v = s6g.spearman(a, b)
    return float(v) if np.isfinite(v) else np.nan


def score_metrics(df: pd.DataFrame, score_col: str, rule: str) -> dict:
    z = df.copy()
    score = z[score_col].astype(float)
    ic = spearman(score, z["future_log_growth"])
    n50 = min(50, len(z))
    top50 = z.assign(_score=score).nlargest(n50, "_score")
    ndec = max(1, int(np.ceil(len(z) * 0.10)))
    topdec = z.assign(_score=score).nlargest(ndec, "_score")
    winner = z.assign(_score=score).nlargest(1, "_score").iloc[0]
    return {
        "target_block": str(z["target_block"].iloc[0]),
        "decision_date": str(z["decision_date"].iloc[0]),
        "rule": rule,
        "candidate_n": int(len(z)),
        "spearman": ic,
        "positive_ic": bool(np.isfinite(ic) and ic > 0),
        "top50_mean_actual_percentile": float(top50["future_rank_pct"].mean()),
        "top_decile_log_lift": float(topdec["future_log_growth"].mean() - z["future_log_growth"].mean()),
        "selected_members": str(winner["members"]),
        "selected_actual_percentile": float(winner["future_rank_pct"]),
        "selected_future_log_growth": float(winner["future_log_growth"]),
        "selected_future_total_return": float(winner["future_total_return"]),
        "selected_score": float(winner[score_col]),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage7a-output")
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

    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    starts = []
    b = 1
    pos = start0
    while pos + FUTURE <= len(cal) - 2:
        starts.append((b, pos))
        b += 1
        pos += FUTURE
    if len(starts) < 6:
        raise RuntimeError(f"too few blocks: {len(starts)}")

    # Rebuild standard Stage6K block libraries exactly for previous-block RF baselines.
    std_rng = np.random.default_rng(SEED)
    std_frames = []
    for bno, pos in starts:
        pack = s6k.block_data(bno, pos, cal, score, gross, close, meta, std_rng)
        if pack is None:
            break
        std_frames.append(pack[0])
    std_data = pd.concat(std_frames, ignore_index=True)

    candidate_frames = []
    metric_rows = []
    selection_rows = []
    target_meta = []

    for ti in range(TRAIN_BLOCKS, len(starts)):
        target_no, target_pos = starts[ti]
        target_bid = f"B{target_no:02d}"
        hist = starts[ti-TRAIN_BLOCKS:ti]
        involved = hist + [starts[ti]]

        pools = []
        for _, p in involved:
            pools.append(set(s5.available_pool(close, meta, cal, int(p))))
        common = sorted(set.intersection(*pools))
        if len(common) < s6g.K:
            raise RuntimeError(f"{target_bid}: common pool too small: {len(common)}")

        past_dates = pd.DatetimeIndex(cal[target_pos-LOOKBACK:target_pos])
        target_dates = pd.DatetimeIndex(cal[target_pos:target_pos+FUTURE])
        past_ev = s6c.Eval(score, gross, past_dates, common)
        target_ev = s6c.Eval(score, gross, target_dates, common)

        # Fixed target-specific deterministic library, generated from X<=t only.
        lib_rng = np.random.default_rng(SEED + target_no * 1009)
        combo_family, _, _ = s6g.build_family_library(past_ev, common, lib_rng)
        combos = list(combo_family.keys())

        hist_evs = []
        hist_bids = []
        for hbno, hpos in hist:
            hdates = pd.DatetimeIndex(cal[hpos:hpos+FUTURE])
            hist_evs.append(s6c.Eval(score, gross, hdates, common))
            hist_bids.append(f"B{hbno:02d}")

        rows = []
        for u in combos:
            hlogs = [float(ev.evaluate(u)["log_growth"]) for ev in hist_evs]
            fut = target_ev.evaluate(u)
            fr = s6e.feature_row(past_ev, u)
            row = {
                "target_block": target_bid,
                "decision_date": str(pd.Timestamp(cal[target_pos]).date()),
                "future_end_date": str(pd.Timestamp(target_dates[-1]).date()),
                "common_pool_n": len(common),
                "family_id": combo_family[u],
                "members": ",".join(u),
                "future_log_growth": float(fut["log_growth"]),
                "future_total_return": float(fut["total_return"]),
                **fr,
            }
            for k, (hb, val) in enumerate(zip(hist_bids, hlogs), start=1):
                row[f"hist{k}_block"] = hb
                row[f"hist{k}_log_growth"] = val
            rows.append(row)
        df = pd.DataFrame(rows)
        df["future_rank_pct"] = rank_pct(df["future_log_growth"]).to_numpy()

        rank_cols = []
        for k in range(1, TRAIN_BLOCKS + 1):
            rc = f"hist{k}_rank_pct"
            df[rc] = rank_pct(df[f"hist{k}_log_growth"]).to_numpy()
            rank_cols.append(rc)
        rv = df[rank_cols].to_numpy(dtype=float)
        df["robust_median_rank"] = np.median(rv, axis=1)
        df["robust_q25_rank"] = np.quantile(rv, 0.25, axis=1)
        df["robust_score"] = 0.5 * df["robust_median_rank"] + 0.5 * df["robust_q25_rank"]
        df["latest126_score"] = df[f"hist{TRAIN_BLOCKS}_log_growth"].astype(float)

        # Previous-block RF trained on the exact completed standard Stage6K library.
        prev_bid = f"B{hist[-1][0]:02d}"
        train_rf = std_data[std_data["block"] == prev_bid].copy().reset_index(drop=True)
        test_features = df.copy().reset_index(drop=True)
        rf_pred, _ = s6k.fit_rf(train_rf, test_features)
        df["previous_block_rf_score"] = rf_pred

        for rule, col in [
            ("robust_3block", "robust_score"),
            ("latest126", "latest126_score"),
            ("previous_block_rf", "previous_block_rf_score"),
        ]:
            met = score_metrics(df, col, rule)
            metric_rows.append(met)
            selection_rows.append({k: met[k] for k in [
                "target_block", "decision_date", "rule", "selected_members",
                "selected_actual_percentile", "selected_future_log_growth",
                "selected_future_total_return", "selected_score"
            ]})

        candidate_frames.append(df)
        target_meta.append({
            "target_block": target_bid,
            "decision_date": str(pd.Timestamp(cal[target_pos]).date()),
            "future_end_date": str(pd.Timestamp(target_dates[-1]).date()),
            "training_blocks": ",".join(hist_bids),
            "common_pool_n": len(common),
            "candidate_n": len(df),
        })

    candidates = pd.concat(candidate_frames, ignore_index=True)
    metrics = pd.DataFrame(metric_rows)
    selections = pd.DataFrame(selection_rows)
    pd.DataFrame(target_meta).to_csv(out / "stage7a_targets.csv", index=False)
    candidates.to_csv(out / "stage7a_candidates.csv", index=False)
    metrics.to_csv(out / "stage7a_metrics.csv", index=False)
    selections.to_csv(out / "stage7a_selections.csv", index=False)

    # Path summaries for the three fixed rules.
    path_rows = []
    path_summary = {}
    for rule, g in selections.groupby("rule"):
        g = g.sort_values("target_block")
        logs = g["selected_future_log_growth"].astype(float).to_numpy()
        rets = g["selected_future_total_return"].astype(float).to_numpy()
        total_log = float(np.sum(logs))
        total_ret = float(np.exp(total_log) - 1.0)
        worst = float(np.min(rets))
        path_summary[rule] = {
            "block_n": int(len(g)),
            "compounded_log_growth": total_log,
            "compounded_total_return": total_ret,
            "worst_block_total_return": worst,
            "median_selected_actual_percentile": float(g["selected_actual_percentile"].median()),
        }
        path_rows.append({"rule": rule, **path_summary[rule]})
    pd.DataFrame(path_rows).to_csv(out / "stage7a_path_summary.csv", index=False)

    # Random choice from each identical target-specific candidate library.
    rrng = np.random.default_rng(SEED + 777777)
    target_ids = sorted(candidates["target_block"].unique())
    random_logs = np.zeros(RANDOM_PATHS, dtype=float)
    random_worst = np.full(RANDOM_PATHS, np.inf, dtype=float)
    for tb in target_ids:
        z = candidates[candidates["target_block"] == tb]
        idx = rrng.integers(0, len(z), size=RANDOM_PATHS)
        l = z["future_log_growth"].to_numpy(dtype=float)[idx]
        r = z["future_total_return"].to_numpy(dtype=float)[idx]
        random_logs += l
        random_worst = np.minimum(random_worst, r)
    random_returns = np.exp(random_logs) - 1.0
    random_summary = {
        "paths": RANDOM_PATHS,
        "median_compounded_log_growth": float(np.median(random_logs)),
        "median_compounded_total_return": float(np.median(random_returns)),
        "p10_compounded_total_return": float(np.quantile(random_returns, 0.10)),
        "p90_compounded_total_return": float(np.quantile(random_returns, 0.90)),
        "median_worst_block_total_return": float(np.median(random_worst)),
    }

    robust_m = metrics[metrics["rule"] == "robust_3block"].copy()
    robust_p = path_summary["robust_3block"]
    latest_p = path_summary["latest126"]
    rf_p = path_summary["previous_block_rf"]
    robust_log = robust_p["compounded_log_growth"]
    robust_random_pct = float(np.mean(random_logs <= robust_log))

    gates = {
        "median_spearman_gt_0_10": bool(float(robust_m["spearman"].median()) > 0.10),
        "positive_ic_at_least_4_of_6": bool(int((robust_m["spearman"] > 0).sum()) >= 4),
        "median_top50_actual_percentile_gt_0_55": bool(float(robust_m["top50_mean_actual_percentile"].median()) > 0.55),
        "median_selected_top1_actual_percentile_gt_0_60": bool(float(robust_m["selected_actual_percentile"].median()) > 0.60),
        "path_beats_both_and_worst_block_beats_both": bool(
            robust_p["compounded_log_growth"] > max(latest_p["compounded_log_growth"], rf_p["compounded_log_growth"])
            and robust_p["worst_block_total_return"] > max(latest_p["worst_block_total_return"], rf_p["worst_block_total_return"])
        ),
    }
    pass_n = int(sum(gates.values()))
    if pass_n == len(gates):
        decision = "robust_selection_supported"
    elif pass_n >= 3:
        decision = "mixed_robust_signal"
    else:
        decision = "robust_objective_not_supported"

    rule_summary = {}
    for rule, g in metrics.groupby("rule"):
        rule_summary[rule] = {
            "target_n": int(len(g)),
            "median_spearman": float(g["spearman"].median()),
            "positive_ic_n": int((g["spearman"] > 0).sum()),
            "median_top50_actual_percentile": float(g["top50_mean_actual_percentile"].median()),
            "median_top_decile_log_lift": float(g["top_decile_log_lift"].median()),
            "median_selected_actual_percentile": float(g["selected_actual_percentile"].median()),
            **path_summary[rule],
        }

    summary = {
        "study": "OURE Stage7A robust K30 across prior regimes strict OOS",
        "status": "completed",
        "decision": decision,
        "target_blocks": target_ids,
        "train_block_count": TRAIN_BLOCKS,
        "robust_formula": "0.5*median(prior3 block percentile ranks)+0.5*q25(prior3 block percentile ranks)",
        "rules": rule_summary,
        "random": random_summary,
        "robust_path_random_percentile": robust_random_pct,
        "gates": gates,
        "gates_passed": pass_n,
    }
    (out / "stage7a_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
