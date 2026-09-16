# OURE Stage8P — OLS State Map Findings

Date: 2026-09-16
Status: descriptive exploratory finding. No production position-sizing rule is promoted here.

## Executive finding
The frozen Stage8N internal variables contain information across the full market-state space, not only in drawdowns. The strongest pattern is a separation between **healthy persistent trend states** and **hot but fragile states**.

Stage8P defines:

`Heat = (BreadthPct252 + MedianSignedStrengthPct252) / 2`

`Stability = ((100 - ChurnPct252) + Recent5Top1LifePct252) / 2`

Each axis is mechanically split into thirds: Low / Mid / High. The primary interpretation sample requires at least 8 OLS-ready risk assets, beginning 2020-03-02.

## Primary 20-session state map (FixV2 + V1-75)

| Heat | Stability | n | Mean fwd20 | Median fwd20 | Win rate | 10% tail | Mean fwd MDD |
|---|---|---:|---:|---:|---:|---:|---:|
| Cold | Fragile | 214 | 5.23% | 1.68% | 54.7% | -12.66% | -8.69% |
| Cold | Neutral | 199 | 2.66% | 1.92% | 59.8% | -10.37% | -8.22% |
| Cold | Stable | 124 | 5.91% | 1.29% | 62.9% | -4.28% | -5.69% |
| Moderate | Fragile | 186 | 4.34% | 4.70% | 63.4% | -10.23% | -7.45% |
| Moderate | Neutral | 172 | 6.45% | 2.50% | 66.9% | -4.88% | -6.65% |
| **Moderate** | **Stable** | **149** | **10.28%** | **5.64%** | **80.5%** | **-3.08%** | **-6.06%** |
| **Hot** | **Fragile** | **181** | **1.35%** | **1.36%** | **56.4%** | **-8.99%** | **-8.21%** |
| Hot | Neutral | 237 | 4.79% | 4.13% | 68.4% | -4.83% | -6.61% |
| Hot | Stable | 107 | 7.99% | 3.96% | 70.1% | -5.17% | -6.60% |

The map is not monotonic in Heat. High Heat is beneficial only when leadership remains reasonably persistent. The sharp contrast is between `Moderate + Stable` and `Hot + Fragile`.

## Horizon consistency

### Moderate + Stable
- 5d: mean +2.73%, median +1.51%, win 62.4%, 10% tail -2.61%
- 10d: mean +5.34%, median +2.60%, win 72.5%, 10% tail -1.75%
- 20d: mean +10.28%, median +5.64%, win 80.5%, 10% tail -3.08%

### Hot + Fragile
- 5d: mean +0.52%, median 0.00%, win 49.7%, 10% tail -4.98%
- 10d: mean +0.35%, median -0.12%, win 49.7%, 10% tail -6.90%
- 20d: mean +1.35%, median +1.36%, win 56.4%, 10% tail -8.99%

### Hot + Stable
- 5d: mean +1.45%, median +0.10%, win 50.5%, 10% tail -4.16%
- 10d: mean +3.76%, median +2.36%, win 68.2%, 10% tail -7.65%
- 20d: mean +7.99%, median +3.96%, win 70.1%, 10% tail -5.17%

This supports the interpretation that heat itself is not bad; **heat without persistence** is the weaker state.

## Naturally non-overlapping next-session check
Conditioning the actual next-session V1 return on the same state map also preserves the main contrast:
- Moderate + Stable: mean +0.549% per conditioned session, Sharpe-like 2.66
- Hot + Fragile: mean +0.093%, Sharpe-like 0.42
- Hot + Stable: mean +0.248%, Sharpe-like 1.86

These are conditional-session statistics, not a tradable portfolio backtest, but they reduce the concern that the 20-day map is only an overlap artifact.

## Annual-state structure
The map also distinguishes different strong years rather than labeling all rising years the same way.

2025:
- Moderate + Stable is the largest single cell, about 20.6% of mapped trading days.
- Hot + Neutral about 19.3%.
- Hot + Stable about 9.5%.

2024:
- Hot + Fragile is the largest single cell, about 25.6%.
- Moderate + Fragile about 22.3%.
- Hot + Stable only about 0.8%.

This is consistent with 2025 containing more persistent trend episodes, while 2024 generated substantial returns in a more competitive/fragile leadership structure.

## 2026 drawdown context
The 20 signal sessions before the June 2026 maximum-drawdown start were not internally 'hot'. They were mostly already cooling:
- Cold + Neutral: 55%
- Moderate + Fragile: 20%
- Hot + Fragile: 10%
- Cold + Stable: 10%
- Moderate + Neutral: 5%

During the June–August drawdown:
- Cold + Fragile: about 63.6%
- Hot + Fragile: about 20.0%
- Cold + Neutral: about 14.5%

This strengthens the earlier Stage8N interpretation: the internal FixV2 cross-asset panel was deteriorating before the broad external market panel visibly broke.

## Important caveats
1. State8P is still same-sample historical mapping. The two-axis construction was motivated after Stage8N diagnostics, so it is not prospective validation.
2. The every-20th-session non-overlap 20-day sample is small (79 observations total); individual 3x3 cells contain only 4–13 observations and are too noisy to rank states reliably. It is retained only as a robustness warning, not as primary evidence.
3. `Moderate + Stable` should therefore be called the strongest descriptive candidate state, not a validated optimal regime.
4. Cold + Fragile has a surprisingly positive mean forward return but very poor tails, illustrating why mean return alone is misleading; it appears to mix rebounds/large winners with high downside risk.
5. No leverage or state-dependent position sizing is tested in Stage8P.

## Current interpretation
A more complete internal regime model is plausible:
- **Healthy Trend:** Moderate heat + high stability. Broad enough and strong enough, but leadership remains persistent.
- **Hot Stable:** strong trend environment that remains investable, but with somewhat weaker short-horizon quality than Healthy Trend.
- **Hot Fragile:** superficially strong cross-asset environment with unstable leadership; substantially weaker forward distribution.
- **Cold Fragile:** stressed/unstable state with especially poor left-tail risk despite occasional large rebounds.

The next valid experiment is not to add more indicators. It is to freeze a small set of state-dependent exposure rules and test whether the state map adds portfolio value without threshold tuning.
