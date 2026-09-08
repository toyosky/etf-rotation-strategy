# Asset Universe Governance

`daily_bars` is a market-data store, not the definition of the live strategy pool.
The canonical current membership registry is `public.asset_universe` in Supabase.

## Status meanings

- `ACTIVE`: formal risk asset. Included in scheduled Asset Health monitoring.
- `CASH_PROXY`: strategy cash signal/proxy. Kept in data, excluded from risk-asset health classification.
- `RETIRED`: formerly used formal asset. Historical bars, scores, signals, trades and old health snapshots are retained, but no new scheduled health snapshots are generated.
- `CANDIDATE`: replacement/research candidate with market data available. Not mixed into the formal monitor until explicitly promoted.

## Current 18-asset registry (2026-09-08)

### ACTIVE (13)

`159509`, `159529`, `159915`, `159981`, `159985`, `161226`, `164824`, `501018`, `511380`, `513100`, `513290`, `513920`, `518880`

### CASH_PROXY (1)

`511220`

### RETIRED (1)

`159825` — retired after Asset Health review; historical records remain intact.

### CANDIDATE (3)

- `513030` Germany DAX ETF — priority replacement test for `159825`
- `513520` Nikkei 225 ETF — replacement candidate
- `512660` military-sector ETF — replacement candidate

## GitHub Actions behavior

`.github/workflows/asset-health.yml` runs `research/asset_health_active.py`.
The wrapper reads only `asset_universe.universe_status = ACTIVE`, then delegates all frozen V1 calculations and thresholds to `research/asset_health.py`.

This split is intentional:

1. `strategy_runs.parameters` remains an immutable record of the historical experiment that produced its signals.
2. `asset_universe` represents current governance / membership.
3. `daily_bars` may retain data for all statuses.
4. Retiring or adding a candidate does not rewrite historical strategy results.

## Change control

Do not promote a candidate by editing only GitHub code. Promotion/retirement should first update `asset_universe` with a reason and effective date. If the formal trading strategy itself is changed, create a new strategy/pool version rather than mutating an old frozen `strategy_runs` record.
