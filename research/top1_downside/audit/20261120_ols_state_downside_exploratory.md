# 2026-11-20: weighted OLS state vs downside event risk — first actual trend-structure calculation

## Scope and execution

Executed read-only SQL on Supabase project `gsyziuzezmmnvgdoazkg`, `public.daily_bars`, and committed the exact executed SQL as `sql/ols_state_downside_exploratory.sql`. Checked draft PR #7 and current Actions; premium sync still failing. No production modification.

This is the first run in this branch to **calculate** 26-session weighted log-price OLS slope and weighted R² per down-day event, rather than slicing price/volume/volatility alone.

- Signal days 2021-01-01 to 2026-11-10, all 19 symbols in current Supabase `public.daily_bars` (historically available symbols only), t daily close/previous close <= -2%.
- Fit 26 consecutive observed sessions ending t. x=0..25 oldest to newest; weight w=exp(-ln(2)*(25-x)/10), half-life 10 sessions. Weighted slope beta = weighted covariance(x,ln(close))/weighted variance(x); weighted R² = squared weighted correlation.
- Three strata: beta<=0; beta>0 and R²<0.5; beta>0 and R²>=0.5. **No historical Top1 selection or routing**; this is not an eligible OLS holding sample.
- Future proxy MAE = min(adjusted daily low of t+1 through t+5) / adjusted open(t+1) - 1. This is not 14:05 execution, not a realized trade, no premium PIT, and is sensitive to adjustment and low-price execution assumptions.
- Events overlap and are not independent; no significance claims, no training or OOS modeling.

## Actual results

| Period | State | n | mean beta | mean R² | mean future MAE % | P(MAE<=-5%) |
|---|---|---:|---:|---:|---:|---:|
| 2021–24 | beta<=0 | 328 | -0.00285 | .419 | -2.32 | 10.98% |
| 2021–24 | beta>0, R²<.5 | 181 | .00171 | .207 | -2.33 | 12.15% |
| 2021–24 | beta>0, R²>=.5 | 169 | .00576 | .721 | -2.60 | 13.61% |
| 2025–26 | beta<=0 | 240 | -0.00422 | .451 | -3.62 | 25.42% |
| 2025–26 | beta>0, R²<.5 | 155 | .00242 | .205 | -2.79 | 16.13% |
| 2025–26 | beta>0, R²>=.5 | 131 | .00939 | .733 | -4.44 | 32.06% |

Totals: 678 (2021–24), 526 (2025–26), **1,204** events. Different earlier event counts can result from requiring 26 valid trailing bars and a valid t+1 open and t+5 low.

## Interpretation and guardrails

**Exploratory finding:** In this conditional down-day sample, a still-positive, high-R² weighted OLS trend does **not** guarantee shallow next-week adverse excursion; the strongest-trend stratum has 13.61% (2021–24) and 32.06% (2025–26) future 5%-MAE event rates. It would be an error to infer that positive beta/high R² itself causes risk or that negative beta is protective: conditioning on a >=2% down-day, beta magnitude, ETF composition, volatility, prior drawdown, and year/regime can create strong selection effects. Also beta<=0 is ordinarily **not eligible** for the production Top1, so cross-stratum comparison does not represent a deployable exit rule.

**Important technical caveat:** This computes true weighted least squares with half-life 10. Production's precise OLS weighting is to be reconciled against `strategy/main.py` (np.polyfit weights q => objective weights q²); do not call it exact frozen production score until numeric parity tests are passed. Other production rules (resistance/Void/premium/intraday) remain unreconstructed.

## Next material gate

1. Numerically compare SQL weighted beta/R² to frozen production `_ols` calculation on dated snapshots, including q vs q² and score transforms; correct if needed.
2. Run risk comparison **within positive beta, R²>=0.5 only** and control ETF/year, beta magnitude, volatility, and prior 5-day path, with purged chronological OOS evaluation; do not substitute another descriptive binning exercise for this.
3. Recover actual executable held Top1 or explicitly split daily-approximation vs PIT-audited execution datasets. Without this, no dynamic-sizing performance claim.

Status: exploratory OLS diagnostic **completed**; primary full research **not completed**. Automation should remain enabled.
