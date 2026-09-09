# Daily Volume Profile / Path of Least Resistance — 2026-09-09

## Research question

Does historical trading density above the current ETF price contain incremental information about the future continuation of an OLS Top1 trend, especially on leader-switch days?

This is an exploratory mechanism test only. It does not modify `strategy/main.py`.

## Data

- Strategy signal source: `FROZEN_C2@20260903T_fixed_window_v2`
- Top1 sample: 2021-01-04 through 2026-08-05
- Daily bars: Supabase `daily_bars`
- Cash proxy `511220` excluded from the resistance test
- Robustness test also excludes oil `501018` and silver `161226`
- Only information strictly before the signal date is used to construct the historical profile; future returns are measured from the signal-date close.

## Data caveat and weighting choice

`amount / volume` matches price well for most ETFs, but some ETFs show unit/split inconsistencies in raw volume (notably `513100`, and `511220` has a larger unit discontinuity). Therefore the first-pass profile uses:

- price location: daily OHLC price range
- weight: daily turnover `amount`, not raw share `volume`

This avoids raw share-unit changes driving the profile weight.

## Frozen V1 proxy

For each Top1 event with current close `P`:

1. Look back 120 trading sessions, excluding the current signal day.
2. Treat each day's turnover amount as uniformly distributed across that day's `[low, high]` range.
3. Estimate historical turnover amount in:
   - upper band: `[P, 1.05P]`
   - local band: `[0.95P, 1.05P]`
4. Define:

`UpperShare = upper-band historical turnover / local-band historical turnover`

Interpretation:

- low `UpperShare` = relatively empty path immediately above price
- high `UpperShare` = relatively heavy historical acceptance / congestion immediately above price

This is only a daily approximation to a true minute/tick Volume Profile.

## Main results

### All Top1 days — 2021–2024

Quartiles from lowest to highest upper resistance:

- Q1: 10d +1.72%, 20d +2.06%
- Q2: 10d +1.55%, 20d +2.38%
- Q3: 10d +1.14%, 20d +1.09%
- Q4: 10d +1.63%, 20d +2.46%

No monotonic resistance effect.

### All Top1 days — 2025–2026

- Q1: 10d +2.59%, 20d +4.04%
- Q2: 10d +2.95%, 20d +5.02%
- Q3: 10d +3.84%, 20d +6.54%
- Q4: 10d +0.38%, 20d +2.06%

The highest-resistance quartile is materially weaker, but the relationship is not monotonic from Q1 to Q4.

### Leader-switch days — 2021–2024

- Q1: 10d +1.86%
- Q2: 10d +1.75%
- Q3: 10d +0.24%
- Q4: 10d +1.61%

No stable monotonic effect.

### Leader-switch days — 2025–2026

- Q1: 5d +1.25%, 10d +1.38%, 20d +2.22%
- Q2: 5d +3.94%, 10d +5.13%, 20d +4.52%
- Q3: 5d +1.81%, 10d +3.19%, 20d +7.64%
- Q4: 5d -0.25%, 10d -0.85%, 20d +0.89%

This is the strongest first-pass finding: on 2025–2026 leader-switch days, the highest historical congestion group has negative average 5d/10d continuation, while lower-resistance groups remain positive.

## Control for simple new-high effect

`UpperShare` is mechanically related to how close price is to its prior high. To test whether the signal is merely a disguised breakout/new-high variable, partial correlations were computed controlling for current price / prior-120d high.

Leader-switch days:

- 2021–2024: 10d partial corr = -0.026
- 2025–2026: 10d partial corr = -0.153

Thus the 2025–2026 result is not fully explained by proximity to the prior 120d high, although the effect remains modest.

## Band-width robustness on leader-switch days

120-day lookback, controlling for prior-120d-high position:

### 2021–2024

- upper ±3% local band: 10d partial corr +0.002
- ±5%: -0.026
- ±10%: -0.093

Inconsistent / weak.

### 2025–2026

- ±3%: -0.126
- ±5%: -0.153
- ±10%: -0.176

Direction is stable across band widths.

## Lookback robustness on leader-switch days

5% upper band, controlling for prior-high position:

### 2021–2024

- 60d lookback: +0.081
- 120d: -0.026
- 240d: -0.107

Not stable.

### 2025–2026

- 60d: -0.202
- 120d: -0.153
- 240d: -0.122

Direction is stable.

## Split-year check

Using the frozen 120d / 5% proxy on switch days:

### 2025

- n = 44
- raw corr with future 10d return: -0.328
- partial corr controlling high position: -0.265
- lower-resistance half: 10d +2.05%
- higher-resistance half: 10d -0.27%

### 2026 through 2026-08-05

- n = 37
- raw corr: -0.118
- partial corr: -0.126
- lower-resistance half: 10d +4.19%
- higher-resistance half: 10d +1.28%

Direction is the same in both years, weaker in 2026.

## Ex-oil / ex-silver robustness, 2025–2026 switch days

Exclude `501018` and `161226`:

- n = 73
- raw 10d corr: -0.186
- partial corr controlling high position: -0.093
- lower-resistance half: 5d +1.22%, 10d +1.73%, 20d +2.16%
- higher-resistance half: 5d +0.21%, 10d -0.18%, 20d +1.66%

The main direction survives, so the result is not solely created by oil/silver trends.

## Interpretation

Current evidence does **not** support a universal rule that lower historical resistance always produces higher future returns. The effect is weak/inconsistent in 2021–2024.

However, in 2025–2026—especially on Top1 leader-switch days—very high historical trading density immediately above the new leader is associated with materially weaker 5–10 day continuation. The effect largely fades by 20 days.

This makes the signal more plausible as a **short-horizon entry-timing / congestion diagnostic** than as a permanent ranking factor or trend score component.

## Current decision

- Do not add this to the production strategy.
- Do not optimize a hard `UpperShare` threshold yet.
- Keep it as a research candidate.
- Next recommended step: reconstruct a true minute-level Volume Profile for switch events only and test whether the 2025–2026 short-horizon effect becomes stronger and whether it exists out-of-sample relative to the daily proxy.
