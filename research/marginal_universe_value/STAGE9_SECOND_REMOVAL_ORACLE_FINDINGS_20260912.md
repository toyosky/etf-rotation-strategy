# MUV Stage 9 — Second-Removal Oracle Headroom Findings

Date: 2026-09-12
Status: completed; substantial second-step headroom exists

## Question

After the frozen Stage-7 primary policy removes one ETF, is there enough additional counterfactual value in removing one more ETF to justify engineering a true sequential retention model?

The first removal is never changed. The second removal is future-aware Oracle and is diagnostic only.

## Sanity

- Stage-7 primary action months reproduced: 16
- maximum absolute difference between recomputed first-removal monthly return and Stage-7 stored return: ~6.94e-17

The Stage-9 engine is therefore numerically aligned with the existing retention counterfactual engine.

## Second-step Oracle headroom

Among the 16 months where Stage 7 made a first removal:

- months with a positive second-removal Oracle: **14 / 16 = 87.5%**
- sum of additional monthly return headroom: **+83.74 percentage points**
- mean additional return over all Stage-7 action months: **+5.23pp**
- mean conditional on positive second-step opportunity: **+5.98pp**
- median conditional positive opportunity: **+5.24pp**
- largest single additional opportunity: **+20.99pp**

Largest second-step opportunity:

```text
2024-09
Stage-7 first removal: 518880
Oracle second removal: 159529
Stage-7 month return: +20.94%
Two-removal Oracle return: +41.93%
Incremental second-step value: +20.99pp
```

## Wealth headroom

- keep-all final wealth: 6.8039
- Stage-7 primary final wealth: 8.8879
- Stage-7 relative advantage vs keep-all: +30.63%
- Stage-7 + Oracle second-removal final wealth: **19.6705**
- incremental terminal wealth vs Stage 7: **+121.32%**
- relative terminal wealth vs keep-all: **+189.10%**

This is an Oracle upper bound, not a tradable result.

## Period split

2023–24:

- Stage-7 action months: 9
- positive second-step Oracle months: 7
- Stage-7 final wealth: 1.6623
- Stage-7 + second Oracle: 2.6377
- incremental terminal wealth: **+58.67%**

2025–26:

- Stage-7 action months: 7
- positive second-step Oracle months: 7
- Stage-7 final wealth: 5.3466
- Stage-7 + second Oracle: 7.4575
- incremental terminal wealth: **+39.48%**

The headroom is not isolated to only one broad period.

## Interpretation

The one-removal cap is materially binding. Once the first harmful competitor is removed, the next-ranked competition structure often still contains another removable source of interference.

This directly supports the original economic decomposition:

```text
Universe value
= opportunity capture
- interference cost
```

A single safe deletion does not exhaust interference cost in many months.

## Decision

The second-step Oracle headroom is large enough to justify building a true dynamic second-removal prediction experiment.

Next stage must remain low freedom:

1. first removal stays exactly frozen Stage-7 primary;
2. remove the first ETF;
3. recompute Universe-dependent features under the reduced universe;
4. reuse the same chronological Stage-3 / Stage-7 model specifications and the same 90% historical regret-coverage logic;
5. allow at most one additional removal;
6. evaluate the exact combined two-removal counterfactual.

No new feature search or threshold optimization is justified by this Oracle result.
