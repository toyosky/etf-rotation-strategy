# OURE Stage8N — Internal Trend-Regime Diagnostic

Date: 2026-09-16
Status: preregistered diagnostic; breadth/strength definition corrected before authoritative rerun

## Purpose
Test whether the frozen FixV2 OLS system contains point-in-time internal state information that predicts when its own future V1 strategy returns deteriorate. This stage is diagnostic only: it does NOT create, tune, or promote a regime trading rule.

## Frozen strategy context
Use the Stage8M main universe and frozen V1-75 implementation unchanged:
- remove 159825
- retain 159981
- 513920 -> 513530
- 518880 -> 159934
- 159915 -> 159957
- all other Fix15 members unchanged
- cash comparator 511220
- V1: ResistancePct252 >= 75% AND raw ScoreDelta_new <= 0, pure rank switches only
- primary execution cost 6 bp per side
- strict real-listing / finite-OLS availability; no pre-listing proxies

## Definition correction before authoritative run
The first implementation attempted to define breadth/strength relative to the `511220` pool score. Inspection showed that `build_wides()` intentionally masks an asset's pool score to NaN whenever its trend is not positive or D2 fails. Therefore a NaN `511220` score is a strategy-state condition, not missing market data, and cannot serve as a continuously defined cross-sectional denominator.

That first four-feature output is invalid and must not be used for inference. No outcome-driven threshold tuning is made. Churn, recent-life, 20/80 percentile rules, horizons and labels remain unchanged.

The corrected breadth/strength definitions below use the frozen risk universe itself and are fully point-in-time.

## Point-in-time internal features
All features use only information available on the signal date and only members with an actual historical OLS estimate by that date.

1. `risk_churn20`
   - Number of raw OLS Top1 changes over the latest 20 signal sessions where both old and new states are non-cash risk assets.
   - A high value represents unstable rank competition.

2. `recent5_risk_episode_mean`
   - Mean duration of the five most recently COMPLETED raw OLS risk-asset Top1 episodes.
   - Current unfinished episode is excluded.
   - A low value represents recently short-lived trends.

3. `breadth`
   - Numerator: number of historically OLS-ready frozen risk members whose current pool score is finite, i.e. positive OLS trend and D2 pass under the same engine used by the strategy.
   - Denominator: number of frozen risk members with a finite unmasked 26-day OLS score on that date.
   - This directly measures the share of the strategy's own available opportunity set that currently has a tradable positive trend.

4. `median_signed_strength`
   - Cross-sectional median of `annual_i * r2_i` across historically OLS-ready frozen risk members.
   - Unlike the pool score, this preserves the sign of the OLS trend and remains defined when trends are negative.
   - Continuous companion to breadth.

For each feature, compute a point-in-time percentile versus up to the strictly prior 252 observations, minimum 60 historical observations. No full-sample percentile is allowed.

## Frozen extreme-state definitions
These thresholds were defined before the authoritative outputs and are NOT trading thresholds:
- high churn warning: `risk_churn20_pct252 >= 80`
- short-life warning: `recent5_risk_episode_mean_pct252 <= 20`
- low-breadth warning: `breadth_pct252 <= 20`
- weak-strength warning: `median_signed_strength_pct252 <= 20`

`bad_count` = number of these four warnings active when all four point-in-time percentiles are available.

## Labels
The thing being predicted is the frozen `FixV2 + V1-75` strategy itself, not ETF returns.

From each signal date compute forward strategy outcomes over 5, 10, and 20 execution sessions:
- compound net return at 6 bp/side
- forward maximum drawdown within the horizon

## Diagnostic outputs
1. Feature percentile quintiles vs future 5/10/20d strategy return and future drawdown.
2. Frozen extreme-state warning vs non-warning future outcomes.
3. `bad_count` 0/1/2/3/4 vs future outcomes.
4. Spearman association by full sample, pre-2021, and 2021+.
5. A non-overlapping 20-session robustness sample.
6. Explicit 2022 and 2026 drawdown diagnostics, including the 20 sessions before each drawdown, to distinguish contemporaneous detection from advance warning.
7. Comparison context for 2020, 2021 and 2025 strong-trend years to identify false-warning risk.

## Interpretation discipline
- No threshold search.
- No weighted composite optimization.
- No regime switch backtest in Stage8N.
- A useful signal should show economically coherent ordering across multiple horizons/subperiods and should not merely flag 2022/2026 after the fact.
- Overlapping forward-return observations are descriptive and not independent. Non-overlapping results are reported as a robustness check.
