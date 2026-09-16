# OURE Stage8P — OLS State Map

Date: 2026-09-16
Status: descriptive state-mapping extension of frozen Stage8N; no trading rule is promoted in this stage.

## Purpose
Map the frozen FixV2 + V1-75 strategy across ALL point-in-time internal states, not only drawdown periods. The goal is to distinguish good, normal, fragile, and bad environments and to test whether superficially hot markets can be separated into healthy vs fragile trend states.

## Frozen inputs
Reuse Stage8N point-in-time percentiles without changing their definitions:
- `risk_churn20_pct252`
- `recent5_risk_episode_mean_pct252`
- `breadth_pct252`
- `median_signed_strength_pct252`

No external macro-market variables are used in Stage8P.

## Two-axis map
To avoid presuming that a hotter market is always better, call the first axis **Heat**, not Opportunity.

`Heat = (breadth_pct252 + median_signed_strength_pct252) / 2`

Interpretation: how broad and strong the cross-asset trend environment currently is.

`Stability = ((100 - risk_churn20_pct252) + recent5_risk_episode_mean_pct252) / 2`

Interpretation: whether recent OLS leadership is persistent and rank competition is calm.

Each axis is divided mechanically into thirds using point-in-time percentile scale:
- Low: [0, 33.33)
- Mid: [33.33, 66.67)
- High: [66.67, 100]

This produces a 3x3 map:
- Cold / Moderate / Hot
- Fragile / Neutral / Stable

No threshold search and no weighting optimization are performed.

## Primary historical window
The full map is computed where all four Stage8N percentiles exist. For interpretation of cross-sectional breadth, the primary table uses dates with at least 8 OLS-ready risk assets. In current-carrier history this starts 2020-03-02 and avoids over-interpreting the sparse 2015–2019 universe.

## Outcomes
For each state report frozen FixV2 + V1-75 forward outcomes at 5, 10 and 20 execution sessions:
- mean return
- median return
- win rate
- 10th and 90th percentile returns
- mean future maximum drawdown

Also report the naturally non-overlapping next-session V1 return conditional on each state. A coarse every-20th-session robustness table is retained as a small-sample diagnostic only.

## Interpretation discipline
- Stage8P is descriptive, not a new production rule.
- Do not call a state 'best' solely from mean forward return; require consistency across horizon, median, win rate, tails and one-step returns.
- A finding that `Hot + Fragile` is weak would support the distinction between late-stage heat and healthy trend persistence.
- Any future position-sizing rule must be frozen and backtested separately after this map is documented.
