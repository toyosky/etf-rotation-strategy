# OURE Stage6I — Half-Year RF Horizon Diagnostic Findings

Date: 2026-09-14
Run: `34862274663`
Artifact: `oure-stage6i-half-year-rf-horizon-34862274663`
Status: frozen
Decision: `strong_horizon_mismatch_support`

## Frozen question
Did Stage6G's weak 2022-24 RF surrogate result mainly come from using an excessively long (~3-year) target horizon, rather than from an intrinsically unlearnable 2022-24 K30 structure?

Only the target horizon changed. K=30, the 19 past-126-day whole-Universe features, mutation-family library construction, GroupKFold semantics, and RF parameters were all inherited unchanged from Stage6G.

Each Jan/Jul decision point used:
- X(U): 19 K30 features from the 126 sessions strictly before the decision date;
- Y(U): frozen downstream OLS log wealth over the next 126 sessions;
- 2496 K30 samples / 676 combination families per period;
- 5-fold GroupKFold by family;
- RF: 800 trees, max_depth=7, min_samples_leaf=10, max_features=sqrt, bootstrap=True, fixed seed.

2026H2 was excluded because a complete future-126-session label is unavailable.

## Primary diagnostic gate: 3/3 PASS
For the six complete 2022-24 half-years:
- median of period-level median fold Spearman = **+0.3799**;
- all **6/6** periods have positive median fold Spearman;
- frozen Stage6G 2022-24 long-horizon median fold Spearman = **+0.0129**;
- half-year minus long-horizon IC = **+0.3670**.

Preregistered gates:
1. old median IC > +0.10: PASS;
2. at least 4/6 positive periods: PASS (6/6);
3. improvement over Stage6G long horizon >= +0.10: PASS (+0.367).

Therefore the frozen decision is `strong_horizon_mismatch_support`.

## Period-by-period results
| period | median fold Spearman | positive folds | predicted Top50 actual pct | top-decile log lift | strict strong-learnable gate |
|---|---:|---:|---:|---:|---|
| 2022H1 | +0.251 | 5/5 | 0.681 | +0.0737 | PASS |
| 2022H2 | +0.443 | 5/5 | 0.819 | +0.1209 | PASS |
| 2023H1 | +0.491 | 5/5 | 0.751 | +0.1072 | PASS |
| 2023H2 | +0.140 | 4/5 | 0.456 | -0.0109 | FAIL |
| 2024H1 | +0.317 | 5/5 | 0.563 | +0.0164 | FAIL |
| 2024H2 | +0.455 | 5/5 | 0.679 | +0.1197 | PASS |
| 2025H1 | +0.348 | 5/5 | 0.545 | +0.0239 | FAIL |
| 2025H2 | +0.049 | 3/5 | 0.428 | -0.0188 | FAIL |
| 2026H1 | +0.738 | 5/5 | 0.788 | +0.2378 | PASS |

Strict strong-learnable periods: `2022H1, 2022H2, 2023H1, 2024H2, 2026H1`.

The 2025-26 median period IC under the same 126-session horizon is +0.3481 and all 3/3 period medians are positive, so the common-horizon comparison no longer supports a simple '2022-24 unlearnable / 2025-26 learnable' dichotomy.

## Main interpretation
The earlier Stage6G contrast was materially confounded by unequal target horizons. Using 2022-start features to predict a three-year 2022-24 terminal value was too long for a dynamic Universe problem.

The corrected result is:

> **K30 set value is often learnable within a roughly half-year horizon in both old and new eras, but learnability strength itself varies strongly by half-year.**

This shifts the research target from 'which era supports RF' toward:

`X_t(U) -> V_{t:t+126}(U)` with periodic Universe re-construction,

rather than trying to learn one static K30 value over multi-year horizons.

## Important nuance
A positive median rank IC does not guarantee the extreme top of the RF ranking is reliable. 2023H2 and 2024H1 have positive median IC but fail the strict Top50/top-decile gates; 2025H1 is similar. 2025H2 is weak on both ranking and top-tail selection. Therefore RF-guided combinatorial optimization can still exploit model error if it chases the predicted maximum.

The strong result is about **cross-sectional value ranking signal at a 126-session horizon**, not yet about safe optimization of the RF argmax.

## Feature importance is unstable across periods
Examples of top features differ materially:
- 2022H1: past126 drawdown, past126 log growth, leader HHI;
- 2022H2: invested ratio, coverage, mean pair trend Jaccard;
- 2023H1: leader HHI/effective leader count/coverage efficiency;
- 2024H2: mean pair trend Jaccard, simultaneous competitors, eligible count;
- 2026H1: past126 log growth, switch counterfactual gain, Top1-Top2 gap.

Feature importance is descriptive only and does not justify period-specific feature selection or RF tuning.

## Frozen conclusions
1. Stage6G's weak 2022-24 result should **not** be interpreted as 'RF cannot learn 2022-24 K30 value'.
2. The primary problem was largely the multi-year forecast horizon; the preregistered horizon diagnostic passes 3/3.
3. A 126-session K30 value function shows positive ranking information in every complete 2022-24 half-year and every complete 2025-26 half-year tested.
4. Learnability magnitude and top-tail reliability remain time-varying; 2023H2 and 2025H2 are clear weak periods.
5. The natural construction cadence is therefore periodic/dynamic (roughly half-year in this experiment), not a one-time multi-year Universe selection.
6. Do not tune the RF or features on these outcomes. Before any RF-guided K30 optimizer is promoted, search behavior and OOD/model-exploitation safeguards must be preregistered and final judgment must use genuinely later unseen data.

## Limitations
- This is same-period grouped CV, not chronological future deployment.
- Current metadata guards retain survivorship-metadata risk.
- Candidate K30 samples are generated by the frozen heuristic family builder, not uniformly over all C(N,30) combinations.
- GroupKFold reduces mutation-family leakage but cannot make overlapping ETF sets statistically independent in a strict sense.
