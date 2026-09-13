# Stage 15 — Hurdle Identifiability Findings (2026-09-13)

## Status

Stage 15 completed successfully from the frozen Stage-3 expanding-window OOS predictions. No new feature search, no new model fit, no threshold search, and no policy backtest were introduced.

## Main result

The MUV problem separates sharply into two hurdles:

1. **Competition-path relevance is identifiable to a useful degree.**
   - OOS path-activity AUC: **0.7328**.
   - 2023–24: **0.7416**.
   - 2025–26: **0.7266**.
   - Spearman between predicted path activity and |realized marginal return|: **0.3594** overall.

2. **Conditional direction/value is not stably identifiable with the current observables/model family.**
   - Among actually active rows, sign AUC: **0.5469** overall.
   - 2023–24: **0.4985**.
   - 2025–26: **0.6003**.
   - Spearman between predicted MUV and realized delta among active rows: **0.0486** overall.
   - 2023–24: **0.0088**.
   - 2025–26: **0.0622**.

Monthly active-rank diagnostics are noisy: 33 eligible months, mean Spearman **0.2061**, median **0.4000**, positive in **66.7%** of eligible months. This does not offset the near-zero pooled conditional value rank correlation and strong period instability.

## False-removal asymmetry

For rows with point-predicted MUV < 0:

- 270 rows overall.
- 10.0% had positive realized marginal value.
- Total positive false-negative regret: **1.4120**.
- Total correctly identified negative value: **1.3601**.
- Largest positive miss: **+0.2919**.

The aggregate regret from the minority false-negative cases is therefore of the same order as the aggregate benefit from correctly negative cases. This is the core non-symmetric deletion-risk mechanism already exposed by Stages 12–14.

## Interpretation

The current observable state is informative about **whether an ETF is likely to matter to the OLS competition path**, but much less informative about **whether that influence will help or hurt the portfolio once it matters**.

This supports using observables for attention allocation, candidate prioritization, or risk budgeting. It does **not** support unconstrained dynamic retention deletion based on a signed point estimate of MUV.

Stage 14 already showed that a distribution-free residual stress rule certifies essentially no deletion as safely negative. Stage 15 explains why: the principal identification failure is conditional sign/value, not competition-path relevance.

## Next lowest-freedom audit

Before closing the retention branch, Stage 16 will test one remaining non-parametric possibility using only the frozen Stage-3 OOS predictions:

> Does conditional sign/value become materially identifiable if we restrict attention to ETFs with the highest cross-sectional predicted path-activity rank?

This is a diagnostic only. It will sweep the full cumulative activity-rank curve rather than select a profitable threshold. No new model, features, hyperparameters, or policy thresholds will be introduced.
