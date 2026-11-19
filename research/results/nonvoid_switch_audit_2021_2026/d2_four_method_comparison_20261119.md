# D2 relative-risk four-way comparison | Research 2026-11-19

Research-only. **No production model change.** 2021-01-01 through 2026-11-16 fully markable signals (source closes through 2026-11-18). Backtest uses 14-risk set (including 512800) + 511220 cash and 513500 Void carrier, rather than only the 13-member original Stage8M study list.

## Predefined candidate D2 filters (all veto 3 trading days after trigger)

1. `fixed`: one-day close change < -3% in last 3 symbol observations.
2. `z`: one-day return is negative and (return - previous-60-observation mean) / previous-60-observation sample SD < -2.0. Minimum 40 historical returns. Today's observation excluded from calibration.
3. `rank`: one-day return is negative and its empirical lower-tail rank among previous up to 252 observations is <=5%. Minimum 120 historical returns. Today's observation excluded; ties counted `historic_return <= today_return`.
4. `ols`: today's return is negative, today's terminal log-price residual from weighted OLS26 < -1.5 times weighted in-sample residual RMS and today's OLS slope < slope at T-3. This is a *specific proxy* for trend rupture, not the only meaningful OLS criterion; neither threshold was optimized.

Signals are computed at day T close. All variants retain common 26-day weighted log OLS/positive annual and R² ranking, V1 75th-percentile resistance veto, cash comparator **with existing fixed -3% filter left unchanged**, and exactly the same 14-risk raw-score-defined Void quadrants / freeze / deepening route. Since the question is risk-asset D2 replacement, do not accidentally alter cash comparator. At the only historically confirmed 2026-09-29 premium rejection, **all variants** reject 159509 in favor of incumbent 159981 if their model target is 159509; no other historical premium is claimed PIT-confirmed.

Past listings/data availability vary by ETF. No-lookahead for mean, sigma or tail percentile; those include strictly prior data. For shorter histories the dynamic flag is inactive, NOT imputed; the existing positive OLS eligibility remains. The OLS residual uses T's data as it must for a T-close signal. The methods' trigger frequencies differ substantially: this is a fair comparison of four concrete rules, **not** a matched-exit-rate causal comparison or proof that their thresholds are optimal.

## Full replay (single 6bp/side cost and open-to-open implementation)

| Version | NonVoid changes | Re-changes <=3d | Exact A→B→A <=3d | CAGR% (unvalidated) | MDD% (unvalidated) |
|---|---:|---:|---:|---:|---:|
| fixed | 196 | 89 | 27 | 58.94 | -36.12 |
| z | 200 | 91 | 30 | 64.3 | -32.41 |
| rank | 238 | 129 | 37 | 48.44 | -31.34 |
| ols | 161 | 54 | 29 | 42.99 | -42.74 |

Validation: fixed method reconstructions equal historical 196 non-Void changes and 89 <=3-day repeats. Dates 2026-10-12/15/16 agree with prior known trade signals. A repeat is any next model target change <=3 sessions; exact reversion is next change to immediately preceding target. End-of-sample is from 2026-11-16 because T+2 opening price from last bars on 2026-11-18 is needed.

## 39 old D2 events: same prior fixed-trigger cohort, not independent samples

| Filter | Flags of the 39 fixed-trigger events | Flags of 11 old-ETF continued declines at T+3 and T+5 | Flags of 24 T+3 rebounds |
|---|---:|---:|---:|
| fixed | 39 | 11 | 24 |
| z | 31 | 10 | 18 |
| rank | 38 | 11 | 23 |
| ols | 10 | 1 | 9 |

Interpretation: z identifies 10/11 of continued-decline cases and does not flag 6 of 24 rebound cases. However z produces 200 (vs 196) nonVoid switches and 30 (vs 27) rapid direct reversals: it may improve **risk recognition** but has **not demonstrated a solution to whipsaw**. Percentile 5% is aggressive; OLS rupture only catches 1/11 continued decline and is unsuitable as a stand-alone substitute.

## Historical subperiod sensitivity

### 2021-2023

| Variant | NonVoid switches | CAGR% | MDD% |
|---|---:|---:|---:|
| fixed | 70 | 17.16 | -28.77 |
| z | 78 | 24.28 | -27.86 |
| rank | 90 | 17.95 | -31.34 |
| ols | 69 | 10.02 | -34.24 |

### 2024-2026

| Variant | NonVoid switches | CAGR% | MDD% |
|---|---:|---:|---:|
| fixed | 126 | 118.77 | -36.12 |
| z | 122 | 120.1 | -32.41 |
| rank | 148 | 88.86 | -30.28 |
| ols | 92 | 88.18 | -42.74 |

Full sweep over 2021–2026 still creates selection bias even when thresholds were not tuned inside this run. Early/late are **descriptive segment checks**, not independent training/test evaluation.

## Stress & limitations

Model PnL: at T signal, hold output target from T+1 open to T+2 open, gross mark-to-market; subtract side_cost * (1 for cash entry/exit or 2 for risk-to-risk change). Historical missing T+1/T+2 opening prices (10–13 days depending method) are currently zero-gross-imputed and counted; **this is a source defect, not a safe fill method**. LOF price adjustment, large returns and unconfirmed premiums also compromise dollar-PnL estimates. Therefore CAGR and MDD are exploratory, not reliable live-performance forecasts. Stress results with 6, 12, 20, 30 bp per side and truncated ±10/20% daily gross returns are in `d2_four_method_stress_2021_2026.csv`. Capping is a robustness diagnostic only, not a tradable strategy.

Trade paths can differ from the 3% baseline even after a dynamic-veto event clears, because V1 holds incumbent and Void freezes pre-Void output. The state map is intentionally fixed to the original raw OLS market state so variations isolate the candidate gate.

## Recommendation

**Keep production unchanged.** Prioritize further Z-score testing because it's the most promising four-way risk-recognition candidate; do not claim it reduces whipsaw. Evaluate the same exit filters at a *matched triggered-exit count*, and separately test the rule for entering versus existing holdings, while imposing an explicit price-data quality audit and prospective out-of-sample validation. The OLS rupture rule must be redesigned, not promoted simply because it switches less.

See [four-method summary](d2_four_method_summary_2021_2026.csv), [segment comparison](d2_four_method_periods_2021_2026.csv), [39-case overlaps](d2_four_method_39_case_overlap.csv) and [stress](d2_four_method_stress_2021_2026.csv).
