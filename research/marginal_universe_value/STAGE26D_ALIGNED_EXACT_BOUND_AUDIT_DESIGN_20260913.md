# Stage26D Aligned Exact/Bound Audit — Frozen Design

Date: 2026-09-13
Parent: Stage26 / Stage26C
Label version: `set_value_next20_fixed_ols_v2`

## Purpose

Repair a mechanical semantic mismatch discovered after Stage26C: the greedy/local Stage26 oracle uses the frozen next 20 trading signal days after each month-end decision, while the first MILP implementation used the interval to the next month-end. Those outputs are not valid for exact-vs-greedy comparison.

This is not a retune. No feature, threshold, model, K, cost, OLS rule or horizon is selected from results. Stage26D restores the already-registered `set_value_next20_fixed_ols_v2` semantics.

## Frozen semantics

For each month-end decision t:
- candidate set = all non-cash point-in-time `universe_eligible` ETFs at t;
- evaluation dates = exactly the next 20 trading signal days after t;
- require two subsequent opens for execution/marking;
- daily target = highest frozen OLS score among trend-eligible members of U;
- signal close(d) -> execute open(d+1) -> mark open(d+2);
- SIDE_COST = 0.0006 per turnover side;
- terminal liquidation included;
- empty Universe allowed;
- primary objective = sum log net growth;
- secondary objective = minimum cardinality conditional on a certified primary optimum.

## Certification rules

- `primary_status == 0` is required to call a month globally exact.
- `primary_status == 0 && secondary_status == 0` is required to call its K minimum-cardinality exact.
- Any nonzero primary status is an incumbent only, never an exact oracle.
- Hard sanity check: certified oracle value must be >= best singleton value within numerical tolerance.
- Record solver MIP gap when available.
- Do not increase solver time after seeing results in order to rescue specific months.

## Comparison role

Stage26D exists only to create a semantics-aligned global calibration reference for the already-frozen greedy/local oracle. Stage27 may proceed using local geometry if exact coverage is limited, provided conclusions distinguish certified exact, bounded incumbent, and greedy/local evidence.

No executable policy is trained here.