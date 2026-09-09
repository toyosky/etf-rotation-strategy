# Full-Market OLS Episode Lifetime Quintile Study — 2026-09-09

## Question

Among ETFs that newly enter an eligible rising OLS trend, which *observable-at-entry* states are associated with longer remaining trend life?

This is an exploratory mechanism study only. No trading rule or production strategy is changed.

## Sample

- Master universe: 633 ETFs from `ETF_daily_bars`
- Dynamic point-in-time eligibility: >=365 calendar days since first bar, >=200 bars, trailing-60d mean amount >= CNY 20m, trailing-60d median amount >= CNY 10m, nonzero-volume ratio >=95%
- OLS: frozen 26-day half-life-10 weighted log-price regression, identical to prior strategy calibration
- Episode: first day `trend_eligible` changes from false to true
- Episode dates: 2021-01-01 through 2026-09-08
- Episodes: 13,114
- Right-censored at 20d: 509

Primary lifetime labels:
- `ma10_life20`: first day close falls below MA10, capped at 20
- `mom5_life20`: first day close is no longer above close 5 trading days earlier, capped at 20
- `ols_life20`: first later day the frozen OLS trend eligibility fails, capped at 20

Secondary outcomes: 10d / 20d forward return.

## Main split: 2021–2024 vs 2025–2026

### 1. Slope delta is the cleanest monotonic lifetime variable

`SlopeDelta = slope_t - slope_{t-1}`.

2021–2024 quintiles, Q1 -> Q5:
- MA10 life: 1.32, 4.48, 5.70, 6.88, 8.40d
- 5d-momentum life: 0.68, 2.97, 4.66, 5.61, 6.79d
- OLS life: 7.87, 8.47, 10.26, 11.86, 11.29d
- 10d return: +0.27%, -0.25%, -0.25%, -0.23%, +1.93%

2025–2026:
- MA10 life: 0.76, 4.45, 7.06, 7.81, 8.39d
- 5d-momentum life: 0.21, 3.04, 5.27, 6.40, 7.09d
- OLS life: 6.81, 8.33, 11.46, 12.77, 10.72d
- 10d return: +0.48%, -0.09%, +0.59%, +0.77%, +0.88%

Year-by-year, MA10 life rises strongly from low to high slope-delta in every year 2021–2026. This is the most stable first-pass lifetime relationship.

### 2. Score delta also separates short-lived from long-lived entries, but the extreme top quintile weakens in 2025–2026

2021–2024 Q1 -> Q5 MA10 life:
1.43, 5.14, 5.87, 6.95, 7.38d.

2025–2026:
0.97, 5.24, 7.04, 8.20, 7.03d.

Thus negative/very weak score change is consistently poor, while Q3–Q4 is strong. Q5 is no longer uniformly best in the recent regime, suggesting an over-acceleration / maturity effect rather than simple monotonicity.

### 3. Current OLS residual has a strong positive lifetime gradient

`current_resid = log(close_t) - fitted_log_price_t`.

2021–2024 Q1 -> Q5:
- MA10 life: 1.30, 4.20, 5.90, 6.86, 8.52d
- 5d-momentum life: 0.54, 2.86, 4.80, 5.64, 6.87d

2025–2026:
- MA10 life: 0.77, 4.27, 7.08, 7.85, 8.50d
- 5d-momentum life: 0.22, 2.83, 5.20, 6.53, 7.22d

The relationship appears in every year. A newly eligible OLS trend with price still below its fitted trend line is usually extremely short-lived; positive residual is associated with much longer price-trend life.

### 4. Five-day return is strongly related to remaining price-trend life

2021–2024 Q1 -> Q5 MA10 life:
1.78, 4.15, 5.85, 6.72, 8.27d.

2025–2026:
0.78, 5.08, 6.95, 7.36, 8.31d.

This relation is stable year-by-year. It should not be interpreted as 'buy the biggest 5d gain' yet, because very high longer-window trend strength shows maturity effects.

### 5. Distance to the 20-day high is another stable state variable

`dist_high20 = close / rolling_20d_high - 1`.

The lowest quintile (furthest below recent high) has very short MA10/momentum life, while entries near the 20-day high have longer remaining life.

2025–2026 Q1 -> Q5 MA10 life:
1.72, 4.58, 6.62, 7.36, 8.20d.

This direction is present in every year 2021–2026.

### 6. Volatility is not simply 'lower is better'; extreme high volatility is poor in the recent regime

For 60d volatility in 2025–2026, Q1 -> Q5:
- MA10 life: 6.51, 6.55, 6.02, 5.26, 4.13d
- OLS life: 11.75, 11.51, 10.92, 9.47, 6.42d
- 10d return: +0.78%, +1.25%, +0.51%, +0.97%, -0.90%
- 20d return: +1.15%, +1.53%, +1.18%, +1.85%, -1.78%

The extreme-high-volatility group is especially poor in 2024–2026. Earlier years are less stable, so volatility looks more like a regime-sensitive risk / maturity penalty than a universal factor.

## Important non-linear result: raw Score and slope are inverted-U, not monotonic

A crucial result is that the highest raw OLS Score / slope quintile does **not** have the longest remaining price-trend life.

2025–2026 Score quintiles Q1 -> Q5:
- MA10 life: 5.61, 6.77, **7.72**, 5.08, 3.28d
- 5d-momentum life: 4.32, 5.40, **6.28**, 4.10, 1.90d
- 10d return: +0.33%, +0.83%, **+1.36%**, +0.47%, **-0.34%**
- 20d return: +0.84%, +1.37%, **+1.92%**, +0.54%, **-0.31%**

2026 alone is even clearer: highest Score quintile has MA10 life 3.06d and 10d return -2.70%.

Raw slope shows a similar inverted-U shape, with middle quintiles generally having longer remaining life than the most extreme slope group.

Interpretation: the current strategy's Top1 ranking can select the **strongest current trend**, but an extremely strong current trend is often already mature. This is direct evidence supporting the separate Universe/Lifetime filter architecture.

## Preliminary ranking of candidate lifetime features

Most promising for a first dynamic-universe prototype:

1. `slope_delta` — strongest monotonic and year-by-year stable lifetime relation
2. `current_resid` — very strong stable price-trend-life relation
3. `ret5` — strong stable relation, simple economic interpretation
4. `dist_high20` — strong stable relation, identifies weak rebound entries vs genuine near-high trend states
5. `score_delta` — useful, but extreme-high group is not always best; likely better as a 'not weakening' condition than a maximize-me factor

Secondary / cautionary:
- raw `score`, raw `slope`, raw `r2`: clear nonlinearity / over-maturity at extreme values
- `vol60`: extreme-high penalty is useful, but less stable before 2024
- 60/120d high position, 20d efficiency: weaker or regime-dependent

## Interpretation

The first full-market study supports a coherent mechanism:

`new OLS eligibility` alone is too permissive.

Long-lived trend entries tend to have:
- positive and rising slope (`slope_delta`)
- price confirming rather than lagging the fitted trend (`current_resid > relatively low states`)
- positive recent 5d momentum
- price close to its recent 20d high
- but **not necessarily the most extreme raw Score / slope**

This suggests the desired universe filter should not simply choose 'the strongest ETFs'. It should identify a **healthy early/mid-stage trend state**, then let the original OLS ranking choose Top1 inside that filtered universe.

## Overfit caution / next step

No hard thresholds are justified yet. The quintiles here are descriptive and were formed within broad periods/years.

Next test should be walk-forward / point-in-time filtering using a very small number of frozen state rules or an ordinal lifetime score, with thresholds derived from prior history only. Key question:

> Can a dynamic candidate pool built from these stable states improve out-of-sample Top1 performance without materially shrinking opportunity count or becoming dominated by duplicated ETFs?

No production strategy changes were made.