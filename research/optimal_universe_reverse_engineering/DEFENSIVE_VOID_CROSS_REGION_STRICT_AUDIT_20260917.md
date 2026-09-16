# Defensive/Void Cross-Region Strict Audit — 2026-09-17

## Question
When FixV2 Market Regime enters `DEFENSIVE_VOID`, can the strategy switch out of A-share risk assets and route into overseas regions while preserving the original OLS trend logic?

## Frozen strict setup
- Defensive/Void entry events are based on the existing State Map concept: Breadth < 50 and Leadership Gap historical percentile < 50; use first-entry events rather than every day in an episode.
- OLS is the formal 26-day weighted log-price regression with half-life 10, matching the repository implementation in `full_market_ols_storage.py`.
- Score = annualized positive trend × weighted R²; non-positive trends score 0.
- A region can participate only after at least 26 bars and at least 365 calendar days since its own first available bar. This prevents later-listed ETFs from leaking into early history.
- `511220` is the hurdle. If no overseas candidate has a higher OLS score, route stays in cash/defense.

## First strict regional pool
Representatives tested:
- US: `513500` S&P 500
- JP: `513880` Nikkei 225
- DE: `513030` DAX
- IN: `164824` India
- FR: `513080` France broad equity
- HK: `159920` Hang Seng broad equity
- BR: `159100` Brazil (only when history eligibility allows)
- Cash hurdle: `511220`

### Year-by-year event-level excess versus 511220

| Year | N | 5d excess | 10d excess | 20d excess | 40d excess | 20d median | 20d win rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2019 | 19 | -0.08% | +0.78% | +0.89% | +1.53% | +0.65% | 57.9% |
| 2020 | 13 | -0.03% | +1.48% | +0.31% | -0.72% | 0.00% | 38.5% |
| 2021 | 16 | +0.35% | +1.10% | +1.23% | -0.21% | +1.66% | 81.3% |
| 2022 | 16 | -0.25% | +0.38% | -1.18% | -2.78% | -2.07% | 25.0% |
| 2023 | 12 | +0.22% | +0.65% | -0.47% | +1.32% | 0.00% | 41.7% |
| 2024 | 13 | -0.03% | -0.26% | +0.98% | +2.39% | 0.00% | 46.2% |
| 2025 | 8 | -1.66% | -1.25% | -1.94% | -2.58% | 0.00% | 25.0% |
| 2026 | 7 | +0.72% | -0.38% | +0.83% | -1.38% | 0.00% | 28.6% |

Important: under the 365-day eligibility rule, Brazil is not eligible in the 2026 sample, so the very strong earlier non-strict 2026 Brazil contribution disappears. This materially reduces the optimistic first-pass result and confirms that listing-time availability matters.

Aggregated:
- 2019–2022: 5d ~ -0.01%, 10d +0.90%, 20d +0.34%, 40d -0.44%; 20d win rate ~51.6%.
- 2023–2026: 5d -0.15%, 10d -0.21%, 20d -0.06%, 40d +0.41%; 20d win rate ~37.5%.

The broad multi-region route is therefore not robust in the recent regime.

## Clean long-lived independent-region pool
To check whether HK/France/Brazil or short histories were contaminating the result, a second frozen pool kept only four relatively independent and longer-lived regions:
- US `513500`
- JP `513880`
- DE `513030`
- IN `164824`
- Cash hurdle `511220`

Results:

| Period | N | 5d excess | 10d excess | 20d excess | 40d excess | 20d median | 20d win rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2019–2022 | 64 | +0.30% | +1.10% | +0.70% | +0.87% | +0.56% | 54.7% |
| 2023–2026 | 40 | -0.15% | -0.08% | +0.17% | +0.87% | 0.00% | 40.0% |

Selection counts in 2023–2026:
- CASH: 12
- US: 6
- JP: 6
- DE: 8
- IN: 8

## Interpretation
1. The optimistic first-pass conclusion `Void -> overseas broad-country OLS` does not survive the stricter formal OLS + historical-availability test.
2. The key problem is not merely candidate contamination. Even the clean US/JP/DE/IN pool is only weakly positive at 20–40d in 2023–2026, with low win rate and no short-horizon edge.
3. This does **not** prove that cross-region opportunity routing is useless. It narrows the hypothesis: the useful migrated trend may live below country-wide broad indices (for example US technology/biotech, Japan factors/sectors, Europe industrial/financial, etc.), or may require a global-health gate rather than unconditional country Top1 selection.
4. Therefore the next research stage should test a hierarchical overseas universe rather than simply add more countries. The hierarchy should preserve low competition noise: first choose a region-level gate, then search a small set of economically distinct sub-exposures inside only healthy regions.
5. `511220` remains the default hurdle until a hierarchical routing design survives walk-forward, leave-one-region-out, parameter-neighborhood, and transaction/QDII-friction checks.

## Next stage
Test a two-level router:
1. Region health gate: broad-country weighted OLS vs 511220 and/or regional breadth.
2. Only inside healthy regions, allow a small pre-defined set of sub-exposures to compete.
3. Compare against both `Void -> 511220` and `Void -> broad-country Top1`.
4. Require recent-period and OOS stability; explicitly test whether performance depends on one theme such as US tech or one late-listed ETF.

Status: broad-country direct routing is **not promoted**. Cross-region research continues only in hierarchical form.
