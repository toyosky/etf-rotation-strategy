# Trendability Stage 1 result — 2026-09-11

Status: **REJECT_STAGE1_V1**

This result is evaluated strictly against the preregistration in `research/trendability_stage1_preregister_20260911.md`. No parameter, horizon, health threshold, shrinkage constant, liquidity threshold, or asset-class exclusion was changed after observing results.

## Data

- Daily bars: 1,201,149 rows / 1,090 products.
- Taxonomy coverage: 1,090 products.
- Monthly representative rows: 6,327.
- Ever-selected liquidity representatives: 225 products.
- Distinct underlying exposures seen historically under the frozen universe screen: 148.
- Healthy representative-trend events: 3,837.

Representative selection is point-in-time monthly, using only the prior trading day:
1. median amount60 descending;
2. average amount60 descending;
3. history bars descending;
4. symbol ascending.

Healthy event is frozen as representative trend state + ScoreDelta > 0 + valid ResistancePct252 < 75, with one first healthy event per continuous representative/trend segment.

Primary outcome is 10-trading-day close return residualized against the equal-weight return of the other monthly representatives.

Trendability estimator is the frozen shrunk historical mean residual continuation with `k=10`.

## Primary 2021–2024

- Total healthy events: 1,913.
- Scored events: 1,776.
- Scored coverage: 92.84%.
- Scored symbols: 130.
- Spearman(Trendability, future residual): **+0.0142**.

Event-weighted quintile mean forward-10 residual return:

| Quintile | Mean residual | Events |
|---|---:|---:|
| Q1 | -0.2085% | 346 |
| Q2 | -0.2411% | 378 |
| Q3 | +0.0930% | 356 |
| Q4 | -0.2177% | 329 |
| Q5 | +0.0129% | 367 |

- Q5 - Q1: **+0.2214 pp**.
- Adjacent non-negative quintile steps: **2 / 4**.
- Preregistered requirement: >=3 / 4.

Symbol-equal mean residual returns are even less supportive:

| Quintile | Symbol-equal residual |
|---|---:|
| Q1 | +0.7494% |
| Q2 | -0.1651% |
| Q3 | +0.0250% |
| Q4 | -0.6871% |
| Q5 | -0.9128% |

Thus the primary sample fails the monotonicity requirement. The Spearman relation is effectively zero despite Q5 being slightly above Q1 on the event-weighted mean.

### Preregistered decision rule

KEEP required all three:
1. Spearman > 0 — **pass, but economically negligible (+0.0142)**.
2. Q5 mean residual > Q1 — **pass (+0.2214 pp)**.
3. >=3/4 adjacent quintile steps non-negative — **fail (2/4)**.

Therefore: **REJECT_STAGE1_V1**.

## Posterior 2025–2026

Posterior evidence reinforces rather than rescues the rejection:

- Events: 1,432; scored: 1,332; coverage 93.02%.
- Spearman: **-0.0351**.
- Q1 residual mean: **+0.3562%**.
- Q5 residual mean: **-0.5077%**.
- Q5 - Q1: **-0.8639 pp**.
- Adjacent non-negative steps: **1/4**.
- Q1 symbol-equal residual: +0.8332%.
- Q5 symbol-equal residual: -2.0554%.

## Year-by-year stability

| Year | Spearman | Q5-Q1 residual | Non-negative adjacent steps |
|---|---:|---:|---:|
| 2021 | +0.0549 | +1.4785 pp | 3/4 |
| 2022 | -0.0819 | -0.5709 pp | 2/4 |
| 2023 | +0.0761 | +0.5931 pp | 3/4 |
| 2024 | -0.0041 | -0.2163 pp | 1/4 |
| 2025 | -0.0769 | -1.0739 pp | 2/4 |
| 2026 | +0.0040 | -0.6373 pp | 1/4 |

The relation is regime-dependent and not stable enough to serve as a slow asset prior.

## Interpretation

This test **does not reject the broader idea that assets differ in OLS tradability**. Earlier fixed15-vs-outsider diagnostics already showed meaningful asset-identity differences even after conditioning on local trend health.

It rejects this specific construction:

> An asset's shrunk unconditional historical mean 10-day residual return after generic healthy OLS events is a stable predictor of future healthy-event continuation.

The main implication is that the useful asset prior is unlikely to be a single stationary historical mean. Plausible future hypotheses, which require separate preregistration rather than tuning this test, include:

- trendability is conditional on macro/market regime rather than stationary;
- some exposures are persistent trend assets while others behave as rare regime-option assets;
- event frequency, continuation duration, tail payoff shape, or drawdown profile may be more stable asset traits than mean fwd10 residual;
- structural exposure identity/risk-source may matter more than an asset-level scalar historical mean.

No Stage 2 candidate-pool backtest should be run from this V1 Trendability score.

## Reproducibility

- Preregister: `research/trendability_stage1_preregister_20260911.md`
- Code: `research/trendability_stage1_walkforward.py`
- Workflow: `.github/workflows/trendability-stage1.yml`
- Successful GitHub Actions run: `34619167113`
- Artifact: `trendability-stage1-34619167113` (artifact id `10271911244`)
