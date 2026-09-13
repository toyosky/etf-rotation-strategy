# Stage 15 — Hurdle identifiability audit design

Date: 2026-09-13

## Purpose

Stage 14 showed that current expected-MUV predictions cannot support distribution-free high-confidence removal certification at useful coverage. Stage 15 therefore stops policy search and asks a more basic identification question:

> Which part of retention MUV is actually predictable from the current observable state?

The economic target is naturally two-stage:

1. **Path activity** — will the ETF matter to next month's OLS competition path at all?
2. **Conditional direction/value** — if it matters, will retaining it help or hurt the portfolio, and by how much?

If only the first hurdle is predictable, the current state representation is useful for attention/risk budgeting but insufficient for directional dynamic retention.

## Frozen inputs

Use the already frozen Stage-3 expanding-window OOS prediction panel:

- `p_active`
- `p_positive_pairwise`
- `muv_pairwise`
- realized `path_active`
- realized `delta_return`

No new features or models are permitted.

## Frozen diagnostics

Report for all OOS rows and separately for 2023-24 and 2025-26:

1. Path-activity ROC AUC from `p_active`.
2. Spearman correlation between `p_active` and `abs(delta_return)`.
3. Conditional sign ROC AUC among realized active rows using `p_positive_pairwise`.
4. Spearman correlation between `muv_pairwise` and realized `delta_return` among active rows.
5. Negative point-MUV audit:
   - number of negative predictions;
   - share that realize positive retention value;
   - cumulative positive regret on those false-negative rows;
   - cumulative correctly captured negative retention value;
   - largest positive miss.
6. Month-level active-row rank correlation where at least three active rows are available; report count, mean, median, and share positive.
7. Descriptive pooled quintiles of `p_active` and `muv_pairwise` only as monotonicity diagnostics. Quintile boundaries must not be used as a policy threshold.

## Interpretation rule frozen before evaluation

- If path activity is stable and materially predictable across both periods, but conditional sign / continuous MUV ranking remains near chance or unstable, conclude that current observables identify **competition relevance** better than **conditional marginal value**.
- If both hurdles are stable, further retention policy work is justified.
- If neither hurdle is stable, suspend current retention modeling and revisit the state representation.

Stage 15 is diagnostic only. No wealth backtest, action threshold, coverage level, or pool-width choice may be optimized from its results.
