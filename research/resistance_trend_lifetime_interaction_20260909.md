# Resistance × Top1 Lifetime Interaction — 2026-09-09

## Question

Test the mechanism hypothesis:

> Upper price-volume resistance may have existed throughout the sample, but it mattered much more in 2025–2026 because Top1 leadership / trend windows became shorter.

This is a diagnostic event study only. It does not modify the formal strategy.

## Data and frozen strategy

- Strategy: `FROZEN_C2@20260903T_fixed_window_v2`
- Rank1 history: 2021-01-04 to 2026-08-05
- Daily bars: Supabase `daily_bars`
- Cash proxy `511220` excluded from resistance tests
- Main resistance definition uses 120 prior trading days and the price band from current price P to P×1.05.

## Definitions

### Top1 lifetime

A new Rank1 episode starts whenever the symbol in `daily_scores` rank=1 changes.

`life_days` = number of consecutive trading days for which the same ETF remains Rank1.

This is an ex-post mechanism variable and is not directly tradable.

Buckets:

- short: <= 3 trading days
- medium: 4–10 trading days
- long: > 10 trading days

### Upper resistance

Using the prior 120 daily bars, each day's `amount` is approximately distributed uniformly across that day's `[low, high]` range.

`UpperShare = historical amount in [P, 1.05P] / historical amount in [0.95P, 1.05P]`

Main descriptive split:

- low resistance: UpperShare <= 0.20
- high resistance: UpperShare > 0.20

A quartile test is also reported to avoid dependence on the 0.20 split.

## 1. Top1 lifetimes clearly shortened in 2025–2026

### 2021–2024

- episodes: 147
- average lifetime: 6.59 trading days
- median: 5 days
- p75: 10 days
- p90: 15 days
- <=3 days: 61 / 147 = 41.5%
- >10 days: 35 / 147 = 23.8%

### 2025–2026

- episodes: 82
- average lifetime: 4.51 trading days
- median: 3 days
- p75: 6 days
- p90: 10 days
- <=3 days: 48 / 82 = 58.5%
- >10 days: 8 / 82 = 9.8%

Fisher exact checks:

- increase in short episodes (<=3d): p ≈ 0.019
- decrease in long episodes (>10d): p ≈ 0.008

So the user's premise that leadership windows shortened in 2025–2026 is directly visible in the frozen Rank1 sequence.

## 2. Resistance matters most when Top1 lifetime is short

### 2021–2024

Short lifetime <=3 days:

- high resistance: n=35, fwd5=-0.72%, fwd10=-0.87%, fwd20=+0.43%
- low resistance: n=25, fwd5=-0.25%, fwd10=+1.17%, fwd20=+1.07%

Medium lifetime 4–10 days:

- high resistance: n=24, fwd10=+0.88%
- low resistance: n=24, fwd10=+0.28%

Long lifetime >10 days:

- high resistance: n=13, fwd10=+5.65%, fwd20=+8.03%
- low resistance: n=21, fwd10=+4.06%, fwd20=+5.28%

Interpretation: high resistance is harmful in short-lived episodes, but long-lived trends can absorb / work through the resistance.

### 2025–2026

Short lifetime <=3 days:

- high resistance: n=32, fwd5=+0.01%, fwd10=+0.72%, fwd20=+4.02%
- low resistance: n=12, fwd5=+2.33%, fwd10=+2.47%, fwd20=+0.16%

Medium lifetime 4–10 days:

- high resistance: n=8, fwd10=+1.79%
- low resistance: n=15, fwd10=+2.06%

Long lifetime >10 days:

- high resistance: n=4, fwd10=+5.23%
- low resistance: n=4, fwd10=+7.75%

Again, the main penalty appears in short-lived episodes.

## 3. Resistance is associated with shorter Top1 survival

Using the fixed UpperShare 0.20 split:

### 2021–2024

High resistance:

- n=72
- average lifetime=5.76d
- median=4d
- survive >3d: 51.4%
- survive >5d: 33.3%
- survive >10d: 18.1%

Low resistance:

- n=70
- average lifetime=7.40d
- median=5d
- survive >3d: 64.3%
- survive >5d: 48.6%
- survive >10d: 30.0%

### 2025–2026

High resistance:

- n=44
- average lifetime=4.07d
- median=2d
- survive >3d: 27.3%
- survive >5d: 20.5%
- survive >10d: 9.1%

Low resistance:

- n=31
- average lifetime=5.39d
- median=4d
- survive >3d: 61.3%
- survive >5d: 45.2%
- survive >10d: 12.9%

The high-vs-low resistance separation in short-term survival is much larger in 2025–2026.

## 4. Quartile test: 2025–2026 is close to monotonic

Resistance quartiles, from lowest to highest:

### 2021–2024

- Q1: avg life 7.83d, median 5d, survive >5d 47.2%
- Q2: avg life 6.97d, median 5d, survive >5d 50.0%
- Q3: avg life 4.89d, median 3d, survive >5d 31.4%
- Q4: avg life 6.54d, median 4d, survive >5d 34.3%

Direction exists but is not monotonic.

### 2025–2026

- Q1: avg life 5.58d, median 6d, survive >5d 52.6%
- Q2: avg life 4.89d, median 2d, survive >5d 31.6%
- Q3: avg life 4.63d, median 2d, survive >5d 31.6%
- Q4: avg life 3.28d, median 2.5d, survive >5d 5.6%

This is a strong ordered relationship.

Extreme-quartile Fisher exact tests for 2025–2026:

- survive >3d, Q1 vs Q4: odds ratio ≈ 9.8, p ≈ 0.0029
- survive >5d, Q1 vs Q4: odds ratio ≈ 18.9, p ≈ 0.0030

These p-values are descriptive rather than confirmatory because the study was not preregistered.

## 5. Excluding oil and silver

2025–2026, excluding `501018` and `161226` as well as cash proxy:

- Q1: median life 6d, survive >5d 52.9%
- Q2: median life 2d, survive >5d 23.5%
- Q3: median life 2d, survive >5d 35.3%
- Q4: median life 2d, survive >5d 6.3%

Therefore the lifetime-resistance relationship is not created by the long commodity trends in oil or silver.

## Interpretation

The evidence is consistent with the mechanism:

`OLS finds a leader -> leader faces upper trading congestion -> price / score leadership needs time to work through it`

When leadership windows are long, as more often in 2021–2024, the resistance penalty can be absorbed and the eventual return remains good.

When leadership windows are short, as more often in 2025–2026, the same resistance consumes a large fraction of the remaining opportunity window. The result is weaker 5–10 day continuation and faster loss of Rank1 status.

This suggests the main role of Volume Profile is likely entry timing / continuation quality, not replacing OLS ranking.

## Important limitation

`life_days` is the lifetime of Rank1 leadership, not a pure price-defined bull-wave duration. It is endogenous to cross-sectional competition in the ETF pool. A second independent mechanism test should therefore use a price-defined trend lifetime before any trading rule is proposed.

## Decision

- Do not modify the formal strategy yet.
- Keep the resistance signal as a research candidate.
- Next test: construct a price-defined trend lifetime independent of Rank1, then test the same resistance interaction.
- Only if the relationship survives should we move to minute-level Volume Profile and then to prospective / walk-forward entry rules.
