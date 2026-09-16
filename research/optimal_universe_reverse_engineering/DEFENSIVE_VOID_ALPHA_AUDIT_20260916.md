# Defensive/Void Alternative Alpha Audit — 2026-09-16

## Question
When the frozen Market Regime Map enters `DEFENSIVE_VOID`, should the system replace OLS with another opportunity-finding method, or simply hold 511220?

## Sample
- Regime definition kept frozen from the live map: Breadth vs 511220 < 50% and Leadership Gap percentile < 50%.
- Use only the first day of each new Defensive/Void episode to reduce serial dependence.
- 160 entry events from 2015-02-05 through 2026-09-14.
- Market data: Supabase `daily_bars`, current coverage through 2026-09-15.
- ETF eligibility for cross-sectional scanners: at least 200 observations, 60-day average turnover >= CNY 20m, >=57/60 non-zero-turnover days.
- 511220 is the hurdle / do-nothing defensive benchmark, not a candidate strategy.

## Frozen first-batch alternatives
1. **Short-term reversal**: bottom 10% of eligible ETFs by trailing 5-day return, equal weighted.
2. **Strong-trend pullback**: all eligible ETFs with positive 60-day and 120-day return but negative 5-day return, equal weighted.
3. **Defensive relative strength**: choose the defensive candidate with the highest trailing 20-day return. Defensive candidates include bonds, physical-gold ETFs, dividend, utilities and bank exposure. 511220 itself is excluded.

## Excess return versus 511220

### 2015–2022 (120 Defensive/Void entry events)

| Method | Excess 5d | Excess 10d | Excess 20d | 5d win rate |
|---|---:|---:|---:|---:|
| Short-term reversal | +0.55% | +0.47% | +0.74% | 30.8% |
| Strong-trend pullback | +0.27% | +0.08% | -0.08% | 26.7% |
| Defensive relative strength | -0.38% | -0.30% | +0.29% | 18.3% |

The positive mean from short-term reversal is not supported by event win rate; it is dominated by a minority of large rebounds and therefore is not a robust replacement for 511220.

### 2023–2026 (40 Defensive/Void entry events)

| Method | Excess 5d | Excess 10d | Excess 20d | 5d win rate |
|---|---:|---:|---:|---:|
| Short-term reversal | -0.28% | -0.64% | -0.57% | 42.5% |
| Strong-trend pullback | -0.03% | -0.09% | -0.31% | 50.0% |
| Defensive relative strength | -0.20% | +0.71% | +0.22% | 37.5% |

Short-term reversal and strong-trend pullback both fail the recent-period hurdle. Defensive relative strength is the only first-batch candidate with positive recent 10/20-day mean excess, so it received a year-level robustness audit.

## Defensive relative-strength year audit

| Year | N | Mean 10d excess | Median 10d excess | 10d win rate | Mean 20d excess | Median 20d excess | 20d win rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 12 | +0.81% | +1.04% | 58.3% | +0.06% | -0.44% | 33.3% |
| 2024 | 13 | -0.20% | +0.90% | 53.8% | +1.05% | +1.08% | 53.8% |
| 2025 | 8 | +2.21% | +1.57% | 50.0% | +0.30% | +0.12% | 50.0% |
| 2026 | 5 | +0.46% | 0.00% | 40.0% | -1.69% | 0.00% | 0.0% |

The signal is not stable enough to promote. Ten-day excess is interesting in 2023 and 2025, but it is weak/negative in 2024 depending on mean vs median and deteriorates in 2026. Twenty-day behavior is inconsistent and fails completely in the available 2026 events.

## Current conclusion
The first batch does **not** identify an alternative alpha that robustly beats 511220 in Defensive/Void regimes.

This supports the current architecture:

`Non-Defensive/Void -> OLS`

`Defensive/Void -> alternative scanner only if a separately validated alpha exists`

`No validated alpha -> 511220`

The purpose of the next stage should therefore be to search for economically different mechanisms, not to weaken or retune OLS to force a position. Candidate next mechanisms: volatility-shock repair, compression/breakout preparation, cross-asset relative value, and QDII cross-time-zone information.

## Caveats
- This is an event study, not yet a full executable portfolio backtest with entry/exit overlap and transaction costs.
- Defensive labels currently use metadata classifications available in the database; historical classification/survivorship should be audited before promotion.
- Parameter sets were intentionally sparse and frozen before seeing these results; no parameter search was used to select winners.
