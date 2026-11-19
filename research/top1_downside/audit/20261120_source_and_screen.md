# Top1 downside research — first execution / source and feasibility audit (2026-11-20)

**Status:** first phase completed (source audit + exploratory screening); primary historical executable-portfolio reconstruction, model fitting, and walk-forward backtests **NOT** complete. This is a research-only branch; no production change.

## 1. Audited sources, dates and grain

- Supabase project `gsyziuzezmmnvgdoazkg`, `public.daily_bars`: 33,205 daily symbol-date records, 19 unique symbols, 2013-05-15 through 2026-11-19. 2021–2026 counts: 2021 2,916 / 12 symbols; 2022 3,156 / 14; 2023 3,486 / 15; 2024 3,849 / 16; 2025 3,954 / 18; 2026 3,862 / 19. All 21,223 observations from 2021–2026 have positive volume and amount. Canonical daily close fields described as Tencent HFQ, amount as raw CNY traded.
- `public.minute_bars`: 168,990 rows, 15 symbols, trading dates **2026-09-14 to 2026-11-19**. **Not** a 2021–2026 intraday execution backtest dataset.
- `public.fund_premium_history`: 4,074 rows / 175 symbols / 2026-02-24 to 2026-11-19, `pit_safe=true` **0 rows**, missing `first_seen_at` in 1,035 rows. Do not retroactively assert a contemporaneously observable 10% premium gate. This is a major blocker for full historical executable reconstruction.
- Repository `data/live-forward.json`: tracking starts 2026-09-14, as-of market data through 2026-11-19. Its own disclaimer says model NAV may include hypothetical fills without dated premium clearance and is **not actual performance**.
- Repository `data/state-map-history.json`: archived market regime trace begins 2025-11-06 (not a full 2021–2026 point-in-time execution trace).
- Historical all-market data is **not absent**: GitHub release tag `research-data-fullmarket-current` contains `refreshed_daily_bars.parquet` (17,287,798 bytes), `today_signals.csv` and `today_report.json`, published 2026-10-20. The older tag `research-data-fullmarket-20261020` has a 16,676,858-byte Parquet; `research-data-fullmarket-20260917` has a 15,457,123-byte tarball. These are candidate archives, not yet validated for historical completeness, adjusted-price consistency, delisted funds, or PIT membership. Research PR #5/#6 uses a distinct expanded taxonomy dataset; must verify lineage before merging histories.

## 2. Frozen execution strategy audit: critical correction

The CURRENT `strategy/main.py` is `FIXV2_V1_75_VOID_ROUTE_BANK14_INTRADAY_S1_PREMIUM10`. Its header explicitly states the historical **C2 two-day confirmation is retired**, not simultaneously active. Therefore the original preregistration mention of C2 is superseded by this source audit; do not reconstruct a fictitious combined C2+Void strategy.

Rules from current code header:
- 14 risk ETFs plus 511220 comparator; 513500 may be Void Carrier, not ordinary competing Top1.
- 26 prices, weighted log-price OLS; `np.polyfit` passes q, actual objective weights are q². Raw Top1 eligibility, V1 resistance block on pure rank switch, Breadth and Gap Percentile, DEFENSIVE_VOID, incumbent freeze / Deepen1 / route.
- End-of-day signal; pre-open premium finalization; 09:31 gap check; **14:00 sells, 14:05 intraday pullback check/buys**, after-close signal. No universal next-open buy. Price-based 3% protection and NAV-date visibility require execution-stage audit.
- `data/registered-live-strategy.json` separately records a proposed 70% OLS / 30% base sleeve; **not** the user's real transaction history. Keep sleeve/simulated signal/human positions separate.

**Consequence:** true 2021–2026 executable holdings cannot be asserted from daily HFQ + hindsight NAV. Need separate (A) conditional theoretical position risk under a clearly flagged daily-bar approximation, (B) true PIT-confirmed live-forward windows, (C) explicit execution sensitivity bounds. No final risk-sizing conclusions until this is dealt with.

## 3. Volume-scale caution (data quality)

Observed median `amount/(volume*HFQ_close)` differs materially by ETF: 159934 ~2.4563, 511220 ~7.3000 with 95th percentile ~76.4154, 511380 ~10.0012, 513100 ~0.2000, 513500 ~0.5002, 512800 lower-tail ~0.4982. This is **not proof of raw share-unit errors**: HFQ price rescaling versus unadjusted volume and historical corporate actions can themselves create these ratios. But it invalidates naive cross-ETF price-volume identity and warns against raw-volume comparisons. Use previous-20-session **turnover amount ratio** as the first screening feature, detect structural breaks, and document symbols with observed instability.

Prior documented study `research/volume_exit_study_20260930.md` found no volume+high-to-close drawdown take-profit threshold robust across 2021–24 and 2025–26. Its outcome was future close return (not future executable MAE), based on raw OLS top days, so it is background rather than an answer to the new question.

## 4. Actual exploratory screen completed — amount × prior path

Reproducible read-only query: `research/top1_downside/sql/exploratory_volume_path.sql`.

**Scope is all-symbol down-day events, not actual held Top1.** Rows with t return <= -2%; at least 20 prior traded-amount observations; prior five-session return split at -3%; normalized amount ratio = t amount / mean previous 20-session amounts. Outcome: minimum of subsequent 5 days' adjusted daily lows / signal-day adjusted close - 1. This is a signal-close descriptive statistic, **not** the t+1 executable-price MAE, does not adjust for costs, and overlapping events are not independent.

- 2021–2024: 678 down-day events in 6 strata. Five-day extra >=5% fall rates by amount group are non-monotonic (~10.6–15.7% across prior-path strata).
- 2025–2026: 528 events. With prior-five-day return <=-3%, high amount >1.5x n=65, future >=5% fall **18.46%**; low amount <0.8x n=105, **31.43%**; normal n=116, **31.90%**. With prior-five-day return >-3%, high n=74, **25.68%**; low n=54, **42.59%**; normal n=114, **18.42%**.
- Current sample composition, ETF fixed effects, year/regime, initial signal-day severity, overlapping outcomes and lookahead in universe membership are **not** controlled. This is an **exploratory association** and does **not** establish volume as a causal or incremental predictive feature; do not trade on any quoted rates.

## 5. Next test gates (in order)

1. Reconcile source versions and decision timestamps against frozen code. Reconstruct two clearly separated portfolios: daily approximation and fully PIT-auditable executable positions; identify exactly which era can be called a genuine historical executable backtest.
2. Validate archived full-market Parquet with source hashes, adjustment conventions, listing/availability dates, delist survivorship, amount scaling. Keep new full-market research distinct from production 14-risk fixed pool.
3. Rebuild 26-session weighted OLS, V1 resistance and Void episode state from complete historical daily OHLCV, **without** C2. Assert reproducibility on known dated state-map/live-forward snapshots before assigning "held Top1" labels.
4. Build the predeclared five feature blocks and 3/5/10-day future excursion labels using t+1 executable price where actually observable. Keep signal-close exploratory labels separate. Create event clusters, purge+embargo, calibrated chronological OOS ablations; compare turnover with and without conditioning on prior path, symbol, and regime.
5. Only if robust OOS improvement exists, implement simulated dynamic sizing against frozen strategy and simple stop/volatility/fixed-exposure baselines, with costs and gap risk. Otherwise report null and retain original portfolio.

## Completion and policy

No OOS classifier, MAE forecaster or dynamic allocation backtest was run in this first execution. This phase found important data/strategy specification issues, and preserved a reproducible hypothesis screen. **Do not disable the automation yet:** the five-group main analysis is not done. Never modify the main strategy on research findings alone.

Data-exposure note: schema inspection also warns `research.ols_episodes` and `research.instrument_metadata_backup_20260911_before_v2` currently have RLS disabled. Separate access-control audit is appropriate; no database security changes performed in this study.
