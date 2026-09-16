# OURE Stage8Q — State Map Position Sizing Validation

Date: 2026-09-16
Status: descriptive / same-sample validation, not yet promoted to live rule

## Frozen context
- Base strategy: Stage8M FixV2 + V1-75, 6 bp per side.
- State variables: Stage8P OLS State Map, unchanged.
- Heat = average of breadth percentile and signed-strength percentile.
- Stability = average of (100 - churn percentile) and recent Top1-life percentile.
- Heat/Stability bins remain fixed tertiles: Low/Mid/High.
- State Map is available once the frozen risk universe has at least 8 OLS-ready members (2020-03 onward). Earlier history remains full exposure.

## Primary sizing family
The rule family was frozen before running the portfolio-level test:
- Full exposure in all states except the two tail-fragile states:
  - `Low Heat + Low Stability` (Cold + Fragile)
  - `High Heat + Low Stability` (Hot + Fragile)
- In those two states, test risk exposure at 75%, 50%, and 0% (0% is stress only).
- Unallocated capital is treated as cash with zero return.
- Exposure changes and ETF switches are charged at 6 bp per side using notional turnover.

Secondary robustness checks:
- `ALL_FRAGILE`: reduce every Low-Stability state, including Mid Heat + Low Stability.
- `BADCOUNT2`: reduce exposure whenever Stage8N `bad_count >= 2`.

## Full-period results (2015-01-26 to 2026-09-14 execution; State Map active only from 2020-03)

| Rule | Cumulative | CAGR | MDD | Sharpe | Calmar | Turnover notional |
|---|---:|---:|---:|---:|---:|---:|
| Base 100% | +4390.08% | 40.34% | -38.59% | 1.162 | 1.045 | 749.0 |
| Tail-fragile -> 75% | +4073.85% | 39.43% | -35.15% | 1.206 | 1.122 | 725.5 |
| Tail-fragile -> 50% | +3693.12% | 38.25% | -31.72% | 1.233 | 1.206 | 702.0 |
| Tail-fragile -> 0% | +2818.49% | 35.06% | -25.94% | 1.202 | 1.352 | 655.0 |
| All fragile -> 50% | +3192.69% | 36.51% | -31.68% | 1.218 | 1.153 | 634.0 |
| BadCount>=2 -> 50% | +3283.32% | 36.85% | -28.22% | 1.200 | 1.306 | 685.0 |

## Interpretation of the primary family
The 50% tail-fragile rule is the clearest return/risk compromise among the pre-declared coarse exposure levels:
- CAGR cost vs base: about -2.09 percentage points/year.
- MDD improvement: about +6.87 percentage points.
- Sharpe improves from 1.162 to 1.233.
- Calmar improves from 1.045 to 1.206.
- Turnover also falls.

75% preserves more return but gives less drawdown relief. 0% minimizes drawdown most, but sacrifices too much return and is retained only as a stress case.

Reducing *all* Low-Stability states to 50% gives almost the same MDD as the tail-fragile 50% rule (-31.68% vs -31.72%) but a materially lower CAGR (36.51% vs 38.25%). This supports the Stage8P distinction that `Mid Heat + Low Stability` is not equivalent to the two tail-fragile states.

The older Stage8N `bad_count >= 2` rule is more defensive (MDD -28.22%) but also more costly to return (CAGR 36.85%), especially in strong years. The State Map therefore adds economically useful selectivity beyond a simple bad-state count.

## Annual comparison: Base vs Tail-Fragile 50%

| Year | Base return | Base MDD | Tail50 return | Tail50 MDD |
|---|---:|---:|---:|---:|
| 2020 | +60.05% | -21.14% | +51.94% | -21.14% |
| 2021 | +34.93% | -15.27% | +32.11% | -15.27% |
| 2022 | +23.87% | -33.41% | +25.82% | -27.20% |
| 2023 | +21.31% | -11.59% | +18.45% | -11.12% |
| 2024 | +65.57% | -28.12% | +68.09% | -19.12% |
| 2025 | +115.42% | -22.43% | +121.25% | -22.43% |
| 2026 partial | +134.99% | -38.59% | +106.50% | -31.72% |

Key observations:
- 2022 improves both return and drawdown.
- 2024 improves both return and drawdown materially.
- 2025 return is not harmed; the large late-year silver shock remains because it was not a tail-fragile regime. This is desirable evidence that the State Map is not masquerading as a single-asset stop-loss system.
- 2026 drawdown improves materially, but the cost is a substantial reduction in the very strong pre/post drawdown gains. This is the principal trade-off.

## Current-state implication
The latest complete Stage8P signal is 2026-09-11 (execution 2026-09-14):
- Heat: Mid
- Stability: Mid
- BadCount: 0

Under the primary tail-fragile sizing family this is a **100% standard risk-budget state**, not a reduced-risk state.

## Research conclusion
The State Map has now passed a portfolio-level plausibility test: simple, coarse, pre-declared exposure reduction in economically fragile states lowers drawdown and improves risk-adjusted performance without requiring threshold optimization.

The strongest practical candidate from this same-sample test is:

`Cold+Fragile OR Hot+Fragile -> 50% risk exposure; otherwise 100%`.

This is **not yet an out-of-sample proof**. It should be treated as a frozen candidate for forward/prospective validation, not as a historically optimized final rule.
