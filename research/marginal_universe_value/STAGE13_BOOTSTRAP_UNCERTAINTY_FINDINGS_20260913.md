# Stage 13 — Month-cluster bootstrap uncertainty findings

Date: 2026-09-13

## Question

Can epistemic uncertainty around the frozen expected-MUV model identify the rare latent winners that made deeper removal unsafe?

The design was frozen before the run:

- resample whole prior label months;
- 300 bootstrap draws;
- one-sided 90% upper bound;
- a candidate is uncertainty-safe only when bootstrap q90 of expected MUV remains below zero;
- no feature search, model search, or confidence-level search.

## Result

The bootstrap does **not** solve the key false-removal problem.

Across 578 OOS rows in 44 months:

- positive-retention rows: 64;
- positive-retention rows still classified uncertainty-safe: 17.19%;
- tail events: 16;
- tail events still uncertainty-safe: 18.75%;
- among the 7 tail events with negative point expected-MUV, 42.86% still pass the uncertainty-safe rule.

The failure is worse in 2025–26 than 2023–24:

- 2023–24 tail false-safe share: 12.5%;
- 2025–26 tail false-safe share: 25.0%.

## Named audits

### 2024-09 — 159915

- realized retention value: +29.19%;
- point expected MUV: -0.117%;
- bootstrap q90: -0.0138%;
- bootstrap probability MUV < 0: 91.33%;
- result: **still judged safe to remove**.

This is the central failure. The model is not merely uncertain; it is confidently wrong under the available state representation.

### 2025-04 — 518880

- realized retention value: +23.48%;
- point expected MUV: -0.815%;
- bootstrap q90: -0.0254%;
- bootstrap probability MUV < 0: 90.33%;
- result: **still judged safe to remove**.

The bootstrap interval is wider than for ordinary cases, but not wide enough to prevent the error.

## Portfolio consequence

Adding the frozen bootstrap veto to Stage 7 is harmful:

- Stage-7 final wealth: 8.8879;
- Stage-7 + uncertainty veto: 7.8076;
- vetoes: 5;
- prevented positive-retention regret: 0;
- sacrificed correct-removal value: 11.57 percentage points in summed monthly improvement.

A direct one-removal policy based on q90 < 0 is also rejected:

- final wealth: 4.2262;
- actions: 22;
- positive-retention mistakes: 7;
- summed positive regret: 70.76 percentage points;
- captured negative retention value: 21.85 percentage points.

## Interpretation

Stage 13 rules out a simple explanation based on parameter uncertainty. The dominant residual failures are not well represented by bootstrap dispersion around the current model family. Some future large winners sit inside a region the current model treats as confidently removable.

This strengthens the case that the unresolved problem is **representation / irreducible decision uncertainty**, not a missing confidence multiplier.

Stage 7 remains useful because its asymmetric safety layer is combined with a hard one-removal-per-month exposure cap. The cap is currently doing real risk-control work that the point model and bootstrap uncertainty cannot replace.

## Decision

- reject the Stage-13 bootstrap veto as a production rule;
- keep Stage 7 as the current retention baseline;
- do not deepen sequential removal;
- next run a distribution-free residual stress test using past-only month-level maximum positive forecast error. This deliberately asks a stricter question: can the existing model certify any removal as safe once observed tail miss magnitude is respected without fitting a new predictor?
