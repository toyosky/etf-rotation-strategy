# Stage26C — Exact Certification Audit

## Registration
- hypothesis: The completed Stage26 MILP artifact contains a sufficiently large, internally valid exact-certified subset to support exact-vs-local geometry claims; non-certified months must be explicitly excluded from exact claims.
- parent_stage: stage26
- label_version: set_value_next20_fixed_ols_v2
- target_scope: universe_set_value
- model_role: solver_certification_audit
- decision: hold

## Frozen inputs
Use the immutable artifact from Stage26 run `34755327797` only. Do not rerun or tune Stage13–25 and do not alter the Stage26 set-value objective, horizon, costs, candidate semantics, K, or OLS rule.

## Frozen checks
1. A month is `primary_exact_certified` iff `solver_primary_status == 0`.
2. A month is `min_cardinality_certified` iff both primary and secondary statuses are 0.
3. Hard sanity condition for any claimed oracle: `oracle_log >= best_singleton_log - 1e-9`.
4. Report certification shares overall and by era, K distribution on certified months only, and count/list of singleton-dominance violations.
5. Never summarize timeout incumbents as exact K* or exact oracle value.

## Decision rule
- If exact/min-cardinality certification covers both eras with enough months for a meaningful era comparison and sanity violations are zero on certified months, Stage27 may use the certified subset for exact-vs-greedy comparison.
- Otherwise full-market exact identification is computationally unresolved. Stage27 may proceed only as a geometry audit using local/greedy paths plus the certified exact subset as limited validation; it must not claim all-month global exactness.

No model fitting, feature search, threshold search, K search, or solver-budget tuning is permitted in this audit.