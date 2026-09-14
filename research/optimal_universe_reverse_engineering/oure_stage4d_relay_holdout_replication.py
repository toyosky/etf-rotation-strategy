#!/usr/bin/env python3
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
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
from optimal_universe_reverse_engineering.oure_stage4c_two_architecture_validation import architecture_metrics, parse_members

START = pd.Timestamp("2021-01-01")
SPLIT = pd.Timestamp("2025-01-01")

FROZEN_DIRECTIONS = {
    "coverage_efficiency": 1,
    "productive_switch_share": 1,
    "switch_counterfactual_gain_mean": 1,
    "leader_year_specialization": 1,
    "leader_transition_diversity": 1,
    "switch_rate": -1,
}
MANDATORY = ["productive_switch_share", "switch_counterfactual_gain_mean"]


def medians(metrics: pd.DataFrame, group: str) -> pd.DataFrame:
    num = [c for c in metrics.columns if c not in {"group", "rank", "members", "era", "source_log_growth"}]
    x = metrics[metrics["group"] == group].groupby("era")[num].median(numeric_only=True).reset_index()
    x.insert(0, "group", group)
    return x


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--stage3b-dir", required=True)
    ap.add_argument("--stage4c-dir", required=True)
    ap.add_argument("--output-dir", default="oure-stage4d-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    elite = pd.read_csv(Path(args.stage3b_dir) / "elite_universes.csv")
    rnd = pd.read_csv(Path(args.stage3b_dir) / "same_k_random_controls.csv")
    used = pd.read_csv(Path(args.stage4c_dir) / "stage4c_universe_metrics.csv")

    hold_elite = elite[(elite["rank"] >= 26) & (elite["rank"] <= 100)].sort_values("rank").copy()
    used_random_members = set(used.loc[used["group"] == "large_k_random", "members"].astype(str))
    available = rnd[~rnd["members"].astype(str).isin(used_random_members)].copy()

    control_parts = []
    counts = hold_elite["k_noncash"].value_counts().sort_index()
    for k, n in counts.items():
        pool = available[available["k_noncash"] == k].sort_values("members").head(int(n)).copy()
        if len(pool) != int(n):
            raise RuntimeError(f"Insufficient unused controls for k={k}: need {n}, got {len(pool)}")
        control_parts.append(pool)
    hold_control = pd.concat(control_parts, ignore_index=True)

    specs = []
    for group, df in [("relay_holdout_elite", hold_elite), ("relay_holdout_random", hold_control)]:
        for i, (_, r) in enumerate(df.iterrows(), 1):
            specs.append({
                "group": group,
                "rank": int(r.get("rank", i)) if group == "relay_holdout_elite" else i,
                "members": parse_members(r["members"]),
                "members_text": str(r["members"]),
                "source_log_growth": float(r["log_growth"]),
            })

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
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

    rows = []
    for spec in specs:
        for era, mask in eras.items():
            met = architecture_metrics(score, gross, signal_dates, exec_dates, spec["members"], mask)
            rows.append({
                "group": spec["group"],
                "rank": spec["rank"],
                "members": spec["members_text"],
                "source_log_growth": spec["source_log_growth"],
                "era": era,
                **met,
            })

    metrics = pd.DataFrame(rows)
    metrics.to_csv(out / "stage4d_holdout_universe_metrics.csv", index=False)

    gm = pd.concat([medians(metrics, "relay_holdout_elite"), medians(metrics, "relay_holdout_random")], ignore_index=True)
    gm.to_csv(out / "stage4d_group_medians.csv", index=False)

    effects = []
    for era in eras:
        a = gm[(gm["group"] == "relay_holdout_elite") & (gm["era"] == era)].iloc[0]
        b = gm[(gm["group"] == "relay_holdout_random") & (gm["era"] == era)].iloc[0]
        for metric, direction in FROZEN_DIRECTIONS.items():
            diff = float(a[metric] - b[metric])
            effects.append({
                "era": era,
                "metric": metric,
                "elite_median": float(a[metric]),
                "control_median": float(b[metric]),
                "difference": diff,
                "expected_direction": "higher" if direction > 0 else "lower",
                "direction_match": bool(diff * direction > 0),
                "mandatory": metric in MANDATORY,
            })
    ef = pd.DataFrame(effects)
    ef.to_csv(out / "stage4d_effects.csv", index=False)

    match = {era: int(ef[ef["era"] == era]["direction_match"].sum()) for era in eras}
    later_non_switch = ef[(ef["era"] == "2025_2026") & (ef["metric"] != "switch_rate")]
    mandatory_ok = {}
    for era in eras:
        ee = ef[(ef["era"] == era) & (ef["metric"].isin(MANDATORY))]
        mandatory_ok[era] = bool(ee["direction_match"].all())

    passed = bool(
        match["full"] >= 5
        and match["2021_2024"] >= 4
        and int(later_non_switch["direction_match"].sum()) >= 4
        and all(mandatory_ok.values())
    )

    summary = {
        "study": "OURE Stage4D relay holdout replication",
        "status": "completed",
        "holdout_elite_n": int(len(hold_elite)),
        "holdout_control_n": int(len(hold_control)),
        "holdout_k_counts": {str(int(k)): int(v) for k, v in counts.items()},
        "frozen_directions": FROZEN_DIRECTIONS,
        "direction_matches": match,
        "later_non_switch_matches": int(later_non_switch["direction_match"].sum()),
        "mandatory_ok": mandatory_ok,
        "replication_pass": passed,
    }
    (out / "oure_stage4d_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
