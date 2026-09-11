# Instrument Taxonomy V2 — 2026-09-11

## Purpose

Build an economic-exposure layer for the current ETF/LOF research universe before any Trendability or OLS asset-selection research.

The taxonomy uses **no returns, OLS scores, backtest performance, or forward labels**. It is therefore a metadata layer, not a performance filter.

Hierarchy:

`product wrapper -> asset class -> region -> risk bucket -> underlying key`

- `product_type`: ETF / LOF wrapper.
- `asset_class`: EQUITY / BOND / COMMODITY / CASHLIKE.
- `region_primary`: primary economic region.
- `risk_bucket`: deliberately coarser economic exposure used for de-duplication.
- `underlying_key`: finer underlying/index/exposure identity.

Important limitation: V2 aims to make every instrument economically classifiable. It does **not** claim that every `underlying_key` is the exact official index identifier. Exact tracking-index identities are used where verified or obvious; otherwise `underlying_key` is a deterministic economic-exposure key suitable for de-duplication. This prevents false precision.

## Before V2

Among the 1,087 instruments with `daily_bars`:

- `needs_review`: 296
- `CHINA_EQUITY_OTHER`: 257
- missing `underlying_key` or `risk_bucket`: 36
- `US_EQUITY_OTHER`: 3

The main problem was under-classification rather than genuinely unknown products. Broad indices, factor ETFs, cash-management ETFs, bond ETFs, gold ETFs and many industry themes were being collapsed into `CHINA_EQUITY_OTHER`.

## V2 corrections

### Verified fixed-income products

36 previously unnamed products were manually verified and mapped into:

- `CHINA_TECH_INNOVATION_BOND`
- `CHINA_CREDIT_BOND`
- `CHINA_GOV_BOND`
- `CHINA_LOCAL_GOV_BOND`
- `CHINA_POLICY_BANK_BOND`
- `CHINA_GOV_POLICY_BANK_BOND`
- `CHINA_CONVERTIBLE_BOND`
- `CHINA_SHORT_CREDIT_BOND`

These mappings are structural and performance-independent.

### Cross-border / wrapper edge cases

- `162719 石油LOF`: US oil & gas exploration/production equities, not crude-oil futures commodity exposure.
- `160416 石油基金LOF`: global oil-company equity-index QDII, not crude-oil futures commodity exposure.
- `513360 教育ETF`: global China education QDII exposure, not domestic China education equity.
- `563330 A股ETF华泰柏瑞`: CSI A-Share broad exposure (`CSI_A_SHARE`).
- `159518 / 513350 标普油气ETF`: S&P oil & gas exploration/production industry equity exposure, not broad S&P 500.
- `159502 标普生物科技ETF`: S&P biotechnology industry exposure, not Nasdaq biotech.
- `562060 标普A股红利ETF`: domestic China A-share dividend exposure despite the S&P name.
- China-concept internet products are separated as `CHINA_OFFSHORE_INTERNET`.
- Brazil, US 50 and Dow Jones products receive explicit foreign-region labels.

### Commodity vs producer equity

A major V1 error came from classifying by name substring alone:

- physical/spot gold ETFs -> `COMMODITY / PRECIOUS_METALS_GOLD / GOLD_SPOT`.
- **gold-miner stock ETFs** -> `EQUITY / CHINA_HK_GOLD_MINERS / CSI_SH_SZ_HK_GOLD_INDUSTRY`.

Thus a gold-miner equity ETF no longer competes as if it were the same underlying as `518880` physical gold.

### Cash management

Cash-management/monetary ETFs (日利/添益/快线/货币ETF etc.) are standardized to:

- `asset_class = CASHLIKE`
- `risk_bucket = CHINA_CASHLIKE`
- `underlying_key = CNY_CASH_MANAGEMENT`

### China broad indices and factors

Examples of distinct `underlying_key` values:

- `CSI_A50`, `MSCI_CHINA_A50_CONNECT`, `FTSE_CHINA_A50`
- `CSI_A100`, `CSI800`, `MSCI_CHINA_A_RMB`
- `SSE180`, `SSE380`, `SSE_COMPOSITE`
- `SZSE100`, `SZSE50`, `SZSE_COMPONENT`
- `CHINEXT100`, `CHINEXT_COMPOSITE`, `STAR_CHINEXT_50`
- cash-flow/free-cash-flow, value, quality, growth, ESG and equal-weight factor families.

The exact underlying remains finer than the risk bucket. For example different A50 index families can share a broad `CHINA_LARGE_A50` risk bucket without pretending they track the exact same index.

### China sectors/themes

V2 adds explicit buckets for, among others:

- cybersecurity / Xinchuang
- digital economy
- industrial internet / IoT / TMT / information technology
- TCM / vaccines / biotech / pharmaceuticals
- aerospace / satellites / aviation / defense
- transportation
- chemicals / materials / rare metals / mining
- oil & gas equity / petrochemical / energy equity
- agriculture/livestock/grain
- low-carbon / environmental
- power grid / machinery / advanced manufacturing
- insurance / film & media / tourism
- Belt & Road and regional themes
- specialized SMEs / new economy / domestic brands
- electronics / telecom

### Hong Kong refinement

The old V1 had many Hong Kong products collapsed into `HK_BROAD` or `HK_TECH`. V2 separates clear name-based exposures such as:

- `HK_HEALTHCARE` (innovation drugs / biotech / healthcare)
- `HK_CONSUMER`
- `HK_AUTOMOTIVE`
- `HK_SECURITIES`
- `HK_TECH` with internet/information-technology sub-identities
- `HK_NEW_ECONOMY`
- `HK_H_SHARE`
- Hang Seng / Stock Connect 50 / Stock Connect 100 identities
- `HK_SOE` for verified mainland-SOE Hong Kong exposure

`HK_BROAD` therefore remains only for genuinely broad or insufficiently sector-specific Hong Kong index products, rather than being a catch-all.

## Current result

After the full V2 pass and reverse audit on the 1,087 instruments with daily bars:

- `needs_review`: **0**
- `CHINA_EQUITY_OTHER`: **0**
- `US_EQUITY_OTHER`: **0**
- missing `underlying_key` / `risk_bucket`: **0**
- missing names: **0**

Asset-class distribution:

- EQUITY: **1,016**
- BOND: **38**
- COMMODITY: **17**
- CASHLIKE: **16**

Region distribution:

- CN: **917**
- HK: **115**
- US: **23**
- GLOBAL: **16**
- CN_OFFSHORE: **5**
- JP: **4**
- DE: **2**
- BR: **2**
- ASIA: **1**
- SA: **1**
- FR: **1**

Reverse audits were used after the initial OTHER cleanup to detect systematic contradictions such as:

- bond products classified as equity;
- gold-miner equities classified as physical gold;
- global/US oil-company equity products classified as crude-oil commodity or broad S&P 500;
- S&P-branded China A-share products incorrectly assigned to the US;
- Hong Kong sector products collapsed into broad Hong Kong exposure.

## Reproducibility

Two idempotent post-processors are committed:

- `research/apply_instrument_taxonomy_v2.py` — main V2 classification pass.
- `research/apply_instrument_taxonomy_v2_fixes.py` — systematic cross-asset / cross-border edge corrections and HK refinements.

`.github/workflows/build-instrument-metadata.yml` runs both immediately after the first-pass metadata builder so future metadata rebuilds do not regress to the coarse `AUTO_NAME_V1` taxonomy.

A pre-change database snapshot exists as:

`research.instrument_metadata_backup_20260911_before_v2`

## Research use

V2 is suitable for the next stages:

1. apply data-quality / liquidity eligibility;
2. choose representatives within repeated `underlying_key` / `risk_bucket` groups;
3. estimate walk-forward asset-level Trendability;
4. only then let OLS rank the eligible exposures.

Do not use taxonomy labels themselves as alpha signals.
