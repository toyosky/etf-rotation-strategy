# Execution 4 — within-ETF-year turnover comparison (2026-11-20)

**Scope:** preliminary, retrospective diagnostic of all ETF symbol-days with close-to-close return <= -2%. **Not actual Top1 held events, not an out-of-sample model, not causal, not an executable risk rule.**

## Question
The prior annual table showed much higher deep-fall frequency following low-turnover down days in 2025–26. Does the direction survive a minimal control for ETF identity and year?

## Reproducible analysis
SQL: `research/top1_downside/sql/matched_symbol_year_volume.sql`. All 19 daily-bars symbols; signal day t close drop <= -2%, amount ratio to previous 20 sessions; low <0.8x and high >1.5x; label min(low[t+1:t+5])/close[t] <=0.95. Group by (symbol, calendar year), retain only strata with **at least 3 low and 3 high** events. Report pooled rates in matched subset, equal-stratum mean low-minus-high risk difference, and a matched-weighted risk difference using min(low_count,high_count) as weights. Neither metric is a confidence interval or regression coefficient.

| Period | matched ETF-years | low events | high events | pooled low deep-fall % | pooled high deep-fall % | equal-stratum diff pp | matched-weighted diff pp |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2021–24 | 16 | 112 | 101 | 9.82 | 17.82 | -9.50 | -11.77 |
| 2025–26 | 12 | 142 | 69 | 36.62 | 31.88 | -6.71 | -2.23 |

**Important Simpson/composition warning:** In 2025–26 the pooled low-turnover group looks worse by **+4.74 pp**, but the **within-ETF-year matched-weighted** difference flips to **-2.23 pp**. The equal-stratum comparison is also negative (-6.71 pp). This is evidence of strong ETF-year composition confounding, **not** proof that low turnover is protective. Even after matching, the initial fall magnitude, prior price path, regime, overlapping outcome windows and within-stratum event selection remain uncontrolled; some strata have only 3 events per side.

## Decision
Reject the simple pooled claim that 'low turnover predicts a larger next-5-day deep-fall risk'. Retain turnover as a candidate interaction/conditional feature for proper OOS ablation, not as a trading threshold. No dynamic sizing warranted.

## Follow-up
1. Add a time-purged event-cluster design and pre-event price-path/severity controls, then compare OLS-only vs OLS+path vs OLS+path+turnover in actual or explicitly approximated Top1 holdings.
2. Validate the archived full-market Parquet and historical PIT NAV/execution feasibility. The existing source audit identifies only 2026-09 onward minute bars and no PIT-safe premium history.
3. Report uncertainty and sample dependence before making any predictive claim.

**Run ledger:** archived SQL and this note on branch `research/top1-downside-20261120`; no production code, trading automation or database tables changed.
