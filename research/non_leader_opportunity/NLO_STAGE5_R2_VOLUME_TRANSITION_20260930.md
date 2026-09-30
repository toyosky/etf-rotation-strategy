# OLS Transition Study — R² Collapse × Volume

Date: 2026-09-30

Status: diagnostic only; no production-rule change.

## Question

Does large trading activity improve the usefulness of R² collapse as an early buy signal?

## Data and normalization

Current 13-risk-asset pool, 2021 onward.

Trading activity is measured with turnover amount rather than raw share volume:

`amount_ratio = current trading amount / trailing 20-session mean amount`

Coverage from 2021 onward is 100% for all 13 current risk assets.

R² collapse is measured continuously as:

`dr2_5 = R²_t - R²_{t-5}`

Negative values mean R² has collapsed over the previous five sessions.

Analysis conditions on annualized < 0 and compares observations within similar annualized-magnitude bands to reduce slope-level confounding.

## Result 1 — volume alone is not a buy signal

Within negative-trend / R²-collapse observations, high amount_ratio does not produce consistently higher future 5/10/20-session returns across 2021–24 and 2025–26.

Several high-volume cells are worse than normal- or low-volume cells.

Therefore:

> R² collapse + high volume is not sufficient evidence for an entry rule.

## Result 2 — price direction matters

When the old negative trend is already close to zero and R² is in the strongest-collapse group, a high-volume **up day** is much more informative about an imminent OLS sign flip.

For the near-zero negative annualized band + strongest 5-day R² collapse:

### 2021–2024
High-volume up-day:
- annualized turns positive within next 5 sessions: ~75%
- future 20-session average return: ~+0.56%

### 2025–2026
High-volume up-day:
- annualized turns positive within next 5 sessions: ~75%
- future 20-session average return: ~+0.97%

Thus the cross-period stable information is:

> High-volume upside participation during R² collapse helps confirm that the OLS direction is likely to flip soon.

The return evidence is much weaker and not sufficient to call this a buy signal.

## Result 3 — high-volume down days are different

High volume on a down/flat day during R² collapse does not have the same sign-flip probability.

This is consistent with volume being direction-agnostic:
- volume may represent buying pressure / absorption;
- or selling pressure / capitulation.

Therefore amount must be interpreted jointly with price direction.

## 513290 September 2026

The current 513290 episode fits the transition-confirmation pattern:

- 2026-09-23:
  - daily return +3.69%
  - amount_ratio ~1.85x
  - annualized ~-17.1%
  - R² ~0.039
  - 5d R² change ~-0.197

- 2026-09-28:
  - daily return +1.65%
  - amount_ratio ~2.45x
  - annualized ~-10.5%
  - R² ~0.017
  - 5d R² change ~-0.308

- 2026-09-29:
  - daily return +2.68%
  - amount_ratio ~2.12x
  - annualized turns positive to ~+14.1%
  - R² remains low at ~0.019

So on 09-28, one session before the production OLS re-entered the positive branch, both structural and volume-price evidence were already saying:

> the prior negative trend had broken down and upside participation was active.

## Interpretation

The evidence currently supports a three-layer interpretation:

1. annualized < 0 + high R²
   - coherent downtrend

2. annualized < 0 + collapsing R²
   - old downtrend losing structure

3. collapsing R² + unusually high volume + positive price move
   - stronger evidence that direction may flip positive soon

This third layer is a **transition confirmation signal**, not yet a proven return/entry signal.

## Decision

Do not add an automatic buy rule.

For the auxiliary radar, it is justified to log:
- annualized
- R²
- dr2_5
- amount_ratio_20
- daily price return
- whether annualized crosses zero within subsequent observations

Future research should evaluate whether multi-day accumulation (e.g. 3-day positive return + sustained elevated amount) predicts realized forward return more robustly than a single high-volume up day.
