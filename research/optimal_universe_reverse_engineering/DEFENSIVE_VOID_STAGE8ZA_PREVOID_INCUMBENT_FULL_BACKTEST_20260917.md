# Stage8ZA — Pre-Void incumbent full backtest

Date: 2026-09-17
Authoritative run: 35165349642
Artifact: oure-stage8za-35165349642

## Frozen design
Base strategy is Stage8M FixV2/V1(75), formal 26-day weighted log-price OLS, half-life 10, 6bp per side.

Critical correction versus Stage8Z: on the first DEFENSIVE_VOID signal day, freeze the actual pre-Void output target from the prior signal day. The new base target calculated on the Void-entry day is not allowed to replace it.

Deepening is intentionally parameter-light: Breadth and Gap percentile must both be below their Void-entry values for N consecutive Void signal days. A route is allowed only when the frozen incumbent also no longer beats 511220. Then use 513500 only if it is at least 365 days old and its raw OLS score exceeds 511220; otherwise use 511220. Once routed, hold until Void exit.

N=1/2/3 are mechanism-neighborhood checks, not an ex-post optimization.

## Full-period results

| Variant | CAGR | MDD | Sharpe | Calmar | Turnover sides | Switches |
|---|---:|---:|---:|---:|---:|---:|
| ORIGINAL_V1 | 40.58% | -38.59% | 1.167 | 1.052 | 749 | 408 |
| VOID_IMMEDIATE_US_CARRIER | 34.49% | -29.28% | 1.071 | 1.178 | 931 | 479 |
| PREVOID_FREEZE_INVALID_CASH | 44.43% | -32.20% | 1.257 | 1.380 | 611 | 319 |
| PREVOID_DEEPEN1_INVALID_ROUTE | 44.53% | -31.30% | 1.249 | 1.423 | 575 | 298 |
| PREVOID_DEEPEN2_INVALID_ROUTE | 44.03% | -31.98% | 1.238 | 1.377 | 563 | 292 |
| PREVOID_DEEPEN3_INVALID_ROUTE | 44.28% | -33.42% | 1.239 | 1.325 | 557 | 289 |

All pre-Void-freeze variants outperform ORIGINAL_V1 on CAGR, MDD and turnover. N=1/2/3 all preserve the sign of the mechanism; the result is therefore not dependent on the previously chosen 2-day streak.

The strongest historical risk-adjusted result is N=1 by Calmar, but no threshold retuning is authorized from this same sample. The robust conclusion is the neighborhood-level mechanism: do not treat first entry into Void as a sell signal; freeze the existing incumbent, and route only after further deterioration plus incumbent failure.

## Structural interpretation

DEFENSIVE_VOID is better interpreted as a competition-freeze / no-new-leader state, not an automatic defensive-exit state.

State machine:

Normal OLS/V1 -> first Void entry -> freeze actual pre-Void incumbent -> observe -> if map deepens AND incumbent score <= 511220 -> route to healthy 513500 else 511220 -> hold until Void exit.

This reduces switches from 408 in ORIGINAL_V1 to 289-298 in the N=1/2/3 deepening variants while also improving full-period return and drawdown. That supports the hypothesis that premature cross-sectional re-ranking during Void is a material source of turnover and performance loss.

## Key caveats

1. This is still a same-history mechanism audit, not a final live-rule approval.
2. 513500 QDII premium/NAV timing is not yet fully reconstructed; cost stress remains favorable but does not substitute for historical premium modeling.
3. The N=1/2/3 neighborhood is robust in sign, but should not be optimized further on this sample.
4. A final validation should freeze one simple rule and evaluate walk-forward/subperiod stability, especially 2021-2024 versus 2025-2026 and historical Void episodes with long underwater periods.
