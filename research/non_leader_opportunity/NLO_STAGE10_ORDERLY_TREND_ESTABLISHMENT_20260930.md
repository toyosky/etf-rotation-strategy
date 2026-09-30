# NLO Stage 10 — Does a Forward-Return Signal Exist After Trend Establishment?

Date: 2026-09-30

Status: exploratory discovery + fixed-threshold OOS validation. No production-rule change.

## Question

After a trend-establishment event

- annualized recently crossed from <=0 to >0
- first observable session within 1–3 sessions after crossing
- R² is rebuilding on that session

does any observable information robustly predict the *magnitude* of future return, rather than merely whether annualized remains positive?

The null hypothesis is explicitly allowed:

> trend persistence may be forecastable while return magnitude is not.

## Event construction

One event per zero-axis crossing:
- crossing occurred within previous 1–3 sessions
- annualized remains >0
- current 1-session delta R² >0
- use the first qualifying session

Outcomes:
- future 20-session absolute return
- future 20-session return minus same-date current-pool average
- MFE/MAE over the following 20 sessions

Candidate observable features:
- annualized level
- R² level
- raw score
- 1d/3d delta annualized
- 1d/3d delta R²
- 1d/3d delta raw score
- 1d/3d/5d price return
- current/3d amount ratios
- 10d realized volatility
- 20d drawdown
- cross-sectional positive-score rank fraction

## 1. Broad factor screen

Most features do not show stable forward-return IC across periods.

Two features stand out directionally:

### 3-session delta R²
Future20 excess-return Rank IC:
- 2021–2024: +0.120
- 2025–2026: +0.117

Interpretation:
faster medium-horizon rebuilding of trend fit is mildly favorable.

### 3-session delta annualized
Future20 excess-return Rank IC:
- 2021–2024: -0.094
- 2025–2026: -0.086

Interpretation:
after the zero crossing, an excessively rapid slope acceleration is mildly unfavorable.

This suggests an economically coherent hypothesis:

> orderly trend establishment may be better than explosive trend establishment.

Other observations:
- 10d volatility is generally negatively related to future return, especially 2025–2026.
- trading-amount ratios are strongly negative in 2021–2024 but near-neutral/slightly positive in 2025–2026; volume is not stable enough.
- annualized level, raw score, short price return, and instantaneous R² level are not robust return predictors.

## 2. OOS test of an "orderly establishment" rule

Discovery only on 2021–2024.

Use fixed discovery cut points:
- 3d delta R² >= discovery 33rd percentile
- 3d delta annualized < discovery 67th percentile

No threshold retuning on 2025–2026.

This is intentionally broad:
- R² rebuild is at least moderate;
- slope acceleration is not in the most explosive third.

### Discovery 2021–2024

ORDERLY, n=120:
- future20: +1.86%
- excess vs pool: +0.60 pct
- median excess: +0.14 pct
- beat-pool rate: 50.8%
- >=+5% future20: 20.0%
- average MFE20: +4.10%
- average MAE20: -2.17%

OTHER, n=120:
- future20: +0.43%
- excess vs pool: -0.60 pct
- median excess: -1.55 pct
- beat-pool rate: 42.5%
- >=+5% future20: 18.3%
- average MFE20: +4.04%
- average MAE20: -3.75%

### Validation 2025–2026

ORDERLY, n=48:
- future20: +2.65%
- excess vs pool: +0.49 pct
- median excess: +0.88 pct
- beat-pool rate: 52.1%
- >=+5% future20: 37.5%
- average MFE20: +4.99%
- average MAE20: -2.61%

OTHER, n=66:
- future20: +0.33%
- excess vs pool: -1.45 pct
- median excess: -3.45 pct
- beat-pool rate: 33.3%
- >=+5% future20: 19.7%
- average MFE20: +5.52%
- average MAE20: -4.24%

The OOS directional difference survives and is economically plausible:
- similar upside excursion,
- materially smaller adverse excursion,
- higher realized final return.

## 3. Year-by-year behavior

ORDERLY excess vs pool:
- 2021: +0.03 pct
- 2022: -0.26 pct
- 2023: +0.36 pct
- 2024: +1.92 pct
- 2025: +0.45 pct
- 2026: +0.70 pct

The rule is not positive every year, but 5 of 6 years are non-negative/positive and the only negative year is small.

However sample size in 2026 is only 8 orderly events.

## 4. Statistical uncertainty

Validation 2025–2026:
- ORDERLY n=48
- OTHER n=66
- mean future20 difference: +2.32 pct
- approximate 95% CI: [-0.34 pct, +4.98 pct]

Mean excess-return difference:
- +1.94 pct
- approximate 95% CI: [-0.68 pct, +4.56 pct]

Both confidence intervals cross zero.

Therefore the evidence is suggestive, not conclusive.

## 5. Asset concentration check

Validation results were recomputed while excluding each asset one at a time.

The ORDERLY-minus-OTHER excess-return difference remains positive for every leave-one-asset-out sample.

Range:
- minimum: +0.99 pct (excluding 159957)
- maximum: +2.55 pct (excluding 501018)

Thus the OOS effect is not driven by one ETF.

Asset-level outcomes remain heterogeneous, so this should not be interpreted as a universal per-asset law.

## 6. Interpretation

The current evidence does **not** support a high-confidence standalone buy signal.

It does support a weaker proposition:

> among already-established new positive trends, an orderly rebuilding process — moderate-to-strong R² recovery without explosive annualized acceleration — may identify better risk-adjusted entry candidates than noisy/explosive transitions.

The notable feature is not only higher final return. The ORDERLY group has substantially smaller average adverse excursion in both discovery and validation.

This looks more like a **quality-of-entry / transition-quality filter** than an alpha engine.

## Decision

Do not promote this to production buy logic.

Current confidence hierarchy:

1. annual crossing + R² rebuild predicts structural persistence: strong evidence.
2. orderly R² rebuild + non-explosive annual acceleration predicts better future return/risk: weak-to-moderate evidence, OOS direction survives.
3. exact entry threshold / standalone buy rule: not established.

Recommended handling:
- preserve as research-only candidate;
- collect future live events prospectively;
- do not retune thresholds;
- reassess after additional independent events accumulate.
