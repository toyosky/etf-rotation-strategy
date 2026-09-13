# Stage 12 — Tail-winner guard design

Date frozen: 2026-09-13

## Motivation

Stage 11 shows that broad second-order interaction is not the main reason Stage 10 failed. The unresolved failure mode is rare but severe false-removal regret: a future large positive-retention-value ETF can receive low predicted participation/value risk.

Examples include 2024-09 159915 and 2025-04 518880.

Stage 12 does **not** tune Stage A, Stage B, the Stage-7 90% safety coverage, or the one-removal cap. It adds a diagnostic model whose only job is to identify future large positive-retention-value tail events.

## Tail definition

For each OOS prediction month `t`:

1. Use only rows with `label_month < t`.
2. Among prior rows with `delta_return > 0`, compute the 80th percentile of positive `delta_return`.
3. Define a prior training row as a tail winner when `delta_return >= q80_positive(t)`.
4. Evaluate current-month realized tail status against the same prior-only cutoff.

The 80th percentile is frozen in advance as a conventional upper-tail definition. It is not selected by backtest performance.

## Model

Fixed L2 logistic regression, `C=1`, identical preprocessing style to previous stages.

Target:

`P(tail winner | X_t)`

This is fit directly on all prior month×ETF rows. It intentionally bypasses multiplication by Stage-A `P(active)`.

Frozen feature block = union of already-used point-in-time variables:

- Stage-A participation features
- Stage-3 pairwise features
- Stage-5/7 regime breadth features

No new feature search.

## Evaluation

Expanding monthly OOS, policy period beginning 2023-01 where training support is adequate.

Primary diagnostics:

- ROC AUC for tail-winner event
- average precision
- tail-event score percentile within each month
- performance in 2023–24 and 2025–26 separately
- realized large-positive-RV events that current `muv_pairwise < 0` misclassifies

## Fixed protective calibration

A secondary diagnostic guard is allowed, but no threshold optimization:

For each OOS month, derive a tail-risk score cutoff using only earlier OOS tail events. The protected region is chosen to cover 90% of historical realized tail-regret mass. An ETF below that score is outside the protected region.

This mirrors the Stage-7 regret-coverage principle and allows an apples-to-apples test of whether direct tail modeling catches events that the Stage-7 safety model misses.

Minimum support before calibration:

- at least 8 prior realized tail events

## Policy tests

No production promotion from AUC alone.

Two frozen comparisons:

1. **Stage7 + tail guard**: keep the original Stage-7 one-removal candidate selection, but veto the removal if the candidate lies in the tail-protected region.
2. **Stage10 + tail guard diagnostic**: keep the Stage-10 second candidate unchanged, but veto it if the direct tail model protects it. This is diagnostic only; Stage 10 remains rejected unless this fixed guard materially fixes the failure without threshold tuning.

Success requires:

- materially lower catastrophic false-removal regret,
- no reliance on one isolated year,
- and limited sacrifice of correct-removal gains.

If direct tail risk is not predictably separable, the correct conclusion is to keep the hard one-removal risk budget rather than increase sequential depth.