# OURE Stage6E — Random-Forest K30 Set-Ranking Test

Date: 2026-09-14
Status: preregistered before outcome inspection
User-directed model escalation: random forest.

## Question
With non-cash K fixed at 30, can set-level information available in the trailing 126 sessions rank K30 ETF Universes by their next-126-session downstream OLS value?

This stage predicts the value of the whole K30 set. It does not assume a known K29 core and does not use member identity as a feature.

## Point-in-time protocol
Decision dates: first trading session on/after Jan 1 and Jul 1, 2022–2026, when 252-session history is available.

At decision date t:
1. Build the point-in-time ETF pool with >=240 finite closes in the prior 252 sessions, daily bars available, and no leveraged/inverse flag.
2. Generate a fixed-K30 candidate library using ONLY data <= t: past-126 singleton shortlist, multiple greedy K30 paths, local/random perturbations, and same-K random sets. Future data are not used to generate validation candidates.
3. De-duplicate near-identical Universes using member Jaccard >0.90, ordered only by past-126 log growth.
4. Compute frozen trailing-126 set features X_t(U).
5. Evaluate each already-generated U during the next 126 sessions and convert future log growth to a within-period percentile rank Y_t(U) in [0,1]. Top50 is retained only as a diagnostic label.

The final incomplete 2026H2 period is descriptive only and excluded from formal gates.

## Frozen feature set
No ETF symbols, names, sectors, or future identities are features. No feature search after outcome inspection.

- past126_log_growth
- past126_max_drawdown
- invested_ratio
- coverage_share
- mean_eligible_count
- mean_competitors_when_covered
- coverage_efficiency
- leader_switch_rate
- mean_top1_tenure
- median_top1_tenure
- short_run_le2_share
- top1_top2_gap_median
- active_leader_count
- leader_hhi
- effective_leader_count
- mean_pair_trend_jaccard
- max_pair_trend_jaccard
- productive_switch_share
- switch_counterfactual_gain_mean

Missing feature values are imputed using TRAINING-period medians only.

## Frozen random forest
RandomForestRegressor only:
- n_estimators = 500
- max_depth = 5
- min_samples_leaf = 20
- max_features = "sqrt"
- bootstrap = true
- random_state = 20260914
- n_jobs = -1

No hyperparameter tuning and no validation-set model selection.

## Validation
Strict expanding-time validation. A test half-year may use only labeled periods whose future windows ended before that test decision date. Require at least two completed training periods before issuing a formal OOS prediction.

Metrics per OOS period:
- Spearman(predicted score, actual future percentile rank), primary rank IC;
- actual mean percentile of predicted Top50;
- actual Top50 capture@50;
- percentile and future return/log growth of the model's top-ranked Universe;
- past126 winner as a simple baseline.

Highly similar Universes within a decision period are de-duplicated before training/testing, but the split itself is always chronological, never random.

## Pre-registered gates
Primary evidence is considered promising only if, across complete formal OOS half-years:
1. median OOS rank IC > +0.10;
2. at least 60% of OOS periods have rank IC > 0;
3. predicted Top50 mean actual percentile > 0.60 in median OOS period;
4. performance does not depend solely on one era: median rank IC must be >0 in every era having >=2 formal OOS periods.

If these fail, freeze RF set-level identification as failed. Do not tune depth, windows, features, labels, Top-N, or Jaccard threshold to rescue this stage.

## Interpretation constraints
- Candidate library is heuristic and finite, not the full C(N,30) space.
- A positive result establishes ranking information within executable past-generated K30 libraries, not proof of the global optimal 30.
- Feature importance is descriptive after OOS validation; it is not causal.
- Current metadata guards retain known survivorship-metadata caveat.
