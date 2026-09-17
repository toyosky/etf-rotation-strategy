# Void Route Baseline v1 — FROZEN

Freeze date: 2026-09-17
Status: frozen working baseline for live / out-of-sample validation
Parent strategy: Stage8M FixV2 + V1(75)
Research basis: Stage8ZA + Stage8ZB

## Frozen rule

This version intentionally stops historical tuning here.

1. Outside `DEFENSIVE_VOID`, run the frozen Stage8M FixV2 + V1 logic unchanged.
2. On the first signal day entering `DEFENSIVE_VOID`, do **not** accept the newly calculated cross-sectional Top1. Freeze the actual position held on the prior signal day (`pre-Void incumbent`).
3. While Void persists, suppress normal Top1 switching.
4. Define `incumbent invalidation` as raw 26-day weighted OLS score of the frozen incumbent <= raw OLS score of 511220.
5. Define `Void deepening` for this frozen baseline as: on a later Void signal day, both Breadth and Leadership Gap percentile are below their values on the Void-entry day. The frozen baseline uses **N=1**; N=2/3 remain robustness neighbors and are not to be re-optimized on historical data.
6. Only when **both** Void deepening and incumbent invalidation are true may the strategy leave the incumbent.
7. Post-failure route:
   - use `513500` as US Carrier only when it has >=365 calendar days of listing history and its raw OLS score > 511220 raw OLS score;
   - otherwise use `511220`.
8. Once routed inside the same Void episode, hold the routed target until Void exits.
9. When Void exits, resume the normal frozen Stage8M FixV2 + V1 competition logic.

## Why this version is frozen

The purpose of this freeze is not to claim historical optimality. It creates a stable rule that can now accumulate genuinely new evidence.

Full-period Stage8ZA results at 6 bp / side:

| Variant | CAGR | MDD | Sharpe | Calmar | Switches |
|---|---:|---:|---:|---:|---:|
| Original V1 | 40.58% | -38.59% | 1.167 | 1.052 | 408 |
| Pre-Void Deepen1 + invalidation route | 44.53% | -31.30% | 1.249 | 1.423 | 298 |

Stage8ZB subperiod robustness:

- 2015–2022: Deepen1 CAGR 23.23% vs Original 21.13%; MDD -31.30% vs -33.41%.
- 2023–2026 partial: Deepen1 CAGR 103.78% vs Original 93.78%; MDD -28.54% vs -38.59%.
- Important counterexample, 2023–2024: Deepen1 CAGR 40.44% vs Original 43.79%, while MDD improves to -21.56% from -28.12%.

The counterexample is accepted rather than optimized away. No additional regional / sector threshold may be added merely to repair this historical block.

## Anti-overfitting lock

From the freeze timestamp onward:

- Do not select among N=1/2/3 using additional historical returns.
- Do not replace 513500 with another region because a past subperiod looks better.
- Do not introduce a new post-Void country / industry selector from the same historical sample.
- Historical analysis may be used for diagnostics and implementation bugs only, not for performance-driven rule changes.
- Any future strategy change must be versioned separately and justified primarily by evidence accumulated after this freeze or by an independently preregistered test.

## Live / OOS validation protocol

Validation start: 2026-09-17.

Maintain three shadow paths using the same market data and execution assumptions:

1. `FROZEN_BASELINE_V1`: this frozen Deepen1 + invalidation + 513500/511220 route.
2. `ORIGINAL_V1_SHADOW`: original Stage8M V1 with no Void intervention.
3. `FREEZE_INVALID_CASH_SHADOW`: freeze pre-Void incumbent; after invalidation route only to 511220.

For every real or simulated trade, preserve point-in-time records of:

- signal timestamp and intended execution timestamp;
- current State Map quadrant, Breadth and Gap percentile;
- pre-Void incumbent and its raw OLS score;
- 511220 raw OLS score;
- 513500 raw OLS score and listing-age eligibility;
- route decision and actual traded symbol;
- actual execution price / slippage when available;
- ETF premium / discount observations when available;
- subsequent realized PnL and drawdown.

Primary forward metrics:

- cumulative and annualized return;
- MDD and Calmar;
- Sharpe;
- turnover / switches;
- performance specifically during Void episodes;
- incremental PnL versus both shadow paths;
- realized cost / slippage on 513500 routes.

Review forward evidence periodically, but do not change the frozen rule merely because of a small number of adverse trades. Any modification must create a new version instead of rewriting this baseline.

## Interpretation

`DEFENSIVE_VOID` is frozen as a **competition-freeze state**, not an automatic risk-off signal.

The baseline hypothesis to validate prospectively is:

> When opportunity breadth and leadership clarity collapse, the first response should be to stop unnecessary cross-sectional switching. Continue holding the incumbent while it remains stronger than cash. Only after the state deteriorates further and the incumbent itself fails should the strategy leave, preferring a healthy US broad-market Carrier over cash when that Carrier independently passes the same OLS hurdle.
