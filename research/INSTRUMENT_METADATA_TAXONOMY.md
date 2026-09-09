# Instrument Metadata Taxonomy

Purpose: define the ETF/LOF universe in terms of **economic exposure first, product wrapper second** so that future OLS research can answer “which assets deserve to be traded by OLS?” without treating hundreds of near-duplicate fund products as independent assets.

## Core hierarchy

`Product -> Economic Exposure -> Risk Bucket -> Historical Trendability -> Current OLS`

The metadata layer must not use returns or backtest performance.

## Primary fields

- `symbol`: exchange-traded fund code.
- `name`: current fund short name from current public fund masters when available.
- `product_type`: `ETF`, `LOF`, or `UNKNOWN`.
- `asset_class`: `EQUITY`, `COMMODITY`, `BOND`, `CASHLIKE`, `OTHER`.
- `region_primary`: primary economic region (`CN`, `HK`, `US`, `JP`, `DE`, `FR`, `EU`, `IN`, `VN`, `SA`, `ASIA`, `GLOBAL`, ...).
- `region_tags`: additional region tags when one primary region is insufficient.
- `exposure_level1`: broad economic sleeve, e.g. `CHINA_EQUITY`, `US_EQUITY`, `COMMODITY`, `CHINA_FIXED_INCOME`.
- `exposure_level2`: more specific sleeve, e.g. `US_TECH`, `PRECIOUS_METALS_GOLD`, `DEFENSE`, `CONVERTIBLE_BOND`.
- `underlying_key`: canonical underlying/exposure identity, e.g. `NASDAQ100`, `GOLD`, `CHINEXT`, `DAX`.
- `risk_bucket`: strategy-level grouping used for exposure de-duplication. It is intentionally coarser than exact fund identity but finer than asset class.
- `style_sector`: optional style/sector descriptor.

## Execution metadata

- `is_qdii`: QDII/cross-border economic wrapper.
- `nav_lag_days`: explicit NAV publication lag only when verified; otherwise NULL.
- `premium_sensitive`: whether premium/NAV divergence deserves explicit execution controls.
- `t0_flag`: T+0 only when known; unknown is NULL rather than guessed.
- `derivative_exposure`: economic exposure materially obtained through futures/derivatives.
- `roll_cost_exposure`: materially exposed to futures roll/carry.
- `currency_exposure`: main foreign-currency exposure where applicable.
- `leveraged_flag`, `inverse_flag`: structural leverage/inverse products.

## Historical validity

Current fund names cannot automatically be projected backward through the entire backtest.

- `label_scope = CURRENT_SNAPSHOT`: current-name based automatic label. `historical_safe = false`.
- `label_scope = HISTORICAL_MANUAL`: manually verified structural reference label. `historical_safe = true` and `valid_from` begins at the first available daily bar.
- `valid_from` / `valid_to`: allow future split histories for funds that rename, change index, or transform.

The first pass intentionally leaves most of the 645-product universe as current snapshots. Historical walk-forward Trendability research must only use `historical_safe=true` rows until a separate historical metadata audit expands coverage.

## Classification methods

- `MANUAL_REFERENCE_V1`: original fixed15 plus explicitly researched candidate exposures; structural labels only, no performance information encoded.
- `AUTO_NAME_V1`: deterministic keyword taxonomy from current public fund names/types.

Rows with generic buckets or uncertain wrapper identity are marked `needs_review=true`.

## Design constraints

1. No return, Score, forward return, IC, win rate, or backtest result may determine metadata labels.
2. Correlation is not metadata. Correlation can later help choose representatives inside a tagged risk bucket, but it must not define what the asset economically is.
3. ETF and LOF are wrappers, not separate asset classes.
4. Multiple distinct underlyings may coexist inside one broad risk bucket (e.g. Gold and Silver inside precious metals).
5. Near-identical products tracking the same underlying should later compete on execution quality/liquidity rather than all enter OLS independently.
