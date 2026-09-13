# Stage 11 — Conditional second-order MUV findings

Date: 2026-09-13

## Question

Does the failure of Stage 10 come from a general breakdown of first-order marginal value after the first removal?

We compare:

- first-order: `MUV(j | U)`
- conditional second-order: `MUV(j | U - i)`
- interaction: `MUV(j | U - i) - MUV(j | U)`

No policy was fit and no threshold was searched in Stage 11.

## Panel

- 68 months, 2021-01 through 2026-08
- 9,248 conditional rows
- unit: `label_month × hypothetical first_removed × second_candidate`
- conditional path-active share: 29.13%
- conditional positive share: 12.25%
- conditional negative share: 16.86%

## Main result

First-order and conditional second-order MUV are usually very similar.

Across all matched rows:

- sign flip, conditional on both non-zero: 4.87%
- first-order zero -> conditional non-zero: 1.59%
- |change| > 1 percentage point: 4.87%
- |change| > 3 percentage points: 2.12%
- Pearson correlation among both non-zero rows: 0.974
- Spearman correlation among both non-zero rows: 0.931

Within the 16 months in which the frozen Stage-7 policy actually made a first removal:

- sign flip: 4.84%
- zero -> non-zero: 2.50%
- |change| > 1pp: 6.50%
- |change| > 3pp: 4.50%
- Pearson: 0.926
- Spearman: 0.924

Therefore the Stage-10 failure is **not** explained by a broad collapse of the first-order MUV ordering after one removal.

## Interaction is sparse but locally material

For a fixed `month × second_candidate`, changing the hypothetical first removal can still matter in a minority of states:

- 36.67% of groups have within-state range > 1pp
- 21.88% have range > 3pp
- maximum observed within-state range: 22.79pp

So higher-order interaction exists, but it is not pervasive enough to explain Stage 10 as a whole.

## Failure mechanism exposed by 2024-09

Stage 10 removed 159915 after the Stage-7 first removal and suffered a large loss.

The key point is that 159915 was already a large positive-retention-value asset in the original universe. Its sign did not flip after the first removal. The model had instead assigned it a very low participation probability and a negative expected MUV.

This changes the diagnosis:

> The dominant unresolved risk is not universal second-order interaction. It is rare but severe false-removal regret: a future large winner can receive low predicted participation/value risk and slip through the safety layer.

Stage 7's success should therefore be understood as the combination of:

1. asymmetric safety filtering, and
2. a hard risk budget of at most one removal per month.

The one-removal cap itself materially limits exposure to latent winner-risk.

## Decision

- Stage 7 remains the current best retention policy.
- Stage 10 is rejected and should not be rescued by threshold tuning.
- Do not proceed to third-order sequential removal yet.
- Stage 12 will directly model large positive-retention-value tail risk, bypassing the Stage-A participation bottleneck.

Any Stage-12 model must remain expanding walk-forward, use only point-in-time predictors, and avoid global threshold fitting.