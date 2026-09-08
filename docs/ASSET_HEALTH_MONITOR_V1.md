# Asset Health Monitor V1

## Purpose

Asset Health is a diagnostic layer for the ETF candidate pool. It asks a different question from the trading strategy:

- OLS ranking: **which eligible asset is strongest now?**
- Asset Health: **when this asset historically looked strong under the same strategy state, did that state actually continue?**

The monitor **does not trade, does not edit `ETF_POOL`, and does not automatically remove an ETF**. A `WATCH` or `WARNING` is evidence for human review and, if appropriate, a separately preregistered deletion/replacement experiment.

## Research provenance and anti-hindsight rule

V1 was motivated by the 2026-09-08 review of `159825`, where `Top1 + near 20-day high` states showed unusually weak subsequent 5/10-trading-day continuation compared with other assets.

Therefore the exact V1 definition below is **exploration-derived, not clean historical out-of-sample evidence**. It is frozen prospectively from this implementation onward. Future observations should be accumulated without tuning the thresholds in place. Any threshold change must create a new monitor version such as `ASSET_HEALTH_V2`.

## Source strategy

Default source strategy snapshot:

`FROZEN_C2@20260903T_fixed_window_v2`

The monitor uses the strategy's historical `signals.top1` and `signal_date`, rather than recomputing a different ranking rule from raw prices. This keeps the diagnostic aligned with the actual strategy state that produced the historical Top1.

`511220` is the cash proxy and is excluded from risk-asset health classification.

## Data inputs

- `daily_bars`: closing prices and row-level source labels.
- `signals`: strategy Top1 and signal date.
- `daily_scores`: Top1 score and R² for descriptive fields.
- `strategy_runs`: candidate pool and source strategy metadata.

All return fields stored in `asset_health_snapshots` are decimal fractions, e.g. `-0.04 = -4%`. Win rates are also decimals in `[0, 1]`.

## Event definition

For each historical Top1 signal date `t` and asset `i`:

- Require at least 20 daily closes through `t`.
- Require 10 later trading-day closes so that the event is mature.
- Compute forward returns from the signal-date close:
  - `fwd5 = close[t+5] / close[t] - 1`
  - `fwd10 = close[t+10] / close[t] - 1`
- Define a near-high state when:
  - `close[t] >= 0.995 * max(close[t-19:t])`
  - i.e. the close is within 0.5% of the 20-trading-day closing high.

## Mixed-source seam protection

The current `daily_bars` snapshot mixes GM hfq data with a rescaled JoinQuant tail for 12 ETFs. The 2026-07-21 seam is known to have a forced 0% splice return.

V1 therefore excludes any event whose full analysis window (`t-19` through `t+10`) contains more than one `source` value. This prevents the GM/JoinQuant splice from contaminating near-high and forward-return diagnostics.

## Monitoring windows

For every asset the monitor records:

1. All mature historical Top1 events.
2. All mature historical `Top1 + near-high` events.
3. `Top1 + near-high` events in the latest 2 calendar years relative to the available data cutoff.
4. The latest 1 year as descriptive context only.

The 2-year window participates in V1 status classification; the 1-year window does not, because samples are often too small.

## Frozen V1 status rules

Minimum evidence:

- all-history near-high sample count >= 10, and
- recent-2y near-high sample count >= 5.

Otherwise: `INSUFFICIENT_DATA`.

With sufficient data:

### WARNING

All of the following must hold:

- all-history near-high 10d mean return < 0;
- recent-2y near-high 10d mean return < 0;
- all-history near-high 10d win rate < 35%;
- recent-2y near-high 10d win rate < 35%.

### WATCH

Either:

- all-history and recent-2y near-high 10d mean returns are both negative but the stricter `WARNING` rule is not met; or
- recent-2y near-high 10d mean return < 0 **and** recent-2y 10d win rate < 40%.

### HEALTHY

No frozen V1 deterioration condition is triggered.

These thresholds are intentionally simple. V1 is a monitoring rule, not a fitted forecasting model.

## Data freshness

`data_status` is separate from health status.

- `FRESH`: latest `daily_bars` and source-strategy signal dates are both within 10 calendar days of the snapshot date.
- `STALE`: either source is older than 10 calendar days.

A stale snapshot can still describe historical evidence, but it must not be interpreted as current monitoring coverage.

## Supabase output

Table: `public.asset_health_snapshots`

Primary key:

`(snapshot_date, symbol, monitor_version, source_strategy_version)`

This makes a rerun on the same date idempotent while retaining prior monthly snapshots for walk-forward audit.

The public-schema table has RLS enabled. `anon` and `authenticated` Data API privileges are revoked; the backend secret maps to `service_role` and is the intended GitHub Actions credential.

## GitHub Actions schedule

Workflow: `.github/workflows/asset-health.yml`

- Monthly on the 2nd day at 00:30 UTC.
- Manual `workflow_dispatch` is also enabled.
- Unit tests run before the database job.
- The Markdown report is appended to the GitHub Actions Step Summary.

Required repository secrets:

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY` — preferred new `sb_secret_...` backend key.

The legacy `SUPABASE_SERVICE_ROLE_KEY` is accepted by the Python script as a fallback, but new deployments should use `SUPABASE_SECRET_KEY`.

## Change-control rule

Do not modify `strategy/main.py` based directly on an Asset Health status. The intended workflow is:

1. Monitor detects persistent deterioration.
2. Review sample count and market/data-quality context.
3. Preregister a single-variable pool deletion/replacement experiment.
4. Rerun the frozen strategy with that one pool change.
5. Promote only if evidence is economically coherent and robust.
