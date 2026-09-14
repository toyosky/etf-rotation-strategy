# OURE Stage6E — Random-Forest K30 Set-Ranking Findings

Date: 2026-09-14
Run: `34854353654`
Artifact: `oure-stage6e-rf-k30-rank-34854353654`
Status: frozen_failed_primary_gate
Decision: `rf_k30_set_rank_not_stably_oos_identifiable`

## Frozen question
With non-cash K fixed at 30, can a preregistered random forest use only trailing-126-session whole-Universe structure to rank past-generated K30 candidate Universes by their next-126-session downstream OLS value?

The model was explicitly requested by the user. Hyperparameters, features, label, chronological split and gates were frozen before outcome inspection. Validation libraries were generated using past-only information; future data were used only for labels.

## Dataset
Point-in-time pools grew from 265 ETFs at 2022-01-04 to 827 at 2026-01-05 (962 by the partial 2026-07-01 decision).

Each decision period retained about 522–544 near-duplicate-controlled K30 candidates after Jaccard >0.90 de-duplication. Candidate generation used only past-126 information: multiple greedy K30 paths, local perturbations, shortlist same-K controls and full-pool same-K controls.

Future label: within-period percentile rank of next-126-session frozen downstream OLS log growth.

Formal expanding OOS tests required at least two fully realized prior periods and excluded incomplete 2026H2. Because a 126-session label can finish slightly after the next Jan/Jul decision date, only labels fully realized before each test date were admitted to training.

## Frozen RF
RandomForestRegressor:
- n_estimators = 500
- max_depth = 5
- min_samples_leaf = 20
- max_features = sqrt
- bootstrap = true
- random_state = 20260914

19 preregistered set-level features; no ETF identity features; no tuning after results.

## Primary gate: FAIL 0/4
Aggregate formal OOS:
- formal OOS periods: 6
- median OOS Spearman rank IC: **-0.0257**
- positive IC share: **50.0%**
- median actual future percentile of predicted Top50: **0.4710**
- era median rank IC: 2022–24 **-0.0783**, 2025–26 **+0.0270**

Preregistered gates:
1. median IC > +0.10: FAIL
2. >=60% periods IC >0: FAIL
3. median predicted-Top50 actual percentile >0.60: FAIL
4. median IC positive in each era with >=2 OOS periods: FAIL

## OOS period detail
| test decision | era | rank IC | predicted Top50 mean actual pct | RF top1 actual pct | past126 winner actual pct |
|---|---|---:|---:|---:|---:|
| 2023-07-03 | 2022–24 | -0.078 | 0.446 | 0.011 | 0.501 |
| 2024-01-02 | 2022–24 | +0.223 | 0.622 | 0.752 | 0.150 |
| 2024-07-01 | 2022–24 | -0.360 | 0.284 | 0.298 | 0.608 |
| 2025-01-02 | 2025–26 | -0.349 | 0.393 | 0.468 | 0.573 |
| 2025-07-01 | 2025–26 | +0.027 | 0.496 | 0.599 | 0.138 |
| 2026-01-05 | 2025–26 | +0.280 | 0.688 | 0.721 | 0.972 |

The RF therefore has isolated good half-years but no stable temporal transfer. In particular the strong positive 2024H1 and 2026H1 periods are offset by large negative 2024H2 and 2025H1 ICs.

Across the six formal OOS periods:
- RF top-ranked Universe median future percentile: ~0.533
- simple past126 winner median future percentile: ~0.537
- linked RF-top1 forward return: ~+75.5%
- linked past126-winner forward return: ~+105.9%

These linked returns are secondary because the primary object is cross-sectional rank identification, but they do not rescue the RF conclusion.

## Feature importance: descriptive only
Mean impurity importance across OOS folds is led by:
1. mean_pair_trend_jaccard ~0.151
2. past126_log_growth ~0.090
3. coverage_share ~0.084
4. invested_ratio ~0.066
5. coverage_efficiency ~0.065
6. max_pair_trend_jaccard / mean competitors / mean eligible count ~0.059–0.063

Mean pair trend overlap is the top feature in both era subsets, but because OOS prediction fails, feature importance must not be promoted as a production signal or causal mechanism. Random-forest importance also has no direction by itself.

## Interpretation
This experiment directly tests the user's proposed route: fix K30, compute trailing structural indicators for whole K30 Universes, train a random forest and ask whether it can recognize future high-value sets.

Under strict chronological validation, the answer is currently **no**. The past-126 set state contains patterns that a random forest can exploit in some periods, but those nonlinear mappings are not stable across the 2022–24 / 2025–26 transition or even between adjacent half-years.

This is stronger negative evidence than Stage6D's K29+1 result because Stage6E does not assume a hindsight K29 core; it attempts whole-K30 ranking directly.

The failure does not prove no predictive structure exists. It says the frozen 19-feature / 126-session RF mapping is not robust enough to use as a unified K30 constructor.

## Frozen conclusion
1. Keep K≈30 as an engineering research anchor, not a universal optimum.
2. Do not use this RF as a production K30 selector.
3. Do not tune depth, number of trees, feature subset, target horizon, Top-N or validation threshold to rescue Stage6E.
4. The next informative question is not 'which RF parameters are better', but whether the mapping is **state-conditional**: can X<=t first identify which historical relationship/regime should govern K30 selection?
5. Stage6D's prior-challenge warning remains a separate conditional-admission observation; it was not validated as a from-scratch constructor here.

## Limitations
- Candidate K30 libraries are finite heuristic past-generated libraries, not the full combinatorial space.
- Current metadata guards retain the known survivorship-metadata caveat.
- Six formal OOS half-years are a small time-series sample even though each cross-section contains ~500 K30 Universes.
