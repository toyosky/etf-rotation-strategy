# OLS Factor Decomposition — Annualized Trend vs R²

Date: 2026-09-30

## Formula correction

Production OLS:

- annualized = exp(slope * 250) - 1
- R² is clipped to [0, 1]
- continuous raw_score = annualized * R²
- trading eligibility masks annualized <= 0 to zero / ineligible

Therefore production cannot create a "negative × negative = positive" score.

Across the current 13-risk-asset history, 23,651 valid OLS windows were checked:
- negative R² observations: 0
- minimum raw R²: ~9.7e-9
- maximum raw R²: ~0.9769

A legacy research helper contains a redundant annual<0 and r2<0 branch, but it is not economically active in the observed data and does not match the production clipping logic.

## Separate information content

Cross-sectional mean rank IC to future 20-session return:

### 2021–2024
- annualized: +0.0506
- R²: +0.0232
- raw_score = annualized * R²: +0.0659

### 2025–2026
- annualized: +0.1318
- R²: +0.0945
- raw_score: +0.1397

The product retains more information than either component alone in the recent period.

## Conditional interpretation

R² is not an independent bullish factor. It is trend confidence.

When annualized > 0:
- 2025–26 R² 20d rank IC: +0.0726
- 2021–24 R² 20d rank IC: +0.0537

When annualized <= 0:
- 2025–26 R² 20d rank IC: -0.0251
- 2021–24 R² 20d rank IC: -0.0319

Thus:
- positive slope + high R² = stable uptrend
- negative slope + high R² = stable downtrend
- low R² = weak/irregular trend, irrespective of direction

## Interaction evidence

2025–26, among the highest annualized-trend tertile:
- low-R² group: future 20d mean -1.37%, median -2.25%
- medium-R² group: +3.71%, median +0.77%
- high-R² group: +4.18%, median +2.24%

So a very high annualized slope without fit quality is often a noisy spike rather than a durable trend. R² is doing real filtering work.

For clearly negative annualized trends, high R² is worse:
- low-R² negative-trend group: future 20d mean +0.78%, median +0.67%
- high-R² negative-trend group: +0.20%, median -0.58%

This does not make low-R² negative trends a buy signal; it means the downtrend is less structurally persistent.

## Implication

The two components should be logged separately in the auxiliary radar:

1. annualized = direction and speed
2. R² = trend persistence / fit quality
3. raw_score = signed combination

Do not rank negative raw_score mechanically as a return forecast. In the negative region, mean reversion and trend persistence coexist and raw_score has weak predictive IC.

For positive-trend candidate selection, the multiplicative score remains economically defensible because it suppresses high-slope / low-quality spikes.
