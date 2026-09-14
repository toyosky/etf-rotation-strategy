# OURE Stage2 — Identity-Free Universe Architecture Audit

Date: 2026-09-14
Parent: OURE Stage1 run `34805780500`
Status: preregistered

## Question

Stage1 found an exact best static Fix15 subset at K=7 including cash and showed large set interactions. Stage2 asks whether high-value subsets share identity-free OLS architecture properties that are not merely ETF-code effects.

No predictive model is fitted in this stage.

## Frozen labels

Use the exact Stage1 exhaustive subset table without changing its return semantics. Analyze separately:

- 2021-2024 log growth;
- 2025-2026 log growth;
- full 2021-2026 log growth only as a descriptive reference.

Because K itself is strongly related to return, the primary association statistic is within-K rank association. A feature is not credited merely because it proxies for subset size.

## Identity-free architecture features

For every static subset, compute from the frozen OLS score/eligibility path without ETF identity as a feature:

- opportunity coverage share: fraction of days at least one non-cash member is trend-eligible;
- mean eligible competitors per day;
- mean eligible competitors conditional on coverage;
- coverage efficiency = coverage / mean eligible count;
- fraction of days the selected OLS leader is non-cash;
- leader switch rate;
- mean and median non-cash Top1 tenure;
- share of Top1 runs lasting <=2 days;
- leader concentration HHI across included members;
- active-member share: fraction of included non-cash members ever selected;
- mean and maximum pairwise trend-eligibility Jaccard overlap;
- mean member trend-eligibility episode length.

All are set/path descriptors; ETF code is never entered as a covariate.

## Primary test

Within every K, rank subsets by each feature and by return. Pool the within-K ranks and compute the rank correlation for each feature separately in 2021-24 and 2025-26.

Also compare the within-K top return decile with the within-K bottom return decile and report standardized feature differences.

A structural characteristic may be promoted only if its direction is consistent across both eras. Magnitude may differ.

## Anti-overfit rule

Stage2 does not combine features into an optimized score, choose thresholds, select ETFs, or search the full market. Its only role is to identify a small set of architecture hypotheses.

Stage3 must be preregistered after Stage2. Any Symbol-disjoint replication rule must be frozen before observing its return result.
