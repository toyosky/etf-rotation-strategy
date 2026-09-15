# OURE Stage6N — Frozen Nonlinear Second-Layer Test Findings

Date: 2026-09-15
Run: `34911172587`
Artifact: `oure-stage6n-xgboost-second-layer-34911172587`
Status: frozen formal non-pass
Decision: `xgboost_second_layer_not_supported`

## Question
Stage6L found stable internal structural differences between future true-good and false-positive K30 sets inside the first-layer RF top-20%, while a chronological Ridge residual detector failed. Stage6N tested whether nonlinear model misspecification was the main reason for that failure.

The design was preregistered before outcome inspection. No hyperparameter search, feature search, window tuning, early-stopping tuning, or result-conditioned model selection was used.

## Frozen setup
- strict Stage6K non-overlapping 126-session blocks;
- target blocks B05..B09;
- first-layer K30 RF unchanged;
- RF-high = top 20% of first-layer predictions, 500 sets per target block;
- same 47 Stage6L internal past-only features;
- chronological training on all earlier completed RF-high blocks only;
- compared first-layer RF, past126 set-log-growth baseline, Ridge47 residual, frozen XGBoost residual regression, and frozen XGBoost pairwise ranker.

Frozen XGBoost configuration: 300 trees, depth 3, learning rate 0.03, min_child_weight 10, subsample/colsample 0.8, L1=1, L2=10.

## Aggregate results across B05..B09

| Rule | Median within-RF-high Spearman | Positive blocks | Median Top50 actual percentile | Median top-decile future-log lift |
|---|---:|---:|---:|---:|
| first-layer RF | -0.0866 | 1/5 | 0.4544 | -0.0174 |
| past126 set log-growth | **+0.1459** | **4/5** | **0.5588** | **+0.0524** |
| Ridge47 residual | -0.1563 | 1/5 | 0.4345 | -0.0289 |
| XGBoost residual | -0.1307 | 1/5 | 0.4325 | -0.0203 |
| XGBoost pairwise ranker | -0.0344 | 2/5 | 0.4878 | -0.0067 |

Residual-prediction Spearman:
- Ridge47 median: **-0.0905**, positive 1/5;
- XGBoost residual median: **+0.0553**, positive 3/5.

Thus XGBoost residual improves the residual-learning diagnostic materially versus Ridge, but not enough to produce stable final ranking or top-tail value.

## Pairwise ranker block behavior
Within-RF-high Spearman / Top50 actual percentile / top-decile log lift:
- B05: -0.204 / 0.423 / -0.0231
- B06: -0.034 / 0.488 / -0.0067
- B07: **+0.375 / 0.655 / +0.0909**
- B08: -0.117 / 0.385 / -0.0707
- B09: +0.121 / 0.494 / -0.0014

The nonlinear pairwise model can work strongly in an individual block (B07) and modestly in B09, but the mapping is not stable enough across the five chronological targets.

## Frozen primary gate — M2 pairwise ranker
Required all four:
1. median within-RF-high IC > +0.10: **FAIL** (-0.0344);
2. positive IC in >=4/5 blocks: **FAIL** (2/5);
3. median Top50 actual percentile gain vs first-layer RF >= +0.05: **FAIL** (0.4878 - 0.4544 = +0.0334);
4. median top-decile future-log lift positive and above RF: **FAIL** (-0.0067).

Primary result: **formal FAIL**.

## Frozen secondary gate — M1 XGBoost residual
Required:
- median residual IC > +0.10: **FAIL** (+0.0553);
- positive residual IC >=4/5: **FAIL** (3/5);
- median Top50 actual percentile improves Ridge by >= +0.05: **FAIL** (XGB 0.4325 vs Ridge 0.4345).

Secondary result: **FAIL**.

## Important interpretation
Stage6N changes one part of the interpretation but not the deployability conclusion.

1. **Ridge misspecification was real to some degree.** XGBoost changes residual median IC from negative (-0.0905) to positive (+0.0553) and produces useful signal in some blocks. Therefore Stage6L Ridge failure should not be read as proof that the second layer is purely linear-noise-free or unlearnable by any nonlinear method.
2. **Model capacity alone does not solve the transfer problem.** The preregistered nonlinear residual and pairwise models both fail chronological aggregate gates. The strongest pairwise block (B07) does not generalize to B05/B06/B08/B09.
3. **Conditioning on RF-high removes most first-layer discrimination.** Inside the top-20% RF set, first-layer RF itself has median Spearman -0.0866. This is consistent with Stage6K's top-tail weakness: RF is useful as a coarse filter but not as an internal ranker of its own high-score tail.
4. **The simple past126 baseline is the strongest result in this stage.** Within the already RF-filtered top-20%, current past126 set log-growth has median IC +0.1459, 4/5 positive blocks, median Top50 percentile 0.5588 and positive top-decile lift +0.0524. This was a preregistered secondary baseline, not a tuned model. It suggests that a coarse RF filter followed by a simple current-strength rerank may be more robust than learning a complex residual mapping on the current history.

The past126 result is a new hypothesis, not authorization to deploy it or retroactively tune thresholds. A dedicated preregistered cascade test would be required before promotion.

## Frozen conclusion
The user's concern about prematurely rejecting complex algorithms was valid: XGBoost demonstrates that nonlinear capacity can recover signal that Ridge misses. However, this one-shot frozen test does **not** show that XGBoost can reliably identify the true-good K30 sets inside the RF-high tail across time.

Current evidence therefore supports:

`RF coarse filter -> internal tail remains difficult -> nonlinear residual/ranking models improve some blocks but are unstable`.

Do not tune XGBoost depth/tree count/learning rate/features/window on the same history. Do not authorize CEM/GA/swap search from Stage6N. The clearest new research hypothesis is the simpler cascade `RF coarse filter -> past126 rerank`, which should be evaluated separately under a frozen design if pursued.
