#!/usr/bin/env python3
"""Universe Oracle V1: does replacing known-deteriorated Fixed15 members matter?

This is deliberately a hindsight upper-bound diagnostic, NOT a tradable rule.
Only the pool composition changes from 2025-01-01 onward. 2021-2024 is kept
identical to the original Fixed15 benchmark.

Frozen deteriorated symbols came from the preceding Post-OLS diagnostic:
- 513100 NASDAQ ETF
- 159529 S&P Consumer ETF

Oracle replacement selection uses 2025-2026 outcomes and is therefore explicitly
look-ahead. Its purpose is only to estimate whether universe quality has enough
economic importance to justify a later walk-forward universe model.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import sys
RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from walk_forward_candidate_pool import backtest_open_to_open, summarize_variant

FIXED15 = {
    "518880", "159985", "159825", "161226", "513100",
    "159915", "511220", "159509", "513290", "159529",
    "159981", "501018", "513920", "511380", "164824",
}
CASH_SIGNAL = "511220"
CHANGE_DATE = pd.Timestamp("2025-01-01")
MIN_FIRST_DATE = pd.Timestamp("2024-01-01")  # >= ~1y history by 2025-01-01
MIN_ORACLE_EPISODES = 5
BAD_NASDAQ = "513100"
BAD_CONSUMER = "159529"


def load_metadata(engine) -> pd.DataFrame:
    q = """
    select symbol,name,asset_class,region_primary,exposure_level1,risk_bucket,
           is_qdii,historical_safe,needs_review
    from public.instrument_metadata_current
    """
    m = pd.read_sql_query(text(q), engine)
    m["symbol"] = m["symbol"].astype(str).str.zfill(6)
    return m


def load_first_dates(engine) -> pd.DataFrame:
    return pd.read_sql_query(text("select symbol,min(date) first_date from public.daily_bars group by symbol"), engine,
                             parse_dates=["first_date"])


def load_oracle_stats(engine) -> pd.DataFrame:
    q = """
    select symbol,
           count(*) filter(where start_date>=date '2025-01-01' and right_censored=false) as n_2526,
           avg(fwd20) filter(where start_date>=date '2025-01-01' and right_censored=false) as mean_fwd20_2526,
           percentile_cont(0.5) within group(order by ols_life20)
             filter(where start_date>=date '2025-01-01' and right_censored=false) as median_life20_2526,
           avg((ols_life20>=10)::int::float)
             filter(where start_date>=date '2025-01-01' and right_censored=false) as survive10_2526
    from research.ols_episodes group by symbol
    """
    return pd.read_sql_query(text(q), engine)


def choose_oracles(meta: pd.DataFrame, firsts: pd.DataFrame, stats: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    x = meta.merge(firsts, on="symbol", how="inner").merge(stats, on="symbol", how="left")
    x["n_2526"] = pd.to_numeric(x["n_2526"], errors="coerce").fillna(0).astype(int)
    eligible = x.loc[
        (~x["symbol"].isin(FIXED15))
        & (~x["needs_review"].fillna(False).astype(bool))
        & (x["first_date"] <= MIN_FIRST_DATE)
        & (x["n_2526"] >= MIN_ORACLE_EPISODES)
        & x["mean_fwd20_2526"].notna()
    ].copy()

    base_meta = meta.set_index("symbol")
    bad1 = base_meta.loc[BAD_NASDAQ]
    same_bucket = eligible.loc[
        (eligible["risk_bucket"] == bad1["risk_bucket"])
        & (eligible["region_primary"] == bad1["region_primary"])
        & (eligible["exposure_level1"] == bad1["exposure_level1"])
    ].sort_values(["mean_fwd20_2526", "symbol"], ascending=[False, True])
    if same_bucket.empty:
        raise RuntimeError("No same-risk-bucket oracle replacement for 513100")
    rep1 = str(same_bucket.iloc[0]["symbol"])

    # For consumer, no same-bucket candidate may exist. Preserve diversification:
    # first try same bucket; otherwise same region/exposure but exclude risk buckets
    # already represented by the remaining Fixed15 plus replacement #1.
    bad2 = base_meta.loc[BAD_CONSUMER]
    same2 = eligible.loc[
        (eligible["risk_bucket"] == bad2["risk_bucket"])
        & (eligible["region_primary"] == bad2["region_primary"])
        & (eligible["exposure_level1"] == bad2["exposure_level1"])
        & (eligible["symbol"] != rep1)
    ].sort_values(["mean_fwd20_2526", "symbol"], ascending=[False, True])

    fallback = False
    if not same2.empty:
        rep2 = str(same2.iloc[0]["symbol"])
    else:
        fallback = True
        remaining = (FIXED15 - {BAD_CONSUMER}) | {rep1}
        represented = set(meta.loc[meta["symbol"].isin(remaining), "risk_bucket"].dropna().astype(str))
        broad = eligible.loc[
            (eligible["region_primary"] == bad2["region_primary"])
            & (eligible["exposure_level1"] == bad2["exposure_level1"])
            & (~eligible["risk_bucket"].astype(str).isin(represented))
            & (eligible["symbol"] != rep1)
        ].sort_values(["mean_fwd20_2526", "symbol"], ascending=[False, True])
        if broad.empty:
            raise RuntimeError("No diversified US-equity fallback oracle replacement for 159529")
        rep2 = str(broad.iloc[0]["symbol"])

    chosen = {
        BAD_NASDAQ: rep1,
        BAD_CONSUMER: rep2,
        "consumer_used_fallback": fallback,
    }
    audit = x.loc[x["symbol"].isin([BAD_NASDAQ, BAD_CONSUMER, rep1, rep2])].copy()
    return chosen, audit


def pool_mask(features: pd.DataFrame, original: set[str], post2025: set[str]) -> pd.Series:
    sym = features["symbol"].astype(str)
    pre = (features["date"] < CHANGE_DATE) & sym.isin(original)
    post = (features["date"] >= CHANGE_DATE) & sym.isin(post2025)
    return pre | post


def build_targets(features: pd.DataFrame, original: set[str], post2025: set[str]) -> tuple[pd.Series, pd.Series, pd.Series]:
    # Deliberately ignore full-market universe_eligible for Fixed15-style pool research.
    # Keep the frozen OLS engine + D2 only, so legacy LOFs/commodity funds are not
    # accidentally removed by a universe-infrastructure filter.
    trend = (
        (features["annual"] > 0)
        & (features["r2"] > 0)
        & (features["score"] > 0)
        & (~features["recent_drop3"].fillna(False))
    )
    allowed = pool_mask(features, original, post2025)
    d = features.loc[trend & allowed & (features["date"] >= pd.Timestamp("2020-12-01")),
                     ["date", "symbol", "score"]].copy()
    all_dates = pd.Index(sorted(pd.to_datetime(features.loc[features["date"] >= pd.Timestamp("2020-12-01"), "date"].unique())), name="date")
    counts = d.groupby("date").size().reindex(all_dates, fill_value=0).astype(int)
    if d.empty:
        return pd.Series(dtype=object), counts, pd.Series(dtype=object)
    idx = d.groupby("date", sort=True)["score"].idxmax()
    ranked = d.loc[idx, ["date", "symbol"]].sort_values("date").set_index("date")["symbol"]
    targets = ranked.where(ranked != CASH_SIGNAL, None)
    return targets, counts, ranked


def tenure_stats(ranked: pd.Series, start: str, end: str | None = None) -> dict:
    x = ranked.loc[ranked.index >= pd.Timestamp(start)].copy()
    if end:
        x = x.loc[x.index <= pd.Timestamp(end)]
    x = x.dropna().astype(str)
    if x.empty:
        return {}
    groups = (x != x.shift()).cumsum()
    runs = x.groupby(groups).size()
    return {
        "runs": int(len(runs)),
        "mean_top1_tenure": float(runs.mean()),
        "median_top1_tenure": float(runs.median()),
        "p75_top1_tenure": float(runs.quantile(0.75)),
        "max_top1_tenure": int(runs.max()),
    }


def variant_summary(label: str, bars: pd.DataFrame, features: pd.DataFrame,
                    original: set[str], post2025: set[str]) -> dict:
    targets, counts, ranked = build_targets(features, original, post2025)
    pnl = backtest_open_to_open(bars, targets)
    out = summarize_variant(label, pnl, targets, counts)
    out["post2025_pool"] = sorted(post2025)
    out["top1_tenure_2021_2024"] = tenure_stats(ranked, "2021-01-01", "2024-12-31")
    out["top1_tenure_2025_2026"] = tenure_stats(ranked, "2025-01-01")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    p.add_argument("--summary-path", default="universe-oracle-v1-summary.json")
    p.add_argument("--report-path", default="universe-oracle-v1-report.md")
    args = p.parse_args()
    if not args.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars = load_daily_bars(engine)
    features = build_features(bars)
    meta = load_metadata(engine)
    firsts = load_first_dates(engine)
    stats = load_oracle_stats(engine)
    chosen, audit = choose_oracles(meta, firsts, stats)
    r1 = str(chosen[BAD_NASDAQ]); r2 = str(chosen[BAD_CONSUMER])

    pools = {
        "fixed15": set(FIXED15),
        "drop_513100": set(FIXED15) - {BAD_NASDAQ},
        "replace_513100": (set(FIXED15) - {BAD_NASDAQ}) | {r1},
        "drop_159529": set(FIXED15) - {BAD_CONSUMER},
        "replace_159529": (set(FIXED15) - {BAD_CONSUMER}) | {r2},
        "drop_both": set(FIXED15) - {BAD_NASDAQ, BAD_CONSUMER},
        "replace_both": (set(FIXED15) - {BAD_NASDAQ, BAD_CONSUMER}) | {r1, r2},
        "add_both": set(FIXED15) | {r1, r2},
    }

    variants = {k: variant_summary(k, bars, features, FIXED15, v) for k, v in pools.items()}
    result = {
        "study": "Universe Oracle V1 — hindsight upper bound only",
        "change_date": str(CHANGE_DATE.date()),
        "frozen_bad_symbols": [BAD_NASDAQ, BAD_CONSUMER],
        "oracle_rule": {
            "min_complete_2025_26_episodes": MIN_ORACLE_EPISODES,
            "listed_by": str(MIN_FIRST_DATE.date()),
            "primary": "same region + exposure_level1 + risk_bucket; max 2025-26 mean fwd20",
            "fallback_for_consumer": "same region/exposure, new risk bucket vs remaining pool; max 2025-26 mean fwd20",
            "lookahead": True,
        },
        "chosen_replacements": chosen,
        "replacement_audit": audit.replace({np.nan: None}).to_dict(orient="records"),
        "variants": variants,
    }
    Path(args.summary_path).write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    base = variants["fixed15"]["period_2025_2026"]
    lines = [
        "# Universe Oracle V1",
        "",
        "> Hindsight upper-bound diagnostic. This report must not be interpreted as a tradable universe rule.",
        "",
        f"- Change date: `{CHANGE_DATE.date()}`",
        f"- 513100 oracle replacement: `{r1}`",
        f"- 159529 oracle replacement: `{r2}`",
        f"- Consumer fallback used: `{chosen['consumer_used_fallback']}`",
        "",
        "## 2025-2026 comparison",
        "",
        "| Variant | Total return | Max DD | Switches | Candidate mean | Mean Top1 tenure |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, v in variants.items():
        p25 = v["period_2025_2026"]
        ten = v["top1_tenure_2025_2026"]
        lines.append(
            f"| {key} | {p25.get('total_return', 0):.2%} | {p25.get('max_drawdown', 0):.2%} | "
            f"{p25.get('switch_events', 0)} | {v.get('candidate_count_mean', 0):.2f} | {ten.get('mean_top1_tenure', float('nan')):.2f} |"
        )
    lines += [
        "",
        "## Interpretation contract",
        "",
        "- `drop` tests whether a deteriorated incumbent itself is harmful.",
        "- `replace` vs `drop` tests whether the new ETF adds incremental opportunity rather than merely deleting a loser.",
        "- `add_both` tests whether more opportunity helps or whether extra candidates worsen cross-sectional competition.",
        "- Only the 2025-2026 delta is meaningful because replacements are selected with 2025-2026 outcomes.",
        "- A positive Oracle result only licenses a later point-in-time walk-forward universe study; it does not license these replacements.",
        "",
    ]
    Path(args.report_path).write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

if __name__ == "__main__":
    main()
