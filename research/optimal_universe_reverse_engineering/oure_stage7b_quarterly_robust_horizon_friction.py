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
TRAIN_BLOCKS = 3
K = 30
COSTS = [0.0006, 0.0012, 0.0020]


def bp_label(c: float) -> int:
    return int(round(c * 10000))


def rank_pct(x: pd.Series) -> pd.Series:
    return s6g.rank_pct(pd.Series(x, dtype=float))


def spearman(a, b) -> float:
    v = s6g.spearman(a, b)
    return float(v) if np.isfinite(v) else np.nan


def block_starts(cal: pd.DatetimeIndex, start0: int, h: int):
    out = []
    b = 1
    pos = int(start0)
    while pos + h <= len(cal) - 2:
        out.append((b, pos))
        b += 1
        pos += h
    return out


def target_symbols(ev: s6c.Eval, members: tuple[str, ...]) -> list[str | None]:
    _, targ = ev.target_state(members)
    ans = []
    for j in targ:
        j = int(j)
        ans.append(None if j < 0 else ev.cands[j])
    return ans


def select_horizon(h: int, cal, score, gross, close, meta, start0: int, common_start: int, common_end: int):
    starts = block_starts(cal, start0, h)
    selections = []
    metrics = []
    target_payloads = []

    for ti in range(TRAIN_BLOCKS, len(starts)):
        bno, pos = starts[ti]
        if pos < common_start or pos + h > common_end:
            continue
        hist = starts[ti-TRAIN_BLOCKS:ti]
        involved = hist + [starts[ti]]
        pools = [set(s5.available_pool(close, meta, cal, int(p))) for _, p in involved]
        common = sorted(set.intersection(*pools))
        if len(common) < K:
            raise RuntimeError(f"H{h} B{bno:02d}: common pool too small {len(common)}")

        recent_dates = pd.DatetimeIndex(cal[pos-h:pos])
        fut_dates = pd.DatetimeIndex(cal[pos:pos+h])
        recent_ev = s6c.Eval(score, gross, recent_dates, common)
        future_ev = s6c.Eval(score, gross, fut_dates, common)
        rng = np.random.default_rng(SEED + bno * 1009)
        combo_family, _, _ = s6g.build_family_library(recent_ev, common, rng)
        combos = list(combo_family.keys())

        hist_evs = []
        for _, hp in hist:
            hdates = pd.DatetimeIndex(cal[hp:hp+h])
            hist_evs.append(s6c.Eval(score, gross, hdates, common))

        rows = []
        for u in combos:
            hlogs = [float(ev.evaluate(u)["log_growth"]) for ev in hist_evs]
            fut = future_ev.evaluate(u)
            row = {
                "horizon": h,
                "block": f"H{h}_B{bno:02d}",
                "block_no": bno,
                "decision_date": str(pd.Timestamp(cal[pos]).date()),
                "end_date": str(pd.Timestamp(fut_dates[-1]).date()),
                "common_pool_n": len(common),
                "candidate_n": len(combos),
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
        for j in range(1, TRAIN_BLOCKS + 1):
            rc = f"hist{j}_rank_pct"
            df[rc] = rank_pct(df[f"hist{j}_log_growth"]).to_numpy()
            rcols.append(rc)
        rv = df[rcols].to_numpy(float)
        df["robust_median_rank"] = np.median(rv, axis=1)
        df["robust_q25_rank"] = np.quantile(rv, 0.25, axis=1)
        df["robust_score"] = 0.5 * df["robust_median_rank"] + 0.5 * df["robust_q25_rank"]

        ic = spearman(df["robust_score"], df["future_log_growth"])
        top50 = df.nlargest(min(50, len(df)), "robust_score")
        win = df.nlargest(1, "robust_score").iloc[0]
        metrics.append({
            "horizon": h,
            "block": win["block"],
            "decision_date": win["decision_date"],
            "spearman": ic,
            "top50_actual_pct": float(top50["future_rank_pct"].mean()),
            "selected_actual_pct": float(win["future_rank_pct"]),
            "selected_future_return_independent": float(win["future_total_return"]),
        })
        members = tuple(str(win["members"]).split(","))
        selections.append({
            "horizon": h,
            "block": win["block"],
            "block_no": int(bno),
            "decision_pos": int(pos),
            "decision_date": win["decision_date"],
            "end_date": win["end_date"],
            "members": win["members"],
            "robust_score": float(win["robust_score"]),
            "actual_pct": float(win["future_rank_pct"]),
            "independent_return_6bp": float(win["future_total_return"]),
        })
        target_payloads.append((int(pos), h, members, common))

    return pd.DataFrame(selections), pd.DataFrame(metrics), target_payloads


def one_day_target(score, gross, date, members: tuple[str, ...]):
    cands = sorted(set(members))
    ev = s6c.Eval(score, gross, pd.DatetimeIndex([date]), cands)
    return target_symbols(ev, tuple(cands))[0]


def build_chained_path(h: int, sels: pd.DataFrame, payloads, cal, score, gross):
    if sels.empty:
        raise RuntimeError(f"H{h}: no selections")
    sels = sels.sort_values("decision_pos").reset_index(drop=True)
    daily_rows = []
    boundary_rows = []
    prev_target = None
    prev_members = None
    tenures = []
    run_sym = None
    run_n = 0

    for bi, r in sels.iterrows():
        pos = int(r["decision_pos"])
        members = tuple(str(r["members"]).split(","))
        dates = pd.DatetimeIndex(cal[pos:pos+h])
        ev = s6c.Eval(score, gross, dates, sorted(set(members)))
        syms = target_symbols(ev, members)

        if bi > 0:
            boundary_date = dates[0]
            old_u = tuple(prev_members)
            old_target_today = one_day_target(score, gross, boundary_date, old_u)
            new_target_today = syms[0]
            inter = len(set(old_u) & set(members))
            boundary_rows.append({
                "horizon": h,
                "decision_date": str(boundary_date.date()),
                "jaccard": inter / len(set(old_u) | set(members)),
                "members_replaced": K - inter,
                "update_induced_target_change": bool(old_target_today != new_target_today),
                "old_universe_target_today": old_target_today,
                "new_universe_target_today": new_target_today,
                "previous_held": prev_target,
                "previous_held_removed": bool(prev_target is not None and prev_target not in set(members)),
            })

        for d, sym in zip(dates, syms):
            if sym == prev_target:
                sides = 0
            elif sym is None or prev_target is None:
                sides = 1
            else:
                sides = 2
            g = 0.0 if sym is None else float(gross.loc[d, sym])
            if not np.isfinite(g):
                g = 0.0
            row = {"horizon": h, "date": str(pd.Timestamp(d).date()), "target": sym, "gross": g, "sides": sides}
            for c in COSTS:
                b = bp_label(c)
                net = (1.0 + g) * (1.0 - c * sides) - 1.0
                row[f"log_net_{b}bp"] = float(np.log1p(net))
            daily_rows.append(row)

            if sym is None:
                if run_sym is not None:
                    tenures.append(run_n)
                run_sym = None; run_n = 0
            elif sym == run_sym:
                run_n += 1
            else:
                if run_sym is not None:
                    tenures.append(run_n)
                run_sym = sym; run_n = 1
            prev_target = sym
        prev_members = members

    if run_sym is not None:
        tenures.append(run_n)

    daily = pd.DataFrame(daily_rows)
    bounds = pd.DataFrame(boundary_rows)
    summary = {
        "horizon": h,
        "sessions": int(len(daily)),
        "turnover_sides": int(daily["sides"].sum()),
        "annualized_turnover_sides": float(daily["sides"].sum() * 252.0 / len(daily)),
        "mean_top1_tenure": float(np.mean(tenures)) if tenures else np.nan,
        "median_top1_tenure": float(np.median(tenures)) if tenures else np.nan,
        "boundary_n": int(len(bounds)),
        "mean_universe_jaccard": float(bounds["jaccard"].mean()) if len(bounds) else np.nan,
        "mean_members_replaced": float(bounds["members_replaced"].mean()) if len(bounds) else np.nan,
        "update_induced_target_change_n": int(bounds["update_induced_target_change"].sum()) if len(bounds) else 0,
        "update_induced_target_change_share": float(bounds["update_induced_target_change"].mean()) if len(bounds) else np.nan,
        "previous_held_removed_n": int(bounds["previous_held_removed"].sum()) if len(bounds) else 0,
        "previous_held_removed_share": float(bounds["previous_held_removed"].mean()) if len(bounds) else np.nan,
    }
    for c in COSTS:
        b = bp_label(c)
        lg = float(daily[f"log_net_{b}bp"].sum())
        summary[f"total_return_{b}bp"] = float(np.exp(lg) - 1.0)

    return daily, bounds, summary


def paired_126(daily: pd.DataFrame):
    z = daily.copy().reset_index(drop=True)
    z["pair126"] = np.arange(len(z)) // 126
    rows = []
    for p, g in z.groupby("pair126", sort=True):
        if len(g) != 126:
            continue
        rec = {"pair126": int(p), "start_date": g["date"].iloc[0], "end_date": g["date"].iloc[-1]}
        for c in COSTS:
            b = bp_label(c)
            rec[f"return_{b}bp"] = float(np.exp(g[f"log_net_{b}bp"].sum()) - 1.0)
        rows.append(rec)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage7b-output")
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
    common_start = start0 + 3 * 126
    common_end = start0 + 9 * 126
    if common_end > len(cal) - 2:
        raise RuntimeError("insufficient data for common comparison window")

    all_sels = []
    all_metrics = []
    path_summaries = []
    paired_frames = []
    boundary_frames = []
    daily_frames = []

    for h in (126, 63):
        sels, mets, payloads = select_horizon(h, cal, score, gross, close, meta, start0, common_start, common_end)
        daily, bounds, ps = build_chained_path(h, sels, payloads, cal, score, gross)
        pair = paired_126(daily); pair["horizon"] = h
        all_sels.append(sels); all_metrics.append(mets); path_summaries.append(ps)
        paired_frames.append(pair); boundary_frames.append(bounds); daily_frames.append(daily)

    selections = pd.concat(all_sels, ignore_index=True)
    metrics = pd.concat(all_metrics, ignore_index=True)
    paths = pd.DataFrame(path_summaries)
    paired = pd.concat(paired_frames, ignore_index=True)
    boundaries = pd.concat(boundary_frames, ignore_index=True)
    daily = pd.concat(daily_frames, ignore_index=True)

    selections.to_csv(out / "stage7b_selections.csv", index=False)
    metrics.to_csv(out / "stage7b_cross_section_metrics.csv", index=False)
    paths.to_csv(out / "stage7b_path_summary.csv", index=False)
    paired.to_csv(out / "stage7b_paired126_returns.csv", index=False)
    boundaries.to_csv(out / "stage7b_boundary_friction.csv", index=False)
    daily.to_csv(out / "stage7b_daily_path.csv", index=False)

    diag = {}
    for h, g in metrics.groupby("horizon"):
        diag[str(int(h))] = {
            "target_n": int(len(g)),
            "median_spearman": float(g["spearman"].median()),
            "positive_ic_n": int((g["spearman"] > 0).sum()),
            "median_top50_actual_pct": float(g["top50_actual_pct"].median()),
            "median_selected_actual_pct": float(g["selected_actual_pct"].median()),
        }

    p126 = paths[paths["horizon"] == 126].iloc[0]
    p63 = paths[paths["horizon"] == 63].iloc[0]
    pair126 = paired[paired["horizon"] == 126].sort_values("pair126")
    pair63 = paired[paired["horizon"] == 63].sort_values("pair126")
    paired_compare = []
    for i in range(min(len(pair126), len(pair63))):
        a = pair126.iloc[i]; b = pair63.iloc[i]
        paired_compare.append({
            "pair126": i,
            "start_date": a["start_date"],
            "end_date": a["end_date"],
            "h126_return_6bp": float(a["return_6bp"]),
            "h63_return_6bp": float(b["return_6bp"]),
            "h63_minus_h126_6bp": float(b["return_6bp"] - a["return_6bp"]),
        })
    pc = pd.DataFrame(paired_compare)
    pc.to_csv(out / "stage7b_paired126_comparison.csv", index=False)

    h63_ahead_all_costs = all(float(p63[f"total_return_{b}bp"]) > float(p126[f"total_return_{b}bp"]) for b in (6, 12, 20))
    worst126_h126 = float(pair126["return_6bp"].min())
    worst126_h63 = float(pair63["return_6bp"].min())
    if h63_ahead_all_costs and worst126_h63 >= worst126_h126 - 0.05:
        decision = "quarterly_preferred"
    elif float(p126["total_return_6bp"]) >= float(p63["total_return_6bp"]) or (float(p63["total_return_6bp"]) > float(p126["total_return_6bp"]) and not h63_ahead_all_costs) or worst126_h63 < worst126_h126 - 0.05:
        decision = "halfyear_preferred"
    else:
        decision = "mixed_horizon_tradeoff"

    summary = {
        "study": "OURE Stage7B quarterly Robust30 horizon and friction audit",
        "status": "completed",
        "decision": decision,
        "common_start": str(pd.Timestamp(cal[common_start]).date()),
        "common_end": str(pd.Timestamp(cal[common_end-1]).date()),
        "cross_section": diag,
        "paths": {str(int(r["horizon"])): {k: (int(v) if isinstance(v, (np.integer,)) else float(v) if isinstance(v, (np.floating,)) else v) for k, v in r.items() if k != "horizon"} for _, r in paths.iterrows()},
        "paired126": {
            "h126_worst_6bp": worst126_h126,
            "h63_worst_6bp": worst126_h63,
            "h126_positive_n": int((pair126["return_6bp"] > 0).sum()),
            "h63_positive_n": int((pair63["return_6bp"] > 0).sum()),
            "pair_n": int(min(len(pair126), len(pair63))),
            "h63_beats_h126_n": int((pc["h63_minus_h126_6bp"] > 0).sum()),
        },
        "interpretation_rule": {
            "h63_ahead_all_costs": bool(h63_ahead_all_costs),
            "h63_worst_not_more_than_5pp_worse": bool(worst126_h63 >= worst126_h126 - 0.05),
        },
    }
    (out / "stage7b_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
