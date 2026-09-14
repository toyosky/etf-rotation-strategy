# OURE Stage6L — RF False-Positive Matched Structural Audit

Date: 2026-09-14
Status: preregistered before Stage6L outcome inspection

## Question
Stage6K established a narrow but important pattern: the immediately previous 126-session RF carries weak broad-ranking information for the next K30 cross-section, but its extreme predicted tail is unreliable. The new hypothesis is that the first-layer RF already recognizes a coarse class of externally good-looking K30 sets, while real future winners and false positives inside that RF-high class differ in internal structure not represented by the frozen 19 aggregate set features.

This stage asks:
1. Among K30 sets with similarly high first-layer RF predictions, what past-only internal structural traits distinguish future winners from future losers?
2. Are any such matched differences stable across strict non-overlapping 126-session blocks?
3. Only if stable traits exist, can a low-complexity chronological second layer predict first-layer residual quality in later blocks?

## Frozen first layer
Reuse Stage6K exactly:
- K = 30 noncash members; cash handling/downstream OLS unchanged.
- lookback = 126 sessions; outcome horizon = 126 sessions.
- strict consecutive non-overlapping blocks starting 2022-01-04.
- first-layer RF = frozen Stage6G/6K 19 features and RF hyperparameters.
- for each target block Bj (j>=2), RF is trained only on immediately preceding completed block B(j-1).
- no symbol identity feature.

## RF-high population and matched outcome contrast
For each target block B02..B09:
- rank all K30s by previous-block RF prediction.
- RF-high population = top 20% by prediction rank; this threshold is frozen.
- create 10 equal-frequency prediction strata inside RF-high.
- define rank residual: `future_rank_pct - rf_pred_rank_pct` within the full target-block library.
- within each prediction stratum, define good = top residual quartile and bad = bottom residual quartile.
- nearest-neighbor match good to bad without replacement on RF prediction rank within the same stratum.
- future outcomes are used only to define residual/good/bad labels; no future member path or contribution enters X.

This matched design deliberately asks why two K30s that look nearly equally attractive to RF end up very differently.

## New past-only internal structural features
These features are computed only for RF-high sets and deliberately add distributional/robustness information beyond the frozen first-layer aggregates.

### A. Member standalone harvestability distribution
For each of 30 members over the current past126 window, compute singleton frozen-OLS log growth. Summaries:
- p10, p25, p50, p75, p90;
- IQR, standard deviation;
- fraction positive.

### B. Member eligibility participation distribution
For each member, fraction of past126 days with finite risk score. Summaries:
- p10, p25, p50, p75, p90;
- IQR, standard deviation;
- fraction with eligibility participation >= 50%.

### C. Leader participation / concentration shape
Using the K30 past126 frozen OLS leader path, compute each member's share of invested leader days. Summaries:
- largest, top3 cumulative, top5 cumulative leader share;
- median nonzero leader share;
- fraction of members ever becoming leader;
- Gini coefficient of 30-member leader shares.
Existing leader HHI/effective leader count are not reused as second-layer inputs.

### D. Pair internal geometry
Across 435 member pairs on past126:
- eligibility-Jaccard p25/p50/p75/p90;
- score-correlation p25/p50/p75/p90, requiring >=20 common finite-score days;
- realized-return correlation p25/p50/p75/p90 from frozen gross returns, requiring >=40 finite days;
- connected-component count under return-correlation > 0.85 (single-link graph);
- largest component share.

### E. Leave-one-out robustness
For each member i, compute past126 set log value of U\{i}. Define damage = base K30 past log value minus leave-one-out log value. Summaries:
- damage p10/p25/p50/p75/p90;
- maximum positive damage;
- standard deviation;
- fraction of deletions that improve the set (damage < 0).
This measures whether the good-looking K30 is robust/distributed or propped up by a few members.

No future member contribution, future leader path, symbol ID, asset label, or post-decision data may enter these features.

## Matched structural audit
For each feature and target block:
- compute paired good-minus-bad difference across matched pairs;
- scale by the RF-high feature standard deviation in that block to obtain standardized matched effect.

A feature is `stable_internal_trait` in the full B02..B09 audit only if:
- finite effect in >= 6 blocks;
- the same nonzero sign in >= 6 of 8 blocks;
- median absolute standardized effect >= 0.15.
Direction is not preregistered; stability, not a favorable sign, is the primary mechanism criterion.

Stage-1 structural gate passes if at least 3 features from at least 2 distinct feature families (A-E) satisfy `stable_internal_trait`.

If this gate fails, freeze Stage6L as negative and do not train a second layer.

## Conditional Stage 2 — low-complexity residual model
Only if Stage-1 gate passes.

### Chronological feature selection
For each test block from B05 onward:
- use only earlier target blocks B02..B(test-1);
- minimum 3 historical target blocks is required;
- a feature survives if its matched effect is finite in at least 75% of those historical blocks, the same nonzero sign appears in at least `ceil(0.75*n_history)` blocks, and median absolute standardized effect >= 0.15;
- this is the chronological proportional analogue of the full-history 6-of-8 rule;
- if fewer than 2 features survive, emit a neutral score for that test block; no fallback tuning.

### Model
- target: rank residual (`future_rank_pct - rf_pred_rank_pct`) among RF-high training sets.
- model: Ridge regression, alpha = 10.0, fit_intercept = true.
- inputs: retained internal features, standardized using training data only.
- group/sample weighting: equal total weight per historical block so larger libraries do not dominate.
- no hyperparameter tuning.

### Test population
The test model only ranks the frozen RF-high top20% population of the next block. It is not permitted to search new K30s.

### Baselines inside the same RF-high population
1. first-layer RF prediction rank;
2. current past126 set log-growth rank.

### Stage-2 primary metrics across B05..B09
- Spearman(second-layer residual score, actual rank residual), median > +0.10;
- positive residual IC in >= 4 of 5 blocks;
- median actual future percentile of the second-layer top50 (within RF-high population) > 0.60;
- second-layer top50 future percentile exceeds first-layer-RF top50 by median >= +0.05.
All four are required.

## Interpretation
- Stage-1 pass only: evidence that RF false positives have stable internal structural differences, but no deployable detector yet.
- Stage-2 pass: evidence that a low-complexity second layer can distinguish internally good RF-high K30s chronologically. This still does not authorize CEM/GA/swap search.
- Any failure is frozen; do not rescue with new features, thresholds, model classes, or hyperparameter search on the same history.

## One-shot stopping rule
After results, write findings and update registry. Whether pass or fail, disable the existing OURE research automation. This stage is intentionally one-shot.