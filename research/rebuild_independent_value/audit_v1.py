#!/usr/bin/env python3
"""Exploratory independent predictive-value test for 26d ETF rebuild signals.
Historical prices are frozen; 2026-11-12 labels are *not* historical PIT.
No changes to live signals, data stores, holdings, or schedules.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from research.full_market_rebuild.fullmarket_window_backtest_v1 import ols_arrays

START = pd.Timestamp("2021-01-01")
END = pd.Timestamp("2026-10-13")
HORIZONS = (5, 10, 20)
COST = 0.0006
CALIPERS = np.array([0.03, 0.05, 0.08], dtype=float)
FEATURES = ("ret5", "ret10", "ret26")
SEED = 20261113


def prepare(bars_path, taxonomy_path, min_turnover):
    sha = hashlib.sha256(Path(bars_path).read_bytes()).hexdigest()
    tax = pd.read_parquet(taxonomy_path)
    required = {"symbol", "classification_status", "exact_index_key",
                "exposure_type", "region_primary", "sector_level1"}
    assert required.issubset(tax.columns), sorted(required.difference(tax.columns))
    tax["symbol"] = tax.symbol.astype(str).str.zfill(6)
    tax = tax.loc[tax.classification_status.eq("VERIFIED_CURRENT_INDEX")].copy()
    tax = tax.loc[tax[list(required - {"symbol", "classification_status"})].notna().all(axis=1)].copy()
    tax = tax.sort_values("symbol").drop_duplicates("symbol")
    bars = pd.read_parquet(bars_path, columns=["symbol", "date", "open", "close", "amount"])
    all_rows, all_codes = len(bars), bars.symbol.nunique()
    bars["symbol"] = bars.symbol.astype(str).str.zfill(6)
    bars["date"] = pd.to_datetime(bars.date).dt.normalize()
    bars = bars.merge(tax[list(required)], on="symbol", how="inner", validate="many_to_one")
    for c in ["open", "close", "amount"]:
        bars[c] = pd.to_numeric(bars[c], errors="coerce")
    bars = bars[(bars.open > 0) & (bars.close > 0) & (bars.amount >= 0)]
    bars = bars.drop_duplicates(["symbol", "date"], keep="last").sort_values(
        ["symbol", "date"]).reset_index(drop=True)
    dates = np.sort(bars.date.unique())
    bars["tid"] = np.searchsorted(dates, bars.date.to_numpy(dtype="datetime64[ns]"))
    n = len(bars)
    arr = {c: np.full(n, np.nan) for c in
           ["ret5", "ret10", "ret26", "turn60", "age", "net5", "net10", "net20"]}
    sig = np.zeros(n, dtype=bool)
    for sym, g in bars.groupby("symbol", sort=False):
        pos = g.index.to_numpy()
        c, o = g.close.to_numpy(float), g.open.to_numpy(float)
        amt, tid = g.amount.to_numpy(float), g.tid.to_numpy(int)
        length = len(g)
        if length < 85:
            continue
        slope, r2 = ols_arrays(c, 26)
        turn = pd.Series(amt).rolling(60, min_periods=60).mean().shift(1).to_numpy()
        arr["turn60"][pos] = turn
        for days in (5, 10, 26):
            x = np.full(length, np.nan)
            ok = tid[days:] - tid[:-days] == days
            q = c[days:] / c[:-days] - 1
            x[days:] = np.where(ok, q, np.nan)
            arr[f"ret{days}"][pos] = x
        for h in HORIZONS:
            x = np.full(length, np.nan)
            # T close signal -> buy T+1 open -> sell T+h+1 open.
            k = h + 1
            valid = tid[k:] - tid[:-k] == k
            valid &= tid[1:length-h] - tid[:length-h-1] == 1
            gross = o[k:] / o[1:length-h] * (1 - COST) / (1 + COST) - 1
            x[:length-k] = np.where(valid, gross, np.nan)
            arr[f"net{h}"][pos] = x
        crosses = np.flatnonzero((slope[1:] > 1e-8) & (slope[:-1] <= 1e-8)) + 1
        last = -100000
        for i in crosses:
            if not np.isfinite(r2[i]):
                continue
            for q in range(i + 1, min(i + 4, length)):
                if (slope[q] > 1e-8 and np.isfinite(r2[q - 1]) and
                    r2[q] > r2[q - 1] + 1e-12 and r2[q] > r2[i] + 1e-12):
                    if q - last >= 20:
                        sig[pos[q]] = True
                        last = q
                    break
        recent = np.where(sig[pos], tid, -100000)
        age = tid - np.maximum.accumulate(recent)
        arr["age"][pos] = age
    for key, data in arr.items():
        bars[key] = data
    bars["signal"] = sig
    bars = bars[(bars.turn60 >= min_turnover) & (bars.amount > 0) &
                bars[list(FEATURES)].notna().all(axis=1)].copy()
    # One representative per *identical official index* on each signal date.
    # Representative selection only uses turnover known by T-1.
    bars = bars.sort_values(["date", "exact_index_key", "turn60", "symbol"],
                            ascending=[True, True, False, True])
    bars = bars.drop_duplicates(["date", "exact_index_key"], keep="first")
    bars = bars[bars[list(f"net{h}" for h in HORIZONS)].notna().all(axis=1)]
    bars = bars[(bars.date >= START) & (bars.date <= END)].copy()
    bars["group_strict"] = (bars.exposure_type.astype(str) + "|" +
                            bars.region_primary.astype(str) + "|" +
                            bars.sector_level1.astype(str))
    bars["group_coarse"] = (bars.exposure_type.astype(str) + "|" +
                            bars.region_primary.astype(str))
    info = dict(snapshot_sha256=sha, bars_source_rows=all_rows, bars_source_symbols=int(all_codes),
                taxonomy_verified_symbols=int(len(tax)), panel_rows=int(len(bars)),
                panel_symbols=int(bars.symbol.nunique()),
                first_panel=str(bars.date.min().date()), last_panel=str(bars.date.max().date()),
                signal_panel=int(bars.signal.sum()), eligible_control_panel=int((bars.age > 20).sum()),
                classification_known_from="2026-11-13", turnover_floor_cny=min_turnover,
                is_history_point_in_time_safe=False)
    return bars, info


def match_pairs(panel, group_col, calipers):
    treated = panel[panel.signal].copy()
    control = panel[(~panel.signal) & (panel.age > 20)].copy()
    controls = {(d, k): g for (d, k), g in
                control.groupby(["date", group_col], sort=False)}
    paired = []
    for (d, k), group in treated.groupby(["date", group_col], sort=True):
        pool = controls.get((d, k))
        if pool is None:
            continue
        used = set()
        cfeat = pool[list(FEATURES)].to_numpy(float)
        for t in group.sort_values("symbol").itertuples(index=False):
            target = np.array([getattr(t, x) for x in FEATURES])
            difference = np.abs(cfeat - target)
            eligible = np.all(difference <= calipers, axis=1)
            eligible &= pool.exact_index_key.to_numpy() != t.exact_index_key
            eligible &= ~pool.symbol.isin(used).to_numpy()
            if not eligible.any():
                continue
            distance = np.square(difference / calipers).sum(axis=1)
            distance[~eligible] = np.inf
            best = int(np.argmin(distance))
            c = pool.iloc[best]
            used.add(c.symbol)
            r = dict(date=str(d.date()), year=int(d.year), month=str(d)[:7],
                     group=str(k), signal=str(t.symbol), control=str(c.symbol),
                     signal_index=str(t.exact_index_key), control_index=str(c.exact_index_key),
                     distance=float(distance[best]))
            for key in FEATURES:
                r["treated_"+key] = float(getattr(t, key))
                r["control_"+key] = float(c[key])
            for h in HORIZONS:
                r[f"treated{h}"] = float(getattr(t, f"net{h}"))
                r[f"control{h}"] = float(c[f"net{h}"])
                r[f"excess{h}"] = r[f"treated{h}"] - r[f"control{h}"]
            paired.append(r)
    return pd.DataFrame(paired)


def confidence(rows, h, weight="event", repeats=1200):
    if rows.empty:
        return None
    if weight == "date":
        sample = rows.groupby(["date", "month"], as_index=False)[f"excess{h}"].mean()
    else:
        sample = rows[["month", f"excess{h}"]].copy()
    months = list(sample.month.unique())
    by = sample.groupby("month")[f"excess{h}"].agg(["sum", "count"]).reindex(months)
    cells = by[["sum", "count"]].to_numpy(float)
    rng = np.random.default_rng(SEED + h + (1 if weight=="date" else 0))
    index = rng.integers(0, len(months), size=(repeats, len(months)))
    num = cells[index, 0].sum(axis=1)
    den = cells[index, 1].sum(axis=1)
    boot = num / den
    return [round(float(x)*100, 3) for x in np.quantile(boot, [0.025, 0.975])]


def metrics(rows):
    if rows.empty:
        return {"n": 0}
    out = {"n": int(len(rows)), "dates": int(rows.date.nunique()),
           "months": int(rows.month.nunique()), "symbols": int(rows.signal.nunique())}
    for k in FEATURES:
        out["avg_abs_gap_"+k+"_pp"] = round(float(
            (rows["treated_"+k] - rows["control_"+k]).abs().mean())*100, 3)
    for h in HORIZONS:
        gap = rows[f"excess{h}"]
        out[str(h)] = {
            "treated_mean_pct": round(float(rows[f"treated{h}"].mean()*100), 3),
            "control_mean_pct": round(float(rows[f"control{h}"].mean()*100), 3),
            "excess_mean_pp": round(float(gap.mean()*100), 3),
            "excess_median_pp": round(float(gap.median()*100), 3),
            "excess_positive_share_pct": round(float((gap>0).mean()*100), 2),
            "ci95_month_event_pp": confidence(rows,h,"event"),
            "equal_day_mean_pp": round(float(rows.groupby("date")[f"excess{h}"].mean().mean()*100), 3),
            "ci95_month_day_pp": confidence(rows,h,"date")
        }
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bars", required=True)
    p.add_argument("--taxonomy", required=True)
    p.add_argument("--min-turnover", type=float, default=3_000_000)
    p.add_argument("--out", default="research/rebuild_independent_value")
    a = p.parse_args()
    root = Path(a.out); root.mkdir(parents=True, exist_ok=True)
    panel, coverage = prepare(a.bars, a.taxonomy, a.min_turnover)
    out = {"version": "v1_predeclared_caliper_20261113", "coverage": coverage,
           "signal_definition": "weighted OLS26 slope crosses +, R2 first improves within 1-3 sessions, per-symbol 20-session cooldown",
           "entry_exit": "T+1 open to T+h+1 open; six basis points each side",
           "predeclared_calipers_pp": {"prior5":3,"prior10":5,"prior26":8},
           "control_not_recently_rebuilt_sessions":20, "yearly": {}, "cohorts": {}}
    for label, group, caps in [
        ("STRICT_SECTOR", "group_strict", CALIPERS),
        ("COARSE_REGION", "group_coarse", CALIPERS),
        ("STRICT_LOOSE", "group_strict", CALIPERS * 1.5),
    ]:
        pairs = match_pairs(panel, group, caps)
        if pairs.empty:
            raise RuntimeError(f"No control pairs under {label}")
        pairs.to_csv(root / f"{label.lower()}_pairs.csv.gz", compression="gzip", index=False)
        out["cohorts"][label] = {"all": metrics(pairs),
                                 "2021_2024": metrics(pairs[pairs.year<=2024]),
                                 "2025_2026": metrics(pairs[pairs.year>=2025]),
                                 "yearly": {str(y): metrics(g) for y,g in pairs.groupby("year")}}
        out["cohorts"][label]["match_rate"] = round(
            float(len(pairs) / panel.signal.sum()), 4)
        print("MATCH_RESULT", label, len(pairs), json.dumps(
            out["cohorts"][label]["all"], ensure_ascii=False), flush=True)
    (root/"result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf8")
    lines = ["# 重建信号独立预测价值：同日同暴露匹配 V1", "",
             "性质：探索性复盘，不是无前视策略回测。2026-11-12的分类在2021-2026不能按当时已知处理，现存活基金存在幸存者偏差。",
             "样本：2021-01至2026-10-13，冻结行情截止2026-11-11。只包括当前可核实的被动指数产品，使用26日OLS。",
             "交易：T收盘信号，T+1开盘买入；T+(h+1)开盘退出；单边费率0.06%。",
             "匹配：同日，精确指数去重，控制组过去20交易日无重建；前5/10/26日收益距离<=3/5/8个百分点；对照不与信号同指数。",
             "主检验：相同暴露类型、地区、一级行业；稳健性：地区+类型；行业内放宽1.5倍收益卡尺。", ""]
    for name, record in out["cohorts"].items():
        lines += [f"## {name}: {record['all']['n']} 对，匹配率 {record['match_rate']:.1%}", ""]
        for era in ["all", "2021_2024", "2025_2026"]:
            r = record[era]
            lines.append(f"### {era}: n={r['n']}")
            if r["n"]:
                for h in HORIZONS:
                    z = r[str(h)]
                    lines.append(f"- {h}日：重建 {z['treated_mean_pct']:+.3f}%，控制 {z['control_mean_pct']:+.3f}%，差 {z['excess_mean_pp']:+.3f}pp；月区块95% CI {z['ci95_month_event_pp']}，日等权差 {z['equal_day_mean_pp']:+.3f}pp，日等权区间 {z['ci95_month_day_pp']}")
            lines.append("")
        lines.append("分年10日差： " + "；".join(f"{y}: {r['10']['excess_mean_pp']:+.3f}pp (n={r['n']})"
                     for y,r in record["yearly"].items() if r["n"]) + "")
    lines += ["", "## 局限",
              "- 这不是因果识别：相似历史涨幅并不保证所有其他特征平衡，例如波动率、成交额、基本面信息。",
              "- 控制组不重建的定义为过去20交易日没有正式首次合格重建；控制组可能有不合格的斜率翻正。",
              "- 只对找到同日近邻的事件计算效应，匹配率反映外推限制；重复事件可能有重叠持仓。",
              "- 月区块bootstrap考虑时间聚集，但不足以解决截面相关性、分类回溯与历史复权修订。",
              "- 没有真实退市基金全集、历史PIT官方分类、溢价、追踪误差与分钟成交执行过滤。"]
    (root/"REPORT.md").write_text("\n".join(lines)+"\n", encoding="utf8")
    print("DONE", json.dumps(coverage, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
