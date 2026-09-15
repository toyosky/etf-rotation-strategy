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
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

HIST_SESSIONS = 378
HORIZONS = (21, 63, 126)
STRIDE = 7
KS = (15, 30)
COST = 0.0006
CASH = s8a.CASH
START_EXEC = pd.Timestamp("2021-01-01")
FIX15 = tuple(s8a.FIX15)


def realized_history_positions(pos: int) -> tuple[int, int]:
    start = pos - HIST_SESSIONS
    stop = pos - 1
    if start < 0 or stop <= start:
        raise RuntimeError("insufficient point-in-time history")
    return start, stop


def build_windows(t: int) -> dict[int, list[tuple[int, int]]]:
    out: dict[int, list[tuple[int, int]]] = {}
    for h in HORIZONS:
        starts = list(range(0, max(0, t - h + 1), STRIDE))
        if starts and starts[-1] != t - h:
            starts.append(t - h)
        out[h] = [(s, s + h) for s in sorted(set(starts)) if s >= 0 and s + h <= t]
        if not out[h]:
            raise RuntimeError(f"no windows for horizon {h}, t={t}")
    return out


def path_from_arrays(S: np.ndarray, G: np.ndarray, cash: np.ndarray, ids: list[int]) -> tuple[np.ndarray, np.ndarray]:
    t = S.shape[0]
    if not ids:
        target = np.full(t, -1, dtype=np.int32)
        return np.zeros(t, dtype=float), target
    ss = S[:, ids]
    safe = np.where(np.isfinite(ss), ss, -np.inf)
    loc = np.argmax(safe, axis=1)
    mx = safe[np.arange(t), loc]
    chosen = np.asarray(ids, dtype=np.int32)[loc]
    target = np.where(mx > cash, chosen, -1).astype(np.int32)
    gross = np.zeros(t, dtype=float)
    m = target >= 0
    if m.any():
        gv = G[np.arange(t)[m], target[m]]
        gross[m] = np.where(np.isfinite(gv), gv, 0.0)
    sides = np.zeros(t, dtype=np.int8)
    if t:
        sides[0] = 1 if target[0] >= 0 else 0
    if t > 1:
        prev, cur = target[:-1], target[1:]
        diff = cur != prev
        one_cash = (cur < 0) | (prev < 0)
        sides[1:] = np.where(diff, np.where(one_cash, 1, 2), 0).astype(np.int8)
    net = (1.0 + gross) * (1.0 - COST * sides) - 1.0
    net = np.maximum(net, -0.999999999)
    return np.log1p(net), target


def window_sums(lognet: np.ndarray, windows: list[tuple[int, int]]) -> np.ndarray:
    cs = np.r_[0.0, np.cumsum(lognet)]
    return np.asarray([cs[b] - cs[a] for a, b in windows], dtype=float)


def oracle_by_horizon(S: np.ndarray, G: np.ndarray, cash: np.ndarray, windows_by_h: dict[int, list[tuple[int, int]]]) -> dict[int, np.ndarray]:
    n = S.shape[1]
    out = {h: np.zeros(len(ws), dtype=float) for h, ws in windows_by_h.items()}
    for j in range(n):
        lognet, _ = path_from_arrays(S, G, cash, [j])
        for h, ws in windows_by_h.items():
            vals = np.maximum(window_sums(lognet, ws), 0.0)
            out[h] = np.maximum(out[h], vals)
    return out


def capture_score(lognet: np.ndarray, windows_by_h: dict[int, list[tuple[int, int]]], oracle: dict[int, np.ndarray]) -> tuple[float, dict[int, float]]:
    by_h = {}
    for h, ws in windows_by_h.items():
        o = oracle[h]
        den = float(o.sum())
        vals = np.maximum(window_sums(lognet, ws), 0.0)
        cap = np.minimum(vals, o)
        by_h[h] = float(cap.sum() / den) if den > 0 else 1.0
    return float(np.mean(list(by_h.values()))), by_h


def greedy_moc_order(score: pd.DataFrame, gross: pd.DataFrame, cal: pd.DatetimeIndex, pos: int, common: list[str], max_k: int = 30):
    hs, he = realized_history_positions(pos)
    dates = pd.DatetimeIndex(cal[hs:he])
    S = score.loc[dates, common].to_numpy(float)
    G = gross.loc[dates, common].to_numpy(float)
    cash = score.loc[dates, CASH].to_numpy(float) if CASH in score.columns else np.full(len(dates), -np.inf)
    cash = np.where(np.isfinite(cash), cash, -np.inf)
    windows = build_windows(len(dates))
    oracle = oracle_by_horizon(S, G, cash, windows)

    selected: list[int] = []
    remaining = set(range(len(common)))
    rows = []
    prev_score = 0.0
    for rank in range(1, max_k + 1):
        best_j = None
        best_sc = -np.inf
        best_by_h = None
        for j in remaining:
            lognet, _ = path_from_arrays(S, G, cash, selected + [j])
            sc, by_h = capture_score(lognet, windows, oracle)
            key = (sc, -j)
            if best_j is None or key > (best_sc, -best_j):
                best_j = j
                best_sc = sc
                best_by_h = by_h
        if best_j is None:
            raise RuntimeError("MOC greedy selection failed")
        selected.append(best_j)
        remaining.remove(best_j)
        rows.append({
            "rank": rank,
            "symbol": common[best_j],
            "capture": float(best_sc),
            "marginal_capture": float(best_sc - prev_score),
            **{f"capture_h{h}": float(best_by_h[h]) for h in HORIZONS},
        })
        prev_score = float(best_sc)
    return selected, pd.DataFrame(rows), dates


def old_order_point_in_time(score, gross, cal, pos, common, max_k=30):
    hs, he = realized_history_positions(pos)
    dates = pd.DatetimeIndex(cal[hs:he])
    n_full = len(dates) // 21
    rows = []
    for w in range(n_full):
        wd = dates[w * 21:(w + 1) * 21]
        subS = score.loc[wd, common].to_numpy(float)
        subG = gross.loc[wd, common].to_numpy(float)
        cash = score.loc[wd, CASH].to_numpy(float) if CASH in score.columns else np.full(len(wd), -np.inf)
        cash = np.where(np.isfinite(cash), cash, -np.inf)
        arr = []
        for j in range(len(common)):
            ln, _ = path_from_arrays(subS, subG, cash, [j])
            arr.append(float(np.sum(ln)))
        rows.append(s8a.rank_pct(pd.Series(arr, index=common)).reindex(common).to_numpy(float))
    mat = np.vstack(rows).T
    order = s8b.greedy_order(mat, common, max_k=max_k)
    return order, mat, dates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage8c-output")
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

    old15_by, old30_by, moc15_by, moc30_by = {}, {}, {}, {}
    sel_rows, order_rows = [], []
    for bno, pos in need:
        common = s8a.common_pool_for_block(bno, pos, starts_map, cal, close, meta)
        old_order, old_mat, old_dates = old_order_point_in_time(score, gross, cal, pos, common, 30)
        moc_order, moc_diag, moc_dates = greedy_moc_order(score, gross, cal, pos, common, 30)
        if not old_dates.equals(moc_dates):
            raise RuntimeError("history date mismatch")

        for k in KS:
            old_members = tuple(sorted(common[j] for j in old_order[:k]))
            moc_members = tuple(sorted(common[j] for j in moc_order[:k]))
            if k == 15:
                old15_by[bno], moc15_by[bno] = old_members, moc_members
            else:
                old30_by[bno], moc30_by[bno] = old_members, moc_members
            order_rows.extend([
                {"block_no": bno, "decision_date": str(pd.Timestamp(cal[pos]).date()), "algorithm": "OLD_SAFE", "k": k, "members": ",".join(old_members)},
                {"block_no": bno, "decision_date": str(pd.Timestamp(cal[pos]).date()), "algorithm": "MOC", "k": k, "members": ",".join(moc_members)},
            ])

        r15 = moc_diag.loc[moc_diag["rank"] == 15].iloc[0]
        r30 = moc_diag.loc[moc_diag["rank"] == 30].iloc[0]
        sel_rows.append({
            "block_no": bno,
            "decision_date": str(pd.Timestamp(cal[pos]).date()),
            "common_pool_n": len(common),
            "safe_history_start": str(old_dates[0].date()),
            "safe_history_end_signal": str(old_dates[-1].date()),
            "moc_capture_k15": float(r15["capture"]),
            "moc_capture_k30": float(r30["capture"]),
            "moc_k15_over_k30": float(r15["capture"] / r30["capture"]) if float(r30["capture"]) > 0 else np.nan,
            "old_moc_overlap_k15": len(set(old15_by[bno]) & set(moc15_by[bno])),
            "old_moc_overlap_k30": len(set(old30_by[bno]) & set(moc30_by[bno])),
            "moc_fix15_overlap_k15": len(set(moc15_by[bno]) & set(FIX15)),
            "moc_fix15_overlap_k30": len(set(moc30_by[bno]) & set(FIX15)),
        })
        d = moc_diag.copy()
        d.insert(0, "block_no", bno)
        d.insert(1, "decision_date", str(pd.Timestamp(cal[pos]).date()))
        d["algorithm"] = "MOC_ORDER"
        order_rows.extend(d.to_dict(orient="records"))

    fix_by = {b: FIX15 for b, _ in need}
    parts = [
        s8a.build_variant_daily("OLD_SAFE_K15", old15_by, starts_map, cal, score, gross, first_signal, last_signal),
        s8a.build_variant_daily("OLD_SAFE_K30", old30_by, starts_map, cal, score, gross, first_signal, last_signal),
        s8a.build_variant_daily("MOC_K15", moc15_by, starts_map, cal, score, gross, first_signal, last_signal),
        s8a.build_variant_daily("MOC_K30", moc30_by, starts_map, cal, score, gross, first_signal, last_signal),
        s8a.build_variant_daily("FIX15_BENCHMARK", fix_by, starts_map, cal, score, gross, first_signal, last_signal),
    ]
    daily = pd.concat(parts, ignore_index=True)
    daily = daily.loc[daily["execution_date"] >= START_EXEC].copy()
    ann, _ = s8a.summarize(daily)
    full_rows = []
    for variant, g in daily.groupby("variant"):
        full_rows.append({"variant": variant, **s8b.path_stats(g)})
    full = pd.DataFrame(full_rows)

    selections = pd.DataFrame(sel_rows)
    orders = pd.DataFrame(order_rows)
    selections.to_csv(out / "stage8c_selections.csv", index=False)
    orders.to_csv(out / "stage8c_orders.csv", index=False)
    daily.to_csv(out / "stage8c_daily.csv", index=False)
    ann.to_csv(out / "stage8c_annual.csv", index=False)
    full.to_csv(out / "stage8c_full.csv", index=False)

    summary = {
        "study": "OURE Stage8C marginal opportunity capture",
        "status": "completed",
        "history_sessions_requested": HIST_SESSIONS,
        "history_fully_realized_signals": HIST_SESSIONS - 1,
        "horizons": HORIZONS,
        "stride": STRIDE,
        "cost_per_side": COST,
        "ks": KS,
        "blocks": int(len(need)),
        "mean_moc_k15_over_k30": float(selections["moc_k15_over_k30"].mean()),
        "full": full.to_dict(orient="records"),
    }
    (out / "stage8c_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(full.to_string(index=False))
    print(selections[["block_no","decision_date","moc_capture_k15","moc_capture_k30","moc_k15_over_k30"]].to_string(index=False))


if __name__ == "__main__":
    main()
