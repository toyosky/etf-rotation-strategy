# Healthy Leader Independence Diagnostic — preregistration

Date: 2026-09-09
Status: preregistered, results pending

## Motivation
The preceding healthy-trend attribution found that, in 2021-2024, Cluster90 healthy leaders outside fixed15 had negative forward drift while fixed15 alternatives on the same dates had positive forward drift. The same fixed15 assets did not deteriorate when selected by Cluster90. This points to an asset-identity / universe-prior effect rather than merely a large-cross-section argmax problem.

## Question
Is the fixed15 advantage associated with lower exposure to the common cross-sectional ETF/equity factor, i.e. greater return-path independence from the rest of the eligible Cluster90 opportunity set?

## Frozen design
- Same exact OLS / Cluster90 / healthy-leader definition as `healthy_trend_universe_attribution_20260909.md`.
- Primary sample 2021-2024; 2025-2026 posterior.
- At each healthy Cluster90 leader entry, use only prior 120 trading-day close returns.
- Compute against the other current Cluster90 trend-eligible candidates:
  1. median pairwise correlation;
  2. mean pairwise correlation;
  3. share of peers with correlation >=0.50;
  4. correlation to the equal-weight return series of the other eligible candidates (common-factor proxy).
- Compare fixed15 member leaders vs outside-fixed15 leaders.
- Within outside-fixed15 leaders, split at the period median of the common-factor correlation for descriptive diagnosis only. The median is not a proposed trading threshold.
- Report Spearman correlation between independence metrics and forward 10d return.
- No threshold search and no strategy backtest.

Interpretation:
- If fixed15 leaders are substantially more independent and low-common-factor outsiders also have better follow-through, independence is a plausible ex-ante universe-selection primitive.
- If independence does not separate forward returns, the next candidate prior should be asset-level historical trendability rather than correlation structure.
