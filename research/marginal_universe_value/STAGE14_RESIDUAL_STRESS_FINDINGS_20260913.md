# Stage 14 — Distribution-free residual stress findings

Date: 2026-09-13

## Result

Stage 14 completed successfully. The frozen diagnostic was intentionally conservative: for each OOS month it used only prior completed OOS months, took the cross-sectional maximum positive forecast error in each prior month, then used the historical 90th percentile (`higher`) of those monthly maxima as an additive stress to the current Stage-3 pairwise expected MUV.

No model was refit and no threshold was searched.

## Main diagnostics

- calibrated rows: 443
- calibrated months: 32
- candidates certified safe for removal: 0
- safe share: 0.0%
- candidates with negative point MUV: 197
- negative-point-MUV candidates still certified safe: 0

The known latent winners were correctly blocked by the stress test:

- 2024-09 / 159915: realized retention value +29.19%, point MUV -0.12%, historical-tail stress +9.33%, stressed upper bound +9.22%; not safe to remove.
- 2025-04 / 518880: realized retention value +23.48%, point MUV -0.81%, historical-tail stress +10.09%, stressed upper bound +9.27%; not safe to remove.

## Stage-7 policy overlay

The frozen Stage-7 policy made 16 removal actions. Stage 14 vetoed all 16.

- Stage-7 final wealth: 8.8879
- Stage-14-stressed final wealth: 6.8039
- surviving Stage-7 actions: 0

The stress rule therefore collapses to keep-all. This is not a candidate policy failure to be repaired by lowering the 90% coverage threshold. It is the intended diagnostic outcome.

## Interpretation

The current observable state / Stage-3 expected-MUV model cannot certify dynamic deletion at useful coverage once the magnitude of historically observed positive tail misses is respected.

This sharply separates two claims that must not be conflated:

1. **ranking / relevance prediction may contain information**;
2. **high-confidence directional retention decisions may still be unsupported**.

The failure mechanism is asymmetric. A small number of hidden positive-retention events are large enough that honest past-only error calibration dominates the small negative point estimates used to justify deletion.

The implication for the original MUV question is therefore narrower than “MUV is unpredictable.” The evidence instead says that the present feature representation may be able to predict whether an ETF is likely to affect the OLS competition path, but it has not yet shown stable ability to predict whether that effect will be beneficial or harmful with enough confidence for unconstrained retention deletion.

## Next stage

Proceed to Stage 15: a model-free hurdle-identifiability audit using the already frozen Stage-3 OOS predictions.

The audit will separately measure:

- path-activity predictability;
- conditional sign predictability once the ETF actually affects the path;
- continuous MUV ranking quality;
- false-removal-regret concentration among negative point-MUV rows;
- stability across 2023-24 and 2025-26.

No new features, model fitting, threshold search, or policy optimization are allowed in Stage 15.
