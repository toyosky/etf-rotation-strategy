# OURE Stage6M — Second-Layer Sample-Size Diagnostic Findings

Date: 2026-09-15
Status: frozen diagnostic
Decision: `sample_size_not_primary_explanation`

## Question
Stage6L found repeatable internal structural differences inside first-layer RF-high K30 sets, but the chronological Ridge residual detector failed. Was that mainly because there were too few independent 126-session training blocks?

## Frozen setup
The design was preregistered before inspecting Stage6M outcomes. Stage6L's artifact was reused without changing K=30, the first-layer RF, RF-high top20%, 126-session horizon, residual target, or Ridge alpha=10.

To remove target-period composition as a confound, the primary learning curve uses the same four target blocks B06..B09 for every training-history length N=1,2,3,4. For each target, N means the N immediately preceding completed blocks only.

Two frozen feature curves were evaluated:
- Curve A: the 12 Stage6L globally stable structural traits. This is a best-case diagnostic only because those traits were discovered on the same history.
- Curve B: all 47 preregistered Stage6L internal features.

## Curve A — 12 frozen stable traits
Median chronological residual IC across common targets B06..B09:
- N=1: **-0.0243**
- N=2: **+0.1072**
- N=3: **-0.0069**
- N=4: **-0.0759**

Positive target-block counts out of 4:
- N=1: 2/4
- N=2: 3/4
- N=3: 2/4
- N=4: 2/4

Median Top50 percentile gain versus the first-layer RF within RF-high:
- N=1: **-0.0137**
- N=2: **+0.0998**
- N=3: **+0.0667**
- N=4: **-0.0067**

Per-target paired residual-IC change N=4 minus N=1:
- B06: -0.0089
- B07: +0.1207
- B08: -0.0763
- B09: -0.1475

Median paired delta: **-0.0426**; mean: **-0.0280**; only 1/4 targets improve when going from one prior block to four.

## Frozen primary gates
1. Median IC N=4 minus N=1 >= +0.10: **FAIL** (-0.0517).
2. Median IC non-decreasing in at least 2/3 adjacent N steps: **FAIL** (only 1/3; N1->N2 improves, N2->N3 and N3->N4 deteriorate).
3. N=4 IC positive in at least 3/4 common targets: **FAIL** (2/4).
4. Median Top50 gain at N=4 > N=1: **PASS** (-0.0067 > -0.0137), but both are negative.

Only 1/4 gates pass, so the preregistered decision is `sample_size_not_primary_explanation`.

## Curve B — all 47 internal features
Median residual IC:
- N=1: **-0.2183**
- N=2: **-0.0873**
- N=3: **-0.1564**
- N=4: **-0.1538**

Positive target-block counts: 0/4, 0/4, 0/4, 1/4 respectively.

This curve also does not show a monotone learning curve. More history modestly reduces the severe N=1 failure but never reaches positive median IC and deteriorates again after N=2.

## Interpretation
The current evidence does **not** support the simple hypothesis:

`more independent historical blocks -> steadily better second-layer mapping`.

Instead, both curves have their best aggregate point at N=2 and then weaken as older blocks are added. On the best-case 12-trait curve, N=4 is worse than N=1 in median IC and in 3 of 4 paired target comparisons.

This pattern is more consistent with **mapping drift / stale-history contamination** than with pure time-sample scarcity. It does not prove sample size is irrelevant: nine total 126-session blocks remain a very small historical record, and genuinely new future blocks could still improve estimation. But current history gives no empirical learning-curve evidence that simply accumulating more old blocks solves Stage6L's failure.

The distinction is important:
- Stage6L says internal structural signal exists in matched hindsight comparisons.
- Stage6M says the mapping from that structure to next-block residual value does not become more stable merely by feeding Ridge more prior blocks.

Therefore the priority should not be to synthesize more K30 rows or blindly pool a longer historical window. A future branch would need either genuinely new independent time blocks or a new hypothesis about how the structure-to-value mapping changes with state/regime.

## Restrictions
Do not promote N=2 as a strategy: its apparent superiority is observed after this diagnostic and is therefore post-hoc. Do not tune N, alpha, features, or RF-high threshold on this history.
