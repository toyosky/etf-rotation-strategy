# OURE Stage8A — Opportunity-Coverage Universe Design

Date: 2026-09-15
Status: preregistered before run

## Decision question
Can a point-in-time K30 Universe built to maximize **opportunity coverage / complementarity**, rather than historical performance stability, recover more of the economic value that Fix15 exhibited without using Fix15 identities or future information?

A second fixed variant tests whether an amount/turnover participation feature should move upstream into Universe selection.

## Non-negotiable anti-lookahead rules
- Fix15 is benchmark only. Its identities are never used in selection, candidate restriction, weights, thresholds, or tie-breaking.
- Every deployment Universe uses only information available strictly before its decision date.
- K=30 and 126-session deployment horizon remain fixed.
- The comparison calendar, OLS engine, cash proxy, execution convention, and 6 bp/side cost are identical across variants.
- No parameter will be changed after observing Stage8A results.

## Historical representation
At each 126-session deployment decision, use the immediately preceding 3×126 = 378 sessions and split them into 18 non-overlapping 21-session windows.

For each eligible ETF and each 21-session historical window:
1. run the frozen single-asset OLS/cash strategy;
2. record its 21-session net log growth under the existing 6 bp/side accounting;
3. convert that return cross-sectionally into a percentile rank among the point-in-time common pool.

Thus every ETF is represented by an 18-dimensional vector describing **when** it historically supplied a useful OLS trend opportunity. Dormant assets are not penalized merely for being dormant; they can be selected if they fill windows that the current set does not cover.

## Opportunity30 selection rule
Build K30 greedily.

For a proposed set U, define each 21-session window's coverage as the average percentile rank of the best two members of U in that window. Define total coverage as the mean of those 18 window coverages.

Starting from an empty set, repeatedly add the ETF that maximizes total coverage until K=30. Ties are resolved by the candidate's mean 18-window rank, then symbol ordering.

The use of the best two rather than only the best one is frozen ex ante to reduce saturation and avoid a set whose historical coverage depends on a single accidental winner in each regime.

## Amount-aware upstream variant
The V1 resistance veto is not copied directly because Stage7G showed its joint threshold is too sparse on Robust30 and does not transfer cleanly.

Instead Stage8A tests a broader upstream participation-quality feature derived from `amount`:
- for each ETF/day, compute current amount divided by the strictly-prior rolling 60-session median amount;
- on days when the ETF is OLS trend-eligible, take the median of that ratio over the 378-session history;
- cross-sectionally rank this median participation ratio among the point-in-time pool;
- missing/sparse values receive neutral rank 0.5.

For the amount-aware variant, each ETF/window value is frozen as:
`0.5 * historical opportunity percentile + 0.5 * amount-participation percentile`.

The identical greedy best-two coverage procedure then selects `OPPORTUNITY30_AMOUNT`.

This is deliberately an upstream participation test, not a new V1 switch veto.

## Fixed variants
- `OLD_ROBUST30`: existing 3×126 robust-score K30, unchanged.
- `OPPORTUNITY30`: new opportunity-coverage rule.
- `OPPORTUNITY30_AMOUNT`: opportunity coverage + amount participation.
- `FIX15_BENCHMARK`: benchmark only; never used in selection.

## Evaluation
Point-in-time dynamic Universes are rebuilt every 126 sessions and held fixed until the next scheduled refresh. Within each Universe, the frozen OLS Top1/cash process runs unchanged.

Report 2021–2026 partial year-by-year:
- total return;
- maximum drawdown;
- turnover sides.

Also report full-period compounded return/MDD/turnover, current B10 members, and overlaps with Fix15 **only as post-selection diagnostics**.

## Interpretation
This is a historical mechanism test, not fresh prospective OOS. A better result would justify further validation, not immediate deployment. A worse result rejects this particular formalization of optionality/coverage; it does not prove that optionality itself is irrelevant.