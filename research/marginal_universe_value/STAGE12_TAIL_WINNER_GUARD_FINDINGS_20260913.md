# Stage 12 — Direct tail-winner guard findings

Date: 2026-09-13

## Frozen design

A direct upper-tail classifier was fitted in expanding walk-forward form. For each OOS month, the tail threshold was the 80th percentile of prior positive retention values. The model used the frozen union of Stage-A, pairwise and regime features and bypassed Stage-A `P(active)` multiplication.

A secondary guard used only prior OOS tail events and a fixed 90% historical tail-regret-mass coverage rule.

No feature, model or threshold search was performed.

## Predictive result

The direct tail target contains real information:

- OOS rows: 556 across 42 months
- realized tail events: 16
- tail base rate: 2.88%
- overall ROC AUC: 0.747
- average precision: 0.188
- 2023–24 AUC: 0.774
- 2025–26 AUC: 0.719
- median within-month percentile of realized tail events: 84.7%

So broad large-winner risk is not random.

## But it does not solve the decision failure

Among realized tail winners for which the existing pairwise expected MUV was negative:

- events: 7
- Stage-7 asymmetric safety protected: 85.7%
- new direct-tail guard protected: 57.1%

The new model therefore performs worse on exactly the subset that matters for safe removal.

The key 2024-09 case remains missed:

- symbol: 159915
- realized retention value: +29.19%
- expanding tail threshold: +5.52%
- Stage-A p(active): 10.59%
- pairwise expected MUV: -0.117%
- direct p(tail): 0.074%
- within-month tail-risk percentile: 28.6%
- not protected by the direct tail guard

2025-04 518880 is protected, but it was already protected by the Stage-7 safety model.

## Portfolio effect

Adding the frozen tail guard to Stage 7 changes essentially nothing:

- Stage-7 final wealth: 8.8879
- Stage-7 + tail guard final wealth: 8.8879
- tail vetoes: 1
- no non-zero realized portfolio effect

Adding it to the rejected Stage-10 second-removal policy also changes nothing:

- Stage-10 final wealth: 8.0677
- Stage-10 + tail guard: 8.0677
- second-removal vetoes: 0

## Interpretation

The failure is not fixed by simply creating a more tail-focused classification target. The current price/state feature set can rank many obvious future large winners, but a small and economically dominant residual class remains: assets that look safe to remove under several models yet subsequently become large positive-retention-value winners.

This is now best treated as an epistemic-uncertainty / abstention problem rather than another point-prediction problem.

## Decision

- Do not promote the Stage-12 tail guard.
- Keep Stage 7 as the current best retention policy.
- Preserve the one-removal-per-month risk budget.
- Stage 13 will test a month-cluster bootstrap uncertainty bound around the frozen expected-MUV model. A removal is considered statistically safe only if the one-sided 90% bootstrap upper bound of expected MUV remains below zero.
