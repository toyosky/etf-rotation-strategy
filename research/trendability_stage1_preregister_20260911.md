# Trendability Stage 1 preregistration — 2026-09-11

## Objective

Test whether an asset-level historical **Trendability** prior has genuine out-of-sample predictive value for future healthy OLS continuation after removing product duplication with point-in-time liquidity representatives.

This stage is **predictive validation only**. No trading backtest, candidate threshold search, or production rule change is allowed.

## Mother universe and representative layer

1. Use `public.daily_bars` and current structural `underlying_key` taxonomy.
2. Build the same frozen OLS features as `research/full_market_ols_storage.py`.
3. At the start of each calendar month, use only information through the prior trading day.
4. Within each `underlying_key`, among point-in-time `universe_eligible` products, choose one representative by:
   - trailing 60-day median amount descending;
   - trailing 60-day average amount descending;
   - history bars descending;
   - symbol ascending as deterministic tie-break.
5. Freeze that representative for the whole month.
6. The current 2026 representative is **not** projected backward.

Known limitation: most taxonomy labels are current structural labels, not fully audited historical label histories. No return information was used to create the labels, but historical fund transformations remain a survivorship/metadata caveat.

## Frozen OLS / universe inputs

Use the existing research implementation without changes:
- 26-price weighted log-price OLS;
- half-life 10;
- annualization 250;
- Score = positive annualized slope return × positive weighted R²;
- D2 recent 3-day single-day drop floor 0.97;
- historical universe eligibility from `full_market_ols_storage.py`:
  - >=200 bars;
  - >=365 calendar days listed;
  - trailing 60-day average amount >= RMB 20m;
  - trailing 60-day median amount >= RMB 10m;
  - nonzero-volume share >=95%.

No threshold is changed after seeing results.

## Healthy OLS event

Use the previously frozen health definition:
- asset is the frozen monthly representative for its `underlying_key`;
- asset is `trend_eligible`;
- `ScoreDelta > 0`;
- valid `ResistancePct252 < 75`.

Resistance definition is frozen:
- prior 120 trading days;
- each day's amount distributed uniformly over `[low, high]`;
- current-price ±5% profile window;
- `UpperShare = amount[P,1.05P] / amount[0.95P,1.05P]`;
- point-in-time empirical percentile versus strictly prior max252 profile observations;
- minimum 60 prior valid profile observations.

To reduce event overlap, count at most one event per entry into the tradable representative-trend state: the first healthy day after either (a) the asset was not the monthly representative on the prior trading day or (b) it was not trend-eligible on the prior trading day.

## Outcome

Primary horizon: **forward 10 trading-day close-to-close return** only.

For every healthy event:
- `fwd10_raw = close[t+10]/close[t]-1`.
- Build a contemporaneous equal-weight factor from all other valid monthly representatives on the same event date with a valid forward-10 return.
- `fwd10_residual = fwd10_raw - factor_fwd10`.

The residual return is the primary target because Trendability is intended to identify asset-specific follow-through rather than simply rediscover broad market regimes.

## Historical Trendability estimator

At each month start `m`, using only healthy events whose 10-day outcome is fully known by the prior trading day:

- `asset_mean_i` = historical mean `fwd10_residual` for asset `i`.
- `n_i` = count of historical known healthy events for asset `i`.
- `global_mean` = mean residual across all historical known healthy events.
- Frozen shrinkage prior sample size `k = 10`.

`Trendability_i = n_i/(n_i+k) * asset_mean_i + k/(n_i+k) * global_mean`.

Assets with zero prior healthy events receive the global mean but are excluded from quintile tests until they have at least one asset-specific prior event. No minimum-event threshold beyond `n_i >= 1` is optimized.

## Validation

Each future healthy event receives the Trendability estimate frozen at the start of its month.

Primary sample: **2021-01-01 through 2024-12-31**.
Posterior sample: **2025-01-01 onward**.

Report:
1. event count and scored-event coverage;
2. Spearman correlation between frozen Trendability and future `fwd10_residual`;
3. quintile mean residual return Q1..Q5;
4. quintile symbol-equal mean residual return;
5. Q5 minus Q1 residual spread;
6. quintile raw fwd10 and positive residual share;
7. year-by-year diagnostics.

## Frozen decision rule

`KEEP_CANDIDATE` only if the **2021-2024 primary sample** satisfies all three:

1. Spearman(Trendability, future residual) > 0;
2. Q5 mean residual > Q1 mean residual;
3. at least 3 of the 4 adjacent quintile mean steps are non-negative.

Otherwise: `REJECT_STAGE1_V1`.

2025-2026 is posterior robustness evidence only and cannot reverse the primary KEEP/REJECT decision.

## Prohibited after run

- no alternate holding horizons;
- no alternate Resistance percentile thresholds;
- no alternate ScoreDelta threshold;
- no alternate shrinkage `k`;
- no liquidity threshold sweep;
- no excluding inconvenient asset classes;
- no thresholding Trendability into a strategy in Stage 1.

If this construction fails, preserve the result and design a new hypothesis separately.
