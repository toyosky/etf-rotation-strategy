# Stage 16 — Activity-Conditioned Sign Identifiability Audit

Date: 2026-09-13

## Question

Stage 15 shows that path activity is predictably ranked but conditional sign/value is weak. Stage 16 asks the narrowest remaining retention question:

> Among ETFs that are most likely to participate in the OLS competition path, does signed marginal value become materially more identifiable?

If the answer is no, the retention branch should be treated as identified enough to conclude that current observables support relevance/risk budgeting but not signed deletion decisions.

## Frozen inputs

Use only the frozen Stage-3 expanding-window OOS predictions:

- `p_active`
- `p_positive_pairwise`
- `muv_pairwise`
- realized `path_active`
- realized `delta_return`
- `label_month`
- `oos_period`

No label rebuilding changes, no new features, no new model fit, no hyperparameter search.

## Cross-sectional activity rank

For each label month, compute the percentile rank of `p_active` across the available retention symbols. Higher percentile means greater predicted competition relevance.

Evaluate the full cumulative curve for activity percentile cutoffs:

- 0.0, 0.1, 0.2, ..., 0.9

For each cutoff, retain **actually path-active** rows whose monthly `p_active` percentile is above the cutoff.

This is not a policy threshold search. Every pre-specified cutoff is reported and no cutoff may be selected based on portfolio performance.

## Diagnostics

For every cumulative activity slice report:

1. active sample count;
2. conditional sign AUC using `p_positive_pairwise`;
3. Spearman(`muv_pairwise`, `delta_return`);
4. count of point-predicted negative-MUV rows;
5. positive false-negative regret sum;
6. correctly identified negative-value sum;
7. largest positive miss.

Repeat sign AUC and MUV Spearman for the frozen OOS subperiods 2023–24 and 2025–26.

## Interpretation rule fixed ex ante

Evidence for conditional identifiability requires **broad, monotone, cross-period improvement** as activity rank is tightened. A local or period-specific bump is not sufficient.

If sign AUC remains near chance, MUV rank correlation remains near zero, or improvement reverses across subperiods, conclude that high competition relevance does not repair signed-MUV identification.

No threshold will be converted into a retention rule in Stage 16.

## Next branch

If Stage 16 fails to establish conditional signed identifiability, freeze the retention conclusion and move to an admission-label project. Admission must be studied with add-one counterfactual labels and the same time-forward/no-threshold-tuning principles rather than inferred from retention results.
