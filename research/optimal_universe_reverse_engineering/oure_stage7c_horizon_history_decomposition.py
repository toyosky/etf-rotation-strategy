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
VARIANTS = {
    "A_H126_Hist126": (126, 126),
    "B_H63_Hist63": (63, 63),
    "C_H63_Hist126": (63, 126),
    "D_H126_Hist63": (126, 63),
}


def bp_label(c: float) -> int:
    return int(round(c * 10000))


def rank_pct(x: pd.Series) -> pd.Series:
    return s6g.rank_pct(pd.Series(x, dtype=float))


def spearman(a, b) -> float:
    v = s6g.spearman(a, b)
    return float(v) if np.isfinite(v) else np.nan


def target_symbols(ev: s6c.Eval, members: tuple[str, ...]) -> list[str | None]:
    _, targ = ev.target_state(members)
    ans = []
    for j in targ:
        j = int(j)
        ans.append(None if j < 0 else ev.cands[j])
    return ans


def decision_positions(common_start: int, common_end: int, hold_h: int) -> list[int]:
    return list(range(int(common_start), int(common_end), int(hold_h)))


def history_starts(pos: int, hist_h: int) -> list[int]:
    return [int(pos - hist_h * j) for j in range(TRAIN_BLOCKS, 0, -1)]


def select_variant(label: str, hold_h: int, hist_h: int, cal, score, gross, close, meta,
                   start0: int, common_start: int, common_end: int):
    selections = []
    metrics = []

    for pos in decision_positions(common_start, common_end, hold_h):
        if pos + hold_h > common_end:
            continue
        hstarts = history_starts(pos, hist_h)
        if hstarts[0] < start0:
            continue

        pool_positions = hstarts + [pos]
        pools = [set(s5.available_pool(close, meta, cal, int(p))) for p in pool_positions]
        common = sorted(set.intersection(*pools))
        if len(common) < K:
            raise RuntimeError(f"{label} pos={pos}: common pool too small {len(common)}")

        recent_dates = pd.DatetimeIndex(cal[pos-hist_h:pos])
        fut_dates = pd.DatetimeIndex(cal[pos:pos+hold_h])
        recent_ev = s6c.Eval(score, gross, recent_dates, common)
        future_ev = s6c.Eval(score, gross, fut_dates, common)

        # Reproduce frozen Stage7A/7B seed semantics for each holding grid.
        block_no = int((pos - start0) // hold_h + 1)
        rng = np.random.default_rng(SEED + block_no * 1009)
        combo_family, _, _ = s6g.build_family_library(recent_ev, common, rng)
        combos = list(combo_family.keys())

        hist_evs = []
        for hp in hstarts:
            hdates = pd.DatetimeIndex(cal[hp:hp+hist_h])
            hist_evs.append(s6c.Eval(score, gross, hdates, common))

        rows = []
        for u in combos:
            hlogs = [float(ev.evaluate(u)["log_growth"]) for ev in hist_evs]
            fut = future_ev.evaluate(u)
            row = {
                "variant": label,
                "hold_h": hold_h,
                "hist_h": hist_h,
                "block_no": block_no,
                "decision_pos": int(pos),
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
            "variant": label,
            "hold_h": hold_h,
            "hist_h": hist_h,
            "block_no": block_no,
            "decision_date": win["decision_date"],
            "spearman": ic,
            "top50_actual_pct": float(top50["future_rank_pct"].mean()),
            "selected_actual_pct": float(win["future_rank_pct"]),
            "selected_future_return_independent": float(win["future_total_return"]),
        })
        selections.append({
            "variant": label,
            "hold_h": hold_h,
            "hist_h": hist_h,
            "block_no": block_no,
            "decision_pos": int(pos),
            "decision_date": win["decision_date"],
            "end_date": win["end_date"],
            "members": win["members"],
            "robust_score": float(win["robust_score"]),
            "actual_pct": float(win["future_rank_pct"]),
            "independent_return": float(win["future_total_return"]),
        })

    return pd.DataFrame(selections), pd.DataFrame(metrics)


def one_day_target(score, gross, date, members: tuple[str, ...]):
    cands = sorted(set(members))
    ev = s6c.Eval(score, gross, pd.DatetimeIndex([date]), cands)
    return target_symbols(ev, tuple(cands))[0]


def build_chained_path(label: str, hold_h: int, sels: pd.DataFrame, cal, score, gross):
    if sels.empty:
        raise RuntimeError(f"{label}: no selections")
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
        dates = pd.DatetimeIndex(cal[pos:pos+hold_h])
        ev = s6c.Eval(score, gross, dates, sorted(set(members)))
        syms = target_symbols(ev, members)

        if bi > 0:
            boundary_date = dates[0]
            old_u = tuple(prev_members)
            old_target_today = one_day_target(score, gross, boundary_date, old_u)
            new_target_today = syms[0]
            inter = len(set(old_u) & set(members))
            boundary_rows.append({
                "variant": label,
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
            row = {"variant": label, "date": str(pd.Timestamp(d).date()), "target": sym, "gross": g, "sides": sides}
            for c in COSTS:
                b = bp_label(c)
                net = (1.0 + g) * (1.0 - c * sides) - 1.0
                row[f"log_net_{b}bp"] = float(np.log1p(net))
            daily_rows.append(row)

            if sym is None:
                if run_sym is not None:
                    tenures.append(run_n)
                run_sym = None
                run_n = 0
            elif sym == run_sym:
                run_n += 1
            else:
                if run_sym is not None:
                    tenures.append(run_n)
                run_sym = sym
                run_n = 1
            prev_target = sym
        prev_members = members

    if run_sym is not None:
        tenures.append(run_n)

    daily = pd.DataFrame(daily_rows)
    bounds = pd.DataFrame(boundary_rows)
    summary = {
        "variant": label,
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
        summary[f"log_wealth_{b}bp"] = lg
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


def classify_effects(paths: pd.DataFrame):
    p = paths.set_index("variant")
    cost_effects = {}
    hist_vals = []
    hold_vals = []
    for b in (6, 12, 20):
        A = float(p.loc["A_H126_Hist126", f"log_wealth_{b}bp"])
        B = float(p.loc["B_H63_Hist63", f"log_wealth_{b}bp"])
        C = float(p.loc["C_H63_Hist126", f"log_wealth_{b}bp"])
        D = float(p.loc["D_H126_Hist63", f"log_wealth_{b}bp"])
        e_hist = 0.5 * ((A - D) + (C - B))
        e_hold = 0.5 * ((A - C) + (D - B))
        interaction = (A - D) - (C - B)
        hist_vals.append(e_hist)
        hold_vals.append(e_hold)
        cost_effects[str(b)] = {
            "history_effect_log_wealth": e_hist,
            "holding_effect_log_wealth": e_hold,
            "interaction_log_wealth": interaction,
        }

    hist_all_pos = all(x > 0 for x in hist_vals)
    hold_all_pos = all(x > 0 for x in hold_vals)
    mh = float(np.median(hist_vals))
    mo = float(np.median(hold_vals))

    if hist_all_pos and not hold_all_pos and mh > 0:
        verdict = "history_depth_dominant"
    elif hold_all_pos and not hist_all_pos and mo > 0:
        verdict = "holding_horizon_dominant"
    elif hist_all_pos and hold_all_pos:
        if mh >= 1.5 * mo:
            verdict = "history_depth_dominant"
        elif mo >= 1.5 * mh:
            verdict = "holding_horizon_dominant"
        else:
            verdict = "mixed"
    else:
        verdict = "unresolved"
    return verdict, cost_effects


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage7c-output")
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
    meta = pd.read_sql_query(text("select symbol,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    start0 = int(cal.searchsorted(pd.Timestamp("2022-01-01"), side="left"))
    common_start = start0 + 3 * 126
    common_end = start0 + 9 * 126
    if common_end > len(cal) - 2:
        raise RuntimeError("insufficient data for frozen common comparison window")

    sels_all = []
    mets_all = []
    paths_all = []
    pairs_all = []
    bounds_all = []
    daily_all = []

    for label, (hold_h, hist_h) in VARIANTS.items():
        sels, mets = select_variant(label, hold_h, hist_h, cal, score, gross, close, meta, start0, common_start, common_end)
        daily, bounds, ps = build_chained_path(label, hold_h, sels, cal, score, gross)
        pair = paired_126(daily)
        pair["variant"] = label
        sels_all.append(sels)
        mets_all.append(mets)
        paths_all.append(ps)
        pairs_all.append(pair)
        bounds_all.append(bounds)
        daily_all.append(daily)

    selections = pd.concat(sels_all, ignore_index=True)
    metrics = pd.concat(mets_all, ignore_index=True)
    paths = pd.DataFrame(paths_all)
    paired = pd.concat(pairs_all, ignore_index=True)
    boundaries = pd.concat(bounds_all, ignore_index=True)
    daily = pd.concat(daily_all, ignore_index=True)

    # Exact structural reproduction guards for the two Stage7B corner variants.
    a = paths.set_index("variant").loc["A_H126_Hist126"]
    b = paths.set_index("variant").loc["B_H63_Hist63"]
    if abs(float(a["total_return_6bp"]) - 1.1773) > 0.005:
        raise RuntimeError(f"Stage7B H126 baseline reproduction failed: {float(a['total_return_6bp']):.6f}")
    if abs(float(b["total_return_6bp"]) - (-0.1663)) > 0.005:
        raise RuntimeError(f"Stage7B H63 baseline reproduction failed: {float(b['total_return_6bp']):.6f}")

    diag = {}
    for label, g in metrics.groupby("variant"):
        diag[label] = {
            "target_n": int(len(g)),
            "median_spearman": float(g["spearman"].median()),
            "positive_ic_n": int((g["spearman"] > 0).sum()),
            "median_top50_actual_pct": float(g["top50_actual_pct"].median()),
            "median_selected_actual_pct": float(g["selected_actual_pct"].median()),
        }

    verdict, effects = classify_effects(paths)
    pair_diag = {}
    for label, g in paired.groupby("variant"):
        pair_diag[label] = {
            "pair_n": int(len(g)),
            "positive_n_6bp": int((g["return_6bp"] > 0).sum()),
            "worst_6bp": float(g["return_6bp"].min()),
            "median_6bp": float(g["return_6bp"].median()),
        }

    selections.to_csv(out / "stage7c_selections.csv", index=False)
    metrics.to_csv(out / "stage7c_cross_section_metrics.csv", index=False)
    paths.to_csv(out / "stage7c_path_summary.csv", index=False)
    paired.to_csv(out / "stage7c_paired126_returns.csv", index=False)
    boundaries.to_csv(out / "stage7c_boundary_friction.csv", index=False)
    daily.to_csv(out / "stage7c_daily_path.csv", index=False)

    summary = {
        "study": "OURE Stage7C horizon-vs-history decomposition",
        "status": "completed",
        "verdict": verdict,
        "common_start": str(pd.Timestamp(cal[common_start]).date()),
        "common_end": str(pd.Timestamp(cal[common_end-1]).date()),
        "variants": {k: {"hold_h": v[0], "hist_h": v[1]} for k, v in VARIANTS.items()},
        "cross_section": diag,
        "paths": paths.set_index("variant").to_dict(orient="index"),
        "paired126": pair_diag,
        "factor_effects": effects,
        "baseline_reproduction": {
            "A_H126_Hist126_return_6bp": float(a["total_return_6bp"]),
            "B_H63_Hist63_return_6bp": float(b["total_return_6bp"]),
            "passed": True,
        },
    }
    (out / "stage7c_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
