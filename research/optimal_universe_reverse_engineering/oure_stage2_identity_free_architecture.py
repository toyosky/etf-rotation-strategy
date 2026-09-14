#!/usr/bin/env python3
"""OURE Stage2: identity-free architecture audit across all Fix15 subsets."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from validate_fixed15_vs_full_market import FIXED15
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

CASH = "511220"
START = pd.Timestamp("2021-01-01")


def run_lengths(x: np.ndarray) -> list[int]:
    out: list[int] = []
    cur = -1
    n = 0
    for v in x.astype(int):
        if v <= 0:
            if cur > 0:
                out.append(n)
            cur, n = -1, 0
        elif v == cur:
            n += 1
        else:
            if cur > 0:
                out.append(n)
            cur, n = v, 1
    if cur > 0:
        out.append(n)
    return out


def bool_episode_mean(x: np.ndarray) -> float:
    lens: list[int] = []
    n = 0
    for v in x.astype(bool):
        if v:
            n += 1
        elif n:
            lens.append(n); n = 0
    if n:
        lens.append(n)
    return float(np.mean(lens)) if lens else np.nan


def build_target_and_counts(score_m: np.ndarray, n_noncash: int) -> tuple[np.ndarray, np.ndarray]:
    t = score_m.shape[0]
    nmasks = 1 << n_noncash
    targets = np.full((nmasks, t), -1, dtype=np.int16)
    counts = np.zeros((nmasks, t), dtype=np.uint8)
    cash_ok = np.isfinite(score_m[:, 0])
    targets[0, cash_ok] = 0
    rows = np.arange(t)
    eligible_non = np.isfinite(score_m[:, 1:])
    for mask in range(1, nmasks):
        lsb = mask & -mask
        bit = lsb.bit_length() - 1
        prev = mask ^ lsb
        idx = bit + 1
        prev_t = targets[prev]
        prev_score = np.full(t, -np.inf, dtype=float)
        ok = prev_t >= 0
        prev_score[ok] = score_m[rows[ok], prev_t[ok]]
        cand = score_m[:, idx]
        choose = np.isfinite(cand) & (
            (cand > prev_score) | ((cand == prev_score) & ((prev_t < 0) | (idx < prev_t)))
        )
        targets[mask] = prev_t
        targets[mask, choose] = idx
        counts[mask] = counts[prev] + eligible_non[:, bit].astype(np.uint8)
    return targets, counts


def pair_jaccard(eligible: np.ndarray) -> np.ndarray:
    n = eligible.shape[1]
    j = np.full((n, n), np.nan, dtype=float)
    for a in range(n):
        j[a, a] = 1.0
        for b in range(a + 1, n):
            union = np.sum(eligible[:, a] | eligible[:, b])
            val = float(np.sum(eligible[:, a] & eligible[:, b]) / union) if union else np.nan
            j[a, b] = j[b, a] = val
    return j


def architecture_rows(
    masks: np.ndarray,
    noncash: list[str],
    targets: np.ndarray,
    counts: np.ndarray,
    eligible: np.ndarray,
    era_mask: np.ndarray,
    era: str,
) -> list[dict]:
    eidx = np.flatnonzero(era_mask)
    et = targets[:, eidx]
    ec = counts[:, eidx]
    elig_era = eligible[eidx]
    pj = pair_jaccard(elig_era)
    episode_mean = np.array([bool_episode_mean(elig_era[:, i]) for i in range(len(noncash))], dtype=float)
    rows: list[dict] = []
    for mask in masks:
        members = [i for i in range(len(noncash)) if mask & (1 << i)]
        k = len(members)
        c = ec[mask].astype(float)
        covered = c > 0
        coverage = float(covered.mean()) if len(c) else 0.0
        mean_count = float(c.mean()) if len(c) else 0.0
        cond_count = float(c[covered].mean()) if covered.any() else 0.0
        eff = float(coverage / mean_count) if mean_count > 0 else np.nan

        raw = et[mask]
        pos = np.where(raw > 0, raw, -1)
        invested = pos > 0
        switch_rate = float(np.mean(pos[1:] != pos[:-1])) if len(pos) > 1 else 0.0
        lens = run_lengths(pos)
        if invested.any():
            vals, cnt = np.unique(pos[invested], return_counts=True)
            sh = cnt / cnt.sum()
            hhi = float(np.square(sh).sum())
            active_share = float(len(vals) / k) if k else np.nan
        else:
            hhi = np.nan
            active_share = 0.0 if k else np.nan

        if len(members) >= 2:
            vals = [pj[a, b] for ii, a in enumerate(members) for b in members[ii + 1:] if np.isfinite(pj[a, b])]
            mean_j = float(np.mean(vals)) if vals else np.nan
            max_j = float(np.max(vals)) if vals else np.nan
        else:
            mean_j = np.nan
            max_j = np.nan

        em = episode_mean[members] if members else np.array([], dtype=float)
        rows.append({
            "era": era,
            "mask": int(mask),
            "k_including_cash": 1 + k,
            "noncash_k": k,
            "coverage_share": coverage,
            "mean_eligible_count": mean_count,
            "mean_competitors_when_covered": cond_count,
            "coverage_efficiency": eff,
            "selected_noncash_share": float(invested.mean()),
            "leader_switch_rate": switch_rate,
            "mean_top1_tenure": float(np.mean(lens)) if lens else np.nan,
            "median_top1_tenure": float(np.median(lens)) if lens else np.nan,
            "short_run_le2_share": float(np.mean(np.asarray(lens) <= 2)) if lens else np.nan,
            "leader_hhi": hhi,
            "active_member_share": active_share,
            "mean_pair_trend_jaccard": mean_j,
            "max_pair_trend_jaccard": max_j,
            "mean_member_trend_episode_length": float(np.nanmean(em)) if len(em) and np.isfinite(em).any() else np.nan,
        })
    return rows


def assoc_table(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    out = []
    for era, g0 in df.groupby("era"):
        g = g0[g0["noncash_k"] > 0].copy()
        g["return_rank_within_k"] = g.groupby("k_including_cash")["log_growth"].rank(pct=True, method="average")
        g["return_decile_within_k"] = g.groupby("k_including_cash")["log_growth"].rank(pct=True, method="average")
        for f in feature_cols:
            q = g[["k_including_cash", "return_rank_within_k", "return_decile_within_k", f]].dropna().copy()
            if len(q) < 20 or q[f].nunique() < 2:
                continue
            q["feature_rank_within_k"] = q.groupby("k_including_cash")[f].rank(pct=True, method="average")
            corr = float(q["feature_rank_within_k"].corr(q["return_rank_within_k"]))
            top = q[q["return_decile_within_k"] >= .90][f]
            bot = q[q["return_decile_within_k"] <= .10][f]
            sd = float(q[f].std(ddof=0))
            smd = float((top.mean() - bot.mean()) / sd) if sd > 0 and len(top) and len(bot) else np.nan
            out.append({
                "era": era,
                "feature": f,
                "n": int(len(q)),
                "within_k_rank_corr": corr,
                "top_decile_mean": float(top.mean()) if len(top) else np.nan,
                "bottom_decile_mean": float(bot.mean()) if len(bot) else np.nan,
                "top_minus_bottom_smd": smd,
            })
    return pd.DataFrame(out)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--stage1-dir", required=True)
    p.add_argument("--output-dir", default="oure-stage2-output")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    labels = pd.read_csv(Path(args.stage1_dir) / "all_fix15_subsets.csv")
    labels["mask"] = labels["mask"].astype(int)

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine); bars["symbol"] = bars["symbol"].astype(str)
    features = build_features(bars); features["symbol"] = features["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, features)

    fixed = sorted(str(x) for x in FIXED15)
    noncash = sorted(s for s in fixed if s != CASH)
    symbols = [CASH] + noncash
    start_i = int(cal.searchsorted(START, side="left"))
    spos = np.arange(start_i, len(cal) - 2, dtype=int)
    signal_dates = pd.DatetimeIndex(cal[spos])
    exec_dates = pd.DatetimeIndex(cal[spos + 1])
    score_m = score.loc[signal_dates, symbols].to_numpy(float)
    targets, counts = build_target_and_counts(score_m, len(noncash))
    eligible = np.isfinite(score_m[:, 1:])

    masks = labels["mask"].to_numpy(int)
    eras = {
        "2021_2024": np.asarray(exec_dates <= pd.Timestamp("2024-12-31")),
        "2025_2026": np.asarray(exec_dates >= pd.Timestamp("2025-01-01")),
    }
    all_rows: list[dict] = []
    for era, emask in eras.items():
        all_rows.extend(architecture_rows(masks, noncash, targets, counts, eligible, emask, era))
    arch = pd.DataFrame(all_rows)

    label_long = []
    for _, r in labels.iterrows():
        label_long.append({"era":"2021_2024", "mask":int(r["mask"]), "log_growth":float(r["log_growth_2021_2024"])})
        label_long.append({"era":"2025_2026", "mask":int(r["mask"]), "log_growth":float(r["log_growth_2025_2026"])})
    merged = arch.merge(pd.DataFrame(label_long), on=["era","mask"], how="left", validate="one_to_one")
    merged.to_csv(out / "subset_identity_free_architecture.csv", index=False)

    feature_cols = [
        "coverage_share", "mean_eligible_count", "mean_competitors_when_covered",
        "coverage_efficiency", "selected_noncash_share", "leader_switch_rate",
        "mean_top1_tenure", "median_top1_tenure", "short_run_le2_share",
        "leader_hhi", "active_member_share", "mean_pair_trend_jaccard",
        "max_pair_trend_jaccard", "mean_member_trend_episode_length",
    ]
    assoc = assoc_table(merged, feature_cols)
    assoc.to_csv(out / "feature_association_by_era.csv", index=False)

    piv = assoc.pivot(index="feature", columns="era", values="within_k_rank_corr")
    promoted = []
    for f in feature_cols:
        if f not in piv.index or not {"2021_2024","2025_2026"}.issubset(piv.columns):
            continue
        a = piv.at[f,"2021_2024"]; b = piv.at[f,"2025_2026"]
        if pd.notna(a) and pd.notna(b) and a != 0 and b != 0 and np.sign(a) == np.sign(b):
            promoted.append({"feature":f, "corr_2021_2024":float(a), "corr_2025_2026":float(b), "direction":"higher" if a>0 else "lower"})

    best_mask = int(labels.loc[labels["log_growth"].idxmax(), "mask"])
    best_arch = merged[merged["mask"] == best_mask].to_dict(orient="records")
    full_mask = (1 << len(noncash)) - 1
    fix_arch = merged[merged["mask"] == full_mask].to_dict(orient="records")
    summary = {
        "study": "OURE Stage2 identity-free Universe architecture audit",
        "status": "completed",
        "subsets": int(labels["mask"].nunique()),
        "features": feature_cols,
        "promotion_rule": "same sign of within-K rank association in 2021-24 and 2025-26; no combined score fitted",
        "directionally_consistent_features": promoted,
        "global_best_mask": best_mask,
        "global_best_architecture_by_era": best_arch,
        "fix15_architecture_by_era": fix_arch,
        "next_gate": "Preregister a low-DoF Symbol-disjoint replication rule using only a small subset of the consistent architecture features before evaluating return.",
    }
    (out / "oure_stage2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
