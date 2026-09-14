# New Stage 5 — Conservative Fixed-K15 Executable Composition Audit

Date frozen: 2026-09-14
Parent: New Stage4

## Why this stage is conservative

Stage4 found large fixed-K15 composition headroom but weak same-month single-symbol inclusion stability and essentially zero adjacent-month symbol persistence. Therefore Stage5 is not a learned member-model stage. It is a final low-DoF executable audit before deciding whether composition optimization should stop.

K=15 remains an engineering anchor only.

## Frozen monthly information set

At each month start, use only information available through the previous trading day. Reuse the Stage1 corr=0.95 representative parent pool and the exact same Frozen OLS monthly evaluation/execution semantics.

No K search, new correlation threshold, feature search, model fitting, hyperparameter search, or future information from the evaluation month is allowed.

## Frozen K15 rules

Each K15 Universe contains the existing cash signal 511220 plus 14 non-cash ETFs.

### Rule A — current_score_top14

From the current representative parent pool:
1. rank ETFs with non-null Stage1 `pool_score` at the previous trading day by descending `pool_score`;
2. ties by descending `avg_amount60`, then symbol;
3. if fewer than 14 active ETFs exist, fill remaining slots from current eligible representatives by descending `avg_amount60`, then symbol.

This is a pure X<=t rule and contains no training.

### Rule B — lagged_inclusion_top14

Use only the immediately previous completed month's frozen Stage4 randomized inclusion contrasts:
1. among current representative symbols with a previous-month contrast, rank descending by that contrast;
2. ties by current `pool_score`, current `avg_amount60`, then symbol;
3. fill any remaining slots using Rule A ordering.

The previous-month contrast is historical at the current decision date. It is used only to test whether Stage4's symbol-value signal has actionable one-month persistence. No multi-month window or decay parameter is searched.

## Benchmarks

Primary:
- existing Stage1 random K15 monthly distribution: mean, median, P90 and percentile rank of each simple rule.

External diagnostics:
- frozen Fix15 universe under the same monthly Frozen OLS evaluator;
- full point-in-time eligible ETF universe under the same evaluator.

These external benchmarks do not change K15 member-rule selection.

## Inference

Month is the inference unit. Start in 2021-02 for Rule B because one completed prior month is required. Report overall and separately for 2021–24 / 2025–26:
- rule minus random-K15 mean return;
- rule minus random-K15 median return;
- fraction of months above random P90;
- mean monthly percentile within the random K15 distribution;
- paired month bootstrap 95% interval for rule minus random mean;
- return, MDD, switches and observed Top1 tenure diagnostics;
- Fix15 and full-market return diagnostics.

Use a single fixed bootstrap seed `20260914` with 20,000 month resamples. This is inference only, not selection.

## Decision rule

If neither simple rule shows a stable positive paired advantage versus random K15, especially if the later era does not improve, freeze the research conclusion as: `composition headroom exists but is not stably identifiable/executable with low-DoF X<=t rules`. Stop model-capacity escalation on this history.

If one simple rule shows a stable positive advantage overall and does not reverse materially by era, it may be retained as the only composition mechanism for a later clean forward validation. This does not authorize feature search or a learned member model.

Stage4 future-aware inclusion contrast from the current evaluation month is never permitted in Stage5.