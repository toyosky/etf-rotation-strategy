# 2026-11-20 — prior 20-session volatility and 5-day downside screen

## Scope and outcome
Executed read-only SQL in Supabase project `gsyziuzezmmnvgdoazkg`, `public.daily_bars`. Exact SQL: `sql/volatility20_nextopen_mae.sql`. Sample: all 19-symbol fixed-table events with signal day close-to-close decline >=2%, 2021-01-01 to 2026-11-10, at least 20 prior return observations, and 5 future lows. Volatility is sample standard deviation of **prior 20 trading-session log returns** (excluding signal day t). Outcome is min(low[t+1:t+5])/open[t+1]-1; event is adverse excursion <= -5%. Price is HFQ and execution reference is t+1 open **proxy**, not actual strategy 14:05 fill. Groups at <1.5%, 1.5–3%, >=3% daily vol are exploratory thresholds, not optimized or validated cutoffs.

## Executed results

| Period | Prior vol | N | Mean 5d worst excursion | Deep fall >=5% |
|---|---|---:|---:|---:|
| 2021–24 | <1.5% | 327 | -1.98% | 7.65% |
| 2021–24 | 1.5–3% | 320 | -2.49% | 13.75% |
| 2021–24 | >=3% | 36 | -5.13% | 33.33% |
| 2025–26 | <1.5% | 161 | -2.39% | 11.80% |
| 2025–26 | 1.5–3% | 223 | -2.95% | 17.94% |
| 2025–26 | >=3% | 146 | -5.80% | 47.26% |

An event-thinning sensitivity (retain every fifth down-day event within symbol/year, not necessarily five-session non-overlap) gives:
- 2021–24 low 1/75 (1.33%), mid 8/74 (10.81%), high 2/7 (28.57%).
- 2025–26 low 5/47 (10.64%), mid 9/39 (23.08%), high 11/34 (32.35%).

## Interpretation

Unlike raw turnover conditioning, **higher pre-event realized volatility displays a monotone association with deeper subsequent 5-day adverse excursion in both multi-year periods**, and the direction survives this limited thinning diagnostic. It may merely reflect scale (a 5% absolute loss threshold is easier to cross in a high-volatility asset), ETF/asset mix, and market regime; therefore the result does NOT demonstrate independent alpha or a profitable timing signal. Must compare volatility-normalized MAE, control for signal-day severity, symbol/year and other feature groups, and test incremental OOS predictive skill and risk-adjusted portfolio impact. No confidence intervals, purge/embargo, PIT holdings, or model training were performed here.

## Source audit and next gate

Latest GitHub Actions listing shows Qualified Rebuild Premium Sync failures at 2026-11-19 17:39, 20:06, 21:35 UTC; Research Rebuild Market Context Indicators succeeded at 21:35 UTC. Historical premium PIT blocker remains. Need prioritize an actual frozen-strategy state replay and five-block OOS ablation; do not continue endlessly with univariate threshold screens. The 2026-10-20 GitHub Release full-market Parquet is a known candidate archive but not yet content-validated. No production changes.

**Status:** exploratory volatility block diagnostic, not accepted sizing rule. Research still incomplete.
