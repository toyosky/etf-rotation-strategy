#!/usr/bin/env python3
from __future__ import annotations

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
import cluster90_resistance_score_v1_test as v1lib
import optimal_universe_reverse_engineering.oure_stage8m_fixv2_v1_long_horizon as s8m

RISK = tuple(s8m.MAIN_RISK)
COST = 0.0006
V1_THRESHOLD = 75.0

# Pre-specified by economic role, not by observed backtest performance.
DEFENSIVES = {
    "511220": "城投债ETF海富通",
    "511010": "国债ETF国泰",
    "159001": "货币ETF易方达",
    "511260": "十年国债ETF国泰",
    "511360": "短融ETF海富通",
    "511520": "政金债ETF富国",
    "511580": "国债政金债ETF招商",
}


def side_count(prev: str | None, cur: str | None) -> int:
    if prev == cur:
        return 0
    if prev is None or cur is None:
        return 1
    return 2


def choose_target(score: pd.DataFrame, d: pd.Timestamp, defensive: str) -> str | None:
    vals = score.loc[d, list(RISK)].astype(float)
    vals = vals[np.isfinite(vals)]
    if vals.empty:
        return None
    sym = str(vals.idxmax())
    rv = float(vals.loc[sym])
    dv = float(score.at[d, defensive]) if defensive in score.columns and pd.notna(score.at[d, defensive]) else -np.inf
    return sym if np.isfinite(rv) and rv > dv else None


def build_raw(cal: pd.DatetimeIndex, score: pd.DataFrame, defensive: str, start_i: int, last_i: int) -> pd.DataFrame:
    rows = []
    prev = None
    for i in range(start_i, last_i + 1):
        d = pd.Timestamp(cal[i])
        cur = choose_target(score, d, defensive)
        rows.append({
            "signal_pos": i,
            "signal_date": d,
            "execution_date": pd.Timestamp(cal[i + 1]),
            "return_end_date": pd.Timestamp(cal[i + 2]),
            "target": cur,
            "sides": side_count(prev, cur),
        })
        prev = cur
    return pd.DataFrame(rows)


def build_v1(raw: pd.DataFrame, score: pd.DataFrame, raw_delta: pd.DataFrame,
             profiles: dict, defensive: str) -> pd.DataFrame:
    rows = []
    current = None
    prev_output = None
    rset = set(RISK)
    for r in raw.itertuples(index=False):
        d = pd.Timestamp(r.signal_date)
        challenger = None if pd.isna(r.target) else str(r.target)
        rp = np.nan
        sd = np.nan
        if challenger is not None and challenger in raw_delta.columns:
            x = raw_delta.at[d, challenger]
            if pd.notna(x) and np.isfinite(x):
                sd = float(x)
        if challenger is not None:
            x = profiles.get((d, challenger), np.nan)
            if pd.notna(x) and np.isfinite(x):
                rp = float(x)

        if challenger == current:
            pass
        elif challenger is None:
            current = None  # never veto exit to defensive/cash
        elif current is None:
            current = challenger
        else:
            dv = float(score.at[d, defensive]) if defensive in score.columns and pd.notna(score.at[d, defensive]) else -np.inf
            ov = float(score.at[d, current]) if current in score.columns and pd.notna(score.at[d, current]) else np.nan
            incumbent_valid = bool(current in rset and np.isfinite(ov) and ov > dv)
            if not incumbent_valid:
                current = challenger
            elif np.isfinite(rp) and rp >= V1_THRESHOLD and np.isfinite(sd) and sd <= 0.0:
                pass
            else:
                current = challenger

        rows.append({
            "signal_pos": int(r.signal_pos),
            "signal_date": d,
            "execution_date": pd.Timestamp(r.execution_date),
            "return_end_date": pd.Timestamp(r.return_end_date),
            "target": current,
            "sides": side_count(prev_output, current),
        })
        prev_output = current
    return pd.DataFrame(rows)


def attach_signal_only(path: pd.DataFrame, gross: pd.DataFrame) -> pd.DataFrame:
    return s8m.attach_returns(path, gross, COST)


def attach_held_defensive(path: pd.DataFrame, gross: pd.DataFrame, defensive: str) -> pd.DataFrame:
    z = path.copy()
    actual = z["target"].where(z["target"].notna(), defensive).astype(str)
    sides = []
    prev = None
    for cur in actual.tolist():
        sides.append(side_count(prev, cur))
        prev = cur
    gs = []
    for d, sym in zip(z["signal_date"], actual):
        x = gross.at[pd.Timestamp(d), sym] if sym in gross.columns else np.nan
        gs.append(float(x) if pd.notna(x) and np.isfinite(x) else 0.0)
    z["target"] = actual
    z["sides"] = np.asarray(sides, dtype=int)
    z["gross_ret"] = np.asarray(gs, dtype=float)
    z["net_ret"] = (1.0 + z["gross_ret"].to_numpy(float)) * (1.0 - COST * z["sides"].to_numpy(int)) - 1.0
    z["cost_per_side"] = COST
    return z


def stat_row(label: str, defensive: str, mode: str, overlay: str, p: pd.DataFrame) -> dict:
    rec = {
        "window": label,
        "defensive": defensive,
        "name": DEFENSIVES[defensive],
        "mode": mode,
        "overlay": overlay,
        **s8m.stats(p),
    }
    rec["defensive_days"] = int((p["target"].astype(str) == defensive).sum()) if mode == "HELD" else int(p["target"].isna().sum())
    return rec


def main() -> None:
    db = os.getenv("ETF_DAILY_BARS_DATABASE_URL")
    if not db:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(os.getenv("OUTPUT_DIR", "stage8p-defensive-anchor-output"))
    out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(db), pool_pre_ping=True)
    bars = load_daily_bars(eng)
    bars["symbol"] = bars["symbol"].astype(str).str.zfill(6)
    bars["date"] = pd.to_datetime(bars["date"])
    feat = build_features(bars)
    feat["symbol"] = feat["symbol"].astype(str).str.zfill(6)
    feat["date"] = pd.to_datetime(feat["date"])
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)

    missing = [s for s in list(RISK) + list(DEFENSIVES) if s not in score.columns]
    if missing:
        raise RuntimeError(f"missing symbols in score matrix: {missing}")

    raw_score = s8m.raw_score_wide(feat, cal, list(score.columns.astype(str)))
    raw_delta = raw_score.diff()
    profile_df = v1lib.build_needed_profiles(bars, set(RISK))
    profile_map = profile_df.set_index(["date", "symbol"])["resistance_pct252"].to_dict()
    last_i = len(cal) - 3

    # Windows are intentionally fixed before results are viewed.
    windows = {
        "FULL_AVAILABLE": None,
        "COMMON_2023": pd.Timestamp("2023-01-01"),
    }
    rows = []
    annual_focus = []

    for defensive in DEFENSIVES:
        ok = score[defensive].notna() & np.isfinite(score[defensive])
        if not ok.any():
            continue
        first_valid = pd.Timestamp(score.index[ok][0])

        for wlabel, floor in windows.items():
            start = first_valid if floor is None else max(first_valid, floor)
            eligible = cal[cal >= start]
            if len(eligible) == 0:
                continue
            start_i = int(cal.get_loc(pd.Timestamp(eligible[0])))
            if start_i > last_i:
                continue

            raw = build_raw(cal, score, defensive, start_i, last_i)
            v1 = build_v1(raw, score, raw_delta, profile_map, defensive)
            for overlay, base in (("RAW", raw), ("V1_75", v1)):
                p0 = attach_signal_only(base, gross)
                ph = attach_held_defensive(base, gross, defensive)
                rows.append(stat_row(wlabel, defensive, "SIGNAL_ONLY", overlay, p0))
                rows.append(stat_row(wlabel, defensive, "HELD", overlay, ph))

                if defensive == "511220" and wlabel == "FULL_AVAILABLE" and overlay == "V1_75":
                    a0 = s8m.annual_table(p0, None, "511220_SIGNAL_ONLY")
                    ah = s8m.annual_table(ph, None, "511220_HELD")
                    annual_focus.extend([a0, ah])

    results = pd.DataFrame(rows)
    results.to_csv(out / "stage8p_defensive_comparison.csv", index=False)
    if annual_focus:
        pd.concat(annual_focus, ignore_index=True).to_csv(out / "stage8p_511220_annual.csv", index=False)

    # Focused deltas: same comparator and same signal path, only 0%-cash vs actually holding defensive.
    piv = results.pivot_table(
        index=["window", "defensive", "name", "overlay"],
        columns="mode",
        values=["cagr", "mdd", "sharpe_0rf", "calmar", "total_return", "turnover_sides", "defensive_days"],
        aggfunc="first",
    )
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    piv = piv.reset_index()
    piv["cagr_delta_pp_held_vs_zero"] = (piv["cagr_HELD"] - piv["cagr_SIGNAL_ONLY"]) * 100.0
    piv["total_return_delta_pp_held_vs_zero"] = (piv["total_return_HELD"] - piv["total_return_SIGNAL_ONLY"]) * 100.0
    piv["mdd_delta_pp_held_vs_zero"] = (piv["mdd_HELD"] - piv["mdd_SIGNAL_ONLY"]) * 100.0
    piv["sharpe_delta"] = piv["sharpe_0rf_HELD"] - piv["sharpe_0rf_SIGNAL_ONLY"]
    piv.to_csv(out / "stage8p_held_vs_zero_delta.csv", index=False)

    focus = piv[(piv.window == "FULL_AVAILABLE") & (piv.defensive == "511220")].copy()
    common = piv[(piv.window == "COMMON_2023") & (piv.overlay == "V1_75")].copy()

    summary = {
        "study": "OURE Stage8P defensive-anchor audit",
        "purpose": "isolate 511220 signal/comparator value from investable defensive-carrier value, then exploratory role-substitution audit",
        "cost_per_side": COST,
        "risk_universe": list(RISK),
        "defensives": DEFENSIVES,
        "511220_full_available": focus.to_dict(orient="records"),
        "common_2023_v1": common.to_dict(orient="records"),
        "interpretation_rule": "Exploratory only. Do not promote a replacement from same-sample ranking; first isolate 511220 held-vs-zero effect, then use common-window robustness as evidence for a future frozen test.",
    }
    (out / "stage8p_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    md = []
    md.append("# Stage8P — 511220 Defensive Anchor Audit")
    md.append("")
    md.append("## 511220: same signals, zero-cash vs actually holding 511220")
    md.append("")
    if not focus.empty:
        show = focus[["overlay","cagr_SIGNAL_ONLY","cagr_HELD","cagr_delta_pp_held_vs_zero","mdd_SIGNAL_ONLY","mdd_HELD","sharpe_0rf_SIGNAL_ONLY","sharpe_0rf_HELD","turnover_sides_SIGNAL_ONLY","turnover_sides_HELD","defensive_days_SIGNAL_ONLY"]].copy()
        md.append(show.to_markdown(index=False, floatfmt=".4f"))
    md.append("")
    md.append("## Common 2023+ defensive-carrier comparison (V1-75)")
    md.append("")
    if not common.empty:
        show = common[["defensive","name","cagr_SIGNAL_ONLY","cagr_HELD","cagr_delta_pp_held_vs_zero","mdd_HELD","sharpe_0rf_HELD","calmar_HELD","defensive_days_HELD"]].copy()
        md.append(show.to_markdown(index=False, floatfmt=".4f"))
    md.append("")
    md.append("Interpretation: this stage is diagnostic/exploratory; same-sample ranking is not a promotion rule.")
    (out / "stage8p_summary.md").write_text("\n".join(md), encoding="utf-8")

    print((out / "stage8p_summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
