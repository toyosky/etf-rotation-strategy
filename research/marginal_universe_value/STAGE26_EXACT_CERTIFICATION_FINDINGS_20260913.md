# Stage26 exact certification findings — 2026-09-13

## Status

The GitHub Actions run `34755327797` completed successfully as infrastructure, but its reported monthly solutions are **not certified exact optima** and must not be used as the Stage26 exact/min-cardinality oracle.

This is a computational-certification finding, not a change to the frozen Stage26 research semantics.

## Evidence

Artifact: `muv-stage26-set-value-oracle-34755327797`.

Across the exported monthly rows, `solver_primary_status = 1` rather than HiGHS/Scipy MILP optimal status `0`. The primary optimization therefore stopped at the time limit with an incumbent solution. The secondary minimum-cardinality solve was then constrained to that incumbent objective value, so a successful secondary status does not certify the primary objective as globally optimal.

A direct consistency check also finds months where the reported `oracle_log` is below the separately enumerated `best_singleton_log` (for example 2026-04-30: oracle 0.099803 vs best singleton 0.271054). A true unrestricted set-value optimum cannot be worse than a feasible singleton. This is a decisive certificate failure.

Therefore the attractive exported size statistics (mean K about 2.54, median K 2, K<=5 about 94%) are **provisional incumbent geometry only**. They are not evidence that the exact optimal Universe is usually tiny.

## Frozen interpretation

Keep the earlier greedy/local-oracle evidence as a local-search structural diagnostic. Do not merge it with this uncertified MILP output and do not promote the latter as an exact upper bound.

Stage27 remains on hold until Stage26 has either:

1. a genuinely certified exact/min-cardinality benchmark on an auditable reduced problem, or
2. a pre-registered bounded-gap formulation that explicitly reports optimality gaps and is used only to decide whether greedy is sufficiently close for the geometry audit.

No Stage13–Stage25 experiment is reopened. No feature, threshold, K, horizon, label, or downstream OLS rule is changed.

## Required computational next step

Reformulate/certify Stage26 rather than increasing model capacity. The next implementation must fail closed when the primary MILP is not optimal and must include sanity checks such as `oracle_value >= best_singleton_value` and explicit primary MIP gap/status in the published report. If exact certification remains computationally infeasible, branch explicitly to a bounded-gap/local-geometry audit instead of calling incumbents exact.
