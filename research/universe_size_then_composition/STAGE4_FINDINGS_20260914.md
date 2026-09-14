# New Stage 4 — Fixed-K15 Composition Structure Audit Findings

Date: 2026-09-14
Source run: `34791802474`
Artifact: `universe-size-stage4-34791802474`
Status: frozen
Decision: composition_identifiability_bottleneck

## Executive conclusion

At fixed K=15, composition has large hindsight downstream value headroom, but randomized single-symbol inclusion contrasts are only weakly reproducible within the same month and have essentially zero adjacent-month persistence.

Therefore the bottleneck is not lack of composition value. It is identifiability of member value from stable symbol-level effects. Stage5 must remain conservative/simple same-K; this evidence does not justify a higher-capacity learned member selector.

## Frozen evidence

Across 68 months and 12,240 already-generated K15 random universes:

### 2021–2024
- mean P90 minus random-K15 mean: +6.69 percentage points
- mean sampled-best minus random-K15 mean: +13.80 pp
- mean P90 minus P10 spread: 12.99 pp
- split-half inclusion-contrast Spearman: mean 0.137, median 0.129, valid 48/48 months
- adjacent-month inclusion-contrast Spearman: mean -0.009, median 0.001, valid 47 pairs

### 2025–2026
- mean P90 minus random-K15 mean: +10.42 pp
- mean sampled-best minus random-K15 mean: +26.10 pp
- mean P90 minus P10 spread: 19.39 pp
- split-half inclusion-contrast Spearman: mean 0.069, median 0.050, valid 20/20 months
- adjacent-month inclusion-contrast Spearman: mean 0.009, median 0.016, valid 20 pairs

### Overall stability diagnostics
- split-half median Spearman: 0.114
- 92.6% of months have positive split-half Spearman, but only 11.8% exceed 0.20
- adjacent-month median Spearman: 0.0008
- adjacent-month positive share: 52.2%, effectively coin-flip
- no adjacent pair exceeds Spearman 0.20

The headroom metrics are positive in every month, so composition clearly matters. But the weak split-half rank stability means a symbol's estimated inclusion contrast is noisy even within the same month. The near-zero adjacent-month correlations are much stronger evidence against stable symbol-identity persistence.

## Interpretation

1. Fixed-K composition is economically important in hindsight.
2. The value is not well represented by a stable independent ETF-quality label.
3. Single-symbol randomized inclusion contrasts likely mix true member contribution with substantial set interaction/context dependence and Monte Carlo noise.
4. Adjacent-month symbol identity is not persistent enough to justify identity-based learning.
5. Stage4 does not prove that relational/role state is predictable; it only says future composition headroom exists while simple symbol-level labels are poorly identifiable.

## Branch decision

Proceed only to a conservative Stage5 same-K executable audit. Do not train a high-capacity member model.

Stage5 may test a small number of pre-registered, point-in-time/simple historical rules against the existing K15 random baseline, while retaining Fix15 and full-market as external benchmarks. If these simple rules cannot capture stable OOS improvement, freeze composition optimization as an identifiability bottleneck rather than escalating model capacity.

No support threshold, K, random seed, parent-pool rule, or Stage4 label definition may be reopened.