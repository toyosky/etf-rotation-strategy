# MUV Stage 7 — Asymmetric Retention Safety Design

Date: 2026-09-12
Status: frozen before Stage 7 policy results

## Why Stage 7 exists

Stage 6 translated the Stage-3 pairwise MUV estimate into a one-removal-per-month policy. It failed:

- keep-all Fixed15 final wealth: 6.8039
- pairwise no-gate: 6.2254 (-8.50% relative)
- primary crowding < 2/3: 5.9208 (-12.98% relative)
- strict crowding < 1/3: 6.6983 (-1.55% relative)

The primary policy also underperformed in both 2023–24 and 2025–26. A random one-removal control, matched to the same 25 action months, had median relative wealth advantage of about +3.03%, while the model-selected policy was about -12.98%.

The key failure mode is asymmetric regret. A small number of false removals of large positive-RV ETFs can dominate many correctly removed small negative-RV ETFs. The 2025-04 removal of 518880 is the canonical example: realized retention value was about +23.48 percentage points.

Therefore ordinary sign AUC is not the correct policy objective.

## Frozen Stage 7 question

Instead of asking:

> Is next-month retention value positive or negative?

ask:

> Do we have enough historical evidence that removing this ETF is safe from large opportunity-loss regret?

## Model

Stage A / expected-MUV machinery from Stage 3 is not retuned. Stage 7 adds a separate safety score conditional on realized participation.

Training rows: historical `path_active == True` rows only.

Target:

```text
y = 1(delta_return > 0)
```

Sample weight:

```text
w_i = |delta_return_i| / mean_train(|delta_return|)
```

Thus large positive and large negative marginal outcomes receive more influence than tiny outcomes. Weight normalization makes the overall scale invariant.

Primary feature set is frozen as:

- the 10 existing pairwise competitor features from Stage 3;
- plus 3 already-predeclared market-state variables from Stage 5:
  - `regime_risk_qualified_count`
  - `regime_risk_ret20_positive_frac`
  - `regime_risk_ret20_median`

Model: L2 LogisticRegression, C=1.0, no hyperparameter search.

A pairwise-only weighted model is reported as an ablation, not selected post hoc.

## Past-only regret coverage calibration

The safety score is not thresholded at 0.5.

For each evaluation month, use only earlier OOS predictions and realized outcomes. Among earlier realized positive-RV active rows:

1. sort safety scores high to low;
2. accumulate realized positive `delta_return`;
3. find the lowest score needed to cover a predeclared share of total historical positive-RV mass.

Primary coverage target: 90%.

Sensitivity targets, all reported: 80% and 95%.

Interpretation:

> the protected set is calibrated to contain roughly the historical score region responsible for 90% of cumulative opportunity-loss mass.

No current/future outcome is used to set the current month's cutoff.

## Action rule

For each month:

1. start from Stage-3 OOS `muv_pairwise`;
2. candidate must have `muv_pairwise < 0`;
3. candidate must fall below the past-only safety cutoff (not in protected high-regret region);
4. among safe negative-MUV candidates, remove only the one with the most negative predicted MUV;
5. maximum one removal per month.

If historical calibration support is insufficient, take no action.

No crowding gate is used in Stage 7. Stage 6 showed that crowding terciles were not a valid final action rule.

## Evaluation

Primary policy:

```text
weighted pairwise + regime safety model
90% past positive-regret coverage
```

Predeclared sensitivities:

- same model, 80% coverage;
- same model, 95% coverage;
- weighted pairwise-only model, 90% coverage.

Report:

- final wealth and relative wealth vs keep-all;
- 2023–24 and 2025–26 separately;
- action count;
- realized action win / harm rate;
- cumulative realized removal improvement;
- cumulative positive false-removal regret;
- maximum single false-removal regret;
- random one-removal control matched to primary action months;
- one-removal Oracle only as an upper bound.

## Anti-overfitting boundary

- no feature search in Stage 7;
- no C / regularization search;
- no coverage-target selection after seeing results;
- 90% is primary; 80%/95% are sensitivities only;
- no crowding threshold search;
- all calibration is chronological and past-only;
- if Stage 7 fails, do not rescue it by choosing the best reported coverage level.
