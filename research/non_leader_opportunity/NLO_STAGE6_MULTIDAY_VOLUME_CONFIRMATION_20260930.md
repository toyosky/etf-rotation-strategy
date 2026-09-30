# OLS Transition Study — Multi-day Price/Volume Confirmation

Date: 2026-09-30

Status: diagnostic only; no production-rule change.

## Question

Does multi-day positive price action plus elevated trading activity, when R² is collapsing and annualized is still negative, provide a robust early-entry signal?

## Setup

Current 13-risk-asset pool, 2021 onward.

Core structural state:
- annualized < 0
- R² declining over the previous 5 sessions

Exploratory multi-day confirmation:
- 3-session price return > 0
- 3-session average trading amount > trailing 20-session average
- current amount ratio higher than prior session

Trading activity uses amount rather than share volume.

## 1. Signal timing

When annualized is in its least-negative tercile and 5-day R² change is in its strongest-collapse tercile, the multi-day confirmation is strongly associated with a near-term OLS sign flip.

After de-duplicating first signal occurrences:

### 2021–2024
- 58 first signal events
- annualized positive within next 5 sessions: 72.4%
- future 20-session mean return: +1.23%
- future 20-session median return: 0.0%
- 20-session win rate: 46.6%

### 2025–2026
- 25 first signal events
- annualized positive within next 5 sessions: 72.0%
- future 20-session mean return: +3.14%
- future 20-session median return: +1.05%
- 20-session win rate: 60.0%

A sequence test that first waits for the R²-collapse state and then allows up to five sessions for the first multi-day price/volume confirmation gives similar sign-flip probabilities:

- 2021–2024: 77.6%
- 2025–2026: 79.0%

Therefore the robust part is transition timing.

## 2. Return strength is not stable through time

Year-level future 20-session return after the sequence signal:

- 2021: +2.12% (n=7)
- 2022: -0.37% (n=9)
- 2023: -1.19% (n=15)
- 2024: +1.61% (n=18)
- 2025: +2.01% (n=12)
- 2026: +4.28% (n=7), but median -0.77%

The 2026 mean is driven by a small number of large winners; the median is negative.

This is not a stable entry-return signal.

## 3. Continuous, threshold-free check

To reduce overfitting from tercile and threshold definitions, define a continuous price-volume intensity:

`flow3 = 3-session return * (3-session average amount / 20-session average amount)`

Then restrict only to:
- annualized < 0
- 5-day R² change < 0

Cross-sectional mean rank IC of flow3 to future return:

### 2021–2024
- 5d: -0.043
- 10d: -0.051
- 20d: -0.022

### 2025–2026
- 5d: +0.001
- 10d: +0.006
- 20d: -0.038

So higher positive price-volume intensity does **not** monotonically predict higher forward return.

This is the strongest evidence against treating volume as a direct buy factor.

## 4. 513290 September 2026

513290 triggered the exploratory multi-day confirmation twice:

### 2026-09-23
- 3d return: +3.99%
- current amount ratio: 1.85x
- 3d average amount ratio: 1.14x
- annualized: -17.1%
- R²: 0.039
- 5d R² change: -0.197
- exploratory signal: TRUE

### 2026-09-28
- 3d return: +1.53%
- current amount ratio: 2.45x
- 3d average amount ratio: 1.69x
- annualized: -10.5%
- R²: 0.017
- 5d R² change: -0.308
- exploratory signal: TRUE

Annualized turned positive on 2026-09-29.

Thus the 513290 episode is a very good example of **transition confirmation**, but it must not be used as proof of a profitable entry rule.

## Interpretation

The evidence supports:

1. R² collapse
   - old trend structure is failing

2. R² collapse + multi-day positive price/volume activity
   - much higher probability that annualized will cross above zero soon

It does **not** support:

3. R² collapse + multi-day positive price/volume activity
   - reliably high subsequent investment return

The stable prediction target is **OLS state transition**, not forward return.

## Decision

Do not promote volume to a buy factor.

Use price/volume activity, if retained, as an auxiliary transition-confirmation diagnostic only.

The production OLS entry logic should remain unchanged until an out-of-sample return effect is demonstrated.
