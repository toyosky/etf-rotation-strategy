# Non-Leader Opportunity Study — Stage 2

Date: 2026-09-30  
Status: completed exploratory decomposition; diagnostic only; no live-rule change.

## 1. Shadow leaders: Top2–5 are not harmless ranking noise

Daily observations first showed that 2025–2026 Rank2–3 assets had average future 20-session return around +3.67%, and Rank4–5 around +2.30%.

To reduce overlap, Stage 2 uses **first-entry shadow episodes**: an episode begins when an asset newly enters Rank2–3 or Rank4–5.

### First-entry shadow episodes

| Period | State | Episodes | Avg fwd20 | Beat same-day Top1 over 20d | +8% hit | Become Top1 within 20d | Median delay |
|---|---|---:|---:|---:|---:|---:|---:|
| 2021–24 | Rank2–3 | 353 | +1.62% | 46.7% | 13.6% | 39.9% | 5d |
| 2021–24 | Rank4–5 | 494 | +1.14% | 47.0% | 10.5% | 22.9% | 10d |
| 2025–26 | Rank2–3 | 167 | +2.58% | **53.9%** | 16.8% | 41.9% | 4d |
| 2025–26 | Rank4–5 | 241 | +2.23% | 48.6% | 17.0% | 22.8% | 8d |

Interpretation:

- In 2025–2026, a newly entering Rank2–3 asset subsequently beats the current Top1 over 20 sessions slightly more often than not.
- Yet fewer than half of these Rank2–3 shadow episodes ever become Top1 within the same 20-session horizon.
- Rank4–5 also contains real opportunity information, although it is weaker as a winner-selection signal.

This supports a **shadow book / observation layer**, not automatic multi-asset buying.

## 2. Score=0 is at least three different states

The initial hand-written REPAIR rule was weak. Univariate quintile tests revealed a different structure.

Two thresholds were unusually stable across 2021–24 and 2025–26 quintile boundaries:

- Bottom quintile of 10d return was near -4% in both samples.
- Bottom quintile of distance to 20d high was near -8% in both samples.
- Top quintile of Signed Score among zero-score observations was near -0.01 in both samples.

Therefore Stage 2 uses rounded, economically interpretable diagnostic thresholds rather than exact fitted cutoffs.

### State definitions

**ZERO_DEEP_OVERSOLD**
- production Score = 0 / annual slope <= 0
- 10d return <= -4%
- price is >=8% below its 20d high

**ZERO_NEAR_EXIT**
- annual slope <= 0
- Signed Score >= -0.01
- not already classified as deep oversold

**ZERO_MIDDLE**
- all remaining annual <= 0 observations

### Daily-state results

| Period | State | Avg fwd20 | Median fwd20 | +5% hit | +8% hit |
|---|---|---:|---:|---:|---:|
| 2021–24 | Deep oversold | +1.27% | +1.36% | 23.2% | 11.0% |
| 2021–24 | Near exit | +0.87% | +0.67% | 17.8% | 8.0% |
| 2021–24 | Middle | +0.41% | 0.0% | 17.1% | 7.6% |
| 2025–26 | Deep oversold | **+1.76%** | **+2.23%** | **35.0%** | **21.9%** |
| 2025–26 | Near exit | +1.09% | 0.0% | 20.7% | 13.4% |
| 2025–26 | Middle | +0.23% | 0.0% | 18.7% | 10.8% |

The deep-oversold state is not "trend repair"; it behaves more like mean reversion.

### First-entry event results

| Period | State | Episodes | Avg fwd20 | +8% hit | Re-positive within20 | Median re-positive delay | Top3 within20 | Top1 within20 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2021–24 | Deep oversold | 159 | +1.63% | 13.8% | 66.7% | 13d | 37.1% | 13.2% |
| 2021–24 | Near exit | 475 | +0.81% | 9.7% | **83.6%** | **2d** | 44.4% | 14.9% |
| 2021–24 | Middle | 385 | +0.67% | 8.6% | 69.4% | 10d | 37.1% | 12.5% |
| 2025–26 | Deep oversold | 74 | **+2.30%** | **25.7%** | 64.9% | 11d | 33.8% | 13.5% |
| 2025–26 | Near exit | 219 | +1.18% | 14.2% | **80.8%** | **2d** | 34.3% | 12.8% |
| 2025–26 | Middle | 167 | +0.89% | 15.0% | 69.5% | 9d | 29.3% | 12.6% |

This separates two mechanisms:

1. **Deep oversold** = higher subsequent return / mean-reversion candidate, but slow OLS recovery.
2. **Near exit** = strong state-transition predictor; it usually returns to positive Score quickly, but is not itself a strong return signal.

That distinction matters. A state can be useful for monitoring even if it should not trigger a buy.

## 3. 513290 September 2026 under Stage 2

513290 did not follow a simple monotonic repair path.

- 2026-09-11: ZERO_NEAR_EXIT
- 09-15 to 09-22: mostly ZERO_MIDDLE
- 09-23: ZERO_NEAR_EXIT
- 09-24: back to ZERO_MIDDLE after the >3% down day
- 09-28: ZERO_NEAR_EXIT
- 09-29: POSITIVE again

At 09-28:
- Signed Score ≈ -0.0018
- 10d return ≈ +3.5%
- still raw Score = 0

At 09-29:
- Signed Score ≈ +0.0027
- raw Score finally turns positive

So a zero-state monitor could have said **"OLS is very close to re-confirmation"** on 09-28, one session before raw Score became positive.

However, the Stage 2 evidence does not justify buying ZERO_NEAR_EXIT. Its strongest meaning is a **transition warning**.

## 4. What this changes conceptually

The cross-section now looks more naturally like:

`Top1 execution leader`
→ `Top2–3 shadow leaders`
→ `Rank4–5 emerging leaders`
→ `Score=0 state decomposition`

Within Score=0:

`Deep oversold = mean-reversion watch`

`Near exit = OLS re-confirmation watch`

`Middle = low-information zero state`

This is much richer than treating every non-Top1 asset as irrelevant.

## 5. Next test

The next stage should not add rules yet.

Priority:

1. Build a **daily shadow radar** from current data.
2. Record Top1 / Top2–3 / Rank4–5 / Zero-state for every risk asset every day.
3. Add state transitions and persistence:
   - zero -> near exit -> positive
   - rank5 -> rank3 -> rank1
   - deep oversold -> near exit
4. Then test whether **transition sequences**, rather than single-day states, improve opportunity precision.

No production promotion is justified at Stage 2.
