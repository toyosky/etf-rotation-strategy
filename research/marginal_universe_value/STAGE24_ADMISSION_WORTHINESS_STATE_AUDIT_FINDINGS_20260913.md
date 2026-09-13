# Stage24 Admission Worthiness State Audit — Findings

Date: 2026-09-13

## Verified execution

- Workflow: `MUV Stage24 Admission Worthiness State Audit`
- Run ID: `34749515375`
- Conclusion: success
- Artifact: `muv-stage24-admission-worthiness-34749515375`
- Artifact SHA256: `d83e6b6da489ccb2fcff9072b52ad872c9e033b20cb33719cb5e874c01ba889b`

## Frozen design

Target: an outside-Fixed15, point-in-time trend-eligible ETF is positive if its next-20-trading-day close return exceeds the contemporaneous Fixed15 oracle-best next-20-day close return.

Fixed state features:
- score
- r2
- score_delta
- current_resid
- efficiency20
- dist_high20

Model: fixed LogisticRegression (L2, C=1, class_weight=balanced) with median imputation and scaling.

Validation: strict monthly expanding OOS from 2023-01. No feature search, hyperparameter search, TopK search, threshold search, or strategy backtest.

Predeclared support rule: Hit@5 and MRR must not deteriorate versus raw OLS score overall or in either era.

## Results

OOS positive months: 33.
Mean candidate count: 157.03.
Mean positive count: 21.79.
Mean positive share: 20.19%.

Overall:
- raw score Hit@5: 54.55%
- low-DoF state Hit@5: 54.55%
- raw score MRR: 0.36995
- low-DoF state MRR: 0.41672
- median first-positive rank: 5 -> 3

2023-24:
- Hit@5: 61.11% -> 61.11%
- MRR: 0.44809 -> 0.49567
- median first-positive rank: 4 -> 3

2025-26:
- Hit@5: 46.67% -> 46.67%
- MRR: 0.27618 -> 0.32200
- median first-positive rank: 8 -> 11

Frozen decision: `low_dof_admission_state_supported = true` because Hit@5 did not deteriorate and MRR improved overall and in both eras.

## Branch review

1. State information vs model capacity

Stage24 shows that the six-feature point-in-time state contains some incremental ranking information beyond raw OLS score. Therefore the evidence does not justify saying state information is absent, and it also does not justify increasing model capacity yet. The gain is modest: Hit@5 is unchanged and only reciprocal-rank improves.

2. Target difficulty

The Stage24 target is already weaker than unique-winner prediction, but it still depends on Fixed15 as the reference opportunity frontier. That makes it useful for admission around a fixed core, not for the more fundamental question of whether a dynamic full-market opportunity universe can be constructed without a fixed pool.

3. Sample size

Only 33 OOS positive months contribute to the frozen month-level evaluation. This is enough for a mechanism signal but too small to justify feature expansion, threshold tuning, or neural-network escalation.

4. Branch decision

Do not tune TopK or add hand-picked features on this OOS history. Do not jump to a nonlinear-capacity benchmark yet. Instead branch to a lower-assumption, no-Fixed15 Dynamic Opportunity Universe identifiability audit.

The new question is: at month-end, using only information available then, can the full ETF market be compressed into a variable-size opportunity set that captures a high share of subsequent strong opportunities without requiring exact future-winner prediction?
