# OURE Stage6F — Random-Forest Surrogate Value Function for K30

Date: 2026-09-14
Status: preregistered before outcome inspection

## Question
Within each broad market era separately, do pre-era 126-session whole-Universe features contain enough information for a random forest to predict the **final downstream OLS value of an unseen K30 Universe**?

This is a mechanism/learnability experiment, not yet a walk-forward trading rule.

The target is explicitly portfolio value, not ETF membership:

`Y(U) = final log wealth of frozen OLS rotation run on K30 Universe U over the era`.

If a sufficiently stable mapping exists, the RF can later be used as a surrogate objective inside a K30 combinatorial search:

`U* = argmax_{|U|=30} RF(X_pre(U))`.

## Eras
- Era A: 2022-01 start through 2024-12-31.
- Era B: 2025-01 start through 2026-09-09 (partial broad era by construction).

For each era, the point-in-time candidate pool is frozen at the era start using the existing availability guard. Fix15 identity is never used.

## X: pre-era information only
For each K30 U, compute the following over the 126 trading sessions immediately before the era starts:

1. `past126_log_growth`
2. `past126_max_drawdown`
3. `invested_ratio`
4. `coverage_share`
5. `mean_eligible_count`
6. `mean_competitors_when_covered`
7. `coverage_efficiency`
8. `leader_switch_rate`
9. `mean_top1_tenure`
10. `median_top1_tenure`
11. `short_run_le2_share`
12. `top1_top2_gap_median`
13. `active_leader_count`
14. `leader_hhi`
15. `effective_leader_count`
16. `mean_pair_trend_jaccard`
17. `max_pair_trend_jaccard`
18. `productive_switch_share`
19. `switch_counterfactual_gain_mean`

No feature is added after outcome inspection.

## Y
Primary continuous target:

`future_log_growth = log(final wealth / initial wealth)`

over the whole era under the frozen daily OLS evaluator and frozen transaction cost semantics.

Secondary derived evaluation target only:
- within-library future percentile rank.

RF is trained as a regression model on `future_log_growth`, not on a Top50 binary label.

## K30 library construction
The purpose is to create a large and heterogeneous set of K30s without using future outcomes.

Per era:
1. Rank singletons using only pre-era 126-session data.
2. Construct several past-only greedy K30 bases.
3. Add structurally diverse random bases from both the past singleton shortlist and the full point-in-time pool.
4. Require base-set Jaccard similarity <= 0.55 when forming mutation families.
5. Around each base, generate local K30 mutations by replacing 1-6 members; each base and all descendants carry one immutable `family_id`.
6. Add broad full-pool random K30s as independent singleton families.

Target scale: roughly 3,000-5,000 unique K30 samples per era. Exact count is mechanical, not tuned from outcomes.

## Leakage control: family-group validation
Ordinary random row split is prohibited.

K30s within one mutation family can differ by only a few ETFs. Therefore the primary validation is 5-fold `GroupKFold` by `family_id`: the full family must be entirely in train or validation.

Additionally, base families themselves are constrained to Jaccard <= 0.55 at creation. Broad random singleton families are naturally low-overlap controls.

This is still **within-era** validation and therefore only a mechanism/learnability test. It is not chronological OOS evidence.

## Random forest — frozen
Use `RandomForestRegressor` with:
- `n_estimators=800`
- `max_depth=7`
- `min_samples_leaf=10`
- `max_features='sqrt'`
- `bootstrap=True`
- `random_state=20260914`
- `n_jobs=-1`

No hyperparameter search.

## Primary validation metrics
For each era and fold:
1. Spearman correlation between predicted and actual `future_log_growth`.
2. Predicted Top50 mean actual future percentile.
3. Actual-Top50 capture rate by predicted Top50.
4. RF top-decile mean future log-growth minus validation-set mean.

Feature importance is descriptive only and cannot rescue a failed gate.

## Preregistered learnability gate
An era passes only if all are true across its 5 group folds:
1. median validation Spearman > +0.15;
2. >= 4/5 folds have positive Spearman;
3. median predicted-Top50 actual percentile > 0.65;
4. median top-decile future-log lift > 0.

Overall Stage6F conclusion:
- `both_eras_learnable` only if both eras pass independently;
- `era_specific_learnability` if exactly one passes;
- `not_learnable_from_frozen_X` if neither passes.

Do not tune model, feature list, family split, thresholds, era endpoints, or sample-generation recipe after seeing outcomes to rescue this stage.

## Secondary cross-era transfer (not part of primary gate)
After primary gates are frozen, train one RF on all Era-A samples and evaluate on all Era-B samples, and vice versa. Report Spearman only as descriptive evidence about structural transfer. No tuning from this result.

## Interpretation boundary
Passing means only:

> pre-era whole-set features contain learnable information about which **unseen K30 combinations** perform better within that same era.

It does not yet show that a model trained on past eras can choose K30 in a future era. That would require a later strict chronological test and RF-guided combinatorial search.
