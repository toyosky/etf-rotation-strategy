# OURE Stage8O — Global Macro Market Pilot

Date: 2026-09-16
Status: exploratory pilot on the currently available Massive free-plan history; NOT a promoted trading rule.

## Purpose
Test whether a small external global-market panel adds useful regime context to the frozen Stage8N internal regime diagnostics over the overlapping Massive history (~2024-09-16 to 2026-09-15).

## Frozen external panel
No variable selection after outputs:
- SPY: US broad equities
- QQQ: US technology/growth
- TLT: long-duration US Treasuries / rate pressure proxy
- HYG: US high-yield credit
- UUP: US dollar proxy
- GLD: gold
- USO: crude oil
- COPX: copper/miners / global cyclical growth proxy
- EEM: emerging markets

## Descriptive market state
Primary continuous diagnostic:
`RiskBreadth6` = fraction of SPY, QQQ, HYG, USO, COPX, EEM whose 20-session return is positive.

Also inspect 20-session returns for TLT, UUP and GLD separately. No optimized macro score or trading threshold is fitted in this pilot.

## Key results
### 2025 full year
- Average RiskBreadth6: 0.641
- RiskBreadth6 <= 1/3 on 26.8% of sessions
- RiskBreadth6 <= 1/2 on 34.0% of sessions
- Yet Stage8M FixV2+V1 returned about +115% in 2025.

Interpretation: external market breadth alone would create many false de-risking signals during a highly profitable strategy year.

### 2026 before the main drawdown
Window: 2026-05-06 to 2026-06-02
- Average RiskBreadth6: 0.781
- Minimum breadth: 0.667
- Breadth <= 1/2: 0% of sessions
- SPY average 20d return: +5.8%
- QQQ: +11.33%
- HYG: -0.51%
- USO: +6.66%
- COPX: +4.65%
- EEM: +7.39%
- TLT: -1.71%
- UUP: +0.69%
- GLD: -2.73%

Stage8N internal state, however, already had `BadCount >= 2` on about 55% of the pre-drawdown sessions.

Interpretation: the broad global-market panel did NOT anticipate the 2026 drawdown. The internal OLS regime deteriorated while the external global market still looked broadly strong.

### 2026 during the main drawdown
Window: 2026-06-03 to 2026-08-19
- Average RiskBreadth6: 0.463
- Breadth <= 1/3: 40.7%
- Breadth <= 1/2: 64.8%
- SPY average 20d return: +0.83%
- QQQ: -0.43%
- HYG: -0.20%
- USO: -2.50%
- COPX: -0.44%
- EEM: -1.11%
- TLT: -1.01%
- UUP: +0.82%
- GLD: -2.76%

Timing around the break:
- 2026-06-02 RiskBreadth6 = 0.833
- 2026-06-03 = 0.667
- 2026-06-05 = 0.333
- 2026-06-09 = 0.000
- 2026-06-10 = 0.000

Interpretation: the external market panel became a strong confirmation signal roughly 2–4 US trading sessions after the strategy drawdown began, not a useful lead signal.

### 2025 short sharp strategy drawdown counterexample
Stage8M 2025 year-end short drawdown was roughly -22%.
External market state around 2025-12-24 to 2025-12-29:
- RiskBreadth6 about 0.722
- SPY +1.50% 20d
- QQQ +1.43%
- HYG -0.39%
- USO -0.97%
- COPX +18.91%
- EEM +0.91%
- TLT -2.67%
- UUP -4.54%
- GLD +6.64%

Stage8N internal `BadCount >= 2` was also essentially absent in that shock window.

Interpretation: this loss looks unlike broad systemic cross-asset deterioration; an external macro layer should not be expected to catch every holding-specific or trend-specific shock.

## Main conclusion
The two-year pilot supports a layered interpretation rather than a standalone macro timing model:

1. Internal Regime (Stage8N) can deteriorate before broad global markets do. This was visible before the 2026 major drawdown.
2. External Global Market breadth is useful as a confirmation / classification layer: once global risk proxies deteriorate together, the probability that the problem is broad/systemic is higher.
3. External breadth alone is too noisy for a hard risk switch; 2025 had many low-breadth days despite very strong strategy performance.
4. A plausible future architecture is:
   - Internal bad + external healthy -> caution / modest de-risking, not exit.
   - Internal bad + external deteriorating -> stronger de-risking candidate.
   - Internal healthy + external healthy -> normal exposure.
   - Holding shock with both layers healthy -> treat as idiosyncratic / execution / asset-specific, not macro-regime failure.

## Limitations
- Massive free plan only supplied about two years of stock/ETF history; direct long-history index data was not entitled.
- Only one major long drawdown (2026) is fully available in the overlap, so this is not sufficient for statistical validation.
- No macro threshold, score weighting, or position-sizing rule is promoted from this pilot.
- Proper Stage8O validation requires a longer history (ideally 2015–2026) from another source, then an incremental test conditional on the frozen Stage8N state.
