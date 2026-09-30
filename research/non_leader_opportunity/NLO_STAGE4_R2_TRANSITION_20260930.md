# OLS Transition Study — Does R² Collapse Lead the Slope Flip?

Date: 2026-09-30

Status: diagnostic finding; no production-rule change.

## Question

For assets currently in a negative OLS trend, does R² collapse before annualized slope turns positive, and is that collapse informative beyond the mechanical effect of slope approaching zero?

## Event definition

Event time t=0 is the first session where:
- previous annualized <= 0
- current annualized > 0

No threshold is imposed on R².

Current frozen 13-risk-asset pool, production-style 26-session weighted OLS.

## 1. R² collapses before zero-axis crossing

Average R² path around all negative-to-positive annualized crossings:

### 2021–2024 (271 events)
- t-10: 0.368
- t-5: 0.285
- t-3: 0.168
- t-1: 0.019
- t0: 0.015

### 2025–2026 (131 events)
- t-10: 0.358
- t-5: 0.277
- t-3: 0.183
- t-1: 0.028
- t0: 0.014

This pattern is nearly identical across the two periods.

## 2. The collapse contains information beyond annualized level

To avoid the trivial explanation "R² must fall because slope is near zero", negative-annual observations were split into annualized terciles first, then R² terciles within each annualized band.

Outcome: probability annualized crosses above zero within the next 5 sessions.

### 2025–2026

Deeply negative annualized (roughly <= -42%):
- low R²: 19.9%
- middle R²: 6.1%
- high R²: 2.5%

Moderately negative annualized (roughly -42% to -21%):
- low R²: 38.3%
- middle R²: 19.9%
- high R²: 9.1%

Near-zero negative annualized:
- low R²: 52.0%
- middle R²: 45.9%
- high R²: 26.1%

### 2021–2024

Deeply negative:
- low R²: 16.1%
- middle R²: 7.4%
- high R²: 2.4%

Moderately negative:
- low R²: 35.0%
- middle R²: 20.2%
- high R²: 10.6%

Near-zero negative:
- low R²: 59.5%
- middle R²: 46.0%
- high R²: 32.6%

The ordering is highly stable.

Interpretation:

> Conditional on roughly similar negative slope magnitude, low R² means the old downtrend is less structurally coherent and is substantially more likely to lose its negative sign soon.

This is a genuine transition signal, not just a re-expression of annualized slope.

## 3. R² collapse does NOT by itself predict a successful rally

Classify zero-axis crossings by future 20-session outcome:
- SUCCESS_5P: >= +5%
- FAIL_NONPOS: <= 0%
- MIDDLE: between 0% and +5%

Both successful and failed crossings exhibit the same pre-cross R² collapse.

2025–2026:
- success t-5/t-3/t-1/t0: 0.208 / 0.158 / 0.023 / 0.019
- failure t-5/t-3/t-1/t0: 0.277 / 0.182 / 0.024 / 0.014

Therefore R² collapse primarily answers:

> "Is the old trend breaking?"

It does NOT answer:

> "Will the new direction become a profitable persistent trend?"

## 4. Post-cross R² rebuilding is regime-dependent

At t+5 in 2025–2026:
- successful crossings: mean R² 0.408
- failed crossings: mean R² 0.249

This looks like confirmation in the recent regime.

However, when predicting the remaining return from t+1/t+3/t+5 to t+20:
- 2025–2026 R²/rebuild has positive event-level rank IC
- 2021–2024 the same relationship is negative or near zero

So "R² rebuild after crossing = buy" is not robust across periods and must not be promoted.

## 5. Practical interpretation

A more faithful OLS state description is:

1. negative annualized + high R²
   - coherent downtrend
2. negative annualized + falling/low R²
   - old downtrend is losing structure
3. annualized crosses zero while R² is near zero
   - transition point; direction has flipped but no stable new trend yet
4. positive annualized + rising/high R²
   - new uptrend is becoming structurally coherent

Only steps 1–3 are currently supported as a **state-transition interpretation**.

Step 4 remains useful as a description, but its use as an entry confirmation is not historically robust enough yet.

## 6. 513290 interpretation

513290 September 2026 fits the transition mechanism well:
- 2026-09-17: annualized ≈ -46%, R² ≈ 0.328 — coherent downtrend
- 2026-09-23: annualized ≈ -17%, R² ≈ 0.039 — downtrend structure largely collapsed
- 2026-09-28: annualized ≈ -10.5%, R² ≈ 0.017 — weak residual negative trend
- 2026-09-29: annualized ≈ +14.1%, R² ≈ 0.019 — slope flips positive, but new uptrend is not yet structurally confirmed

Thus the auxiliary value is not "buy before Score turns positive"; it is:

> Detect that the previous negative trend has become unreliable before the production score re-enters the positive branch.

## Decision

Keep production OLS unchanged.

For the auxiliary radar, log and visualize:
- annualized
- R²
- raw_score = annualized * R²
- their 1/3/5-session changes
- zero-axis crossings

Do not introduce fixed R² thresholds or automated entries at this stage.
