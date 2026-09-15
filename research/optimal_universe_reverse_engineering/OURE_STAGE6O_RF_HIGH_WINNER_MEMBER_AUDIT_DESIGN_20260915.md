# OURE Stage6O — RF-high Winner-Member Audit and Chronological Admission Test

Date: 2026-09-15
Status: preregistered before outcome inspection

## Question
Inside the K30 combinations that already pass the frozen first-layer RF coarse filter, which ETF members are disproportionately associated with the next 126-session winner combinations, what did those members look like at decision time, and can those member-level traits prospectively identify better members in the next block?

This stage explicitly changes the unit of analysis from whole-K30 ranking to member admission value.

## Frozen upstream setup
- Reuse Stage6K strict non-overlapping 126-session blocks B01..B09.
- K=30, downstream OLS evaluator, candidate-pool rules, deterministic K30 family generation, 19 first-layer whole-set features, and first-layer RF are unchanged.
- For target blocks B02..B09, fit the first-layer RF on the immediately previous completed block only and score the target block.
- RF-high is fixed at the top 20% of first-layer RF predictions in the target block (approximately 500 K30 sets).
- No symbol identity, future member path, future member return, or future-derived variable may enter X.

## Future labels used only for historical research
For each target block, future 126-session OLS value of every RF-high K30 is already historically realized and is used only as Y.

### Set winner / loser labels
- Winner sets: top 20% of RF-high K30 by future 126-session OLS log-growth.
- Loser sets: bottom 20% by the same outcome.

### Member enrichment diagnostics
For each ETF member appearing in at least 20 RF-high K30 sets, report:
- RF-high presence count/rate;
- winner presence rate and loser presence rate;
- winner enrichment = P(member | winner set) - P(member | all RF-high sets);
- winner-minus-loser presence difference.

### Primary member future-value label
To reduce confounding by first-layer RF score, split RF-high K30 into 10 fixed quantile strata by first-layer RF prediction. For each ETF and each stratum with at least 3 present and 3 absent sets, compute:

`delta_s = mean(future_log_growth | member present, stratum s) - mean(future_log_growth | member absent, stratum s)`.

The member's `conditional_future_marginal` is the presence-count-weighted mean of valid `delta_s` values. This is an association / conditional marginal label, not a causal effect.

Within each target block, rank this label to `future_member_rank_pct`.

## Past-only member features at decision time
All features are computed using information available no later than t-1 over the trailing 126 sessions and the contemporaneous RF-high candidate family generated at t.

### A — standalone OLS harvestability
- `singleton_log126`: OLS log-growth when the ETF is the only risk member over the trailing 126 sessions.

### B — eligibility / score state
- `elig_participation126`: fraction of trailing 126 sessions with finite OLS score.
- `score_last`.
- `score_mean126`.
- `score_p90_126`.
- `score_recent_minus_prior21`: mean score over the most recent 21 sessions minus the preceding 21 sessions, using finite observations.

### C — price momentum / risk state
- `ret21`, `ret63`, `ret126`.
- `vol21`, `vol63`, `vol126` from close-to-close returns.
- `maxdd63`, `maxdd126`.
- `dist_high21`, `dist_high63` = current close / trailing high - 1.

### D — contemporaneous RF-high context
These are allowed because RF-high is constructed entirely from X<=t information.
- `rfhigh_presence_rate`: fraction of RF-high K30 containing the ETF.
- `rfhigh_mean_rf_pred_when_present`: mean first-layer RF prediction among RF-high sets containing the ETF.
- `rfhigh_mean_past126_set_when_present`: mean trailing126 whole-K30 OLS log-growth among RF-high sets containing the ETF.
- `rfhigh_comember_corr_mean`: co-occurrence-weighted mean trailing126 return correlation with its co-members inside RF-high.
- `rfhigh_comember_hhi`: concentration of co-member occurrences.

No future information enters these features.

## Stage 1 — descriptive winner-member audit
For each B02..B09 block:
1. rank members by `conditional_future_marginal` and winner enrichment;
2. define future-good members as the top quartile of `future_member_rank_pct` and future-bad members as the bottom quartile;
3. for every past-only feature, compute standardized good-minus-bad effect.

A feature is called historically stable only if:
- finite in at least 6/8 blocks;
- same effect direction in at least 6/8 blocks;
- median absolute standardized effect >= 0.15.

Stage-1 mechanism gate passes if at least 3 features from at least 2 feature families satisfy this rule.

Ticker identities may be reported descriptively but may not be used as predictors or promoted as persistent winners.

## Stage 2 — strict chronological member admission test
Run only as an independent predictive test; Stage 1 does not alter the model feature set.

### Model
Fixed `RandomForestRegressor` on all preregistered past-only member features:
- n_estimators=600
- max_depth=5
- min_samples_leaf=5
- max_features=`sqrt`
- random_state=20260915
- n_jobs=4

Training label is `future_member_rank_pct`, not raw future value, to reduce period-scale differences.

### Chronology
Test B05..B09. For each target block, train only on completed member rows from B02 through the immediately preceding block. No same-block CV is deployment evidence. No hyperparameter search or feature selection.

### Baselines
Evaluate the same target blocks using simple member scores:
- `singleton_log126`;
- `ret126`;
- `elig_participation126`;
- `rfhigh_mean_past126_set_when_present`.

### Metrics
Per target block and aggregated across B05..B09:
- Spearman(predicted member score, `future_member_rank_pct`);
- positive-IC block count;
- mean actual future-member percentile of predicted top 10 members;
- mean `conditional_future_marginal` of predicted top 10 minus the eligible-member mean.

### Frozen predictive gate
The RF member-admission model is supported only if all hold:
1. median member-rank Spearman > +0.10;
2. positive Spearman in at least 4/5 target blocks;
3. median predicted-top10 actual percentile > 0.60;
4. median top10 conditional-future-marginal lift > 0;
5. median IC exceeds the best simple baseline's median IC by at least +0.05.

## Interpretation rules
- Stage 1 PASS / Stage 2 FAIL: future winner combinations do contain members with repeatable historical traits, but those traits are not yet prospectively strong enough to construct the next member set.
- Stage 1 PASS / Stage 2 PASS: member-level admission value is a promising route and may justify a separately preregistered K30 constructor.
- Stage 1 FAIL: do not rescue via ticker identities, feature search, thresholds, or stronger models on the same history.
- Regardless of outcome, do not directly optimize or search K30 membership from future labels in this stage.
