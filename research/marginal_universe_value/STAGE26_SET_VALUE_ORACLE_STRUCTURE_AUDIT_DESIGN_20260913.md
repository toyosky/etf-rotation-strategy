# Stage26 Set-Value Oracle Structure Audit — Frozen Design

Date: 2026-09-13

## Research reset

The primary problem is no longer ETF-level retention/admission around Fixed15.

At decision time `t`, using only information available at or before `t`, the final executable objective is to construct a variable-size ETF Universe `U_t` such that a completely frozen downstream OLS rotation rule produces maximum out-of-sample portfolio value.

Stage26 does **not** yet fit the executable mapping `g(X_<=t) -> U_t`. It constructs a future-aware monthly oracle only to answer structural questions and to generate auditable set-level counterfactual labels for later strictly walk-forward learning.

Fixed15 is retained only as a benchmark. It is not an optimization anchor and does not have to be contained in the oracle set.

## Frozen downstream OLS rule

Reuse the existing daily research engine semantics:

- OLS features come from `research/full_market_ols_storage.py`;
- candidate trading state on each signal date requires `trend_eligible == True`;
- within the chosen Universe, the daily target is the trend-eligible ETF with the highest frozen OLS `score`;
- signal at close(d), execute at open(d+1), mark to open(d+2);
- transaction cost is `SIDE_COST = 0.0006` per turnover side;
- no C2/V1 or other execution overlay is introduced in this stage.

Stage26 deliberately isolates the Universe-selection problem from later execution overlays.

## Decision cadence and information set

Universe decisions are monthly.

For each trading month-end `t`:

1. Define the point-in-time candidate set `C_t` as all non-cash ETFs with `universe_eligible == True` at `t`.
2. Do **not** require `trend_eligible == True` at `t`. An ETF that is dormant at the decision date may become OLS-eligible during the next month, and excluding it would recreate the replacement-emergence problem identified in Stage20.
3. Freeze one Universe `U_t subseteq C_t` for the entire next monthly decision interval.
4. Apply that same `U_t` to all daily OLS signals from month-end `t` through the trading day immediately before the next month-end decision.

The final executable policy will later be required to satisfy `U_t = g(X_<=t)`. The oracle in this stage uses future returns only for label/upper-bound construction and is explicitly non-executable.

## Frozen portfolio-value objective

For each monthly interval, maximize self-contained log portfolio growth under the frozen downstream OLS path.

For every daily selected target, use its open-to-open log return. Penalize each turnover side by `-log(1 - SIDE_COST)`.

The monthly interval is treated as cash before the first signal and cash after the final signal, so entry and exit costs are included and month-level oracle values are path-independent across intervals.

This objective is fixed before observing Stage26 results. No return/risk/cost weight search is allowed in this stage.

## Exact set oracle

Let binary `x_i` indicate whether ETF i is admitted to the month-level Universe.

For each signal day d, binary `y_{d,i}` is constrained to equal 1 exactly when ETF i is the highest-score trend-eligible ETF that day among symbols with `x_i = 1`.

Continuous turnover-side variables linearize daily changes in the target vector.

The resulting objective is a mixed-integer linear program (MILP):

- primary solve: maximize monthly log portfolio value;
- secondary solve: among solutions with the same optimum within numerical tolerance, minimize `sum_i x_i`.

Therefore the reported oracle is the **minimum-cardinality value-optimal Universe**, not a fixed-K solution.

An empty Universe is permitted. If cash dominates every admissible OLS path for a month, `K*=0` is a valid structural result.

## Why cardinality is not pre-fixed

The central hypothesis is that candidate count has an endogenous trade-off:

smaller Universe -> less OLS competition noise / longer effective Top1 tenure

but

smaller Universe -> worse opportunity coverage / more missed emerging trends

Stage26 therefore does not choose K in advance. The observed oracle `K*` distribution is itself an output.

## Required structural outputs

For each decision month report at least:

- candidate count `|C_t|`;
- oracle size `K*`;
- oracle monthly value;
- full-market value;
- Fixed15-intersection value;
- best-singleton oracle value;
- random same-size benchmark mean and upper quantile;
- oracle target-path switch count;
- adjacent-month oracle Jaccard similarity;
- fraction of oracle members that were not trend-eligible at decision time.

Across the full sample and separately for 2021-24 and 2025-26 report:

- distribution of `K*`;
- oracle minus full-market value gap;
- oracle minus Fixed15 value gap;
- oracle minus random-same-K gap;
- frequency of `K*=0`, `K*=1`, small K, and larger K;
- oracle composition stability.

## Local counterfactual labels

After solving `U*_t`, generate per-symbol set-level local labels without additional model fitting:

For i in U*:

`remove_loss_i = V(U*) - V(U* \ {i})`

For j not in U*:

`add_delta_j = V(U* union {j}) - V(U*)`

These labels measure marginal value **conditional on the rest of the set**. They are preferred over treating oracle membership as an independent ETF quality label.

Store the point-in-time state at decision date beside these future labels so later stages can test whether conditional set value is identifiable from `X_<=t`.

## Stage26 is diagnostic, not a strategy backtest

The oracle uses future next-month returns and therefore cannot be promoted directly.

Its purpose is to determine whether the optimization problem has useful structure before fitting an executable policy:

1. Does a materially better subset than full market exist often enough to matter?
2. Is the value-optimal cardinality genuinely variable across time?
3. Is the optimum usually very small, broad, or regime-dependent?
4. Is composition stable enough for point-in-time learning to be plausible?
5. Are important members often dormant at decision time?
6. Are local add/remove values concentrated enough to support a low-DoF set-value surrogate?

## Branch rule

Proceed to a point-in-time policy-learning stage only if Stage26 shows both:

- a non-trivial and repeated oracle value gap versus simple baselines; and
- enough temporal/set structure that the problem is not merely an unstable hindsight winner search.

If oracle value barely improves on full market, Universe optimization has little economic headroom and the research should stop or weaken.

If oracle value is large but oracle sets are extremely unstable and local labels show no persistent state relationship, classify the bottleneck as identifiability rather than search capacity. Do not respond by tuning K, features, or neural-network capacity on the same OOS history.

## Anti-overfit rules

Stage26 prohibits:

- fitting a predictive model;
- choosing a fixed K from future results;
- feature search;
- threshold search;
- objective-weight search;
- changing the monthly horizon after viewing results;
- choosing only favorable months or eras;
- promoting the oracle as an executable strategy.

The next executable stage must use strict expanding/walk-forward training and may use only information available at each decision time.
