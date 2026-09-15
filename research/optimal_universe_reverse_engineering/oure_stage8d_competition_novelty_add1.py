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

import optimal_universe_reverse_engineering.oure_stage8a_opportunity30 as s8a
import optimal_universe_reverse_engineering.oure_stage8b_opportunity_k_frontier as s8b
import optimal_universe_reverse_engineering.oure_stage8c_marginal_opportunity_capture as s8c
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

HIST_SESSIONS = 378
START_EXEC = pd.Timestamp("2021-01-01")
FIX15 = tuple(s8a.FIX15)


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    u = int(np.count_nonzero(a | b))
    return float(np.count_nonzero(a & b) / u) if u else 0.0


def novelty_pick(score: pd.DataFrame, dates: pd.DatetimeIndex, common: list[str], core: tuple[str, ...]):
    S = score.loc[dates, common].to_numpy(float)
    active = np.isfinite(S)
    idx = {s: i for i, s in enumerate(common)}
    core_ids = [idx[s] for s in core]
    core_active = active[:, core_ids]
    core_count = core_active.sum(axis=1)
    safe = np.where(np.isfinite(S[:, core_ids]), S[:, core_ids], -np.inf)
    core_best = np.max(safe, axis=1)

    rows = []
    for s in common:
        if s in core:
            continue
        j = idx[s]
        a = active[:, j]
        novelty = float(np.mean(np.where(a, 1.0 / (1.0 + core_count), 0.0)))
        activity_share = float(np.mean(a))
        exclusive_share = float(np.mean(a & (core_count == 0)))
        js = [jaccard(a, core_active[:, k]) for k in range(core_active.shape[1])]
        sv = S[:, j]
        outrank = a & np.isfinite(core_best) & (sv > core_best)
        rows.append({
            "symbol": s,
            "novelty": novelty,
            "activity_share": activity_share,
            "exclusive_active_share": exclusive_share,
            "mean_pair_trend_jaccard": float(np.mean(js)) if js else np.nan,
            "max_pair_trend_jaccard": float(np.max(js)) if js else np.nan,
            "core_outrank_share": float(np.mean(outrank)),
            "core_outrank_days": int(np.count_nonzero(outrank)),
        })
    df = pd.DataFrame(rows).sort_values(["novelty", "symbol"], ascending=[False, True]).reset_index(drop=True)
    if df.empty:
        raise RuntimeError("no outside candidate for novelty add-one")
    return str(df.iloc[0]["symbol"]), df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage8d-output")
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
    meta = pd.read_sql_query(
        text("select symbol,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"), eng
    )
    meta["symbol"] = meta["symbol"].astype(str)

    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    starts = s8a.extended_starts(cal, start0)
    starts_map = {b: p for b, p in starts}
    first_exec_pos = int(cal.searchsorted(START_EXEC, side="left"))
    first_signal = max(0, first_exec_pos - 1)
    last_signal = len(cal) - 3

    need = []
    for b, p in starts:
        next_p = starts_map.get(b + 1, len(cal))
        if next_p <= first_signal or p > last_signal:
            continue
        if p - HIST_SESSIONS < 0:
            continue
        if all((b - j) in starts_map for j in (1, 2, 3)):
            need.append((b, p))
    if not need:
        raise RuntimeError("no blocks")

    core_by = {}
    opp16_by = {}
    novelty_by = {}
    novelty_symbol_by = {}
    selection_rows = []
    candidate_rows = []

    for bno, pos in need:
        common = s8a.common_pool_for_block(bno, pos, starts_map, cal, close, meta)
        order, _, dates = s8c.old_order_point_in_time(score, gross, cal, pos, common, 30)
        core = tuple(sorted(common[j] for j in order[:15]))
        opp16 = tuple(sorted(common[j] for j in order[:16]))
        added, cands = novelty_pick(score, dates, common, core)
        nov16 = tuple(sorted(set(core) | {added}))
        if len(nov16) != 16:
            raise RuntimeError("novelty add-one did not create K16")

        core_by[bno] = core
        opp16_by[bno] = opp16
        novelty_by[bno] = nov16
        novelty_symbol_by[bno] = added

        chosen = cands.iloc[0]
        opportunity16_added = sorted(set(opp16) - set(core))
        selection_rows.append({
            "block_no": int(bno),
            "decision_date": str(pd.Timestamp(cal[pos]).date()),
            "history_start": str(dates[0].date()),
            "history_end_signal": str(dates[-1].date()),
            "common_pool_n": int(len(common)),
            "novelty_symbol": added,
            "novelty": float(chosen["novelty"]),
            "activity_share": float(chosen["activity_share"]),
            "exclusive_active_share": float(chosen["exclusive_active_share"]),
            "mean_pair_trend_jaccard": float(chosen["mean_pair_trend_jaccard"]),
            "max_pair_trend_jaccard": float(chosen["max_pair_trend_jaccard"]),
            "core_outrank_days": int(chosen["core_outrank_days"]),
            "opportunity_k16_added": opportunity16_added[0] if opportunity16_added else None,
            "same_as_opportunity_k16_added": bool(opportunity16_added and added == opportunity16_added[0]),
            "core15_members": ",".join(core),
            "novelty_k16_members": ",".join(nov16),
        })
        cands = cands.head(20).copy()
        cands.insert(0, "block_no", bno)
        cands.insert(1, "decision_date", str(pd.Timestamp(cal[pos]).date()))
        candidate_rows.append(cands)

    fix_by = {b: FIX15 for b, _ in need}
    parts = [
        s8a.build_variant_daily("CORE15", core_by, starts_map, cal, score, gross, first_signal, last_signal),
        s8a.build_variant_daily("OPPORTUNITY_K16", opp16_by, starts_map, cal, score, gross, first_signal, last_signal),
        s8a.build_variant_daily("NOVELTY_K16", novelty_by, starts_map, cal, score, gross, first_signal, last_signal),
        s8a.build_variant_daily("FIX15_BENCHMARK", fix_by, starts_map, cal, score, gross, first_signal, last_signal),
    ]
    daily = pd.concat(parts, ignore_index=True)
    daily = daily.loc[daily["execution_date"] >= START_EXEC].copy()
    ann, _ = s8a.summarize(daily)

    full_rows = []
    for variant, g in daily.groupby("variant"):
        full_rows.append({"variant": variant, **s8b.path_stats(g)})
    full = pd.DataFrame(full_rows)

    impact_rows = []
    for bno, _ in need:
        a = daily[(daily["variant"] == "CORE15") & (daily["block_no"] == bno)].sort_values("signal_date")
        n = daily[(daily["variant"] == "NOVELTY_K16") & (daily["block_no"] == bno)].sort_values("signal_date")
        if a.empty or n.empty:
            continue
        m = a[["signal_date", "net"]].merge(
            n[["signal_date", "net", "target", "sides"]], on="signal_date", suffixes=("_core", "_nov")
        )
        sym = novelty_symbol_by[bno]
        dl = float((np.log1p(m["net_nov"].to_numpy(float)) - np.log1p(m["net_core"].to_numpy(float))).sum())
        impact_rows.append({
            "block_no": bno,
            "decision_date": next(r["decision_date"] for r in selection_rows if r["block_no"] == bno),
            "novelty_symbol": sym,
            "candidate_top1_sessions": int((m["target"].astype(str) == sym).sum()),
            "delta_log_wealth_vs_core15": dl,
            "wealth_ratio_vs_core15": float(np.exp(dl)),
            "novelty_turnover_sides": int(m["sides"].sum()),
        })

    selections = pd.DataFrame(selection_rows)
    impacts = pd.DataFrame(impact_rows)
    candidates = pd.concat(candidate_rows, ignore_index=True) if candidate_rows else pd.DataFrame()

    selections.to_csv(out / "stage8d_selections.csv", index=False)
    candidates.to_csv(out / "stage8d_top20_novelty_candidates.csv", index=False)
    impacts.to_csv(out / "stage8d_block_impacts.csv", index=False)
    daily.to_csv(out / "stage8d_daily.csv", index=False)
    ann.to_csv(out / "stage8d_annual.csv", index=False)
    full.to_csv(out / "stage8d_full.csv", index=False)

    summary = {
        "study": "OURE Stage8D competition-state novelty add-one",
        "status": "completed",
        "blocks": int(len(need)),
        "selection_uses_returns": False,
        "selection_uses_fix15_identity": False,
        "full": full.to_dict(orient="records"),
        "mean_novelty": float(selections["novelty"].mean()),
        "mean_candidate_top1_sessions": float(impacts["candidate_top1_sessions"].mean()),
        "positive_block_impacts": int((impacts["delta_log_wealth_vs_core15"] > 0).sum()),
        "negative_block_impacts": int((impacts["delta_log_wealth_vs_core15"] < 0).sum()),
    }
    (out / "stage8d_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(full.to_string(index=False))
    print(selections[["block_no", "decision_date", "novelty_symbol", "novelty", "activity_share", "mean_pair_trend_jaccard", "opportunity_k16_added"]].to_string(index=False))
    print(impacts.to_string(index=False))


if __name__ == "__main__":
    main()
