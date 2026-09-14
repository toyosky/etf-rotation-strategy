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

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
from optimal_universe_reverse_engineering.oure_stage4c_two_architecture_validation import parse_members

START = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")


def norm_label(x: object) -> str:
    if x is None or pd.isna(x) or str(x).strip() == "":
        return "UNKNOWN"
    return str(x).strip().upper()


def static_taxonomy_metrics(members: list[str], meta: pd.DataFrame) -> dict:
    mm = meta.set_index("symbol")
    out: dict[str, float] = {}
    for field, prefix in [("risk_bucket", "risk_bucket"), ("exposure_level1", "exposure1")]:
        labels = [norm_label(mm.at[s, field]) if s in mm.index else "UNKNOWN" for s in members]
        vc = pd.Series(labels).value_counts()
        k = len(labels)
        shares = vc.to_numpy(float) / max(1, k)
        pairs = k * (k - 1) / 2
        same_pairs = float(np.sum(vc.to_numpy(float) * (vc.to_numpy(float) - 1) / 2))
        out[f"{prefix}_unique_share"] = float(len(vc) / max(1, k))
        out[f"{prefix}_hhi"] = float(np.square(shares).sum()) if len(shares) else np.nan
        out[f"{prefix}_max_member_share"] = float(shares.max()) if len(shares) else np.nan
        out[f"same_{prefix}_pair_share"] = float(same_pairs / pairs) if pairs > 0 else np.nan
        out[f"{prefix}_unknown_share"] = float(np.mean(np.asarray(labels) == "UNKNOWN")) if labels else np.nan
    return out


def dynamic_domain_metrics(score: pd.DataFrame, signal_dates: pd.DatetimeIndex,
                           members: list[str], meta: pd.DataFrame,
                           era_mask: np.ndarray) -> dict:
    mm = meta.set_index("symbol")
    m = [s for s in members if s in score.columns]
    if not m:
        return {}
    buckets = [norm_label(mm.at[s, "risk_bucket"]) if s in mm.index else "UNKNOWN" for s in m]
    sm_all = score.loc[signal_dates, m].to_numpy(float)
    sub = np.flatnonzero(era_mask)
    sm = sm_all[sub]
    eligible = np.isfinite(sm)
    safe = np.where(eligible, sm, -np.inf)
    t, k = sm.shape

    j_all: list[float] = []
    j_same: list[float] = []
    j_cross: list[float] = []
    for i in range(k):
        for j in range(i + 1, k):
            union = eligible[:, i] | eligible[:, j]
            if not union.any():
                continue
            val = float((eligible[:, i] & eligible[:, j]).sum() / union.sum())
            j_all.append(val)
            if buckets[i] == buckets[j]:
                j_same.append(val)
            else:
                j_cross.append(val)

    leader = np.full(t, -1, dtype=int)
    best = safe.max(axis=1)
    has = np.isfinite(best)
    leader[has] = np.argmax(safe[has], axis=1)

    top2_same: list[bool] = []
    for r in range(t):
        idx = np.flatnonzero(eligible[r])
        if len(idx) < 2:
            continue
        vals = sm[r, idx]
        order = np.argsort(vals)[-2:]
        i1, i2 = int(idx[order[-1]]), int(idx[order[-2]])
        top2_same.append(buckets[i1] == buckets[i2])

    transitions: list[bool] = []
    for r in range(1, t):
        old, new = int(leader[r - 1]), int(leader[r])
        if old < 0 or new < 0 or old == new:
            continue
        transitions.append(buckets[old] != buckets[new])

    active = np.unique(leader[leader >= 0])
    active_buckets = {buckets[int(i)] for i in active}

    return {
        "mean_pair_trend_jaccard": float(np.mean(j_all)) if j_all else np.nan,
        "max_pair_trend_jaccard": float(np.max(j_all)) if j_all else np.nan,
        "mean_same_risk_bucket_trend_jaccard": float(np.mean(j_same)) if j_same else np.nan,
        "mean_cross_risk_bucket_trend_jaccard": float(np.mean(j_cross)) if j_cross else np.nan,
        "top2_same_risk_bucket_share": float(np.mean(top2_same)) if top2_same else np.nan,
        "cross_risk_bucket_transition_share": float(np.mean(transitions)) if transitions else np.nan,
        "active_leader_bucket_diversity_share": float(len(active_buckets) / len(active)) if len(active) else np.nan,
        "active_leader_count": int(len(active)),
    }


def group_medians(df: pd.DataFrame) -> pd.DataFrame:
    excluded = {"construction", "group", "rank", "members", "era", "source_log_growth", "k_noncash"}
    nums = [c for c in df.columns if c not in excluded]
    return df.groupby(["construction", "group", "era"])[nums].median(numeric_only=True).reset_index()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--stage3b-dir", required=True)
    ap.add_argument("--stage4c-dir", required=True)
    ap.add_argument("--stage3c-dir", required=True)
    ap.add_argument("--output-dir", default="oure-stage4f-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    s3b = Path(args.stage3b_dir)
    e3b = pd.read_csv(s3b / "elite_universes.csv")
    r3b = pd.read_csv(s3b / "same_k_random_controls.csv")
    used = pd.read_csv(Path(args.stage4c_dir) / "stage4c_universe_metrics.csv")
    hold_elite = e3b[(e3b["rank"] >= 26) & (e3b["rank"] <= 100)].sort_values("rank").copy()
    used_random = set(used.loc[used["group"] == "large_k_random", "members"].astype(str))
    available = r3b[~r3b["members"].astype(str).isin(used_random)].copy()
    hold_controls = []
    for k, n in hold_elite["k_noncash"].value_counts().sort_index().items():
        pool = available[available["k_noncash"] == k].sort_values("members").head(int(n)).copy()
        if len(pool) != int(n):
            raise RuntimeError(f"Insufficient Stage3B controls for K={k}")
        hold_controls.append(pool)
    hold_control = pd.concat(hold_controls, ignore_index=True)

    s3c = Path(args.stage3c_dir)
    e3c = pd.read_csv(s3c / "elite_universes.csv")
    r3c = pd.read_csv(s3c / "same_k_random_controls.csv")
    ext_elite = e3c[(e3c["rank"] >= 1) & (e3c["rank"] <= 25)].sort_values("rank").copy()
    ext_controls = []
    for k, n in ext_elite["k_noncash"].value_counts().sort_index().items():
        pool = r3c[r3c["k_noncash"] == k].sort_values("members").head(int(n)).copy()
        if len(pool) != int(n):
            raise RuntimeError(f"Insufficient Stage3C controls for K={k}")
        ext_controls.append(pool)
    ext_control = pd.concat(ext_controls, ignore_index=True)

    specs: list[dict] = []
    for construction, elite_df, control_df in [
        ("stage3b_holdout", hold_elite, hold_control),
        ("stage3c_external", ext_elite, ext_control),
    ]:
        for group, df in [("elite", elite_df), ("control", control_df)]:
            for i, (_, r) in enumerate(df.iterrows(), 1):
                specs.append({
                    "construction": construction,
                    "group": group,
                    "rank": int(r.get("rank", i)) if group == "elite" else i,
                    "members": parse_members(r["members"]),
                    "members_text": str(r["members"]),
                    "k_noncash": int(r["k_noncash"]),
                    "source_log_growth": float(r["log_growth"]),
                })

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    meta = pd.read_sql_query(text("""
        select symbol, asset_class, region_primary, exposure_level1, exposure_level2,
               underlying_key, risk_bucket, style_sector
        from public.instrument_metadata_current
        where has_daily_bars
    """), eng)
    meta["symbol"] = meta["symbol"].astype(str)

    bars = load_daily_bars(eng)
    bars["symbol"] = bars["symbol"].astype(str)
    feat = build_features(bars)
    feat["symbol"] = feat["symbol"].astype(str)
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    start_i = int(cal.searchsorted(START, side="left"))
    spos = np.arange(start_i, len(cal) - 2, dtype=int)
    signal_dates = pd.DatetimeIndex(cal[spos])
    exec_dates = pd.DatetimeIndex(cal[spos + 1])
    eras = {
        "full": np.ones(len(exec_dates), dtype=bool),
        "2021_2024": np.asarray(exec_dates < SPLIT),
        "2025_2026": np.asarray(exec_dates >= SPLIT),
    }

    rows: list[dict] = []
    for spec in specs:
        static = static_taxonomy_metrics(spec["members"], meta)
        for era, mask in eras.items():
            dyn = dynamic_domain_metrics(score, signal_dates, spec["members"], meta, mask)
            rows.append({
                "construction": spec["construction"],
                "group": spec["group"],
                "rank": spec["rank"],
                "members": spec["members_text"],
                "k_noncash": spec["k_noncash"],
                "source_log_growth": spec["source_log_growth"],
                "era": era,
                **static,
                **dyn,
            })

    detail = pd.DataFrame(rows)
    detail.to_csv(out / "stage4f_domain_metrics.csv", index=False)
    gm = group_medians(detail)
    gm.to_csv(out / "stage4f_group_medians.csv", index=False)

    metrics = [
        "risk_bucket_hhi",
        "top2_same_risk_bucket_share",
        "cross_risk_bucket_transition_share",
        "risk_bucket_unique_share",
        "risk_bucket_max_member_share",
        "same_risk_bucket_pair_share",
        "exposure1_hhi",
        "exposure1_unique_share",
        "same_exposure1_pair_share",
        "mean_pair_trend_jaccard",
        "max_pair_trend_jaccard",
        "mean_same_risk_bucket_trend_jaccard",
        "mean_cross_risk_bucket_trend_jaccard",
        "active_leader_bucket_diversity_share",
    ]
    effects: list[dict] = []
    for construction in ["stage3b_holdout", "stage3c_external"]:
        for era in eras:
            a = gm[(gm.construction == construction) & (gm.group == "elite") & (gm.era == era)].iloc[0]
            b = gm[(gm.construction == construction) & (gm.group == "control") & (gm.era == era)].iloc[0]
            for metric in metrics:
                effects.append({
                    "construction": construction,
                    "era": era,
                    "metric": metric,
                    "elite_median": float(a[metric]),
                    "control_median": float(b[metric]),
                    "difference": float(a[metric] - b[metric]),
                })
    ef = pd.DataFrame(effects)
    ef.to_csv(out / "stage4f_effects.csv", index=False)

    primary = {
        "risk_bucket_hhi": -1,
        "top2_same_risk_bucket_share": -1,
        "cross_risk_bucket_transition_share": 1,
    }
    gate_detail = []
    construction_pass = {}
    cross_ok = {}
    for construction in ["stage3b_holdout", "stage3c_external"]:
        sub = ef[(ef.construction == construction) & (ef.era == "full")]
        matches = {}
        for metric, direction in primary.items():
            diff = float(sub[sub.metric == metric].iloc[0]["difference"])
            matches[metric] = bool(diff * direction > 0)
            gate_detail.append({"construction": construction, "metric": metric, "difference": diff, "direction_match": matches[metric]})
        construction_pass[construction] = int(sum(matches.values()))
        cross_ok[construction] = bool(matches["cross_risk_bucket_transition_share"])

    strong = bool(all(v == 3 for v in construction_pass.values()))
    partial = bool((not strong) and all(v >= 2 for v in construction_pass.values()) and all(cross_ok.values()))
    if strong:
        decision = "strong_support_cross_domain_relay"
    elif partial:
        decision = "partial_support_cross_domain_relay"
    else:
        decision = "domain_complementarity_not_established"

    pd.DataFrame(gate_detail).to_csv(out / "stage4f_primary_gate.csv", index=False)
    summary = {
        "study": "OURE Stage4F domain complementarity / cross-exposure relay",
        "status": "completed",
        "samples": {
            "stage3b_holdout_elite": int(len(hold_elite)),
            "stage3b_holdout_control": int(len(hold_control)),
            "stage3c_external_elite": int(len(ext_elite)),
            "stage3c_external_control": int(len(ext_control)),
        },
        "primary_gate_matches": construction_pass,
        "cross_transition_mandatory": cross_ok,
        "strong_support": strong,
        "partial_support": partial,
        "decision": decision,
        "metadata_caveat": "instrument_metadata_current is structural/current, not historical point-in-time metadata; Stage4F is explanatory only",
    }
    (out / "oure_stage4f_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
