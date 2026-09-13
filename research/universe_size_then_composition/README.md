# Universe Size → Composition Research

Status: active
Start date: 2026-09-14

This is a new research lineage. Previous `research/marginal_universe_value/` stages are frozen historical evidence and are not continued under their old stage numbers.

## Research question

At month-start t, suppose future one-month outcomes are available only for Oracle diagnosis. From the point-in-time tradable representative ETF market, what Universe size and composition would maximize the value of the frozen downstream OLS rotation rule?

The new lineage deliberately separates two degrees of freedom:

1. **Size first** — determine whether OLS has a structurally favorable Universe-size range.
2. **Composition second** — after that range is frozen, study which ETFs should occupy the limited seats using only information available at t for executable models.

The goal is not to find a single historically optimal K. The goal is to identify whether a stable range exists, why it exists, and whether membership inside that range is predictably selectable out of sample.

## Stage map

- **New Stage 1 — Oracle Universe Size Monte Carlo**
  - point-in-time representative ETF parent pool;
  - independent random Universes for each K, preferably K=3..30 subject to availability;
  - multiple nested deletion paths only as secondary evidence;
  - return distribution by month and K, not only best subsets.

- **New Stage 2 — Size mechanism / OLS remaining-life audit**
  - distinguish observed Top1 tenure from the ETF's own **remaining trend life after first Top1 admission**;
  - test whether larger K delays Top1 admission within the underlying trend episode and reduces remaining life / remaining return;
  - relate K to effective competitor count, correlation, rank turnover, opportunity coverage and other set state.

- **New Stage 3 — Stable K range**
  - identify a cross-month / cross-era robust favorable K range rather than a precise hindsight optimum;
  - reject the fixed-range hypothesis if K is unstable and not explainable by observable market state.

- **New Stage 4 — Composition Oracle within frozen K range**
  - hold the size range fixed;
  - study member conditional marginal value, opportunity coverage, ranking nuisance and redundancy.

- **New Stage 5 — Walk-forward executable selection**
  - use only X<=t;
  - K comes only from previously frozen size-range logic;
  - select members and hold the Universe fixed for the next month while running the same frozen OLS rule.

## Important distinction: OLS remaining life

`remaining_trend_life` means the residual life of the ETF's underlying trend episode **after the ETF first becomes OLS Top1**. It is not the number of consecutive days the ETF remains ranked Top1 inside a given Universe.

The working mechanism hypothesis is intentionally treated as unproven:

`larger K → stronger rank competition → later Top1 admission within trend episode → shorter remaining trend life → weaker realized OLS value`

An opposing force may also exist:

`K too small → poor opportunity coverage / weak trends win too easily → weaker realized OLS value`

If both forces exist, an intermediate favorable K range may emerge.

## Historical precursor

`research/universe/universe_width_oracle_v1.py` is a useful precursor, but it is not sufficient evidence for this new question because it primarily studies subsets of Fixed15 and a limited period. New Stage 1 must use monthly point-in-time representative market pools and independent same-K random samples across periods.
