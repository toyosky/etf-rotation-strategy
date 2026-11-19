# D2 -3% Hard-Cutoff Study | 2021–2026

Status: exploratory **research only**, no strategy rule modification. Signal window for fully markable open-to-open returns: 2021-01-01 to 2026-11-16. Daily bars extend through 2026-11-18. The 2026-11-17 signal has no following T+2 open in this snapshot and is not included in the threshold sweep; the frozen 3% baseline is known to hold 511220 on Nov 17, so the reported baseline 196 non-Void switch count is unaffected.

## Main question

Does the current D2 veto at a strictly lower-than-3% daily close change cause a cliff in model actions, and is there evidence of a corresponding cliff in subsequent risk? The D2 rule considers the **minimum daily close-to-close return among the latest 3 trading observations**; it is an eligibility veto, not an unconditional 3% intraday stop order.

## Methodology and reproducibility

- Source: Supabase `public.daily_bars`; 14 live risk assets including 512800 bank plus 511220 comparator and 513500 Void carrier, history beginning 2013 (symbol availability varies).
- Recomputed OLS and raw scores over 26 daily closes, exponential weighted regression with half-life 10 applied as squared weights, annualization 250. Candidate pool: annual > 0, R² > 0, score > 0, no last-three-day return below the threshold; candidate must outscore 511220 eligible pool score. No universe-volume filter for the fixed risk set.
- V1: if the old candidate is valid, veto a rank switch only when challenger resistance pct252 >=75 AND raw Score delta <=0. Resistance: 120-bar price/turnover overlap, pct252 measured using prior observations only.
- State map: all 14 raw-risk scores vs 511220, breadth >=50%, 252-day inclusive percentile of raw Top1–Top2 gap >=50%; DEFENSIVE_VOID when both below50. Void enters by freezing previous final target. After decline in both breadth/gap versus entry and incumbent raw score no longer above 511220, route 513500 if valid age 365+ / score > 511220, otherwise 511220. Hold route until exit.
- All variants computed from the same historic bars and state map. Only D2 magnitude changes. 3% baseline incorporates the 2026-09-29 specifically recorded 159509 premium rejection/hold-159981 override; other variants are pure model shadows. **Therefore some of the position-day differences in the CSV are unrelated to D2.**
- Non-Void changes count only changes **on a non-DEFENSIVE_VOID signal day**, including Void-exit restoration. Historical outputs are signal-target simulations, not fill receipts or PIT premium-confirmed trades.
- Rough model return/MDD fields are diagnostic only: open(T+1)→open(T+2), 6bp/side costs, missing open-to-open returns are treated as zero gross return and flagged (10–12 missing days per variant). This, fund price adjustment limitations, unverified premium dates and intraday vetoes prohibit choosing a threshold from these in-sample PnL figures. 
- Local discontinuity sample: calendar-day first return shock on the **previous formal-model held risk asset**, signal date not Void, observed 1-day close-to-close return in [-3.6%,-2.4%). One row per shock date; avoids counting each day's 3-day rolling D2 period as independent. The event's 3/5-day forward returns are measured at closes, using the same old ETF; NOT the trading strategy's realized PnL.

## Threshold sweep

| Threshold | Non-Void changes | Non-Void old-invalid D2 switches | Position-days differing vs 3.0% |
|---:|---:|---:|---:|
| 2.50% | 228 | 61 | 103 |
| 2.75% | 216 | 51 | 69 |
| 2.90% | 201 | 41 | 23 |
| 3.00% | 196 | 39 | 0 |
| 3.10% | 192 | 39 | 10 |
| 3.25% | 188 | 38 | 20 |
| 3.50% | 183 | 36 | 62 |
| 4.00% | 175 | 30 | 82 |

Baseline reproduces 196 non-Void changes and 39 D2-driven old-invalid switches. Near -3%, switching changes sharply: at 2.9%, 201 non-Void changes (+5); at 3.1%, 192 (-4). Slightly changed thresholds can alter a future Void-entry incumbent and create multi-day target divergence. The all-variant 2026-09-29 premium-rejection override is not replayed identically, so isolate that date and subsequent effects before attributing changes to D2 alone.

## Local near-cutoff sample

| Actual held ETF day change | N | Formal changes on day | D2 old-invalid switches | Old ETF T→T+3 mean | T+3 positive |
|---|---:|---:|---:|---:|---:|
| [-3.6,-3.4)% | 5 | 5 | 3 | 2.16% | 4/5 |
| [-3.4,-3.2)% | 4 | 4 | 3 | 1.83% | 4/4 |
| [-3.2,-3.0)% | 5 | 5 | 3 | 2.36% | 4/5 |
| [-3.0,-2.8)% | 11 | 0 | 0 | 3.21% | 7/11 |
| [-2.8,-2.6)% | 11 | 1 | 0 | 1.79% | 7/11 |
| [-2.6,-2.4)% | 9 | 5 | 0 | -0.30% | 5/9 |

Around the exact -3% cutoff: [-3.2,-3.0) has 5 observations, all with model target changes (3 explicitly old-invalid); [-3.0,-2.8) has 11 observations, none with model target change. Their T→T+3 average returns are +2.36% and +3.21%, respectively. This is evidence of a **policy discontinuity**, but *not evidence of a market-risk discontinuity*. Small samples, different funds/regimes, and non-random assignment mean no valid causal regression discontinuity inference at present.

## Mechanism cross-check

In the earlier separate 39-event D2 analysis: 24/39 had positive T→T+3 old ETF returns; 30/39 remained raw OLS Top1 at D2 signal time. 8/39 later directly returned to the old ETF on the next model switch; all 8 had cleared D2 by that return signal. However 11/39 continued declining at T+3 and T+5, with old-ETF T→T+5 average -8.99%. A simple removal of D2 is not justified.

## Interpretation and next preregistered checks

1. Keep 3% unchanged in production. The threshold sweep shows turnover responds smoothly across threshold changes, but a hard cliff at the exact crossing; it does not identify a uniquely robust replacement level.
2. Evaluate **soft D2 for held incumbents** as a separate version, not an in-sample threshold optimization: keep -3% no-new-buy gate; when existing holding crosses -3%, first compare raw OLS score vs 511220 and best alternative, with an independently declared panic exit (e.g. -5%) as a guardrail. Test variants in 2021–2023 versus 2024–2026, with bank-admission historical assumption documented, a valid point-in-time premium filter where available, plus 6–30 bp/side stress and missing-price flags.
3. Evaluate re-entry cooldown independently of exit threshold: a recovering asset can regain D2 eligibility after the rolling 3-day window clears even if OLS score is still decreasing. A hold-and-recheck or score-persistence gate may avoid A→B→A at the cost of missing reversals; report both positive/negative effects.
4. Do not treat parameter searches over 2021–2026 as out-of-sample evidence. Freeze explicit alternatives and validate on subsequent prospective data or a truly independent holdout.

Files: [threshold sweep](d2_threshold_sweep_2021_2026.csv) / [cutoff event bands](d2_cutoff_local_bands_2021_2026.csv) / [39-event mechanism audit](d2_event_mechanism_39.csv).
