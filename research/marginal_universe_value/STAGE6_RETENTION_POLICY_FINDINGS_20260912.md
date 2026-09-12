# MUV Stage 6 — Retention Policy Findings

Date: 2026-09-12

## Status

**Result: FAIL for promotion to multi-removal sequential retention.**

Stage 6 translated the frozen Stage-3 OOS MUV predictions and Stage-5 crowding diagnostics into a conservative one-removal-per-month policy.  No model was refit and no threshold was optimized after observing strategy outcomes.

## Frozen decision rules

For each OOS month (2023-01 to 2026-08):

1. rank incumbents by the already-OOS `muv_pairwise` prediction;
2. select the minimum predicted MUV ETF;
3. remove it only when predicted MUV < 0;
4. maximum one removal per month, so realized performance uses the exact remove-one counterfactual rather than an additive approximation.

Three predeclared policies were evaluated:

- `pairwise_no_gate`: no crowding gate;
- `crowding_lt_2_3`: primary policy, act only when the equal-weight prior-history crowding score is below 2/3;
- `crowding_lt_1_3`: strict low-crowding sensitivity policy.

Crowding score used only prior-history percentiles of:

- qualified risk competitor count;
- fraction of risk ETFs with positive 20d return;
- median 20d return across risk ETFs.

## Main results

### Keep-all Fixed15

- 44 months
- final wealth: 6.8039
- total return: +580.39%
- CAGR: 68.70%
- monthly-equity MDD: -36.44%

### Pairwise, no crowding gate

- final wealth: 6.2254
- terminal wealth advantage vs keep-all: **-8.50%**
- acted 44/44 months
- realized action win rate: 38.64%
- realized action harm rate: 22.73%

### Primary crowding < 2/3

- final wealth: 5.9208
- terminal wealth advantage vs keep-all: **-12.98%**
- acted 25/44 months
- realized action win rate: 44.0%
- realized action harm rate: 24.0%
- mean realized improvement when acting: -0.521% per action month

This fails in both broad subperiods:

- 2023–24: terminal wealth advantage vs keep-all = **-10.41%**
- 2025–26: terminal wealth advantage vs keep-all = **-2.87%**

### Strict crowding < 1/3

- final wealth: 6.6983
- terminal wealth advantage vs keep-all: **-1.55%**
- acted 11/44 months
- realized action harm rate: 9.09%

The strict gate improves 2023–24 but hurts 2025–26, therefore it is not a stable solution and must not be selected post hoc.

## Random-removal control

The random baseline removes one random incumbent in exactly the 25 months when the primary policy acts, over 2,000 seeded simulations.

- mean terminal wealth advantage vs keep-all: -1.86%
- median terminal wealth advantage: +3.03%
- probability random removal beats keep-all: 56.4%

The primary MUV selection result of -12.98% is materially worse than the random benchmark.  Therefore Stage 6 does **not** show that the current pairwise model identifies which ETF should be removed.

## Oracle upper bound

A future-aware one-removal oracle, used only as a diagnostic upper bound, produces:

- final wealth: 32.9944
- terminal wealth advantage vs keep-all: +384.93%
- monthly-equity MDD: -18.90%
- action months: 35/44

Therefore the failure is **not** caused by an absence of economically meaningful removal opportunities.  The bottleneck is prediction / decision quality.

## Critical failure example: 2025-04 gold

The primary model selected `518880` (gold) for removal.

Decision-time / model state:

- `p_active` ≈ 0.922
- `p_positive_pairwise` ≈ 0.297
- `cond_ev_pairwise` ≈ -0.00884
- predicted `muv_pairwise` ≈ -0.00815

Realized counterfactual:

- actual retention `delta_return` ≈ +0.23478
- removing gold reduced the month's result by about **23.48 percentage points** relative to keeping it.

This single error is economically much more important than several correctly identified small negative-retention cases.

## Main diagnosis

Stage 3/5 focused heavily on sign discrimination (`RV > 0` vs `RV < 0`) and AUC.  Stage 6 shows that this is insufficient for a portfolio decision because the loss function is highly asymmetric:

```text
false removal of a large positive-RV ETF
    >>
missed removal of a mildly negative-RV ETF
```

The conditional RV distribution is sparse, zero-inflated and heavy-tailed.  A model can have useful AUC in some regimes and still produce a poor policy if it occasionally removes a large positive contributor.

## Decision

Do **not** proceed to true multi-step sequential deletion yet.

The next stage should change the decision objective, not tune the existing crowding threshold.

Recommended direction:

1. keep Stage A participation model, which remains the strongest validated component;
2. reformulate retention as a conservative **safe-to-remove** problem with asymmetric loss;
3. explicitly model / guard against large positive retention tails;
4. require strong one-sided evidence before removing an incumbent;
5. evaluate utility / regret and random-removal controls, not only AUC;
6. avoid selecting `<1/3` just because it looked better in part of this already-seen sample.

Stage 6 therefore falsifies the current sign-AUC-to-policy translation while preserving the broader MUV hypothesis and the large Oracle evidence that correct universe pruning could matter economically.
