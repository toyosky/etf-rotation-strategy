# New Stage 3 — Conditional Universe Size-Direction Identifiability Audit

Date: 2026-09-14
Parent: New Stage2 frozen findings
Status: frozen design before Stage3 outcome inspection

## Question

Stage1 established that the economic effect of Universe size is regime-dependent. Stage2 showed that larger K consistently raises normalized trend age and shortens intrinsic remaining days, but this does not create a stable remaining-return penalty.

Stage3 therefore does **not** try to recover a universal exact K. It asks a weaker executable question:

Using only information available at the month-end decision time t, can a small fixed state vector identify whether expanding Universe size is more likely to help or hurt Frozen OLS value over the next month?

The Stage3 target is the already-used Stage1 future contrast:

`size_contrast_t = mean_return_t(K=30) - mean_return_t(K=3)`

Primary classification target:

`lean_larger_t = 1[size_contrast_t > 0]`

This target is hindsight-only for training/evaluation. No future value enters features.

## No exact-K selection

Stage3 is only a direction/identifiability audit: `lean smaller` versus `lean larger`.

It must not:
- choose a precise K from the full sample;
- tune K endpoints after seeing Stage3 results;
- choose an era cutoff as an executable feature;
- use trend_age_ratio, remaining_days, remaining returns or any other future label as a feature.

K=3 and K=30 are retained only because the same contrast was pre-existing in Stage1 robustness work. They are not declared future executable cardinalities.

## Frozen point-in-time features

Use the frozen Stage1 monthly representative parent-pool snapshots. Compute features at the prior trading day / prior history only.

Exactly five primary features are allowed in the first Stage3 audit:

1. `active_share_t`
   - share of frozen parent-pool members whose Stage1 `pool_score` is non-null at t.
   - coverage/opportunity state.

2. `score_iqr_t`
   - cross-sectional IQR of non-null Stage1 `pool_score` among parent members at t.
   - opportunity-strength dispersion.

3. `prior20_switch_rate_t`
   - number of target changes under Frozen OLS using the full frozen parent set over the previous 20 signal days, divided by observed days.
   - competition pressure.

4. `prior20_top1_tenure_t`
   - mean consecutive Top1 run length over the same previous 20 signal days.
   - persistence state, distinct from intrinsic trend lifetime.

5. `mean_pairwise_corr120_t`
   - mean pairwise close-return correlation of the parent pool over the preceding 120 trading days using available observations.
   - redundancy state.

No feature search or substitutions after outcome inspection.

## Model and evaluation

Effective unit is month. There are only 68 months; ETF rows are not independent observations.

Primary model:
- logistic regression with L2 penalty;
- fixed `C=1.0`;
- standardize features using training history only;
- strict expanding evaluation;
- first prediction only after at least 24 prior months;
- no hyperparameter search.

Baselines:
- expanding training-history majority class;
- previous-month target sign persistence.

Primary metrics:
- OOS ROC AUC when defined;
- balanced accuracy;
- sign accuracy;
- Brier score;
- metrics separately for 2021–24 and 2025–26 OOS portions where available.

Also report point-in-time feature association with continuous `size_contrast_t`, but do not select features from those associations.

## Interpretation

Support for identifiable conditional size state requires the frozen five-feature model to improve meaningfully over simple baselines in expanding OOS and not fail completely in the later era.

If it fails, conclude that the Stage1 regime-dependent size effect is not stably identifiable from this low-DoF point-in-time state. Do not respond by feature search or increasing model capacity on the same history. Stage3 should then weaken to a conservative fixed/range solution before member research.

If it succeeds, a later Stage3 substage may translate predicted direction/uncertainty into a coarse conservative size range. That translation must be frozen before any Stage4 composition optimization.
