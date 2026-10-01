#!/usr/bin/env python3
from __future__ import annotations

import json, os, sys
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
import optimal_universe_reverse_engineering.oure_stage8m_fixv2_v1_long_horizon as s8m
import optimal_universe_reverse_engineering.oure_stage8q_map_comparator_robustness as s8q
import optimal_universe_reverse_engineering.oure_stage8za_prevoid_incumbent_full_backtest as s8za

COST = 0.0006
CASH = "511220"
BASE_RISK = ["513500", "513030", "518880"]
VOL_LOOKBACK = 60
BASE_CASH_WEIGHT = 0.30
BASE_RISK_WEIGHT = 0.70
ALLOCATIONS = [1.00, 0.90, 0.80, 0.70, 0.60, 0.50]
BAND = 0.05


def perf_stats(r: pd.Series) -> dict:
    x = pd.Series(r, dtype=float).fillna(0.0)
    eq = (1.0 + x).cumprod()
    if len(eq) == 0:
        return {}
    peak = eq.cummax()
    dd = eq / peak - 1.0
    years = len(x) / 252.0
    cagr = float(eq.iloc[-1] ** (1 / years) - 1) if years > 0 and eq.iloc[-1] > 0 else np.nan
    vol = float(x.std(ddof=1) * np.sqrt(252)) if len(x) > 1 else np.nan
    sharpe = float(x.mean() / x.std(ddof=1) * np.sqrt(252)) if len(x) > 1 and x.std(ddof=1) > 0 else np.nan
    mdd = float(dd.min())
    return {
        "sessions": int(len(x)),
        "total_return": float(eq.iloc[-1] - 1),
        "cagr": cagr,
        "mdd": mdd,
        "ann_vol": vol,
        "sharpe_0rf": sharpe,
        "calmar": float(cagr / abs(mdd)) if np.isfinite(cagr) and mdd < 0 else np.nan,
    }


def monthly_stats(df: pd.DataFrame, col: str) -> dict:
    z = df.set_index("execution_date")[col].astype(float)
    m = (1.0 + z).resample("ME").prod() - 1.0
    return {
        "monthly_win_rate": float((m > 0).mean()),
        "worst_month": float(m.min()),
        "best_month": float(m.max()),
        "negative_months": int((m < 0).sum()),
        "months": int(len(m)),
    }


def build_base_returns(bars: pd.DataFrame, calendar: pd.DatetimeIndex, signal_dates: pd.Series, execution_dates: pd.Series):
    b = bars[bars["symbol"].isin([CASH] + BASE_RISK)].copy()
    close = b.pivot(index="date", columns="symbol", values="close").sort_index()
    op = b.pivot(index="date", columns="symbol", values="open").sort_index()
    close = close.reindex(calendar)
    op = op.reindex(calendar)

    close_ret = close.pct_change()
    vol = close_ret[BASE_RISK].rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK).std()

    # open-to-next-open return keyed by execution date
    o2o = op.shift(-1) / op - 1.0

    rows = []
    prev_w = None
    active_w = None

    sig = pd.to_datetime(signal_dates).reset_index(drop=True)
    exe = pd.to_datetime(execution_dates).reset_index(drop=True)

    for i, (sd, ed) in enumerate(zip(sig, exe)):
        # rebalance on month-end signal so next execution is first trading day of next month.
        is_month_end_signal = (i == len(sig) - 1) or (exe.iloc[i].month != sd.month) or (
            i + 1 < len(sig) and sig.iloc[i + 1].month != sd.month
        )

        if active_w is None or is_month_end_signal:
            vv = vol.loc[sd, BASE_RISK] if sd in vol.index else pd.Series(index=BASE_RISK, dtype=float)
            if vv.notna().all() and (vv > 0).all():
                inv = 1.0 / vv
                risk_w = BASE_RISK_WEIGHT * inv / inv.sum()
                new_w = {CASH: BASE_CASH_WEIGHT, **{s: float(risk_w[s]) for s in BASE_RISK}}
                turnover = 0.0 if prev_w is None else sum(abs(new_w[k] - prev_w.get(k, 0.0)) for k in new_w)
                active_w = new_w
                prev_w = new_w.copy()
            else:
                turnover = 0.0
        else:
            turnover = 0.0

        gross = 0.0
        if active_w is not None and ed in o2o.index:
            for s, w in active_w.items():
                rr = o2o.at[ed, s] if s in o2o.columns else np.nan
                if pd.notna(rr) and np.isfinite(rr):
                    gross += w * float(rr)
        net = (1.0 + gross) * (1.0 - COST * turnover) - 1.0
        rows.append({
            "signal_date": sd,
            "execution_date": ed,
            "base_gross_ret": gross,
            "base_net_ret": net,
            "base_turnover_sides": turnover,
            **{f"w_{k}": (active_w or {}).get(k, np.nan) for k in [CASH] + BASE_RISK},
        })
    return pd.DataFrame(rows)


def combine_band(ols: pd.Series, base: pd.Series, dates: pd.Series, target_ols: float) -> pd.DataFrame:
    ols = pd.Series(ols, dtype=float).reset_index(drop=True)
    base = pd.Series(base, dtype=float).reset_index(drop=True)
    dates = pd.to_datetime(dates).reset_index(drop=True)

    if target_ols >= 0.999999:
        return pd.DataFrame({"execution_date": dates, "net_ret": ols, "ols_weight_start": 1.0, "rebalance": False})

    nav_ols = target_ols
    nav_base = 1.0 - target_ols
    total_prev = 1.0
    rows = []

    for i, d in enumerate(dates):
        total = nav_ols + nav_base
        w_start = nav_ols / total if total > 0 else target_ols

        # Monthly check only, at the first execution session of a month.
        first_of_month = i == 0 or dates.iloc[i - 1].month != d.month or dates.iloc[i - 1].year != d.year
        reb = False
        trade_cost = 0.0
        if first_of_month and (w_start < max(0.0, target_ols - BAND) or w_start > min(1.0, target_ols + BAND)):
            old_ols = nav_ols
            nav_ols = total * target_ols
            nav_base = total * (1.0 - target_ols)
            moved = abs(nav_ols - old_ols)
            # sell one sleeve + buy the other => two sides
            trade_cost = 2.0 * COST * moved
            nav_base -= trade_cost
            reb = True
            total = nav_ols + nav_base
            w_start = nav_ols / total if total > 0 else target_ols

        nav_ols *= (1.0 + float(ols.iloc[i]))
        nav_base *= (1.0 + float(base.iloc[i]))
        total_now = nav_ols + nav_base
        net_ret = total_now / total_prev - 1.0
        total_prev = total_now
        rows.append({
            "execution_date": d,
            "net_ret": net_ret,
            "ols_weight_start": w_start,
            "rebalance": reb,
            "allocation_trade_cost": trade_cost,
        })
    return pd.DataFrame(rows)


def main():
    db = os.getenv("ETF_DAILY_BARS_DATABASE_URL")
    if not db:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out = Path(os.getenv("OUTPUT_DIR", "base-plus-ols-output"))
    out.mkdir(parents=True, exist_ok=True)

    eng = create_engine(_db_url(db), pool_pre_ping=True)
    bars = load_daily_bars(eng)
    bars["symbol"] = bars["symbol"].astype(str).str.zfill(6)
    bars["date"] = pd.to_datetime(bars["date"])

    feat = build_features(bars)
    feat["symbol"] = feat["symbol"].astype(str).str.zfill(6)
    feat["date"] = pd.to_datetime(feat["date"])
    feat_idx = feat.set_index(["date", "symbol"]).sort_index()

    cal, score, r2, slope, close, op, gross, ret = build_wides(bars, feat)
    cal = pd.DatetimeIndex(cal)
    raw_score = s8m.raw_score_wide(feat, cal, list(score.columns.astype(str)))
    raw_delta = raw_score.diff()

    cash_ok = score[CASH].notna() & np.isfinite(score[CASH]) & (score.index >= s8m.START_FLOOR)
    first = pd.Timestamp(score.index[cash_ok][0])
    start_i = int(cal.get_loc(first))
    last_i = len(cal) - 3
    raw = s8m.build_raw_targets(cal, score, s8m.MAIN_MEMBERS, start_i, last_i)
    prof = v1lib.build_needed_profiles(bars, set(s8m.MAIN_RISK))
    pmap = prof.set_index(["date", "symbol"])["resistance_pct252"].to_dict()
    v1, _ = s8m.build_v1_targets(raw, score, raw_delta, pmap, s8m.MAIN_MEMBERS, s8m.MAIN_THRESHOLD)

    labels = s8q.fixed_strategy_labels(cal, score, gross, feat, bars)
    map_panel = s8q.build_map_panel(cal, score, feat, labels)
    ols_path = s8za.build_prevoid_variant(v1, map_panel, raw_score, feat_idx, "PREVOID_DEEPEN_INVALID_ROUTE", streak_need=1)
    ols = s8m.attach_returns(ols_path, gross, COST).copy()

    base = build_base_returns(bars, cal, ols["signal_date"], ols["execution_date"])
    z = ols[["signal_date", "execution_date", "net_ret"]].rename(columns={"net_ret": "ols_net_ret"}).merge(
        base, on=["signal_date", "execution_date"], how="left"
    )

    # Require base to be fully initialized; makes every allocation directly comparable.
    weight_cols = [f"w_{k}" for k in [CASH] + BASE_RISK]
    valid = z[weight_cols].notna().all(axis=1)
    z = z.loc[valid].reset_index(drop=True)

    mp = map_panel[["signal_date", "quadrant_511220"]].copy()
    mp["signal_date"] = pd.to_datetime(mp["signal_date"])
    z = z.merge(mp, on="signal_date", how="left")

    summary_rows = []
    annual_rows = []
    monthly_rows = []
    void_rows = []

    for target in ALLOCATIONS:
        c = combine_band(z["ols_net_ret"], z["base_net_ret"], z["execution_date"], target)
        c["signal_date"] = z["signal_date"].values
        c["quadrant_511220"] = z["quadrant_511220"].values
        label = f"OLS{int(round(target*100))}_BASE{int(round((1-target)*100))}"
        c["variant"] = label
        c.to_csv(out / f"{label.lower()}_daily.csv", index=False)

        st = perf_stats(c["net_ret"])
        st.update(monthly_stats(c, "net_ret"))
        st["variant"] = label
        st["target_ols"] = target
        st["target_base"] = 1.0 - target
        st["allocation_rebalances"] = int(c["rebalance"].sum())
        st["avg_ols_weight"] = float(c["ols_weight_start"].mean())
        summary_rows.append(st)

        c["year"] = c["execution_date"].dt.year
        for y, g in c.groupby("year"):
            annual_rows.append({"variant": label, "year": int(y), **perf_stats(g["net_ret"])})

        m = c.set_index("execution_date")["net_ret"].resample("ME").apply(lambda x: (1+x).prod()-1)
        for d, r in m.items():
            monthly_rows.append({"variant": label, "month": str(d.date()), "return": float(r)})

        vg = c[c["quadrant_511220"] == "DEFENSIVE_VOID"]
        if len(vg):
            void_rows.append({"variant": label, **perf_stats(vg["net_ret"])})

    # Standalone base benchmark
    base_stats = perf_stats(z["base_net_ret"])
    base_stats.update(monthly_stats(z.rename(columns={"base_net_ret": "tmp"}), "tmp"))
    base_stats["variant"] = "BASE_ONLY"
    base_stats["target_ols"] = 0.0
    base_stats["target_base"] = 1.0
    base_stats["allocation_rebalances"] = 0
    base_stats["avg_ols_weight"] = 0.0
    summary_rows.append(base_stats)

    summary = pd.DataFrame(summary_rows)
    annual = pd.DataFrame(annual_rows)
    monthly = pd.DataFrame(monthly_rows)
    void = pd.DataFrame(void_rows)

    summary.to_csv(out / "allocation_summary.csv", index=False)
    annual.to_csv(out / "allocation_annual.csv", index=False)
    monthly.to_csv(out / "allocation_monthly.csv", index=False)
    void.to_csv(out / "allocation_void.csv", index=False)
    z.to_csv(out / "base_weights_and_returns.csv", index=False)

    md = [
        "# OLS + Base Allocation Backtest",
        "",
        "Frozen OLS: Stage8ZA PREVOID_DEEPEN1_INVALID_ROUTE, 26d weighted log-price OLS, half-life 10, 6bp/side.",
        "Base: 30% 511220 + 70% inverse-vol(60d) across 513500/513030/518880.",
        "Base weights computed at month-end close for next-month execution. Total-account allocation checked monthly; rebalance only outside target OLS +/-5pct band.",
        "",
        "## Full summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Annual",
        "",
        annual.to_markdown(index=False),
        "",
        "## DEFENSIVE_VOID sessions",
        "",
        void.to_markdown(index=False),
    ]
    (out / "summary.md").write_text("\n".join(md), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps({
        "summary": summary.to_dict("records"),
        "annual": annual.to_dict("records"),
        "void": void.to_dict("records"),
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
