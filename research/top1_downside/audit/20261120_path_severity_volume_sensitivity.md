# Execution 5 — volume effect sensitivity to price-path and severity matching

Date 2026-11-20. Reproducible query: `research/top1_downside/sql/matched_path_severity_volume.sql`. Scope: all ETF symbol-days with same-day close return <= -2%, turnover <0.8x or >1.5x of previous 20 days; outcome: next five daily lows below -5% relative to signal close. Not held Top1; no OOS, executable fills, event-cluster confidence intervals or portfolio backtest.

## What changed from previous execution

Execution 4 matched only ETF and year (minimum three low and three high events in each stratum), finding 2025–26 matched-weighted low-minus-high risk difference **-2.23 percentage points**. That result did not control preceding price path or the size of the down day.

This run additionally stratifies by (ETF, calendar year, preceding five-session return <= -3% vs > -3%, same-day return <= -4% vs -2% to -4%). Strata with >=2 low and >=2 high events retained; matched difference weights each stratum by min(n_low,n_high).

| Period | Matched strata | Low n | High n | Low risk | High risk | Weighted low-minus-high |
|---|---:|---:|---:|---:|---:|---:|
| 2021–24 | 21 | 88 | 58 | 9.09% | 15.52% | **-8.81 pp** |
| 2025–26 | 11 | 41 | 38 | 48.78% | 34.21% | **+12.40 pp** |

**Interpretation:** even the *sign* of the turnover association is unstable under modest, reasonable matching refinements: 2025–26 ETF-year-only matched result -2.23 pp becomes +12.40 pp after matching path and daily drop severity. Small 2025–26 groups (41/38 observations across 11 strata), coarse cutoffs, repeated event dates, and no uncertainty intervals make this highly unstable. The large risk rates in the newly retained sample are conditional selection effects and not a population estimate. Do not call this a validated predictive effect, and do not turn either direction into a volume-based exit.

**Conclusion of this diagnostic:** turnover may be useful only as an interaction with recent price path, drop severity and market regime; evidence of *independent* incremental prediction is still absent. Future work should compare proper time-purged OOS B0+B1 against B0+B1+B2, not optimize matched strata in hindsight. This screen is a falsification/sensitivity check, not a new fitted model.

## Data and strategy gates unchanged

Full-market historical Parquet is available as a release asset but still needs actual loading, provenance and survivorship audit. Exact historical premium and 14:05 minute-level execution remains unavailable for 2021–2025, so a daily proxy must be labeled as such. Current production code has retired C2. No changes to production strategy, schedules or database.
