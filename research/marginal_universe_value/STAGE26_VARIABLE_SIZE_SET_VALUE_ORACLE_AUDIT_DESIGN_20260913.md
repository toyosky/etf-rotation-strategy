# Stage26 Variable-Size Set-Value Oracle Audit — Frozen Design

Date: 2026-09-13

## Mainline objective

The project target is now the variable-size Universe itself. At decision time t, an executable future policy must eventually construct U_t using only X_{<=t}; downstream selection is the fixed OLS rule and is not changed by Universe research.

Stage26 is not an executable policy and does not claim OOS performance. It is a future-informed local counterfactual/oracle structural audit used only to define the set-value landscape, endogenous size, and add/remove labels for later walk-forward learning.

Fix15 is retained only as a diagnostic benchmark. It is not a target anchor, mandatory core set, or label definition.

## Frozen downstream OLS rule R

- Candidate membership is frozen at the decision date for the next evaluation window.
- Within a candidate set, each signal day selects the member with maximum existing OLS `score` among ETFs whose existing `trend_eligible` flag is true that day.
- Signal at close(t), execute at open(t+1), mark open(t+1) to open(t+2).
- Transaction cost is the existing research constant `SIDE_COST=0.0006` per turnover side.
- No C2, V1, volume overlay, health filter, maturity veto, new threshold, or alternative ranking is introduced.

## Decision times and candidate market

- Decision times: month-end trading dates.
- Candidate market at each decision date: all non-cash ETFs with point-in-time `universe_eligible=true` on that date.
- The candidate set may include ETFs not currently `trend_eligible`; the downstream OLS rule decides daily whether they can compete.
- Evaluation window: next 20 trading signal days after the decision date, requiring the next two opens for execution/marking.

## Set value V(U; R)

Primary value is fixed with no fitted weights:

`V = sum(log(1 + daily_net_return))`

across the next 20 signal days, including the frozen per-side transaction costs and a terminal liquidation side when the final target is non-cash.

This is monotone-equivalent to compounded net return and avoids introducing arbitrary risk/turnover weights. Diagnostics are reported separately rather than optimized:
- compounded net return
- gross return
- max drawdown
- switch events
- turnover sides
- mean Top1 tenure
- distinct target count
- full-market OLS path coverage

## Oracle local-search construction

No global subset enumeration is allowed.

For each decision month:
1. Start from the empty set.
2. Evaluate every one-symbol addition using the future 20-day frozen OLS value.
3. Add the symbol with the largest positive marginal value.
4. Repeat until no remaining single addition has positive marginal value (mechanical numerical tolerance 1e-12 only).
5. Perform best-improvement single removals from the resulting set until no removal has positive marginal value.
6. Audit, but do not execute, the best one-for-one swap from the final set.

The resulting set is a greedy local oracle, not the global optimum. Its purpose is to expose whether a finite endogenous size and meaningful local marginal-value landscape exist.

## Frozen outputs

Per month:
- candidate count
- forward-oracle size before cleanup
- final local-oracle size
- full-market / Fix15 / oracle net value and return
- oracle vs full-market switch count and mean tenure
- day-level full-market path coverage by the oracle set
- best remaining add marginal value
- best removal marginal value after cleanup
- best one-swap marginal value
- consecutive-month oracle-set Jaccard

Per forward/removal step:
- month
- operation
- symbol
- set size before/after
- value before/after
- marginal value

## Interpretation rules

Stage26 supports a genuine variable-size set-value structure only if all of the following are observed without tuning:
- local-oracle sizes are not mechanically equal to candidate-market size and show meaningful cross-month variation;
- forward marginal values decay and terminate naturally rather than requiring a fixed K cap;
- final sets materially change downstream OLS path behavior (switching/tenure/path coverage) versus the full candidate market;
- the local landscape is not dominated by unresolved positive single removals; swap residuals are reported as a measure of local-search incompleteness;
- conclusions are checked separately for 2023-24 and 2025-26 for structural reversal.

No threshold is fit to declare an economically optimal K. No historical best subset is carried forward as an executable result.

## Branch rule

After Stage26, perform branch review before Stage27:
- if size/value structure is clear and reasonably stable, build a low-DoF point-in-time set generator in strict expanding OOS;
- if local oracle sets are unstable but relation diagnostics are structured, study relation/competition state before predictive selection;
- if even the oracle local landscape is flat/noisy or era-reversing, weaken the objective to structural coverage-minus-nuisance control rather than increasing model capacity.
