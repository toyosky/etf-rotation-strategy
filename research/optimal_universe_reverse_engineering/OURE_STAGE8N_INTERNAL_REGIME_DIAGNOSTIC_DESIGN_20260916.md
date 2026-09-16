# OURE Stage8N — Internal Trend-Regime Diagnostic

Date: 2026-09-16
Status: preregistered before outputs are computed

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
- strict real-listing / finite-score availability; no pre-listing proxies

## Point-in-time internal features
All features use only information available on the signal date and only currently OLS-ready members of the frozen universe.

1. `risk_churn20`
   - Number of raw OLS Top1 changes over the latest 20 signal sessions where both old and new states are non-cash risk assets.
   - A high value represents unstable rank competition.

2. `recent5_risk_episode_mean`
   - Mean duration of the five most recently COMPLETED raw OLS risk-asset Top1 episodes.
   - Current unfinished episode is excluded.
   - A low value represents recently short-lived trends.

3. `breadth`
   - Fraction of currently finite-score risk members whose score exceeds the cash comparator score.
   - Dynamic denominator uses only members actually available at that historical date.

4. `median_excess_score`
   - Cross-sectional median of `score_i - score_cash` across currently finite-score risk members.
   - Continuous companion to breadth.

For each feature, also compute a point-in-time percentile versus up to the strictly prior 252 observations, minimum 60 historical observations. No full-sample percentile is allowed.

## Frozen extreme-state definitions
These thresholds are defined before seeing outputs and are NOT trading thresholds:
- high churn warning: `risk_churn20_pct252 >= 80`
- short-life warning: `recent5_risk_episode_mean_pct252 <= 20`
- low-breadth warning: `breadth_pct252 <= 20`
- weak-score warning: `median_excess_score_pct252 <= 20`

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
