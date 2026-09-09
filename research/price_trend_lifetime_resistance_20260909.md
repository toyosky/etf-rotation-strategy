# Price Trend Lifetime × Upper Resistance — 2026-09-09

## Question

Does the daily Volume Profile proxy predict the **ETF's own price-trend lifetime**, independently of Rank1 persistence?

This is a mechanism study only. No trading rule is changed.

## Signal sample

- Source strategy: `FROZEN_C2@20260903T_fixed_window_v2`
- Events: days when `top1` changes to a new non-cash ETF
- Sample: 2021-01-04 through 2026-08-05
- Cash proxy `511220` excluded

## Resistance proxy

For each switch event with current close `P`:

- Lookback: prior 120 trading days, excluding the signal day
- Local zone: `[0.95P, 1.05P]`
- Upper zone: `[P, 1.05P]`
- Each historical day's `amount` is spread uniformly across that day's `[low, high]` range
- `UpperShare = estimated amount in upper zone / estimated amount in local zone`

Lower `UpperShare` = less historical trading overhead; higher `UpperShare` = denser overhead trading.

## Price-only trend lifetime definitions

All are capped at 20 trading days and use only the ETF's own prices:

1. `MA10 lifetime`: first day on which close < 10-day SMA.
2. `5-day momentum lifetime`: first day on which close <= close five trading days earlier.
3. `3% drawdown lifetime`: first day on which close <= running post-signal peak × 0.97.

Robustness variants also used MA5, MA20 and 3/10-day momentum.

## Main quartile results

### 2021-2024

Lowest-resistance quartile (Q1):

- MA10 lifetime: 8.33 days
- 5-day momentum lifetime: 6.50 days
- MA20 lifetime: 15.14 days
- 3-day momentum lifetime: 3.86 days
- 10-day momentum lifetime: 13.03 days

Highest-resistance quartile (Q4):

- MA10 lifetime: 5.43 days
- 5-day momentum lifetime: 3.40 days
- MA20 lifetime: 11.66 days
- 3-day momentum lifetime: 2.06 days
- 10-day momentum lifetime: 8.69 days

Spearman correlation, `UpperShare` vs lifetime:

- MA5: -0.341
- MA10: -0.327
- MA20: -0.209
- Momentum 3d: -0.354
- Momentum 5d: -0.337
- Momentum 10d: -0.298

### 2025-2026

Lowest-resistance quartile (Q1):

- MA10 lifetime: 8.29 days
- 5-day momentum lifetime: 6.48 days
- MA20 lifetime: 14.10 days
- 3-day momentum lifetime: 4.14 days
- 10-day momentum lifetime: 11.81 days

Highest-resistance quartile (Q4):

- MA10 lifetime: 4.25 days
- 5-day momentum lifetime: 2.60 days
- MA20 lifetime: 8.50 days
- 3-day momentum lifetime: 2.35 days
- 10-day momentum lifetime: 7.80 days

Spearman correlation, `UpperShare` vs lifetime:

- MA5: -0.376
- MA10: -0.371
- MA20: -0.340
- Momentum 3d: -0.388
- Momentum 5d: -0.316
- Momentum 10d: -0.219

## Important negative result

The 3% drawdown lifetime has essentially no relationship with overhead resistance:

- 2021-2024 Spearman: -0.016
- 2025-2026 Spearman: -0.037

Interpretation: overhead resistance appears to predict **trend deceleration / loss of momentum**, not an immediate sharp reversal.

## Control for proximity to prior 120-day high

After linearly controlling for `current close / prior 120-day high`:

- 2021-2024: partial corr UpperShare vs MA10 lifetime = -0.255; vs 5d momentum lifetime = -0.253
- 2025-2026: partial corr UpperShare vs MA10 lifetime = -0.225; vs 5d momentum lifetime = -0.227

Thus the effect is not explained only by "low overhead resistance means the ETF is already at a new high."

## Excluding oil and silver

For 2025-2026, excluding `501018` and `161226`:

Lowest-resistance quartile:

- MA10 lifetime: 8.21 days
- 5d momentum lifetime: 6.58 days

Highest-resistance quartile:

- MA10 lifetime: 4.44 days
- 5d momentum lifetime: 2.56 days

The result is therefore not driven solely by the long commodity trends.

## Year-by-year check

MA10 lifetime was shorter in the high-resistance half than the low-resistance half in **every year 2021-2026**:

- 2021: 7.94 vs 6.59 days
- 2022: 6.50 vs 5.83
- 2023: 9.38 vs 7.31
- 2024: 7.09 vs 2.86
- 2025: 9.00 vs 5.36
- 2026: 8.05 vs 4.56

For 5-day momentum, the same direction appears in every year except 2022, where the two halves are essentially equal (3.28 vs 3.33 days).

## Interpretation

This materially strengthens the mechanism hypothesis:

`high overhead trading density -> slower price progress / earlier momentum loss`

The effect exists already in 2021-2024, so the earlier weak return result should not be read as "resistance was ineffective." Instead, long-lived trends could absorb the delay. In 2025-2026, Rank1 lifetimes are shorter, so the same resistance cost consumes a larger fraction of the available trend window.

The lack of a drawdown relationship is especially informative: this is better described as a **path-of-least-resistance / speed** effect than a crash predictor.

## Current research status

- Mechanism evidence: materially strengthened
- Strategy integration: not yet justified
- No threshold should be optimized yet
- Next high-value step: build a minute-level Volume Profile for switch events and test whether true intraday price-volume distribution strengthens the lifetime relationship versus this daily approximation.
