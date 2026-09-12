# MUV Stage 8 — Frozen Stage-7 Policy Robustness Findings

Date: 2026-09-12
Status: completed; diagnostic robustness passed, but sample remains small

## Scope

Stage 8 does not change Stage 7. The primary policy remains:

```text
pairwise + regime magnitude-weighted safety model
90% past positive-regret coverage
max one removal per month
```

Stage 8 was designed after seeing Stage-7 results and therefore is not a new untouched validation set. It is a concentration / luck stress test only.

## Frozen Stage-7 reference

- keep-all final wealth: 6.8039
- Stage-7 primary final wealth: 8.8879
- relative terminal wealth advantage: **+30.63%**
- actions: 16 / 44 months

## Adversarial winner ablation

The most profitable realized deletion months were deliberately reverted to keep-all, without replacing them with other actions.

Revert largest winner only (`2026-07`):

- final wealth: 7.9210
- relative advantage: **+16.42%**

Revert largest two winners (`2026-07`, `2024-10`):

- final wealth: 7.3165
- relative advantage: **+7.53%**

Revert largest three winners (`2026-07`, `2024-10`, `2023-11`):

- final wealth: 6.9435
- relative advantage: **+2.05%**

Revert all five positive-effect actions:

- final wealth: 6.6035
- relative advantage: -2.95%

Interpretation: the result is concentrated, as expected with only seven nonzero actions, but it is not supported by a single lucky month. Even deleting the three largest realized gains from the policy history leaves a small positive terminal advantage.

## Leave-one-selected-symbol-out

All Stage-7 primary actions involving one symbol were reverted to keep-all, one symbol at a time.

Worst ablation was `501018` (one action):

- relative terminal advantage remains **+16.42%**

Other notable cases:

- revert both `518880` actions: **+21.54%** remains
- revert `159915`: **+20.66%** remains
- revert `513920`: **+26.72%** remains

Reverting `164824` actions actually raises relative advantage to +34.38%, because one of those removals was the largest false-removal regret.

No single selected symbol is necessary for the Stage-7 advantage to remain positive.

## Matched random deletion control — 10,000 draws

Random deletion uses exactly the same 16 action months as Stage-7 primary and randomly chooses the incumbent removed in each action month.

Random terminal advantage vs keep-all:

- mean: +2.68%
- median: +4.90%
- 5th percentile: -27.87%
- 95th percentile: +22.32%
- 99th percentile: +31.20%
- probability random beats keep-all: 67.48%

Stage-7 primary:

- +30.63%
- percentile among random controls: **98.87%**
- probability random matches or beats primary: **1.13%**

This materially strengthens the conclusion that the result is not explained by generic universe shrinkage on the same months.

## Action concentration

Of 16 actions:

- 7 had nonzero counterfactual effect
- 5 were beneficial removals
- 2 were harmful false removals
- 9 had zero realized effect

Gross beneficial removal improvement: +26.23 percentage points.
Observed false-removal harm: -2.84 percentage points.

Share of gross positive improvement:

- largest positive action: 35.66%
- largest two: 59.68%
- largest three: 79.91%

The concentration warning is real. Stage 7 should not be treated as a large-sample established edge.

## Fixed period check

- 2023–24: +12.93% relative terminal wealth; 9 actions
- 2025–26: +15.67%; 7 actions

The sign of the improvement is not isolated to one broad period.

## Decision

Stage 8 supports continuing the asymmetric-regret retention line.

However, the small effective sample means the next step should not immediately add multiple learned deletion decisions per month. First measure whether a second removal after the Stage-7 primary removal has enough counterfactual Oracle headroom to justify the additional modeling degrees of freedom.

Next: Stage 9 sequential second-removal headroom audit.
