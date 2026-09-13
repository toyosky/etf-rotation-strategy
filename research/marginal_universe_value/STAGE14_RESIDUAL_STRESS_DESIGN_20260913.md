# Stage 14 — Distribution-free residual stress test design

Date: 2026-09-13

## Purpose

Stage 13 showed that month-cluster parameter bootstrap uncertainty can remain narrowly negative even before very large positive retention-value misses. Stage 14 therefore does not fit another predictor. It tests whether the existing expected-MUV model can certify removals as safe after respecting the magnitude of forecast errors that has actually occurred in prior months.

## Frozen construction

For each candidate row:

`forecast_error = realized_retention_value - predicted_expected_MUV`

For each prior label month, retain the **maximum positive forecast error across the whole candidate cross-section**. This month-level maximum is the calibration score. It preserves the decision problem's asymmetric loss: one hidden large winner can dominate the cost of a removal.

For month t:

1. use only completed OOS months before t;
2. require at least 12 prior OOS calibration months;
3. compute the empirical 90th percentile of prior monthly maximum forecast errors using the conservative `higher` quantile;
4. define residual-stress upper bound = current predicted MUV + that past-only quantile;
5. certify a removal as safe only when the upper bound is below zero.

## Degrees of freedom

Frozen before evaluation:

- expected-MUV predictor: unchanged Stage-3 pairwise model;
- calibration unit: label month;
- score: cross-sectional maximum positive forecast error;
- minimum history: 12 months;
- coverage level: 90%;
- quantile interpolation: `higher`;
- no feature search;
- no model fitting;
- no threshold search;
- no period-specific parameters.

## Audit questions

1. Are the known 2024-09 159915 and 2025-04 518880 latent winners blocked?
2. How many candidates, and how many actual Stage-7 actions, remain certifiably safe?
3. Does the rule retain any economically useful correct removals, or does honest tail-error calibration force near-total abstention?
4. What does this imply about the original MUV question: is current observable state sufficient for a stable dynamic retention decision, or only for weak ranking under a hard risk budget?

## Decision rule for interpretation

This stage is diagnostic, not a candidate policy search.

- If meaningful safe-removal coverage survives while known hidden winners are blocked, residual-stress abstention may deserve a later policy test.
- If essentially no removals can be certified, do not tune the quantile downward. Interpret that as evidence that the current state representation/model family cannot support statistically defensible dynamic deletion at useful coverage.
