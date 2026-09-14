# OURE Stage6M — Second-Layer Sample-Size Diagnostic

Date: 2026-09-15
Status: preregistered before inspecting Stage6M outcomes

## Question
Stage6L found repeatable internal structural differences among first-layer RF-high K30 sets, but its chronological Ridge residual detector failed. Is that failure mainly consistent with too few independent 126-session market blocks, or with mapping drift/nonstationarity?

## Frozen inputs
- Reuse the frozen Stage6L artifact only; do not regenerate/tune the first-layer RF.
- Strict non-overlapping 126-session blocks B01..B09 from Stage6K/6L.
- K=30, first-layer RF, RF-high top 20%, residual definition, and all 47 Stage6L internal features stay frozen.
- Ridge alpha stays 10.0.
- No symbol identity, future member path, or future leader path enters X.

## Important interpretation limit
This is a **diagnostic**, not a new deployable model test. Stage6L's 12 globally stable traits were discovered on the same historical blocks. Therefore the 12-trait curve is allowed only as a best-case diagnostic of whether more independent blocks help once the relevant structural family is known. It cannot be promoted as clean OOS evidence.

A second curve using all 47 preregistered Stage6L internal features is included as a less-selected robustness check.

## Learning-curve construction
Use common target blocks B06, B07, B08, B09 so every target can be evaluated with exactly N=1,2,3,4 immediately preceding completed blocks.

For each target block T and each N in {1,2,3,4}:
1. Take the N immediately preceding RF-high blocks only.
2. Fit a Ridge(alpha=10) model to predict `residual_rank = future_rank_pct - rf_pred_rank_pct`.
3. Standardize each feature using training-block rows only (training mean/std; missing -> training median then 0 after standardization if necessary).
4. Predict residual_rank for T.
5. Record residual Spearman between prediction and realized residual_rank.
6. Form a second-layer score `rf_pred_rank_pct + predicted_residual`; record Top50 actual future percentile and Top50 gain versus first-layer RF within the same RF-high target population.

Run two frozen feature sets:
- **Curve A (best-case structural set):** the 12 Stage6L globally stable traits frozen in Stage6L findings.
- **Curve B (robustness):** all 47 preregistered Stage6L internal features.

No feature/alpha/N/target selection may be changed after results are inspected.

## Primary sample-size-support gate (Curve A)
All are required for `sample_size_support`:
1. median residual IC at N=4 minus median residual IC at N=1 >= +0.10;
2. median residual IC is non-decreasing in at least 2 of the 3 adjacent N steps (1->2,2->3,3->4);
3. N=4 residual IC is positive in at least 3 of 4 common target blocks;
4. median Top50 gain versus first-layer RF at N=4 is greater than at N=1.

If only 2-3 gates pass: `mixed_sample_size_and_drift`.
If <=1 gate passes: `sample_size_not_primary_explanation`.

## Secondary robustness
Curve B is descriptive. If its N=4-N=1 median IC change has the same sign as Curve A, that strengthens the direction. Opposite sign weakens confidence.

## Additional diagnostics
- Per-target paired delta IC: IC(N=4)-IC(N=1).
- Median/mean paired delta and sign count.
- Recency sensitivity: compare N=1 vs N=4 to see whether adding older mappings helps or hurts.
- Effective sample warning: thousands of K30 rows are not counted as independent time observations; independent regime information is at block level.

## Interpretation rules
- A rising curve supports the hypothesis that the second layer is data-starved in the time dimension, but does not prove future deployability.
- A flat/reversing curve, especially if N=1 >= N=4, supports mapping drift/stale-history contamination over pure sample scarcity.
- Do not respond to failure by changing Ridge alpha, feature definitions, RF-high threshold, or adding model capacity.
