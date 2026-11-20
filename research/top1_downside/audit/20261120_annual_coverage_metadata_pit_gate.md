# 2026-11-20 annual coverage and classification PIT gate (read-only verification)

This check continues run11's reproducibility gate; it does not rerun the completed 14:05 MAE comparison or claim a new OOS experiment.

## Executed read-only SQL

```sql
SELECT EXTRACT(YEAR FROM date)::int yr, COUNT(*) n,
       COUNT(DISTINCT symbol) symbols,
       COUNT(*) FILTER (WHERE volume IS NULL) missing_volume,
       COUNT(*) FILTER (WHERE amount IS NULL) missing_amount,
       MIN(date) first_date, MAX(date) last_date
FROM public.daily_bars
WHERE date >= '2021-01-01'
GROUP BY 1 ORDER BY 1;
```

## Actual result (2026-11-20)

| Year | Daily rows | Distinct symbols | Missing volume | Missing amount |
|---|---:|---:|---:|---:|
| 2021 | 2916 | 12 | 0 | 0 |
| 2022 | 3156 | 14 | 0 | 0 |
| 2023 | 3486 | 15 | 0 | 0 |
| 2024 | 3849 | 16 | 0 | 0 |
| 2025 | 3954 | 18 | 0 | 0 |
| 2026 through Nov 19 | 3862 | 19 | 0 | 0 |

Total 2021–2026: 21,223 daily symbol-date rows. The entire daily_bars table contains 33,205 rows and 19 distinct symbols. Missing-volume/amount counts are zero **only for the existing rows**; this does not establish continuous listing-date coverage, correct units, or an unbiased ETF universe.

Schema inspection confirms `daily_bars` table-level source=tencent_westockdata, adjustment=hfq, amount CNY; `minute_bars` is forward tracked only from 2026-09-14. The `instrument_metadata` table currently contains **zero rows**; consequently asset-class, QDII/NAV lag, historical eligibility and underlying exposure classification cannot be obtained from this table. Metadata from present-day names or fixed-pool membership must not be silently backdated to 2021.

## Implications for next executable step

1. Recover dated classification and universe membership evidence from immutable historical artifacts; explicitly flag unavailable PIT attributes and delisted/late-listed funds. This is separate from obtaining bars.
2. Reconstruct frozen V1/Void route with date-specific rules, recording candidate, routable asset, exclusions, execution timestamp and PIT evidence. If premium PIT is unavailable, classify as candidate proxy, never certified holding.
3. Recover versioned source snapshot and runnable OOS trainer before claiming fully reproducible five-block ablation. Existing historical unified reports are exploratory and not recomputed here.
4. No new live withdrawal policy, no production code changes, no CI success claim. Research completion gate remains open.
