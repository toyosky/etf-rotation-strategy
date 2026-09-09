# Healthy Leader Independence Diagnostic

Date: 2026-09-09
Status: completed

## Question
Is the fixed15 advantage associated with lower exposure to the common cross-sectional ETF/equity factor, i.e. greater return-path independence from the rest of the eligible Cluster90 opportunity set?

## Frozen design
- Same OLS / Cluster90 / healthy-leader definition as `healthy_trend_universe_attribution_20260909.md`.
- Primary 2021-2024; posterior 2025-2026.
- At each healthy Cluster90 leader entry, use only prior 120 trading-day close returns.
- Compare leader with other current Cluster90 trend-eligible candidates using mean/median pairwise correlation, share of peer correlations >=0.50, and correlation to an equal-weight peer return factor.
- At least 60 overlapping observations required.
- No threshold search and no strategy backtest.

## Main result 1 — fixed15 leaders are structurally much more independent
2021-2024 healthy Cluster90 leaders:

| Group | n | Fwd10 | Mean peer corr | Median peer corr | Corr to peer common factor |
|---|---:|---:|---:|---:|---:|
| Fixed15 members | 20 | +0.67% | **0.12** | **0.09** | **0.23** |
| Outside fixed15 | 144 | -0.47% | 0.30 | 0.31 | 0.55 |

Only about 5.4% of fixed15 peer relationships were >=0.50 correlation, versus 26.7% for outside leaders.

2025-2026 shows the same structural distinction:
- fixed15 common-factor corr ~0.31;
- outsiders ~0.60.

So the curated fixed universe is genuinely more cross-asset / less common-factor dominated than the typical Cluster90 outsider.

## Main result 2 — independence alone is not a sufficient selector
Within outside-fixed15 leaders in 2021-2024, splitting at the period median common-factor correlation:
- more independent half: Fwd10 -0.20%;
- more common-factor half: Fwd10 -0.75%.

Independence improves the result, but even the more-independent outsiders remain negative on average.

Worse, the posterior period reverses:
- more independent outsiders: Fwd10 -1.47%;
- more common-factor outsiders: +0.73%.

Spearman relationships between correlation metrics and Fwd10 are weak in both periods (roughly -0.04 to -0.07 in 2021-2024 and +0.09 to +0.17 in 2025-2026).

Therefore a rule such as `average correlation must be below X` would be a weak and regime-sensitive filter.

## Interpretation
The fixed15 advantage has a real structural component: its assets are much more independent from the dominant cross-sectional ETF factor. This is consistent with its intentional cross-asset composition (commodities, overseas equity, broad domestic equity, bonds/cash proxies rather than many related domestic themes).

However, **low correlation is only a descriptor of the useful universe prior, not the missing alpha condition itself**. Many low-correlation Cluster90 outsiders still fail to deliver positive follow-through.

This pushes the next research step toward **asset-level historical trendability**: estimate, using only information available before each date, whether a given ETF historically converts an OLS-positive/healthy state into positive residual forward return and durable leadership. That is closer to the missing property than another contemporaneous price-shape threshold.

## Reproducibility
- Code: `research/healthy_leader_independence_diagnostic.py`
- Workflow: `.github/workflows/healthy-leader-independence.yml`
- Successful run: `34342807507`
- Preregistration commit: `ae2164c2bf727ac700354aabfe7ac1ef9cedde33`
