# Stage8V — US second-layer admission diagnostic — 2026-09-17

## Starting point
Stage8U rejected the simple rule `US broad healthy -> buy highest-Score US sub-exposure`. This stage asks whether active US sub-exposure winners and losers differ in ex-ante trend-health features.

## Frozen definitions
- Defensive/Void first-entry dates: existing 2023–2026 State Map event set.
- OLS: 26 trading days, weighted log-price regression, half-life 10.
- Score: positive annualized slope × weighted R², otherwise 0.
- Historical availability: >=365 calendar days from first available bar.
- Region gate: 513500 Score > 511220 Score.
- US second-layer candidates: 513100, 159509, 513290, 159529; candidate must beat 511220.
- Outcome label for this diagnostic: selected sub-exposure 20d return minus 511220 20d return > 0.

## Diagnostic result
24 active events with complete 20-day forward data were reconstructed from daily_bars under the frozen OLS/availability rules: 14 winners and 10 losers.

Winner means:
- 20d excess vs 511220: +5.37%
- OLS Score: 1.3122
- R²: 0.653
- current log-price OLS residual: -0.0075
- ret3: -0.32%
- ret5: +0.87%

Loser means:
- 20d excess vs 511220: -3.04%
- OLS Score: 1.4739
- R²: 0.698
- current residual: -0.0036
- ret3: +0.77%
- ret5: +1.43%

## Interpretation
The useful separation is opposite to a naive `stronger is better` admission rule. Winners did **not** have higher Score or R². They entered after a softer very-short-term path: lower ret3/ret5 and a more negative current residual. Losers were, on average, more extended in the last 3–5 days while still displaying slightly higher OLS strength/fit.

This supports a specific mechanism: once the broad US region is healthy, second-layer OLS should not chase the strongest/most extended sub-exposure immediately. A `healthy medium-term trend + short-term pullback/not-overextended` admission concept is more plausible than an additional strength threshold.

The sample is small and this is an in-sample diagnostic, so no threshold is promoted. In particular, values such as ret3 <= 0 or residual < 0 must not be selected on the full sample and called a rule.

## Next strict test
Build a walk-forward gate using only past active events. Candidate feature family is deliberately small: ret3, ret5, current residual (optionally normalized by 20d volatility), with Score/R² retained only as the already-frozen trend qualification rather than optimized strength thresholds. Compare three actions when US broad gate opens:
1. 511220;
2. 513500 broad-US;
3. US sub-exposure only when the walk-forward pullback/not-overextended gate admits it, otherwise fall back to 513500 or 511220.

Require improvement in median/left-tail and not merely mean excess. Run leave-one-year-out and parameter-neighborhood checks before expanding to Japan/Europe second layers.

Status: substantive progress; automation continues. The new evidence narrows the second-layer mechanism to `trend + pullback`, but does not yet meet promotion or rejection stopping criteria.
