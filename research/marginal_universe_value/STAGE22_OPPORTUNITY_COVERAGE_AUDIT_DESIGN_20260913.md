# Stage22 Opportunity Coverage Audit — Frozen Design (2026-09-13)

## Question
Does Fixed15 materially fail to cover point-in-time qualified ETF trends that subsequently deliver stronger 20-trading-day continuation, and is that coverage gap present in both 2021-24 and 2025-26?

This is a mechanism/coverage audit, not a trading strategy, not an admission model, and not a policy backtest.

## Why this branch
Stage21 found economically meaningful competition nuisance but weak cross-era persistence in nuisance identity. Therefore we do not tune nuisance thresholds or build a deletion classifier. We step down to a weaker question: whether the current fixed Universe misses opportunity-set coverage in the first place.

## Point-in-time candidate sets
At each trading month-end from 2021-01 onward, using only information available at that close:

1. `fixed15`: Fixed15 risk ETFs that satisfy the existing frozen `trend_eligible` rule. Cash `511220` is excluded from opportunity comparisons.
2. `full_market`: all ETFs in `daily_bars` satisfying the same frozen `trend_eligible` rule.
3. `cluster90`: point-in-time monthly Cluster90 representatives satisfying the same frozen `trend_eligible` rule.

The full-market and Cluster90 views are both reported. The conclusion must not depend solely on Cluster90 because earlier work showed Cluster90 representation itself can be problematic.

## Outcome horizon
Forward 20-trading-day close return from the month-end close. This is label-side only and is never used as a predictor.

## Frozen metrics per month
For each candidate set:
- candidate count;
- OLS-score Top1 forward-20d return (what the current ranking would select from that set);
- oracle best forward-20d return among candidates (coverage ceiling only, explicitly non-tradable);
- oracle top-3 mean forward-20d return among candidates (reduces sensitivity to a single extreme winner; also non-tradable).

Coverage gaps:
- `full_oracle_best - fixed_oracle_best`;
- `cluster90_oracle_best - fixed_oracle_best`;
- corresponding oracle top-3-mean gaps;
- OLS-score Top1 return gap for context, separated from coverage ceiling.

Also report the share of months in which the oracle-best full-market candidate is outside Fixed15.

## Era split
- 2021-24
- 2025-26

Report overall and both eras separately.

## Interpretation rule
Treat an opportunity-coverage gap as structurally supported only if:
1. the full-market oracle-best and oracle-top3-mean gaps are positive overall;
2. both are non-negative in each era;
3. the qualitative conclusion is not reversed by the Cluster90 comparator.

If the gap exists only in one era, or depends on Cluster90, do not tune eligibility thresholds or asset subsets. Record regime dependence and move to a conservative admission/coverage design rather than claiming a universal dynamic-Universe advantage.

If no stable gap exists, do not pursue admission merely to enlarge the Universe; instead revisit retention/competition structure or accept a mostly fixed Universe.

## Anti-overfit constraints
- no new predictive model;
- no feature search;
- no threshold search;
- no asset-class cherry-picking;
- no selecting favorable ETFs after seeing outcomes;
- no policy backtest;
- no changing the existing OLS score or trend eligibility rule;
- no conclusion based only on oracle-best; oracle top-3 mean and era consistency are required.
