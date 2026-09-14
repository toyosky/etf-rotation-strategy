# OURE Stage6I — Half-Year RF Horizon Diagnostic

Date: 2026-09-14
Status: preregistered before outcome inspection

## Question
Stage6G found almost no same-era K30 surrogate learnability for 2022-24 but much stronger signal for 2025-26. Was that mainly a regime difference, or did the unequal forecast horizons contaminate the comparison because 2022-24 used a ~3-year target while 2025-26 used a much shorter target?

## Frozen change from Stage6G
Change **only the target horizon**. Keep the Stage6G random forest, feature set, K, family construction, and grouped validation semantics fixed.

For every completed Jan/Jul decision point from 2022H1 through 2026H1:
- K = 30 non-cash ETFs; cash remains the frozen OLS cash proxy.
- point-in-time candidate pool at decision date, same current-metadata survivorship caveat as prior stages.
- X(U) = the same 19 whole-Universe features from the 126 sessions strictly before the decision date.
- Y(U) = frozen downstream OLS log wealth over the next 126 trading sessions only.
- generate K30 mutation families using only the past 126 sessions, using the frozen Stage6G family-library builder.
- 5-fold GroupKFold by family; near-related mutation families never cross train/validation within a fold.
- RF parameters frozen exactly as Stage6G: 800 trees, max_depth=7, min_samples_leaf=10, max_features=sqrt, bootstrap=True, random_state=20260914.
- no feature changes, hyperparameter tuning, threshold search, or outcome-driven filtering.

2026H2 partial is excluded from the primary analysis because a complete future 126-session label is unavailable.

## Per-period outputs
For each half-year:
- median 5-fold Spearman between RF prediction and realized 126-session log wealth;
- positive-fold count;
- median predicted-Top50 actual future percentile;
- median predicted-top-decile future log-wealth lift versus validation mean;
- feature importance summary for description only.

A period is called `learnable_strong` only if all frozen conditions hold:
1. median fold Spearman > 0.15;
2. at least 4/5 folds have positive Spearman;
3. median predicted-Top50 actual percentile > 0.65;
4. median top-decile log-wealth lift > 0.

This is the same strict Stage6G gate applied at a common 126-session horizon.

## Primary diagnostic gates
For the six complete 2022-24 half-years:
1. `old_median_ic_positive`: median of period-level median fold Spearman > 0.10.
2. `old_positive_period_breadth`: at least 4/6 period-level median Spearman values are > 0.
3. `old_horizon_improvement`: median 2022-24 half-year IC exceeds the frozen Stage6G 2022-24 long-horizon median IC (+0.0129) by at least +0.10.

Interpretation:
- 3/3 => strong support that long-horizon dilution materially caused the prior 2022-24 failure.
- 2/3 => partial support; forecast horizon mattered but regime instability remains.
- <=1/3 => horizon mismatch is insufficient; the 2022-24 weakness is primarily structural/regime-related under the frozen feature/model class.

Secondary comparison: report 2025H1, 2025H2, 2026H1 under the identical 126-session setup. Do not change any gate based on that comparison.

## Constraints
This is a mechanism diagnostic, not a production strategy and not a new RF tuning round. A favorable result does not authorize RF-guided K30 search until a separate X<=t state/transfer gate and genuinely later OOS evaluation are preregistered. A negative result must be frozen rather than rescued by model-capacity escalation.