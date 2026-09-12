# MUV Stage 7 — Asymmetric Retention Safety Findings

Date: 2026-09-12
Status: completed; primary frozen policy passed the first policy-level screen

## Frozen design

Stage 7 was frozen before seeing its results in `STAGE7_ASYMMETRIC_SAFETY_DESIGN_20260912.md`.

Primary policy:

```text
Stage-3 OOS expected MUV < 0
AND
magnitude-weighted pairwise+regime safety score
falls below the past-only cutoff protecting 90% of prior positive-RV mass
    -> remove at most one ETF for the next month
```

No crowding gate, feature search, C search, or coverage search was performed. 80% / 95% coverage and pairwise-only 90% were predeclared sensitivities only.

## Primary result, 2023-01 to 2026-08

Keep-all Fixed15:

- final wealth: 6.8039
- CAGR: 68.70%
- monthly-equity MDD: -36.44%

Frozen Stage-7 primary (`pairwise+regime`, 90% regret coverage):

- final wealth: 8.8879
- CAGR: 81.45%
- monthly-equity MDD: -27.36%
- relative terminal wealth vs keep-all: **+30.63%**
- action months: 16 / 44 (36.36%)
- realized action wins: 31.25%
- realized harmful actions: 12.50%
- zero-effect actions: 9 / 16
- cumulative realized removal improvement: +23.39 percentage points
- captured negative retention value: 26.23 percentage points
- cumulative false-removal regret: 2.84 percentage points
- maximum single false-removal regret: 2.66 percentage points

Worst false removal:

```text
2024-07
removed: 164824
lost retention value: 2.66 percentage points
```

This is materially different from Stage 6, whose canonical false removal (518880 in 2025-04) lost about 23.48 percentage points.

## Period stability

2023–24:

- keep-all final wealth: 1.4720
- Stage-7 primary: 1.6623
- relative advantage: **+12.93%**
- 9 actions
- cumulative false-removal regret: 2.84 percentage points

2025–26:

- keep-all final wealth: 4.6223
- Stage-7 primary: 5.3466
- relative advantage: **+15.67%**
- 7 actions
- cumulative false-removal regret: 0

Year diagnostics:

- 2023: +5.37% relative terminal wealth
- 2024: +7.18%
- 2025: 0% (no action)
- 2026 through August: +15.67%

The primary policy did not require every year to act. In 2025 the safety mechanism abstained for all 12 months, which is economically consistent with a veto/safety design rather than a forced universe-width optimizer.

## Random-control comparison

Random one-removal control was matched to the same 16 primary action months, 2,000 draws.

Random terminal wealth advantage vs keep-all:

- mean: +2.97%
- median: +4.74%
- 95th percentile: +22.22%
- probability random beats keep-all: 68.05%

Stage-7 primary:

- relative terminal advantage: **+30.63%**

The primary total return (788.79%) also exceeds the random-control 95th-percentile total return (731.57%). Thus the Stage-7 result is not explained merely by shrinking the universe in those months.

## Safety-model diagnostics

Magnitude-weighted pairwise-only:

- ordinary sign AUC: 0.541
- positive-regret-weighted mean safety score: 0.531
- negative-value-weighted mean safety score: 0.433

Magnitude-weighted pairwise+regime:

- ordinary sign AUC: 0.517
- positive-regret-weighted mean safety score: 0.532
- negative-value-weighted mean safety score: 0.450

The ordinary AUC remains mediocre. The policy improvement comes from changing the objective and action geometry: protect the score region carrying large historical positive-RV mass and act only outside that protected region. This supports the Stage-6 diagnosis that ordinary sign AUC is not the relevant decision loss.

## Predeclared sensitivities — not model selection

The predeclared sensitivities were also positive:

- regime 80% coverage: +44.42% relative terminal wealth; 26 actions
- regime 95% coverage: +17.00%; 15 actions
- pairwise-only 90% coverage: +35.50%; 14 actions

These are diagnostics only. The primary policy remains the predeclared pairwise+regime 90% policy; the better-looking 80% or pairwise-only result must not replace it after the fact.

## Interpretation

Stage 7 changes the working MUV decision model from symmetric classification to asymmetric regret control:

```text
predicted negative MUV
        +
low estimated large-winner regret risk
        -> safe-to-remove candidate
```

The most important improvement is not the raw return lift but the collapse of catastrophic false-removal tail risk:

```text
Stage 6 worst observed false-removal regret: ~23.48pp
Stage 7 primary worst false-removal regret: ~2.66pp
```

This is exactly the failure mode the correction was designed to address.

## Important limitations

1. 2023–2026 is chronological OOS relative to each monthly model fit, but it is not a pristine untouched final test set: earlier research stages already informed the Stage-7 problem formulation.
2. The sample is still small: only 16 primary actions and only 2 harmful actions.
3. The current experiment removes at most one ETF per month. It does not validate multi-removal sequential retention.
4. Universe-dependent features have not yet been recomputed after a first removal; therefore multi-step deletion cannot be approximated by adding remove-one MUVs.
5. A successful historical safety gate does not establish prospective live efficacy.

## Decision

Stage 7 passes the first conservative policy-level screen and justifies further robustness work.

It does **not** yet justify immediately enabling multiple deletions or changing the live strategy.

Next step: freeze the Stage-7 primary policy and run robustness/concentration diagnostics before building a true sequential multi-removal engine.
