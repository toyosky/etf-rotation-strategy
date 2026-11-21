# Q4 pre-registration: Q90-frozen reduction + Top2 binary qualification

Date 2026-11-21. Research-only. This protocol is committed **before computing Top2 opportunity model outcomes and decisions**. Reuses previous Q1/Q3 evidence but no retuning Q90 exit size or trigger days. Historical 2021–2026 has already been examined extensively: this is a chronological backtest, **not a fresh untouched holdout**.

## Objective and decision

At each frozen Q90+loss-probability event, E is the existing exact removed Top1 fraction, held for five daily decision intervals. Decide **all-or-none** placement: qualified existing point-in-time Top2 receives the full E; otherwise E stays cash. No fractional new E or altering original Top1 routing, no trade when no qualified Top2. Verify whether this two-stage strategy adds *after-fees net return and risk protection* compared with both all cash and all Top2. No model of later repurchase in this stage.

## Training universe and price labels

Use previous frozen Q1 15-instrument OHLC snapshots, 2020–2026; 14 current risk funds + cash comparator 511220. Each day rank funds exactly by actual strategy/main.py 26-close weighted log OLS, effective weights q² with q=.5^((25-i)/10), score=max(expm1(beta*250),0)*R², exclude any past-three daily return below -3%, require risk score > comparator. Production has no R²>=.5 eligibility floor. Top1 and Top2 are both determined at signal close t and only data through t. Freeze original 119 Q90 exit events with Q1 event pair archive; for feature training use **all** daily historical Top1+Top2 eligible pairs, not just 119 events.

For original Top2 candidate at t, trading price entry is following market open t+1, exit at market open t+6 after five daily intervals. Require all t+1 ... t+6 opens and t+1 ... t+5 lows and valid positive prices. Top2 5-day *net* return label = (exit_open / entry_open -1) -0.0012 (6bp per side); if entry path missing, exclude sample from supervised training, report counts and cash fallback at decisions. Top2 adverse-excursion severity: max(0, 1 - min(lows[t+1 ... t+5])/entry_open). 90% quantile target is **positive loss severity**; an appropriately calibrated Q90 tail should be exceeded on roughly 10% of future paths, not 90%.

## Model structure and fixed transformations

Train annual-expanding fit: training dates before Jan 1 of test year, with **10 market-day embargo** preceding January 1 to avoid 5-day overlapping labels. 2020 is earliest train, 2021–2026 test years. No test-year tuning, no reusing future labels to compute features. Train-only feature standardization, clip standardized features to [-5,+5]; transformed features:
1. top2 5-close log return
2. top2 20-observation close-to-close daily log-volatility
3. top2 last-close deviation from its 26-bar weighted OLS prediction in residual-sigma units
4. top2 R²
5. top2 minus Top1 prior-5-close log return spread
6. top2 minus Top1 (previous 3-session OLS score change) computed for the exact fixed symbols, not prior ranked identities.
Complete-case feature only; count impossible cases in historical decisions.

A) Net-positive-opportunity forecast = *ridge* mean prediction of future five-session Top2 net return. Training target equals net 5day return (as above). Ridge slope penalty λ=0.2 in **mean-squared error** standard-x formulation (equivalently normal eq matrix X'X+λ*n*I; intercept unpenalized), fixed before test. No test threshold chosen. A candidate passes expected-return gate iff predicted net return **> 0**.

B) Q90-compatible Top2 downside forecast = Top2 realized vol20 × sqrt(5) × training-only 90th percentile of (next-5-session maximum adverse excursion / [top2 vol20 × sqrt(5)]) among valid training daily pairs. Use a fixed volatility floor 0.002/day for numerical stability; retain record of floor frequency. This explicitly does NOT claim to be the already calibrated *Top1* Q90 model; it is a cheap independent Top2 risk calibrator, subject to checking 10% exceedance calibration OOS. Recompute the ratio once per train-year, using data before the embargo.

## Primary decision and baselines

The predeclared Q4 qualification requires BOTH:
- predicted 5-day **net** Top2 return >0;
- Top2 predicted Q90 adverse move <= frozen original **Top1 Dbase** (normal risk benchmark) at Q90 event signal day.

If either failed/unavailable, E remains cash. The Top1 Dbase threshold aims to prevent using the entirety of risk-reduced cash to acquire another asset with more downside risk than the Top1 normal baseline, though Top1 and Top2 common shock risk may still need stress tests.

Compare:
- frozen Q90 -> cash;
- frozen Q90 -> all eligible Top2 (complete historical path only, research hindsight availability caveat);
- opportunity-only (predict net return >0);
- risk-only (Top2 Q90 <= Top1 Dbase);
- **joint primary** (both);
- sensitivity risk target <= Top1 **D** (current predicted 90th adverse move), explicitly a looser risk threshold, no selection of better-performing parameter after observing outcomes;
- original unmodified Top1 proxy.

Same frozen 119 Q90 signals and E, each for 5 market intervals, next-open fills, 6bp per side on symbol-weight deltas. If no Q90 event, no overlay. Top1 dynamic ranking changes per original archived Q90 daily signal; if original route becomes cash, close Top2. When own qualifying features or needed future prices missing, cash; hindsight price availability must not be claimed PIT-tradeable.

## Evaluation

Yearly model errors/mean return sign accuracy/MAE, risk-Q90 exceedance rates (target ~10% overall and by test year), risk tail reliability, P(Top2-net positive) among selected, average event net gain to cash and to original Top1, and Q90 E weighted 5day event gains. Full NAV CAGR/MDD/Calmar and yearly returns, blocks of 20 trading days within years for paired 95% bootstrap intervals of annualized log returns versus cash and all-Top2; bootstrap repeated at least 1,000 times with deterministic seed. Report 119 decision sample, excluded counts, route changes, costs, selected count, target bias. Inspect performance under high Top1 risk D/Dbase and loss probability *without* optimizing cutoffs on test.

Side questions: asset/correlation concentration, zero-vol spurious predictors, 2025-26 regime instability, membership and NAV/LOF premium, true 09:31 execution and trading halts. No production changes until fresh future test/confirmation. If no benefit, record negative evidence, no opportunistic revision.
