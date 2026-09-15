#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import cluster90_resistance_score_v1_test as v1lib
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

CASH = "511220"
START_FLOOR = pd.Timestamp("2015-01-01")
COSTS = (0.0006, 0.0012, 0.0020, 0.0030)
V1_THRESHOLDS = (70.0, 75.0, 80.0)
MAIN_THRESHOLD = 75.0

MAIN_RISK = (
    "159934",  # gold carrier replaces 518880
    "159985",  # soymeal
    "161226",  # silver
    "513100",  # Nasdaq 100
    "159957",  # standard ChiNext carrier replaces 159915
    "159509",  # Nasdaq technology
    "513290",  # Nasdaq biotech
    "159529",  # S&P consumer
    "159981",  # energy-chemical retained in main version
    "501018",  # crude oil
    "513530",  # HK dividend role replaces 513920
    "511380",  # convertible bonds
    "164824",  # India
)
MAIN_MEMBERS = tuple(sorted(MAIN_RISK + (CASH,)))
NO_ENCHEM_MEMBERS = tuple(sorted(tuple(x for x in MAIN_RISK if x != "159981") + (CASH,)))


def raw_score_wide(feat: pd.DataFrame, cal: pd.DatetimeIndex, symbols: list[str]) -> pd.DataFrame:
    z = feat.copy()
    z["date"] = pd.to_datetime(z["date"])
    z["symbol"] = z["symbol"].astype(str).str.zfill(6)
    return z.pivot(index="date", columns="symbol", values="score").reindex(index=cal, columns=symbols)


def choose_target(score: pd.DataFrame, d: pd.Timestamp, members: tuple[str, ...]) -> str | None:
    risk = [s for s in members if s != CASH and s in score.columns]
    vals = score.loc[d, risk].astype(float)
    vals = vals[np.isfinite(vals)]
    if vals.empty:
        return None
    sym = str(vals.idxmax())
    rv = float(vals.loc[sym])
    cv = float(score.at[d, CASH]) if CASH in score.columns and pd.notna(score.at[d, CASH]) else -np.inf
    return sym if np.isfinite(rv) and rv > cv else None


def side_count(prev: str | None, cur: str | None) -> int:
    if prev == cur:
        return 0
    if prev is None or cur is None:
        return 1
    return 2


def build_raw_targets(cal, score, members, start_i, last_i) -> pd.DataFrame:
    rows = []
    prev = None
    for i in range(start_i, last_i + 1):
        d = pd.Timestamp(cal[i])
        cur = choose_target(score, d, members)
        sides = side_count(prev, cur)
        rows.append({
            "signal_pos": i,
            "signal_date": d,
            "execution_date": pd.Timestamp(cal[i + 1]),
            "return_end_date": pd.Timestamp(cal[i + 2]),
            "target": cur,
            "sides": sides,
        })
        prev = cur
    return pd.DataFrame(rows)


def build_v1_targets(raw: pd.DataFrame, score: pd.DataFrame, raw_delta: pd.DataFrame,
                     profiles: dict, members: tuple[str, ...], threshold: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    events = []
    current = None
    prev_output = None
    mset = set(members)
    for r in raw.itertuples(index=False):
        d = pd.Timestamp(r.signal_date)
        challenger = None if pd.isna(r.target) else str(r.target)
        old = current
        rp = np.nan
        sd = np.nan
        decision = "HOLD"

        if challenger is not None and challenger in raw_delta.columns:
            x = raw_delta.at[d, challenger]
            if pd.notna(x) and np.isfinite(x):
                sd = float(x)
        if challenger is not None:
            x = profiles.get((d, challenger), np.nan)
            if pd.notna(x) and np.isfinite(x):
                rp = float(x)

        if challenger == current:
            decision = "HOLD"
        elif challenger is None:
            current = None
            decision = "EXIT_CASH"
        elif current is None:
            current = challenger
            decision = "ENTER"
        else:
            cv = float(score.at[d, CASH]) if CASH in score.columns and pd.notna(score.at[d, CASH]) else -np.inf
            ov = float(score.at[d, current]) if current in score.columns and pd.notna(score.at[d, current]) else np.nan
            incumbent_valid = bool(current in mset and current != CASH and np.isfinite(ov) and ov > cv)
            if not incumbent_valid:
                current = challenger
                decision = "SWITCH_OLD_INVALID"
            elif math.isfinite(rp) and rp >= threshold and math.isfinite(sd) and sd <= 0.0:
                decision = "VETO_V1"
            else:
                current = challenger
                decision = "SWITCH_NORMAL"

        sides = side_count(prev_output, current)
        rows.append({
            "signal_pos": int(r.signal_pos),
            "signal_date": d,
            "execution_date": pd.Timestamp(r.execution_date),
            "return_end_date": pd.Timestamp(r.return_end_date),
            "target": current,
            "sides": sides,
            "challenger": challenger,
            "resistance_pct252": rp,
            "score_delta_new": sd,
            "decision": decision,
        })
        if decision != "HOLD":
            events.append({
                "signal_date": d,
                "execution_date": pd.Timestamp(r.execution_date),
                "incumbent": old,
                "challenger": challenger,
                "resistance_pct252": rp,
                "score_delta_new": sd,
                "decision": decision,
                "target_after": current,
                "threshold": threshold,
            })
        prev_output = current
    return pd.DataFrame(rows), pd.DataFrame(events)


def attach_returns(path: pd.DataFrame, gross: pd.DataFrame, cost: float) -> pd.DataFrame:
    z = path.copy()
    gs = []
    for r in z.itertuples(index=False):
        target = None if pd.isna(r.target) else str(r.target)
        g = 0.0
        if target is not None and target in gross.columns:
            x = gross.at[pd.Timestamp(r.signal_date), target]
            if pd.notna(x) and np.isfinite(x):
                g = float(x)
        gs.append(g)
    z["gross_ret"] = np.asarray(gs, float)
    z["net_ret"] = (1.0 + z["gross_ret"].to_numpy(float)) * (1.0 - cost * z["sides"].to_numpy(int)) - 1.0
    z["cost_per_side"] = cost
    return z


def run_lengths(targets: pd.Series) -> tuple[float, float, float, float, int]:
    vals = targets.where(targets.notna(), "__CASH__").astype(str).tolist()
    all_runs = []
    risk_runs = []
    if vals:
        cur, n = vals[0], 1
        for v in vals[1:]:
            if v == cur:
                n += 1
            else:
                all_runs.append(n)
                if cur != "__CASH__":
                    risk_runs.append(n)
                cur, n = v, 1
        all_runs.append(n)
        if cur != "__CASH__":
            risk_runs.append(n)
    return (
        float(np.mean(all_runs)) if all_runs else np.nan,
        float(np.median(all_runs)) if all_runs else np.nan,
        float(np.mean(risk_runs)) if risk_runs else np.nan,
        float(np.median(risk_runs)) if risk_runs else np.nan,
        int(len(risk_runs)),
    )


def rolling_worst(r: pd.Series, n: int) -> float:
    if len(r) < n:
        return np.nan
    logs = np.log1p(np.clip(r.to_numpy(float), -0.999999999, None))
    s = pd.Series(logs).rolling(n).sum()
    return float(np.expm1(s.min()))


def stats(path: pd.DataFrame) -> dict:
    if path.empty:
        return {}
    r = path["net_ret"].to_numpy(float)
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.r_[1.0, eq])[1:]
    dd = eq / peak - 1.0
    total = float(eq[-1] - 1.0)
    years = len(path) / 252.0
    cagr = float(eq[-1] ** (1.0 / years) - 1.0) if years > 0 and eq[-1] > 0 else np.nan
    vol = float(np.std(r, ddof=1) * np.sqrt(252)) if len(r) > 1 else np.nan
    sharpe = float(np.mean(r) / np.std(r, ddof=1) * np.sqrt(252)) if len(r) > 1 and np.std(r, ddof=1) > 0 else np.nan
    mdd = float(np.min(dd))
    calmar = float(cagr / abs(mdd)) if np.isfinite(cagr) and mdd < 0 else np.nan
    state_mean, state_med, risk_mean, risk_med, risk_eps = run_lengths(path["target"])
    targets = path["target"].where(path["target"].notna(), "__CASH__").astype(str).tolist()
    switches = int(sum(a != b for a, b in zip(targets[1:], targets[:-1])))
    return {
        "sessions": int(len(path)),
        "total_return": total,
        "cagr": cagr,
        "mdd": mdd,
        "ann_vol": vol,
        "sharpe_0rf": sharpe,
        "calmar": calmar,
        "turnover_sides": int(path["sides"].sum()),
        "switches": switches,
        "mean_state_tenure": state_mean,
        "median_state_tenure": state_med,
        "mean_risk_tenure": risk_mean,
        "median_risk_tenure": risk_med,
        "risk_episodes": risk_eps,
        "positive_day_rate": float(np.mean(r > 0)),
        "best_day": float(np.max(r)),
        "worst_day": float(np.min(r)),
        "worst_5d": rolling_worst(path["net_ret"], 5),
        "worst_20d": rolling_worst(path["net_ret"], 20),
    }


def annual_table(path: pd.DataFrame, events: pd.DataFrame | None, variant: str) -> pd.DataFrame:
    rows = []
    years = sorted(path["execution_date"].dt.year.unique())
    for y in years:
        g = path[path["execution_date"].dt.year == y].copy()
        rec = {"variant": variant, "year": int(y), **stats(g)}
        rec["start"] = str(g["execution_date"].min().date())
        rec["end"] = str(g["execution_date"].max().date())
        if events is not None and not events.empty:
            e = events[events["execution_date"].dt.year == y]
            rec["veto_count"] = int((e["decision"] == "VETO_V1").sum())
            rec["normal_switch_events"] = int((e["decision"] == "SWITCH_NORMAL").sum())
            rec["forced_switch_events"] = int((e["decision"] == "SWITCH_OLD_INVALID").sum())
        else:
            rec["veto_count"] = 0
            rec["normal_switch_events"] = np.nan
            rec["forced_switch_events"] = np.nan
        rows.append(rec)
    return pd.DataFrame(rows)


def contribution_table(path: pd.DataFrame, variant: str, annual: bool) -> pd.DataFrame:
    z = path.copy()
    z["symbol"] = z["target"].where(z["target"].notna(), "__CASH__").astype(str)
    z["log_net"] = np.log1p(np.clip(z["net_ret"].to_numpy(float), -0.999999999, None))
    z["log_gross"] = np.log1p(np.clip(z["gross_ret"].to_numpy(float), -0.999999999, None))
    z["switch_in"] = (z["symbol"] != z["symbol"].shift(1)).astype(int)
    if annual:
        z["year"] = z["execution_date"].dt.year.astype(int)
        groups = ["year", "symbol"]
    else:
        groups = ["symbol"]
    rows = []
    total_log_by_year = z.groupby("year")["log_net"].sum().to_dict() if annual else None
    total_log = float(z["log_net"].sum()) if not annual else None
    for key, g in z.groupby(groups, sort=True):
        if annual:
            y, sym = key
            denom = float(total_log_by_year.get(int(y), np.nan))
        else:
            sym = key[0] if isinstance(key, tuple) else key
            y = None
            denom = total_log
        ln = float(g["log_net"].sum())
        lg = float(g["log_gross"].sum())
        rec = {
            "variant": variant,
            "symbol": str(sym),
            "holding_days": int(len(g)),
            "switch_ins": int(g["switch_in"].sum()),
            "net_log_contribution": ln,
            "gross_log_contribution": lg,
            "isolated_net_compound": float(np.expm1(ln)),
            "isolated_gross_compound": float(np.expm1(lg)),
            "net_log_growth_share": float(ln / denom) if denom is not None and np.isfinite(denom) and abs(denom) > 1e-12 else np.nan,
            "daily_win_rate": float(np.mean(g["net_ret"].to_numpy(float) > 0)),
            "avg_daily_net": float(g["net_ret"].mean()),
        }
        if annual:
            rec["year"] = int(y)
        rows.append(rec)
    cols = (["variant", "year", "symbol"] if annual else ["variant", "symbol"])
    return pd.DataFrame(rows).sort_values(cols)


def episode_table(path: pd.DataFrame, variant: str) -> pd.DataFrame:
    z = path.copy().reset_index(drop=True)
    z["symbol"] = z["target"].where(z["target"].notna(), "__CASH__").astype(str)
    z["episode"] = (z["symbol"] != z["symbol"].shift(1)).cumsum()
    rows = []
    for eid, g in z.groupby("episode"):
        ln = float(np.log1p(np.clip(g["net_ret"].to_numpy(float), -0.999999999, None)).sum())
        lg = float(np.log1p(np.clip(g["gross_ret"].to_numpy(float), -0.999999999, None)).sum())
        rows.append({
            "variant": variant,
            "episode": int(eid),
            "symbol": str(g["symbol"].iloc[0]),
            "start_execution": str(g["execution_date"].iloc[0].date()),
            "end_execution": str(g["execution_date"].iloc[-1].date()),
            "days": int(len(g)),
            "net_return": float(np.expm1(ln)),
            "gross_return": float(np.expm1(lg)),
            "sides": int(g["sides"].sum()),
        })
    return pd.DataFrame(rows)


def drawdown_table(path: pd.DataFrame, variant: str, topn: int = 12) -> pd.DataFrame:
    z = path.reset_index(drop=True).copy()
    eq = np.cumprod(1.0 + z["net_ret"].to_numpy(float))
    dates = pd.to_datetime(z["return_end_date"]).tolist()
    episodes = []
    peak_value = 1.0
    peak_idx = -1
    in_dd = False
    start_peak_idx = -1
    trough_idx = -1
    trough_dd = 0.0
    for i, val in enumerate(eq):
        if val >= peak_value - 1e-14:
            if in_dd:
                episodes.append((start_peak_idx, trough_idx, i, trough_dd, True))
                in_dd = False
            peak_value = val
            peak_idx = i
            continue
        dd = val / peak_value - 1.0
        if not in_dd:
            in_dd = True
            start_peak_idx = peak_idx
            trough_idx = i
            trough_dd = dd
        elif dd < trough_dd:
            trough_idx = i
            trough_dd = dd
    if in_dd:
        episodes.append((start_peak_idx, trough_idx, len(eq) - 1, trough_dd, False))
    rows = []
    for p, t, r, depth, recovered in episodes:
        peak_date = dates[p] if p >= 0 else pd.to_datetime(z["execution_date"].iloc[0])
        rows.append({
            "variant": variant,
            "peak_date": str(pd.Timestamp(peak_date).date()),
            "trough_date": str(pd.Timestamp(dates[t]).date()),
            "recovery_or_end_date": str(pd.Timestamp(dates[r]).date()),
            "depth": float(depth),
            "days_peak_to_trough": int(t - max(p, -1)),
            "days_underwater": int(r - max(p, -1)),
            "recovered": bool(recovered),
        })
    if not rows:
        return pd.DataFrame(columns=["variant","peak_date","trough_date","recovery_or_end_date","depth","days_peak_to_trough","days_underwater","recovered"])
    return pd.DataFrame(rows).sort_values("depth").head(topn).reset_index(drop=True)


def divergence_table(raw_path: pd.DataFrame, v1_path: pd.DataFrame) -> pd.DataFrame:
    a = raw_path[["execution_date", "target", "net_ret"]].rename(columns={"target":"raw_target","net_ret":"raw_net"})
    b = v1_path[["execution_date", "target", "net_ret"]].rename(columns={"target":"v1_target","net_ret":"v1_net"})
    z = a.merge(b, on="execution_date", how="inner")
    z["different"] = z["raw_target"].fillna("__CASH__").astype(str) != z["v1_target"].fillna("__CASH__").astype(str)
    z["seg"] = (z["different"] != z["different"].shift(fill_value=False)).cumsum()
    rows = []
    for seg, g in z[z["different"]].groupby("seg"):
        lr = float(np.log1p(np.clip(g["raw_net"].to_numpy(float), -0.999999999, None)).sum())
        lv = float(np.log1p(np.clip(g["v1_net"].to_numpy(float), -0.999999999, None)).sum())
        rows.append({
            "segment": int(seg),
            "start": str(g["execution_date"].iloc[0].date()),
            "end": str(g["execution_date"].iloc[-1].date()),
            "days": int(len(g)),
            "raw_symbols": ",".join(pd.unique(g["raw_target"].fillna("__CASH__").astype(str))),
            "v1_symbols": ",".join(pd.unique(g["v1_target"].fillna("__CASH__").astype(str))),
            "raw_return": float(np.expm1(lr)),
            "v1_return": float(np.expm1(lv)),
            "alpha_pp": float((np.expm1(lv) - np.expm1(lr)) * 100.0),
        })
    return pd.DataFrame(rows)


def period_table(path: pd.DataFrame, variant: str) -> pd.DataFrame:
    periods = {
        "2015_2019": (pd.Timestamp("2015-01-01"), pd.Timestamp("2019-12-31")),
        "2020": (pd.Timestamp("2020-01-01"), pd.Timestamp("2020-12-31")),
        "2021_2024": (pd.Timestamp("2021-01-01"), pd.Timestamp("2024-12-31")),
        "2025_2026_PARTIAL": (pd.Timestamp("2025-01-01"), None),
        "FULL": (None, None),
    }
    rows = []
    for name, (lo, hi) in periods.items():
        g = path.copy()
        if lo is not None:
            g = g[g["execution_date"] >= lo]
        if hi is not None:
            g = g[g["execution_date"] <= hi]
        if not g.empty:
            rows.append({"variant": variant, "period": name, "start": str(g.execution_date.min().date()), "end": str(g.execution_date.max().date()), **stats(g)})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage8m-output")
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(eng)
    bars["symbol"] = bars["symbol"].astype(str).str.zfill(6)
    bars["date"] = pd.to_datetime(bars["date"])
    feat = build_features(bars)
    feat["symbol"] = feat["symbol"].astype(str).str.zfill(6)
    feat["date"] = pd.to_datetime(feat["date"])
    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)

    cash_ok = score[CASH].notna() & np.isfinite(score[CASH]) & (score.index >= START_FLOOR)
    if not cash_ok.any():
        raise RuntimeError("cash comparator never becomes valid")
    first_signal = pd.Timestamp(score.index[cash_ok][0])
    start_i = int(cal.get_loc(first_signal))
    last_i = len(cal) - 3

    raw_score = raw_score_wide(feat, cal, list(score.columns.astype(str)))
    raw_delta = raw_score.diff()
    profile_df = v1lib.build_needed_profiles(bars, set(MAIN_RISK))
    profile_map = profile_df.set_index(["date", "symbol"])["resistance_pct252"].to_dict()

    raw_main = build_raw_targets(cal, score, MAIN_MEMBERS, start_i, last_i)
    v1_paths = {}
    v1_events = {}
    for th in V1_THRESHOLDS:
        p, e = build_v1_targets(raw_main, score, raw_delta, profile_map, MAIN_MEMBERS, th)
        v1_paths[th] = p
        v1_events[th] = e

    raw_noe = build_raw_targets(cal, score, NO_ENCHEM_MEMBERS, start_i, last_i)
    v1_noe, ev_noe = build_v1_targets(raw_noe, score, raw_delta, profile_map, NO_ENCHEM_MEMBERS, MAIN_THRESHOLD)

    # Primary detailed paths at 6bp.
    raw6 = attach_returns(raw_main, gross, 0.0006)
    v16 = attach_returns(v1_paths[MAIN_THRESHOLD], gross, 0.0006)
    raw6["variant"] = "FIXV2_RAW"
    v16["variant"] = "FIXV2_V1_75"

    # Full + period + annual.
    full = pd.DataFrame([
        {"variant":"FIXV2_RAW", **stats(raw6)},
        {"variant":"FIXV2_V1_75", **stats(v16)},
    ])
    periods = pd.concat([period_table(raw6, "FIXV2_RAW"), period_table(v16, "FIXV2_V1_75")], ignore_index=True)
    annual = pd.concat([
        annual_table(raw6, None, "FIXV2_RAW"),
        annual_table(v16, v1_events[MAIN_THRESHOLD], "FIXV2_V1_75"),
    ], ignore_index=True)

    contrib_full = pd.concat([
        contribution_table(raw6, "FIXV2_RAW", False),
        contribution_table(v16, "FIXV2_V1_75", False),
    ], ignore_index=True)
    contrib_annual = pd.concat([
        contribution_table(raw6, "FIXV2_RAW", True),
        contribution_table(v16, "FIXV2_V1_75", True),
    ], ignore_index=True)
    episodes = pd.concat([episode_table(raw6, "FIXV2_RAW"), episode_table(v16, "FIXV2_V1_75")], ignore_index=True)
    drawdowns = pd.concat([drawdown_table(raw6, "FIXV2_RAW"), drawdown_table(v16, "FIXV2_V1_75")], ignore_index=True)
    divergence = divergence_table(raw6, v16)

    # Cost stress.
    stress_rows = []
    for c in COSTS:
        bp = int(round(c * 10000))
        for name, basep in (("FIXV2_RAW", raw_main), ("FIXV2_V1_75", v1_paths[MAIN_THRESHOLD])):
            q = attach_returns(basep, gross, c)
            stress_rows.append({"stress":"COST", "parameter":f"{bp}bp_per_side", "variant":name, **stats(q)})
    cost_stress = pd.DataFrame(stress_rows)

    # V1 threshold sensitivity, 6bp.
    th_rows = []
    for th in V1_THRESHOLDS:
        q = attach_returns(v1_paths[th], gross, 0.0006)
        e = v1_events[th]
        rec = {"threshold":th, **stats(q)}
        rec["veto_count"] = int((e["decision"] == "VETO_V1").sum()) if not e.empty else 0
        th_rows.append(rec)
    threshold_stress = pd.DataFrame(th_rows)

    # Universe sensitivity to the unresolved 159981 decision.
    raw_noe6 = attach_returns(raw_noe, gross, 0.0006)
    v1_noe6 = attach_returns(v1_noe, gross, 0.0006)
    universe_stress = pd.DataFrame([
        {"universe":"MAIN_WITH_159981", "variant":"RAW", **stats(raw6)},
        {"universe":"MAIN_WITH_159981", "variant":"V1_75", **stats(v16)},
        {"universe":"NO_159981", "variant":"RAW", **stats(raw_noe6)},
        {"universe":"NO_159981", "variant":"V1_75", **stats(v1_noe6)},
    ])

    # Real availability.
    availability = []
    prof_first = profile_df.dropna(subset=["resistance_pct252"]).groupby("symbol")["date"].min().to_dict() if len(profile_df) else {}
    for s in MAIN_MEMBERS:
        gb = bars[bars["symbol"] == s]
        first_bar = pd.Timestamp(gb["date"].min()).date() if len(gb) else None
        if s in score.columns:
            ok = score[s].notna() & np.isfinite(score[s])
            first_score = pd.Timestamp(score.index[ok][0]).date() if ok.any() else None
        else:
            first_score = None
        fp = prof_first.get(s)
        availability.append({
            "symbol": s,
            "role": "CASH_COMPARATOR" if s == CASH else "RISK",
            "first_bar": str(first_bar) if first_bar else None,
            "first_finite_ols_score": str(first_score) if first_score else None,
            "first_finite_resistance_pct252": str(pd.Timestamp(fp).date()) if fp is not None and pd.notna(fp) else None,
        })
    availability = pd.DataFrame(availability)

    # Persist outputs.
    raw6.to_csv(out / "stage8m_daily_raw_6bp.csv", index=False)
    v16.to_csv(out / "stage8m_daily_v1_6bp.csv", index=False)
    full.to_csv(out / "stage8m_full.csv", index=False)
    periods.to_csv(out / "stage8m_periods.csv", index=False)
    annual.to_csv(out / "stage8m_annual.csv", index=False)
    contrib_full.to_csv(out / "stage8m_symbol_contribution_full.csv", index=False)
    contrib_annual.to_csv(out / "stage8m_symbol_contribution_annual.csv", index=False)
    episodes.to_csv(out / "stage8m_holding_episodes.csv", index=False)
    drawdowns.to_csv(out / "stage8m_drawdowns.csv", index=False)
    divergence.to_csv(out / "stage8m_v1_divergence_segments.csv", index=False)
    v1_events[MAIN_THRESHOLD].to_csv(out / "stage8m_v1_events.csv", index=False)
    cost_stress.to_csv(out / "stage8m_cost_stress.csv", index=False)
    threshold_stress.to_csv(out / "stage8m_v1_threshold_stress.csv", index=False)
    universe_stress.to_csv(out / "stage8m_universe_stress.csv", index=False)
    availability.to_csv(out / "stage8m_member_availability.csv", index=False)

    summary = {
        "study":"OURE Stage8M FixV2 + V1 long-horizon audit",
        "status":"completed",
        "main_members": list(MAIN_MEMBERS),
        "main_risk_members": list(MAIN_RISK),
        "first_signal_date": str(first_signal.date()),
        "first_execution_date": str(pd.Timestamp(cal[start_i + 1]).date()),
        "last_execution_date": str(pd.Timestamp(cal[last_i + 1]).date()),
        "last_return_end_date": str(pd.Timestamp(cal[last_i + 2]).date()),
        "v1_rule":"ResistancePct252>=75 AND raw ScoreDelta_new<=0 veto pure rank switch",
        "full": full.to_dict(orient="records"),
        "cost_stress": cost_stress.to_dict(orient="records"),
        "threshold_stress": threshold_stress.to_dict(orient="records"),
        "universe_stress": universe_stress.to_dict(orient="records"),
        "v1_veto_count": int((v1_events[MAIN_THRESHOLD]["decision"] == "VETO_V1").sum()) if not v1_events[MAIN_THRESHOLD].empty else 0,
        "divergence_segments": int(len(divergence)),
        "v1_divergence_win_share": float(np.mean(divergence["alpha_pp"] > 0)) if len(divergence) else None,
    }
    (out / "stage8m_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print("\nANNUAL\n", annual.to_string(index=False))
    print("\nFULL CONTRIBUTION V1\n", contrib_full[contrib_full.variant == "FIXV2_V1_75"].sort_values("net_log_contribution", ascending=False).to_string(index=False))
    print("\nCOST STRESS\n", cost_stress.to_string(index=False))
    print("\nTHRESHOLD STRESS\n", threshold_stress.to_string(index=False))
    print("\nUNIVERSE STRESS\n", universe_stress.to_string(index=False))


if __name__ == "__main__":
    main()
