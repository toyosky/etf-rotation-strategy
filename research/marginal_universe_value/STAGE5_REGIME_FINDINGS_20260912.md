# MUV Stage 5 — Regime diagnostics

Date: 2026-09-12

## Scope

Stage 5 keeps the Stage-3 pairwise sign model frozen and asks whether its OOS ability to distinguish positive vs negative retention value depends on point-in-time market / competition regime.

No regime model is fitted. No outcome-driven threshold search is performed. Each regime feature is converted to an empirical percentile using only prior months, then mapped to fixed terciles for diagnostics.

## Data audit

V1.4 preserves the V1.3 counterfactual panel and labels:

- 68 months
- 818 month × ETF rows
- 14 retention ETFs
- label period: 2021-01 through 2026-08
- positive `delta_return` share: 11.61%
- zero `delta_return` share: 72.37%
- mean `delta_return`: +0.1687%

Only decision-time regime X features were added.

V1.4 Parquet size: 657,515 bytes.
Peak workflow memory: 216.09 MB.

## Frozen model baseline

Stage A remains stable:

- 2023-2026 OOS AUC: 0.733

Stage B pairwise sign model, active rows only:

- overall 2023-2026 AUC: 0.547
- 2023: 0.688
- 2024: 0.366
- 2025: 0.461
- 2026: 0.692

This confirms strong state dependence rather than a simple monotonic time drift.

## Main regime diagnostics

### Broad opportunity strength

`regime_risk_ret20_median`:

- low tercile: AUC 0.689, 58 active rows
- mid tercile: AUC 0.370, 39 active rows
- high tercile: AUC 0.465, 58 active rows

`regime_risk_ret20_positive_frac`:

- low tercile: AUC 0.646, 63 active rows
- mid tercile: AUC 0.421, 41 active rows
- high tercile: AUC 0.457, 51 active rows

Interpretation: pairwise ETF-vs-alternative state is substantially more informative when broad risk-asset momentum / breadth is weak. When many risk assets are broadly strong, the same pairwise relation weakens or reverses.

### Number of qualified competitors

`regime_risk_qualified_count`:

- low tercile: AUC 0.670, 41 active rows
- mid tercile: AUC 0.638, 35 active rows
- high tercile: AUC 0.438, 79 active rows

This is the clearest competition-crowding result. The pairwise value model works better when the qualified opportunity set is sparse and becomes anti-informative when many risk ETFs qualify simultaneously.

### Score dispersion

`asof_score_std`:

- low tercile: AUC 0.695, 41 active rows
- mid tercile: AUC 0.454, 46 active rows
- high tercile: AUC 0.524, 68 active rows

Potentially informative, but not monotonic and therefore not sufficient as a standalone regime gate.

### Top1 switching and tenure

`regime_raw_top1_switches20`:

- low: 0.652
- mid: 0.440
- high: 0.543

`regime_top1_current_streak`:

- low: 0.477
- mid: 0.796
- high: 0.523

These are non-monotonic and should not be promoted to rules from this sample.

### Cross-sectional correlation

`regime_risk_corr120_median`:

- low: 0.500
- mid: 0.511
- high: 0.575

Only a weak gradient is present.

## Economic interpretation

The strongest coherent pattern is not simply "fast switching is bad". It is closer to:

```text
Broad opportunity set / many qualified competitors
    -> competition is crowded
    -> many plausible OLS winners coexist
    -> current pairwise ETF-vs-alternative state is less reliable for deciding marginal Universe value

Sparse / weak broad opportunity set
    -> fewer serious competitors
    -> relative state between ETF and strongest alternative becomes more informative
    -> pairwise MUV discrimination improves
```

This is consistent with the original MUV motivation: adding competitors creates option value but also interference cost, and that interference cost is state-dependent.

## What is NOT established

- No production regime gate is validated.
- Terciles are descriptive, not selected thresholds.
- The active sample is only 155 rows over 44 OOS months; effective regime sample size is monthly, not row count.
- Multiple related regime variables share the same months, so apparently similar results are not independent evidence.
- Stage 5 used the full 2023-2026 OOS history to identify this hypothesis. A new gate constructed from these findings must therefore be tested prequentially / nested, not evaluated on the same data and called OOS.

## Next recommended stage

Stage 6 should test a predeclared, low-dimensional **competition crowding state** without tuning thresholds on final performance.

A defensible starting hypothesis is to use only prior-history percentiles of:

1. risk-qualified competitor count;
2. risk 20-day positive breadth;
3. risk 20-day median return.

These variables represent one economic concept rather than three independent alpha factors.

The Stage-6 evaluation should be nested walk-forward: at each month, all regime calibration and any gate decision must use only earlier months. The goal is to determine whether conditioning Stage B on competition crowding improves sign discrimination and, only after that, whether a sequential retention simulation improves portfolio outcomes.
