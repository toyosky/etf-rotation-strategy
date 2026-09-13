# Stage23 Coverage-to-Score Bridge Audit — Frozen Design (2026-09-13)

## Parent result
Stage22 established a stable opportunity-coverage gap: point-in-time trend-eligible full-market and Cluster90 universes contain substantially stronger ex-post 20-day continuations than Fixed15. But naive full-market / Cluster90 OLS score Top1 selection underperforms Fixed15, especially in 2025–26.

## Frozen question
When the full-market ex-post best 20-day continuation is outside Fixed15, was that missed outsider already near the top of the point-in-time OLS score ordering at month-end?

This is a mechanism audit. It does not estimate admission value, fit a predictive model, search thresholds, or backtest a policy.

## Data and timing
- Same full-market daily bars and frozen feature construction as Stage22.
- Decision dates: trading month-end.
- Point-in-time eligibility: existing frozen `trend_eligible` rule.
- Outcome: forward 20-trading-day close return, label-side only.
- Exclude cash signal ETF `511220`.
- Audit events: month-ends where the full-market oracle-best eligible ETF is outside Fixed15.

## Frozen diagnostics
For each audit event, record the missed oracle-best outsider's month-end:
- OLS score rank among all eligible ETFs.
- OLS score rank among eligible outsiders only.
- rank percentile among all eligible ETFs = rank / eligible candidate count.
- membership in score Top1, Top3, Top5, and Top10.
- whether Fixed15 had zero eligible candidates that month.

Report overall, 2021–24, and 2025–26:
- event count.
- median / mean all-market score rank.
- median all-market rank percentile.
- Top1 / Top3 / Top5 / Top10 capture shares.
- fixed-empty share.

## Predeclared interpretation
Treat the existing OLS score as providing a plausible conservative admission bridge only if BOTH conditions hold overall and separately in 2021–24 and 2025–26:
1. score Top10 captures at least 50% of missed oracle-best outsider events; and
2. median all-market score-rank percentile is no worse than 15%.

These cutoffs are frozen before observing Stage23 results. They are not a trading rule and will not be tuned on this history.

### If supported
Proceed only to a conservative admission-shortlist audit. Do not yet backtest a dynamic-universe policy. The next question becomes whether allowing a very small, point-in-time shortlist of outsiders can improve opportunity coverage without reproducing Stage22's competition dilution.

### If unsupported
Do not tune score cutoffs, horizons, ETF subsets, or asset classes. Conclude that current OLS score state is insufficient to bridge coverage into admission. Branch to either:
- a new low-DoF admission-state representation audit; or
- a fixed-feature nonlinear-capacity benchmark strictly to distinguish state-information failure from function-capacity failure.

## Anti-overfit constraints
- no model fit;
- no threshold search;
- no policy backtest;
- no ETF or asset-class exclusions based on outcomes;
- no horizon change;
- no post-result modification of Top10 / 15% support rule.