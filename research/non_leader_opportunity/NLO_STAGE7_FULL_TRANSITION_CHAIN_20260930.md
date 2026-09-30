# NLO Stage 7 — Full OLS Transition Chain

Date: 2026-09-30

Status: completed diagnostic event study; no production-rule change.

## Research question

Can the full OLS transition chain

`negative annual + coherent R² -> R² collapse -> annual crosses zero -> R² rebuild`

distinguish:
1. false positive slope flips from durable new trends;
2. durable new trends from candidates that are actually worth switching into versus the incumbent/raw OLS Top1?

The study deliberately avoids fitting a production threshold.

Current frozen 13-risk-asset pool. OLS definition matches production:
- 26-session weighted log-price regression
- annualized = exp(slope * 250) - 1
- R² clipped to [0,1]
- continuous raw_score = annualized * R²

## Event definition

t=0:
- previous annualized <= 0
- current annualized > 0

Structural persistence label is independent of price return:
- PERSIST_ALL5: annualized remains >0 on every one of t+1 ... t+5
- NEGATIVE_AT5: annualized <=0 at t+5
- MIXED_BUT_POS_AT5: temporary relapse occurs but annualized is positive at t+5

This avoids defining a "true trend" using a future return threshold.

## 1. R² rebuild strongly distinguishes structural persistence

### 2021–2024

PERSIST_ALL5 (202 events):
- R² t0 0.017
- t+1 0.079
- t+3 0.232
- t+5 0.332
- t+10 0.435

NEGATIVE_AT5 (52 events):
- R² t0 0.008
- t+1 0.023
- t+3 0.040
- t+5 0.107
- t+10 0.208

### 2025–2026

PERSIST_ALL5 (100 events):
- R² t0 0.017
- t+1 0.091
- t+3 0.263
- t+5 0.363
- t+10 0.446

NEGATIVE_AT5 (26 events):
- R² t0 0.005
- t+1 0.013
- t+3 0.077
- t+5 0.152
- t+10 0.366

The cross-period shape is highly similar.

Interpretation:

> A slope sign flip occurs with R² near zero. A durable new trend is characterized by rapid post-cross rebuilding of fit quality.

## 2. R² gives early information about persistence

Event-level rank IC between observable state and the number of positive-annualized days among t+1...t+5:

### 2021–2024
t+1:
- annual level: +0.537
- R² level: +0.528
- R² rebuild: +0.529

t+3:
- annual level: +0.699
- R² level: +0.543
- R² rebuild: +0.528

### 2025–2026
t+1:
- annual level: +0.644
- R² level: +0.594
- R² rebuild: +0.577

t+3:
- annual level: +0.680
- R² level: +0.473
- R² rebuild: +0.464

Thus the distinction is visible as early as the first session after the zero-axis crossing.

## 3. R² adds information beyond annualized level

To test whether R² is merely a transformation of slope strength, events were first split by t+1 annualized level and then by t+1 R².

For the weakest t+1 annualized tercile:

### 2021–2024
PERSIST_ALL5 probability by low / middle / high R²:
- 12.9%
- 50.0%
- 70.0%

### 2025–2026
- 0.0%
- 33.3%
- 66.7%

This is the cleanest incremental finding.

When annualized has only weakly crossed above zero, rapid R² rebuilding materially distinguishes a likely durable transition from a likely false/fragile crossing.

At stronger annualized levels, persistence is already high and R² adds less.

## 4. Structural confirmation does not equal return prediction

R² rebuild predicts persistence much better than it predicts remaining price return.

Rank IC of R² rebuild versus remaining return after observation:

### 2021–2024
- t+1: -0.076
- t+3: -0.063
- t+5: -0.010

### 2025–2026
- t+1: +0.130
- t+3: +0.039
- t+5: +0.080

The return relationship is not stable across regimes.

Therefore:

> R² rebuild is a robust trend-state confirmation variable, not a robust forward-return factor.

## 5. Candidate versus raw OLS Top1 at t=0

Comparator:
- same-date raw OLS Top1 among positive-annualized risk assets
- excludes D2/premium/state-machine effects, so this is a clean OLS comparator rather than exact live incumbent reconstruction

### 2021–2024

PERSIST_ALL5 candidates:
- candidate future 20d: +1.79%
- raw Top1 future 20d: +2.42%
- candidate excess: -0.62 pct
- candidate beats Top1: 45.1%

Non-persistent candidates:
- candidate: -1.10%
- Top1: +2.16%
- excess: -3.26 pct
- beat rate: 31.9%

### 2025–2026

PERSIST_ALL5:
- candidate: +2.36%
- Top1: +4.87%
- average excess: -2.51 pct
- median excess: +0.96 pct
- beat rate: 55.0%

Non-persistent:
- candidate: -3.06%
- Top1: +8.91%
- excess: -11.96 pct
- beat rate: 19.4%

So persistence is useful for rejecting bad candidates, but even a durable new trend is not automatically superior to the incumbent leader.

## 6. Waiting until t+3 does not solve the switching problem

At t+3, events were ranked by R² rebuild speed and compared with the raw Top1 present on t+3.

Rank IC of rebuild3 versus candidate excess return over Top1:
- 2021–2024: +0.084
- 2025–2026: -0.003

No stable monotonic relationship exists.

In 2025–2026 the highest rebuild tercile had:
- candidate future20 from t+3: +2.23%
- raw Top1: +3.77%
- average excess: -1.54 pct
- median excess: +0.29 pct
- beat rate: 51.2%

Again: confirmation of a real trend does not establish opportunity cost superiority.

## 7. Early rebuild in weak crossings: useful for truth, not ranking

At t+1, within the weakest annualized crossings, high R² greatly improves persistence probability, but it still does not robustly beat Top1.

For example, weakest annualized tercile + highest t+1 R²:

### 2021–2024
- candidate future20: +1.56%
- Top1: +2.21%
- excess: -0.64 pct
- beat rate: 46.7%

### 2025–2026
- candidate future20: +1.69%
- Top1: +5.51%
- excess: -3.81 pct
- beat rate: 40.0%

This separates two questions:
- "Is this new trend real?" -> R² helps materially.
- "Should I leave the current leader for it?" -> R² does not answer this.

## 8. Integrated state-chain interpretation

The evidence now supports the following descriptive chain:

1. **Coherent negative trend**
   - annualized < 0
   - R² relatively high

2. **Old trend breakdown**
   - annualized still < 0
   - R² collapses
   - optional price/volume activity can confirm an imminent sign flip

3. **Direction flip**
   - annualized crosses > 0
   - R² is usually near zero

4. **New-trend validation**
   - annualized remains > 0
   - R² rebuilds rapidly during t+1...t+3
   - this strongly predicts structural persistence

5. **Capital-allocation decision**
   - must still compare the candidate with incumbent/Top1
   - R² rebuild alone does not establish that switching improves return

## Decision

Do not alter production entry or switching rules.

The strongest justified use is an auxiliary maturity/state radar:

- annualized
- R²
- raw_score
- delta annualized
- delta R² over 1/3/5 sessions
- zero-axis crossing age
- positive-annualized persistence since crossing
- price/amount confirmation as secondary context
- candidate raw rank
- incumbent/raw Top1 comparison

Recommended interpretation labels should remain descriptive rather than threshold-driven:
- downtrend coherent
- downtrend structure weakening
- zero-axis transition
- new trend rebuilding
- structurally persistent

Do not automatically map these states to buy/sell actions.

## Limitations

1. Current frozen 13-risk-asset pool has changing historical availability because some ETFs listed later.
2. Comparator is raw OLS Top1, not exact live incumbent after D2, premium veto, Void/V1/C2 state logic.
3. Returns are close-to-close and ignore transaction costs/slippage.
4. Persistence is an OLS-state label, not a return label.
5. The study intentionally avoids optimizing exact R² thresholds; any production threshold would require a separate walk-forward/out-of-sample study.
