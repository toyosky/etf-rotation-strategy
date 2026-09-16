# OURE Stage8N — Internal Trend-Regime Diagnostic Findings

Date: 2026-09-16
Authoritative corrected run: `35056894248`
Artifact: `oure-stage8n-internal-regime-diagnostic-35056894248`
Artifact digest: `sha256:fe2982350324a132ff7b82e1691e30f80ff1a805f1c704180cf445cbdbf5fd65`
Status: frozen diagnostic; no trading regime rule promoted

## Definition correction
The initial run used the cash ETF's masked pool score in breadth/strength and is invalid for those two features. The authoritative corrected run uses:
- breadth = positive-trend/D2-pass risk members divided by members with an actual historical OLS estimate;
- median signed strength = median(annual * R2) across historically OLS-ready frozen risk members.

Churn, recent-life, point-in-time percentile lookbacks, 20/80 warning cutoffs, labels and V1 strategy path were not retuned.

## Primary result
The four internal state variables contain economically meaningful information about the future performance of the frozen FixV2 + V1-75 strategy, but the relationship is materially stronger once the fixed universe has matured (roughly 2020 onward). They should be treated as prospective risk-state variables, not as a validated binary market-timing switch.

### Frozen warning definitions
- high churn: risk_churn20 point-in-time percentile >=80
- short recent life: last-5 completed Top1 episode mean percentile <=20
- low breadth: opportunity breadth percentile <=20
- weak cross-sectional strength: median signed strength percentile <=20

## Individual warning effects, full sample, future 20 sessions

| Warning | Non-warning mean | Warning mean | Non-warning q10 | Warning q10 | Non-warning mean fwd MDD | Warning mean fwd MDD |
|---|---:|---:|---:|---:|---:|---:|
| High churn | +3.90% | +2.52% | -6.01% | -7.41% | -6.23% | -5.91% |
| Short recent Top1 life | +4.07% | +1.65% | -5.23% | **-10.35%** | -6.05% | **-6.99%** |
| Low breadth | +3.66% | +1.80% | -5.93% | **-9.45%** | -5.95% | **-6.65%** |
| Weak signed strength | +3.57% | +2.46% | -5.84% | **-9.20%** | -5.92% | **-6.64%** |

Short recent Top1 life is the cleanest single tail-risk warning. Low breadth and weak strength also have meaningful downside-tail deterioration. High churn lowers mean future return but is less reliable by itself.

## Feature-shape result
The relationship is not purely monotonic for breadth/strength.

Future 20-session mean return by point-in-time quintile:

### Churn percentile
Q1 +6.65%, Q2 +3.86%, Q3 +4.44%, Q4 +2.69%, Q5 +2.52%.
Low churn is clearly favorable; high churn is weaker, though middle bins are not perfectly ordered.

### Recent Top1-life percentile
Q1 +1.65%, Q2 +3.57%, Q3 +4.14%, Q4 +2.65%, Q5 +5.34%.
Very short recent episode life is adverse; long episode life is best overall.

### Breadth percentile
Q1 +1.80%, Q2 +3.56%, Q3 +4.58%, Q4 +4.04%, Q5 +2.99%.
The best future outcome is at moderate-to-high breadth, while both very low and very high breadth are weaker.

### Median signed strength percentile
Q1 +2.46%, Q2 +4.46%, Q3 +4.90%, Q4 +3.26%, Q5 +1.63%.
This is clearly hump-shaped: very weak cross-asset trend strength is bad, but extremely strong cross-sectional strength is also followed by weaker outcomes. Stage8N does NOT add a high-strength warning after observing this.

## Frozen composite bad_count
`bad_count` simply counts the four preregistered warning states; no weights are fitted.

Full overlapping future-20 results:
- bad_count <2: n=1853, mean +3.98%, median +1.70%, win 61.2%, q10 -5.34%, mean future MDD -6.00%.
- bad_count >=2: n=757, mean +2.25%, median +1.15%, win 56.9%, q10 **-10.01%**, mean future MDD **-6.98%**.

### Non-overlapping 20-session robustness sample
This is the higher-value robustness check because overlapping forward returns are dependent.

- bad_count <2: n=93, mean +4.14%, median +2.00%, win 58.1%, q10 -5.17%, mean future MDD -5.84%.
- bad_count >=2: n=38, mean **+1.81%**, median **-0.14%**, win **47.4%**, q10 **-10.12%**, mean future MDD **-7.22%**.

Thus the composite carries economically meaningful forward risk information without any fitted weights.

## Era dependence / universe maturity
The regime signal is NOT stable across the literal entire 2015-2026 carrier history.

OLS-ready risk-member count grew approximately:
- 2015: 2-3
- 2016: 3-4
- 2017: 4
- 2018: 4-6
- 2019: ~6
- 2020: 6-9
- 2021: 9
- 2022: 8-11
- 2023: 11-12
- 2024+: ~13

### Before 2020
bad_count >=2 does not identify a worse regime: future 20d mean +1.15% vs +1.06% when <2, and its tail is not worse. The internal cross-sectional state is not reliable when only ~3-6 economic channels exist.

### 2020 onward
The separation becomes large:
- bad_count <2: future20 mean +6.06%, median +3.46%, win 67.5%, q10 -5.32%, mean fwd MDD -6.86%.
- bad_count >=2: future20 mean **+2.75%**, median **+0.87%**, win **55.6%**, q10 **-11.80%**, mean fwd MDD **-8.42%**.

The same pattern is strong in the 2021+ split. This is consistent with the economic interpretation that a cross-asset regime diagnostic needs a sufficiently populated cross-asset universe. It is NOT clean OOS proof and no minimum-member threshold is promoted in Stage8N.

## 2022 drawdown diagnostic
Maximum-drawdown window: 2022-03-09 to 2022-05-10, strategy -32.34% in the window.

During drawdown:
- mean churn20 4.15; churn percentile 83.8
- mean recent-5 Top1 life 4.95d; life percentile 19.4
- breadth 41.7%
- bad_count mean 2.15
- bad_count >=2 on 77.5% of days

Prior 20 sessions (2022-02-09 to 2022-03-08):
- strategy was still +29.83%
- bad_count mean 1.15
- bad_count >=2 only 30%
- high-churn warning occurred 60% of days, but short-life only 10%

The composite therefore does NOT provide a clean advance warning for 2022. High churn was already elevated during a highly profitable late-trend phase, so using churn alone as a hard risk-off switch would exit too early. The broader state becomes clearly bad mostly as the drawdown begins: on 2022-03-09 bad_count reaches 2 and then rises to 3 on subsequent stress days.

## 2026 drawdown diagnostic
Maximum-drawdown window: 2026-06-03 to 2026-08-19, strategy -37.92% in the window.

During drawdown:
- mean churn20 6.71; churn percentile 90.2
- mean recent-5 Top1 life 2.99d
- breadth only 32.6%
- median signed strength negative
- bad_count mean 2.42
- bad_count >=2 on 80.0% of days

Prior 20 sessions (2026-05-06 to 2026-06-02):
- strategy was still +23.28%
- bad_count mean 1.65
- bad_count >=2 on 55% of days
- short-life warning 55%, low-breadth warning 50%, weak-strength warning 60%

There is real advance information before the 2026 break. From roughly May 20 onward the composite is repeatedly 2-3 even while the strategy is still making late-stage gains. This is exactly why a soft exposure scaler is more plausible than a binary off switch.

## False-warning / opportunity-cost evidence
2024 is an important counterexample:
- strategy return +65.57%
- bad_count >=2 on about 38% of sessions

Yet within 2024, future20 mean return after bad_count>=2 states is about +2.58% versus +5.62% after states <2. Thus the warning often identifies LOWER-quality opportunity without implying negative expected return.

Similarly, in 2025 warning-state forward returns are much weaker than normal-state returns even though the full year is exceptionally profitable.

This argues against interpreting the diagnostic as `risk on / risk off`. It is better interpreted as `normal risk / reduced risk` if a later causal backtest validates it.

## Frozen conclusion
1. The internal-regime hypothesis survives Stage8N, especially for the current mature cross-asset universe.
2. Recent Top1 episode life is the strongest single mechanism; low breadth and weak signed cross-sectional strength add meaningful tail information; churn is useful mainly in the mature/post-2020 regime and is dangerous alone near late-stage rallies.
3. A simple unweighted bad_count>=2 condition has materially worse future 20-session outcomes and survives a non-overlapping robustness check.
4. The condition is much more useful after the universe contains many distinct economic channels; early 2015-2019 results do not support a universal historical switch.
5. 2026 shows genuine advance warning; 2022 is mostly contemporaneous detection. Therefore Stage8N does NOT validate a binary cash switch.
6. If research continues, the next frozen experiment should test position-size scaling (e.g. full / reduced / cash) using the already-frozen state definition, with exact turnover accounting and without re-optimizing the four indicators.
