# OURE Stage2 Findings — Identity-Free Universe Architecture Audit

Date: 2026-09-14
Workflow run: `34806085415`
Artifact: `oure-stage2-architecture-34806085415`
Status: completed

## Purpose

Stage2 removed ETF identity from the explanatory layer and tested whether high-return subsets among all 16,384 Fix15 subsets share common OLS architecture properties after controlling for K by within-K ranking.

Evidence was split before interpretation into 2021-24 and 2025-26. No combined feature score or threshold was fitted.

## Main result

Most intuitive architecture descriptors are regime-dependent. Only three tested descriptors preserved the same direction of within-K association with return in both eras:

1. lower maximum pairwise trend-eligibility Jaccard overlap;
2. lower mean number of simultaneously trend-eligible members;
3. slightly lower opportunity coverage share within a fixed K.

The third result should not be interpreted as `low coverage is good` in absolute terms. The exact best K7 subset still covers about 95-96% of days in both eras. The result says that once coverage is already high, admitting additional overlapping opportunities can be more harmful than the marginal coverage they add.

## Strongest robust structural signal

`max_pair_trend_jaccard` is the clearest identity-free descriptor with consistent direction:

- 2021-24 within-K rank correlation with return: -0.2752
- 2025-26: -0.1312

Top-vs-bottom within-K return decile standardized difference:

- 2021-24: -0.9466 SD
- 2025-26: -0.2136 SD

This supports a minimax-redundancy interpretation: a single highly overlapping pair can degrade the Universe even when average pair overlap is not especially high.

## Competition count

`mean_eligible_count` is also negative in both eras but weak:

- 2021-24: -0.0419
- 2025-26: -0.0458

This is directionally consistent with the Stage1 coverage-versus-competition frontier, but by itself is not a strong selector.

## Coverage result

`coverage_share` within fixed K is negative in both eras:

- 2021-24: -0.1096
- 2025-26: -0.2687

However, the exact best K7 subset has high absolute coverage:

- 2021-24: 95.35%
- 2025-26: 96.35%

Fix15 coverage is only modestly higher:

- 2021-24: 98.97%
- 2025-26: 99.03%

The economic interpretation is therefore saturation: pushing coverage from roughly 95% toward 99% by admitting redundant competitors can lower portfolio value.

## Important rejected simplifications

Several initially attractive explanations fail the cross-era gate.

### Longer Top1 tenure

Mean Top1 tenure association:

- 2021-24: +0.5475
- 2025-26: -0.0301

Median tenure:

- 2021-24: +0.4636
- 2025-26: -0.1368

Long tenure is a major description of the 2021-24 winners, but it is not a stable cross-era selection principle.

### Fewer leader switches

Leader switch-rate association:

- 2021-24: -0.5301
- 2025-26: +0.0445

Again, lower churn explains much of the older-era result but does not survive as a universal rule.

### Longer member trend episodes

Mean member trend-episode length:

- 2021-24: +0.1907
- 2025-26: -0.2606

This reverses materially and must not be promoted.

### Average pair overlap

Mean pairwise trend Jaccard:

- 2021-24: -0.1063
- 2025-26: +0.0466

The average is not robust. The maximum pair overlap is more informative, suggesting that avoiding one severe redundancy may matter more than globally minimizing every correlation/overlap.

## Exact best subset architecture versus Fix15

Best K7 subset, 2021-24:

- coverage 95.35%
- mean simultaneous eligible members 2.65
- max pair trend Jaccard 0.415
- mean Top1 tenure 9.14 days

Fix15, 2021-24:

- coverage 98.97%
- mean simultaneous eligible members 5.93
- max pair trend Jaccard 0.574
- mean Top1 tenure 5.84 days

Best K7 subset, 2025-26:

- coverage 96.35%
- mean simultaneous eligible members 3.14
- max pair trend Jaccard 0.579
- mean Top1 tenure 6.71 days

Fix15, 2025-26:

- coverage 99.03%
- mean simultaneous eligible members 7.13
- max pair trend Jaccard 0.905
- mean Top1 tenure 4.32 days

The most stable description is therefore not simply `long tenure`; it is `high but not maximal opportunity coverage without admitting a highly redundant competitor pair`.

## Research decision

Do not yet fit a selector from these three descriptors. Stage2 demonstrates a plausible architecture mechanism but associations are not strong enough to claim that a simple feature rule can reconstruct the optimum.

The next experiment should first answer an existence question with a Symbol-disjoint hindsight control:

Can a static Universe built entirely from non-Fix15 ETFs beat the exact Fix15-internal optimum under the same frozen OLS engine?

If no, there is little point trying to reproduce the architecture outside Fix15 on this sample. If yes, compare the disjoint oracle's architecture with the Fix15 optimum before designing an executable rule.

This next search remains explicitly hindsight/diagnostic; it is not a walk-forward strategy.
