# Q3 — OLS trend-state conditioning of price deviation | 2021–2026

**Status**: completed observational study, no production rule modification.

## Setup and definitions

- Source: Supabase `public.daily_bars`, data through 2026-11-18. 14 tracked risk ETFs including 512800 + comparator 511220. Signal window 2021-01-01 to 2026-11-03; only ETF-days with at least 10 subsequent ETF observations are evaluated.
- Same OLS26 as source `research/full_market_ols_storage.py`: 26 log-closes, weights `0.5^((25-j)/5)`, annual `expm1(beta*250)`, weighted R². Requires `annual>0` and `R²>=0.50` at signal T.
- `deviation_sigma = [log(C_T) - fitted_OLS26_log(C_T)] / sqrt(weighted_SSE/sum_weights)`, calculated with closes through T. This is **not** the 60-day return-Z anomaly used in prior D2 research.
- Deviation bins fixed to Q2: negative [-2,-1.5), neutral [-0.5,+0.5), positive [+1.5,+2). Predefined 3-day trend state uses comparison T versus T-3 **for each ETF's observation sequence**. `B+` iff beta_T>=beta_T-3; `R+` iff R²_T>=R²_T-3; otherwise B-/R-. Score delta also inspected independently.
- Signal-return outcomes: 5d T close→T+5 close and 10d T close→T+10 close. Executable proxy T+1 open→T+6 open does not deduct fees/slippage. 'Adverse low 5d' is the minimum observed low during T+1...T+5 divided by T close minus one. It is **not** portfolio maximum drawdown. Latest raw Top1 is reconstructed across **all** 14 risk ETF raw OLS Scores (not limited to the R²>=0.5 research sample), requiring its Score to exceed comparator; not the V1/D2/Void/Premium10-routed final target.
- All variables through T only, but future returns overlap among adjacent signals; thus n is an ETF-day observation count, not n independent trades.

## Main results: Q2 deviation grouped by beta/R² changes

| Deviation | Trend state | N | Next 5d close mean | 5d next-open mean | 5d low below -5% |
|---|---|---:|---:|---:|---:|
| negative | B+R+ | 2 | 1.229% | 0.926% | 0/2 |
| negative | B+R- | 6 | 2.167% | 4.154% | 1/6 |
| negative | B-R+ | 0 | NA% | NA% | 0/0 |
| negative | B-R- | 127 | 0.586% | 0.662% | 9/127 |
| neutral | B+R+ | 1148 | 0.69% | 0.628% | 85/1148 |
| neutral | B+R- | 13 | -2.204% | -1.901% | 6/13 |
| neutral | B-R+ | 251 | 0.559% | 0.508% | 22/251 |
| neutral | B-R- | 232 | 0.38% | 0.204% | 27/232 |
| positive | B+R+ | 114 | 0.556% | 0.607% | 15/114 |
| positive | B+R- | 36 | -2.853% | -2.361% | 15/36 |
| positive | B-R+ | 0 | NA% | NA% | 0/0 |
| positive | B-R- | 2 | 2.066% | 2.941% | 0/2 |

**Negative deviations**: 127/135 (94.1%) also show B-R-; only 2/135 show B+R+. These are mechanically coupled to a falling latest close in short-window OLS26. Therefore the proposed 'negative deviation while beta and R² both improve' sample is too small to validate an add-on-dip rule.

**Positive deviations**: B+R+ N=114, mean 5d 0.556% and adverse below -5% 15/114; B+R- N=36, mean 5d -2.853% and adverse below -5% 15/36. Signal reflects a rising 26-day beta while fit reliability deteriorates; it is an **exploratory fragility pattern**, not proven trading alpha.

Monthly-block bootstrap (2400 deterministic resamples) B+R- minus B+R+ 5d return mean difference -3.409 pp, 95% empirical interval [-6.455, -0.796] pp. Low adverse difference -3.267 pp, interval [-6.249, -0.794] pp. This is not a full multi-way clustered/causal inference and was selected after observing the data; intervals should NOT be construed as out-of-sample validation.

## Top1-only results

- Raw Top1 B+R+: 39 observations, 5d average 0.545%, low below -5% 9/39.
- Raw Top1 B+R-: 17 observations, 5d average -4.001%, low below -5% 11/17.
- Top1 subset is very small; historic fund NAV premiums and executable fills unconfirmed.

## Robustness and critical limitations

- Adjacent same-ETF identical-bin observations deduped by 10 ETF days: B+R+ N=85, forward 5d 0.707%; B+R- N=29, forward 5d -1.809%.
- 2021-2023: B+R+ N=53, 5d 0.861%; B+R- N=17, 5d -1.941%.
- 2024-2026: B+R+ N=61, 5d 0.291%; B+R- N=19, 5d -3.669%.
- Clamp individual 5d returns to ±10%: B+R- -1.468%, B+R+ 0.54% (not a realizable portfolio backtest).
- Remove largest 3 absolute-negative B+R- records: group mean -0.976%; remove largest 5: -0.091%. **Original -2.85% mean is driven importantly by oil/energy/silver tail events**, including adjacent overlapping dates; do not interpret as usual expected loss.
- Raw Top1 may differ markedly from actual incumbent; risk-asset historical adjusted bars, LOF premia, interruptions and timestamping need audits. The older fixed D2, V1, Void remain unchanged; this study does not model dynamic position sizing or trading costs.
- Conditioning on rising beta and falling R² is not necessarily information independent from recent price changes; overfit/multiple-hypothesis testing from Q1/Q2/Q3 should be accounted for prospectively. Positive residual + R² falling is not unique: neutral-bin B+R- has 13 samples with poor outcomes, suggesting a potentially more general structural-instability signal.

## Decision

1. **Q3 does not validate mechanistic 'oversold but OLS still improving' add-on-dip**; too few qualifying observations.
2. **Candidate for further study**: a high-positive residual combined with beta-rising and R²-falling appears more fragile, especially for 5d downside risk, but cannot justify an automatic sell or position scaling yet.
3. Next step should distinguish the predictive value of R² deterioration from residual overextension after matching volatility, asset, time/regime and baseline score strength, and explicitly test exposure-matched dynamic position sizing with outlier-aware prices and transaction-cost stress. No production change.

Evidence files: [per-day conditioned events](q3_ols_deviation_trend_event_samples_2021_2026.csv) and [group summary](q3_ols_deviation_trend_group_summary_2021_2026.csv).
