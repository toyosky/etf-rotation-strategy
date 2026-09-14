#!/usr/bin/env python3
"""OURE Stage4B: exact local pruning audit around the Stage3B K30 champion.

Mechanism-only audit. No new full-market search and no feature fitting.
Tests whether the large-K elite is merely padded with redundant names or whether
its members form a materially different regime/leader relay structure.
"""
from __future__ import annotations

import argparse
import itertools
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

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
import optimal_universe_reverse_engineering.oure_stage3_exposure_disjoint_search as s3

CASH = "511220"
START = pd.Timestamp("2021-01-01")


def parse_members(x: str) -> list[str]:
    return [z.strip() for z in str(x).split(",") if z.strip() and z.strip() != CASH]


def leader_profile(ev: s3.Evaluator, members: list[str], meta: pd.DataFrame, label: str) -> pd.DataFrame:
    key = sorted(set(members))
    t = len(ev.signal_dates)
    best = np.where(np.isfinite(ev.cash_score), ev.cash_score, -np.inf).copy()
    target = np.full(t, -1, dtype=np.int32)
    for sym in key:
        j = ev.index[sym]
        v = ev.score[:, j]
        choose = np.isfinite(v) & (v > best)
        target[choose] = j
        best[choose] = v[choose]

    rows = []
    for sym in key:
        j = ev.index[sym]
        hit = target == j
        dates = ev.signal_dates[hit]
        # contiguous leader-run count
        run_count = 0
        prev = False
        for v in hit:
            if v and not prev:
                run_count += 1
            prev = bool(v)
        m = meta.loc[meta["symbol"] == sym]
        name = None if m.empty else m.iloc[0].get("name")
        rb = None if m.empty else m.iloc[0].get("risk_bucket")
        rows.append({
            "universe": label,
            "symbol": sym,
            "name": name,
            "risk_bucket": rb,
            "leader_days": int(hit.sum()),
            "leader_share_all_days": float(hit.mean()),
            "leader_share_invested_days": float(hit.sum() / max(1, np.sum(target >= 0))),
            "leader_run_count": int(run_count),
            "first_leader_date": None if len(dates) == 0 else str(dates[0].date()),
            "last_leader_date": None if len(dates) == 0 else str(dates[-1].date()),
        })
    return pd.DataFrame(rows).sort_values("leader_days", ascending=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--stage1-dir", required=True)
    ap.add_argument("--stage3b-dir", required=True)
    ap.add_argument("--output-dir", default="oure-stage4b-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    st1 = pd.read_csv(Path(args.stage1_dir) / "all_fix15_subsets.csv")
    k7row = st1.loc[st1["k_including_cash"] == 7].sort_values("log_growth", ascending=False).iloc[0]
    small = parse_members(k7row["members"])

    st3 = pd.read_csv(Path(args.stage3b_dir) / "elite_universes.csv")
    bigrow = st3.sort_values("log_growth", ascending=False).iloc[0]
    big = parse_members(bigrow["members"])
    if len(big) != 30:
        raise RuntimeError(f"expected Stage3B champion K30 risk assets, got {len(big)}")

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng); bars["symbol"] = bars["symbol"].astype(str)
    features = build_features(bars); features["symbol"] = features["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, features)

    meta = pd.read_sql_query(text("select symbol,name,risk_bucket from public.instrument_metadata_current"), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    union = sorted(set(big) | set(small))
    s3.MAX_NONCASH = max(40, len(union))
    ev = s3.Evaluator(score, gross, cal, union)

    # Leader occupation structure.
    leader = pd.concat([
        leader_profile(ev, small, meta, "small_k6_risk"),
        leader_profile(ev, big, meta, "large_k30_risk"),
    ], ignore_index=True)
    leader.to_csv(out / "leader_occupation.csv", index=False)

    base = ev.evaluate(big)
    base_log = float(base["log_growth"])

    # Exact local deletion shells: all 1-, 2-, and 3-name removals.
    shell_rows = []
    best_by_r = []
    for r in (1, 2, 3):
        best_rec = None
        n = 0
        improved = 0
        for removed in itertools.combinations(big, r):
            keep = sorted(set(big) - set(removed))
            rec = ev.evaluate(keep)
            dlog = float(rec["log_growth"] - base_log)
            n += 1
            if dlog > 1e-12:
                improved += 1
            row = {
                "removed_n": r,
                "removed": ",".join(removed),
                "remaining_k": len(keep),
                "log_growth": float(rec["log_growth"]),
                "delta_log_vs_k30": dlog,
                "final_wealth_change_pct": float((np.exp(dlog) - 1.0) * 100.0),
                "total_return": float(rec["total_return"]),
                "switch_events": int(rec["switch_events"]),
                "mean_top1_tenure": float(rec["mean_top1_tenure"]),
            }
            shell_rows.append(row)
            if best_rec is None or row["log_growth"] > best_rec["log_growth"]:
                best_rec = row
        best_by_r.append({
            "removed_n": r,
            "n_combinations": n,
            "n_improving": improved,
            "best_removed": best_rec["removed"],
            "best_delta_log_vs_k30": best_rec["delta_log_vs_k30"],
            "best_final_wealth_change_pct": best_rec["final_wealth_change_pct"],
            "best_remaining_total_return": best_rec["total_return"],
            "best_switch_events": best_rec["switch_events"],
            "best_mean_top1_tenure": best_rec["mean_top1_tenure"],
        })
    shell = pd.DataFrame(shell_rows)
    shell.sort_values(["removed_n","log_growth"], ascending=[True,False]).to_csv(out / "exact_deletion_shells_1_to_3.csv", index=False)
    pd.DataFrame(best_by_r).to_csv(out / "best_exact_deletion_by_depth.csv", index=False)

    # Greedy forced pruning: at each step delete the member whose removal hurts least / helps most.
    cur = set(big)
    path = []
    prev_log = base_log
    while len(cur) >= 6:
        rec = ev.evaluate(cur)
        path.append({
            "k_noncash": len(cur),
            "members": ",".join(sorted(cur)),
            "log_growth": float(rec["log_growth"]),
            "delta_log_vs_original_k30": float(rec["log_growth"] - base_log),
            "final_wealth_change_pct_vs_k30": float((np.exp(rec["log_growth"] - base_log) - 1.0) * 100.0),
            "step_delta_log": float(rec["log_growth"] - prev_log) if len(cur) < 30 else 0.0,
            "total_return": float(rec["total_return"]),
            "switch_events": int(rec["switch_events"]),
            "mean_top1_tenure": float(rec["mean_top1_tenure"]),
        })
        if len(cur) == 6:
            break
        candidates = []
        for x in sorted(cur):
            nr = ev.evaluate(cur - {x})
            candidates.append((float(nr["log_growth"]), x))
        new_log, drop = max(candidates)
        prev_log = float(rec["log_growth"])
        cur.remove(drop)
        path[-1]["next_drop"] = drop
        path[-1]["next_drop_delta_log"] = float(new_log - prev_log)
    pd.DataFrame(path).to_csv(out / "greedy_forced_pruning_path.csv", index=False)

    # Compact summary.
    big_lead = leader[leader["universe"] == "large_k30_risk"].copy()
    small_lead = leader[leader["universe"] == "small_k6_risk"].copy()
    top5_big_share = float(big_lead.head(5)["leader_share_invested_days"].sum())
    top10_big_share = float(big_lead.head(10)["leader_share_invested_days"].sum())
    summary = {
        "study": "OURE Stage4B K30 pruning and leader-occupation audit",
        "status": "completed",
        "k30_base": base,
        "k6_members": small,
        "k30_members": big,
        "k30_top5_leader_share": top5_big_share,
        "k30_top10_leader_share": top10_big_share,
        "k30_zero_leader_members": int((big_lead["leader_days"] == 0).sum()),
        "k6_top3_leader_share": float(small_lead.head(3)["leader_share_invested_days"].sum()),
        "exact_deletion_best_by_depth": best_by_r,
        "interpretation_gate": "If no 1/2/3 deletion improves K30, large-K value is not explained by a few trivially removable passengers. If forced pruning exhibits a long plateau, the set may still contain redundancy even without profitable local deletion.",
    }
    (out / "oure_stage4b_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
