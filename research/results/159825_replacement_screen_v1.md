# 159825 Replacement Screen V1

Date: 2026-09-08

Status: exploratory / limited daily-signal validation only. This is **not** a full minute-execution backtest and does not change `strategy/main.py` or `asset_universe` statuses.

## Question

Can one of the current replacement candidates provide a better OLS trend-continuation profile than retired `159825`?

Candidates screened:

- `513030` Germany DAX ETF
- `513520` Nikkei 225 ETF
- `512660` military ETF

Reference: retired `159825` agriculture ETF.

## Frozen comparison frame

- Source strategy reference: `FROZEN_C2@20260903T_fixed_window_v2`
- Test window: 2021-01-04 through 2026-08-06
- Daily market data: current Supabase `daily_bars` (`gm_hfq`)
- Candidate OLS: 26 daily closes, half-life 10, squared fit weights, annualization 250
- Candidate ranking screen: candidate score must exceed the best existing eligible score on that date after excluding `159825`
- Minimum signal eligibility used in this limited screen: annualized trend > 0, R² >= 0.50, score > 0
- Forward diagnostics: 5 and 10 trading days from signal-date close
- Near-high definition: within 0.5% of the 20-trading-day closing high

Important limitations:

1. Existing `daily_scores` are reused for the incumbent pool rather than recomputed from the newly refreshed all-GM history.
2. Candidate QDII/LOF premium filters are not reproduced.
3. C2 portfolio path, cash-proxy behavior, 09:31 protections, 14:00/14:05 execution, commissions and slippage are not simulated here.
4. Consecutive Top1 days are overlapping observations and therefore are not statistically independent.

This screen answers only: **does the candidate deserve a more expensive full replacement backtest?**

## Aggregate signal-continuation results

| Symbol | Candidate-Top1 days | 5d avg | 5d win | 10d avg | 10d win | Near-high n | Near-high 10d avg | Near-high 10d win |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 159825 | 19 | -3.783% | 5.3% | -4.372% | 15.8% | 8 | -4.715% | 0.0% |
| 513030 | 74 | -0.285% | 52.7% | +0.363% | 59.5% | 47 | +0.577% | 61.7% |
| 513520 | 80 | -1.189% | 40.0% | -2.738% | 25.0% | 42 | -3.152% | 26.2% |
| 512660 | 147 | +0.853% | 52.4% | +1.385% | 59.9% | 63 | +1.365% | 60.3% |

## Period stability

### 159825

| Period | n | 10d avg | 10d median | 10d win | Near-high n | Near-high 10d avg | Near-high win |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2021-23 | 8 | -7.48% | -7.18% | 0.0% | 4 | -6.82% | 0.0% |
| 2024-26 | 11 | -2.11% | -1.78% | 27.3% | 4 | -2.61% | 0.0% |

### 513030

| Period | n | 10d avg | 10d median | 10d win | Near-high n | Near-high 10d avg | Near-high win |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2021-23 | 46 | +2.17% | +2.07% | 73.9% | 32 | +2.04% | 78.1% |
| 2024-26 | 27 | -2.78% | -1.34% | 33.3% | 15 | -2.54% | 26.7% |

Interpretation: `513030` is dramatically better than `159825` over the full sample, but the apparent edge is not stable. It was strong in 2021-23 and materially negative in 2024-26. It should **not** be promoted solely from this first screen.

### 513520

| Period | n | 10d avg | 10d median | 10d win | Near-high n | Near-high 10d avg | Near-high win |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2021-23 | 26 | -2.23% | -2.01% | 26.9% | 19 | -2.62% | 26.3% |
| 2024-26 | 54 | -2.98% | -3.83% | 24.1% | 23 | -3.59% | 26.1% |

Interpretation: `513520` currently looks poorly matched to this OLS state definition across both periods and is not a priority replacement candidate.

### 512660

| Period | n | 10d avg | 10d median | 10d win | Near-high n | Near-high 10d avg | Near-high win |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2021-23 | 66 | +0.20% | +0.61% | 60.6% | 29 | -0.55% | 58.6% |
| 2024-26 | 81 | +2.35% | +1.68% | 59.3% | 34 | +3.00% | 61.8% |

Interpretation: `512660` is the most stable candidate in this limited screen. Full-sample continuation is positive, and recent-period behavior strengthened rather than deteriorated. The early near-high mean is slightly negative, so this is not uniformly strong evidence, but it is materially more robust than `513030` and `513520`.

## Preliminary ranking for next-stage testing

1. **512660** — highest priority for a full single-variable replacement backtest.
2. **513030** — keep as a candidate, but investigate the 2024-26 deterioration before portfolio promotion.
3. **513520** — deprioritize unless a separate economic rationale emerges.

## Next stage

Before changing the formal pool, run a true single-variable portfolio experiment:

- baseline: original Premium15 / FROZEN_C2 reproduction
- test A: `159825 -> 512660`
- test B: `159825 -> 513030`
- all other parameters frozen
- recompute all daily scores from the same all-GM history for both baseline and candidates
- preserve C2, cash-proxy handling, premium logic where data permits, transaction costs and execution assumptions
- report CAGR, MDD, Sharpe, turnover, per-year results, candidate trade count and marginal contribution

Only after that experiment should `asset_universe` status be changed from `CANDIDATE` to `ACTIVE`.
