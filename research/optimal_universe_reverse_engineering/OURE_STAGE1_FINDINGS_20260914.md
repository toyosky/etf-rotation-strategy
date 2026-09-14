# OURE Stage1 Findings — Fix15 Exhaustive Static-Subset Reverse Engineering

Date: 2026-09-14
Workflow run: `34805780500`
Artifact: `oure-stage1-fix15-34805780500`
Status: completed

## Executive result

Every one of the 2^14 = 16,384 non-cash subsets of Fix15 was evaluated exactly while always retaining cash signal 511220 under the frozen daily OLS engine.

The best hindsight static subset is:

- 511220 cash
- 159915
- 159985
- 161226
- 501018
- 513100
- 513920

Thus the best K is 7 including cash, or 6 risk assets.

Full-sample terminal return diagnostics:

- Fix15: +891.12%
- Fix15 minus 159825: +1,078.43%
- global best Fix15 subset: +2,511.97%

The global-best terminal wealth is 2.635x the Fix15 terminal wealth under exactly the same downstream OLS engine.

This is hindsight/explanatory evidence, not an executable strategy result.

## Size geometry

Best terminal return by K including cash:

- K=2: +205.06%
- K=3: +563.73%
- K=4: +1,155.29%
- K=5: +1,812.44%
- K=6: +2,371.14%
- K=7: +2,511.97%  <- global optimum
- K=8: +2,499.47%
- K=9: +2,319.02%
- K=10: +1,987.70%
- K=11: +1,804.50%
- K=12: +1,639.88%
- K=13: +1,375.30%
- K=14: +1,105.85%
- K=15: +891.12%

The result is not merely `smaller is always better`. The best frontier improves rapidly from K=2 through K=7, is nearly flat at K=8, then deteriorates as further competitors are admitted. This is direct evidence for a coverage-versus-competition optimum inside Fix15.

## Path structure

Fix15:

- switches: 261
- turnover sides: 505
- mean Top1 tenure: 5.30 days
- median Top1 tenure: 3 days
- Top1 runs <=2 days: 37.15%
- max drawdown: -44.72%

Best K7 subset:

- switches: 175
- turnover sides: 309
- mean Top1 tenure: 8.29 days
- median Top1 tenure: 6 days
- Top1 runs <=2 days: 27.74%
- max drawdown: -34.35%

The best subset therefore retains enough opportunity coverage while substantially reducing leader churn and short-lived OLS competition.

## Agriculture 159825

Removing only 159825 from Fix15 changes terminal return from +891.12% to +1,078.43%, increases terminal wealth by about 18.90%, and improves log growth by +0.1731.

More importantly, this is not only a local leave-one-out result:

- singleton return: -12.52%
- context-averaged Banzhaf marginal log value: -0.30835, worst of all 14 non-cash members
- positive marginal contribution share across all contexts: only 0.28%
- top-1%-subset inclusion rate: only 0.61%
- excluded from the exact global-best subset

This is strong evidence that 159825 is structurally incompatible with this frozen OLS Universe over the studied sample, not merely unlucky in one particular context.

## Member-level marginal structure

Highest context-averaged marginal log values:

1. 161226: +0.89685; positive in 100% of contexts; top-1% inclusion 100%
2. 501018: +0.71999; positive in 100% of contexts; top-1% inclusion 100%
3. 513100: +0.26454; positive in 93.0% of contexts; top-1% inclusion 81.1%
4. 159509: +0.22563; positive in 84.9% of contexts; top-1% inclusion 71.3%
5. 159985: +0.14320; positive in 77.4% of contexts; top-1% inclusion 75.6%
6. 159915: +0.14198; positive in 69.6% of contexts; top-1% inclusion 67.7%
7. 513920: +0.06722; positive in 69.0% of contexts; top-1% inclusion 53.7%

Worst context-averaged members:

- 159825: -0.30835
- 164824: -0.08539
- 159529: -0.02752
- 511380: -0.00121

A crucial warning is that local Fix15 leave-one-out and context-averaged marginal value are not identical. For example 159985 has positive context-averaged value but its removal from the already-crowded Fix15 improves value. This directly supports a conditional/set-value interpretation rather than an independent ETF-quality score.

## Interaction evidence

Pair effects are large and heterogeneous. Examples of positive mean second-difference interaction in log value:

- 159915 + 161226: +0.15145
- 159915 + 501018: +0.11513
- 159981 + 161226: +0.11218

Examples of strongly negative interaction:

- 159509 + 159915: -0.30932
- 161226 + 518880: -0.25139
- 159981 + 501018: -0.24726
- 164824 + 513100: -0.19060

Therefore an ETF can be individually useful yet harmful beside a particular competitor. The optimal-Universe problem cannot be reduced to ranking symbols by standalone return or standalone OLS quality.

## Structural hypothesis promoted to Stage2

The first identity-free hypothesis is:

A high-value OLS Universe is a small set with enough trend-opportunity coverage, but low redundant OLS competition. It should exhibit:

- high fraction of days with at least one usable trend;
- low average simultaneous trend competition conditional on coverage;
- longer OLS leader tenure;
- fewer <=2-day leader bursts;
- lower leader churn/turnover;
- lower redundant trend-opportunity overlap;
- enough cross-member complementarity that adding a member expands coverage more often than it merely displaces an already-good leader.

Stage2 must test these statements across all 16,384 subsets using only identity-free OLS/path architecture descriptors. It must not use ETF code as a feature and must report the relationship separately for 2021-24 and 2025-26.

Only characteristics with directionally consistent evidence across eras may be frozen for the later Symbol-disjoint replication search.
