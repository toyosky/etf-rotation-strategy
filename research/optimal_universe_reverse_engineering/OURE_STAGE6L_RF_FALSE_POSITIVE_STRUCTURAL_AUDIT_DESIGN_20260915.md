# OURE Stage6L — RF False-Positive / Matched Good-vs-Bad Structural Audit

Date: 2026-09-15
Status: preregistered before outcomes

## Question
Stage6K showed weak broad adjacent-block ranking transfer but top-tail distortion. Does the previous-block RF already know which K30 sets look broadly plausible, while the RF-high tail mixes structurally different true-good and false-positive sets that the frozen 19 aggregate features cannot distinguish?

The object of study is residual value:

R(U) = future126_log_growth(U) - previous_block_RF_prediction(U)

not future value Y by itself.

## Frozen first layer
- Same strict non-overlapping 126-session blocks as Stage6K.
- K=30 noncash members and frozen downstream OLS/cash semantics.
- Same point-in-time candidate pool and same Stage6G/6I family-library generator.
- Same 19 first-layer whole-set features.
- Same RF parameters: 800 trees, max_depth=7, min_samples_leaf=10, max_features=sqrt, bootstrap=True, seed=20260914.
- For each target block, train first-layer RF only on the immediately previous fully completed block.
- No RF retuning, feature changes, horizon changes, or identity features.

## RF-high cohort
For every target block, retain exactly the top 20% of candidate K30 sets by first-layer RF prediction. This threshold is frozen and may not be changed after seeing outcomes.

## Matched good-vs-bad construction
Within each target block:
1. Compute residual R only after the target block has fully realized.
2. Split the RF-high cohort into five equal-frequency strata by RF prediction.
3. Inside each stratum define:
   - good = top 30% by residual R;
   - bad = bottom 30% by residual R.
4. Pair good and bad sets greedily by smallest absolute RF-prediction distance, without reuse. Ties are deterministic by members string.

Future value/residual is used only for good/bad labels and evaluation, never as a structural X feature.

## Frozen structural features: X<=t only
All are computed from the target block's trailing 126 sessions, before target outcomes.

### Member-distribution features
Across the 30 members, summarize with fixed median / IQR / lower or upper tail where specified:
- member trailing63 return: median, IQR, 10th percentile;
- member trailing126 return: median, IQR, 10th percentile;
- member trailing126 realized volatility: median, IQR;
- member trailing126 max drawdown: median, 90th percentile magnitude;
- member eligibility participation share: median, IQR, 10th percentile;
- member leader participation share within the past-only frozen OLS path: median, max, IQR.

### Pair-structure features over all 435 member pairs
- trailing126 return correlation: median, IQR, 90th percentile;
- eligibility Jaccard: median, IQR, 90th percentile;
- score-crossing rate: median, IQR, 90th percentile. Crossing is the share of adjacent sessions where the sign of score_i-score_j changes while both scores are finite on both sessions.

### Concentration / robustness features
- active leader count, leader HHI, effective leader count (past-only path; included as explicit structural decomposition, although related aggregate concepts existed in layer 1).
- leave-one-out past-set log-loss distribution from deleting each one of 30 members: median, 90th percentile, maximum. Loss = full past126 log_growth - delete-one past126 log_growth; positive means deletion hurts.
- fixed-budget 1-swap neighborhood robustness: use the 10 highest past-singleton-log outsiders; for each outsider evaluate all 30 one-for-one swaps. Record best improvement, median best-per-outsider improvement, and share of outsiders with any positive improving swap. No adaptive search.
- cluster count from trailing126 return-correlation distance using a frozen threshold corr >= 0.80 as same connected component; report component count and largest-component share. This threshold is descriptive and frozen before outcomes.

No symbol ID, taxonomy ID, future member contribution, future leader path, or future pair statistic is allowed in X.

## Stage 1: matched structural audit gate
For every structural feature compute per matched pair good-minus-bad difference, then aggregate within each target block.

A structural feature is called stable only if all hold:
1. it has valid matched-pair estimates in at least 6 target blocks;
2. the sign of the block-level median good-minus-bad difference agrees with its overall median sign in at least 75% of valid blocks;
3. the median absolute standardized paired effect is >= 0.15, where standardization is by the within-block RF-high feature IQR (fallback SD, then 1 if degenerate);
4. the feature's within-RF-high Spearman with residual has the same direction in at least 75% of valid blocks.

Stage-1 audit PASS requires at least 3 stable structural features spanning at least 2 of these 3 families: member-distribution, pair-structure, concentration/robustness.

If Stage-1 audit fails, Stage6L freezes failed and the second-layer model is not evaluated as deployable evidence.

## Stage 2: low-complexity chronological residual ranker
Stage 2 is permitted only if Stage-1 PASS.

- Feature set = only Stage-1 stable features; no additional feature selection.
- Model = Ridge linear regression, alpha=1.0, with training-only median imputation and z-standardization.
- Target = residual R in RF-high samples.
- Chronology: for target block j, train only on RF-high samples from fully completed earlier target blocks. Require at least 2 prior target blocks; no same-period CV.
- Final score for ranking within RF-high = first-layer RF prediction + predicted residual.
- Baselines: first-layer RF prediction alone and current past126 set-return rank.

## Stage 2 frozen gate
Across evaluable chronological target blocks, PASS only if all hold:
1. median within-RF-high Spearman(final_score, future_log_growth) > median Spearman(first-layer RF, future_log_growth);
2. final score beats first-layer RF on Spearman in > 50% of evaluable blocks;
3. median Top50 actual percentile improves by >= +0.03 versus first-layer RF within the full target library;
4. median top-decile actual percentile within RF-high improves by >= +0.03 versus first-layer RF;
5. median Spearman(predicted_residual, realized residual) > 0;
6. no era-direction reversal: median final-minus-first-layer Spearman delta is >= 0 in both 2022-24 and 2025-26 when each has at least 2 evaluable blocks.

The past126 set-return baseline is reported but cannot rescue a failure against the first-layer RF.

## Interpretation
- Audit FAIL: current past-only structural decomposition does not reveal a repeatable false-positive mechanism. Freeze failure; do not increase model capacity or launch CEM/GA/search.
- Audit PASS but Stage-2 FAIL: structure is descriptively repeatable but not chronologically exploitable with the frozen low-complexity residual ranker. Freeze failure; no model escalation.
- Stage-2 PASS: supports a second-layer 'screen the false positives' mechanism only. It does not authorize RF-guided combinatorial search; that requires a separate preregistration and genuinely later evaluation.
