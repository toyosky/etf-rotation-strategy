# OURE Stage6N — Frozen Nonlinear Second-Layer Test

Date: 2026-09-15
Status: preregistered before outcome inspection

## Question
Stage6L showed that, inside the first-layer RF top-20% K30 sets, future true-good and false-positive sets have repeatable internal past-only structural differences, while a low-complexity Ridge residual detector failed chronologically. Is that failure materially due to linear model misspecification rather than absence of exploitable second-layer structure?

## Frozen setup
- Reuse strict Stage6K non-overlapping 126-session blocks B01..B09.
- K=30 noncash, downstream OLS, first-layer 19 features, first-layer RF, 126-session horizon, and RF-high top 20% are unchanged.
- Recompute the same 47 Stage6L internal past-only features. No symbol ID, future member contribution, future leader path, or future-derived X is allowed.
- Target blocks: B05..B09. For each target block, training uses all earlier completed RF-high blocks only. No same-period CV is deployability evidence.
- No hyperparameter search, early-stopping search, feature search, threshold tuning, or result-conditioned retraining.

## Models
### M0 — Ridge47 residual baseline
Use all 47 internal features, standardized from historical training data only, Ridge(alpha=10). Target is Stage6L residual rank:
`future_rank_pct - first_layer_rf_pred_rank_pct`.
This isolates model-class effects because M0/M1 use identical X and target.

### M1 — XGBoost residual regression
`XGBRegressor` with fixed parameters:
- n_estimators=300
- max_depth=3
- learning_rate=0.03
- min_child_weight=10
- subsample=0.8
- colsample_bytree=0.8
- reg_alpha=1.0
- reg_lambda=10.0
- objective=`reg:squarederror`
- n_jobs=4
- random_state=20260915

Target: same residual rank as M0.

Final M1 ranking score within RF-high is `first_layer_rf_pred_rank_pct + predicted_residual`.

### M2 — XGBoost pairwise ranker (primary nonlinear model)
`XGBRanker` with the same tree/regularization parameters, objective=`rank:pairwise`, n_estimators=300. Training groups are historical 126-session target blocks; rows are ordered by block and group sizes are supplied explicitly.

Label is `future_rank_within_high` in [0,1]. No first-layer RF prediction is supplied as a feature. M2 therefore asks whether the new internal structure can directly re-rank sets that already passed the RF-high coarse filter.

## Evaluation within each RF-high target block
For M0/M1/M2 and first-layer RF baseline report:
1. Spearman(score, future_rank_within_high).
2. Top50 mean actual `future_rank_within_high`.
3. Top-decile future log-growth lift versus the full RF-high population.
4. For residual models, Spearman(predicted residual, realized residual rank).

Also report simple `past126_log_growth` ranking if available as a secondary baseline.

## Frozen primary gate for M2
M2 is considered chronologically supported only if all hold across B05..B09:
1. median within-RF-high Spearman > +0.10;
2. positive Spearman in at least 4/5 target blocks;
3. median Top50 actual percentile exceeds first-layer RF baseline by >= +0.05;
4. median top-decile future log-growth lift is positive and exceeds the first-layer RF baseline.

## Secondary gate for M1
M1 receives a secondary nonlinear-residual signal only if:
- median residual Spearman > +0.10;
- positive residual Spearman in at least 4/5 targets;
- median Top50 actual percentile improves M0 by >= +0.05.

M1 cannot rescue M2's primary gate.

## Interpretation rules
- If M2 passes, this supports nonlinear/pairwise model misspecification as an important part of Stage6L Ridge failure. It does not yet authorize CEM/GA/swap search; a separate preregistered construction stage is required.
- If M2 fails but M1 passes, conclude nonlinear residual signal exists but direct top-tail reranking remains unproven.
- If both fail, model capacity alone does not solve the current second-layer transfer problem under this frozen test. Do not tune XGBoost on the same history.
