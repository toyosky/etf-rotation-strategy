# 2026-11-20 minute-session integrity audit (read-only)

## Scope and provenance
Read-only SQL against Supabase project gsyziuzezmmnvgdoazkg, public.minute_bars, on 2026-11-20. This is a data-quality audit, NOT a new OOS prediction, tradable Top1 reconstruction, or strategy performance test. Existing PR #7 preregistration and prior negative OOS findings remain authoritative. Production untouched.

## Exact executed SQL

```sql
WITH s AS (
 SELECT symbol, trade_date,
 count(*) FILTER (WHERE interval_min=1) n,
 count(*) FILTER (WHERE interval_min=1 AND bar_time::time='14:05:00') n1405,
 count(*) FILTER (WHERE interval_min=1 AND bar_time::time='09:31:00') n0931,
 count(*) FILTER (WHERE interval_min=1 AND bar_time::time>='14:05:00') npost,
 count(*) FILTER (WHERE interval_min=1 AND (low>high OR open>high OR open<low OR close>high OR close<low)) bad
 FROM public.minute_bars GROUP BY 1,2
)
SELECT symbol,count(*) days,min(trade_date),max(trade_date),min(n),avg(n),
 count(*) FILTER(WHERE n1405=0) missing_1405,
 count(*) FILTER(WHERE n0931=0) missing_0931,
 count(*) FILTER(WHERE npost=0) no_post,sum(bad) bad_ohlc
FROM s GROUP BY symbol ORDER BY symbol;
```

```sql
WITH d AS (
 SELECT symbol,trade_date,
 min(low) FILTER(WHERE bar_time::time BETWEEN '14:05' AND '15:00') lo_regular,
 min(low) FILTER(WHERE bar_time::time BETWEEN '14:05' AND '15:30') lo_extended,
 sum(volume_shares) FILTER(WHERE bar_time::time>'15:00') post_volume,
 count(*) FILTER(WHERE bar_time::time>'15:00' AND volume_shares=0) post_zero
 FROM public.minute_bars WHERE interval_min=1 GROUP BY 1,2
)
SELECT count(*) pairs,
 count(*) FILTER(WHERE lo_extended<lo_regular-1e-9) lower_extended,
 avg((lo_regular-lo_extended)/lo_regular*100) avg_extra_pct,
 max((lo_regular-lo_extended)/lo_regular*100) max_extra_pct,
 sum(post_zero) zero_volume_after,
 count(*) FILTER(WHERE post_volume>0) days_post_trades
FROM d WHERE post_volume IS NOT NULL;
```

## Observations

- 15 symbols, each 43 dates, 2026-09-14 through 2026-11-19: 645 symbol-days. All have 09:31 and 14:05 minute bars; no OHLC containment violations detected.
- 12 ETF symbols have exactly 267 1-minute rows/day, extending to 15:30; three LOFs (161226,164824,501018) have exactly 242 rows/day, ending at 15:00. The 25 additional ETF rows/day are at 15:06–15:30, consistent with an additional session, but **exchange execution eligibility, price semantics, and order types are NOT certified by this SQL**.
- Across 12×43=516 ETF-days with post-15:00 records, 507 have positive post-15:00 summed volume; 7,644 of the 12,900 post-15:00 rows have zero volume. Do not treat all 267 rows as homogeneous regular-session executable liquidity.
- In these 516 ETF-days, comparing minimum low between 14:05–15:00 against 14:05–15:30, **zero** days have a strictly lower extended-session minimum (floating tolerance 1e-9). Thus the extra 25 rows did not change this specific within-day low statistic; this is not a proof that the additional bars are generally harmless for returns, volume, close-price reference, or order execution.
- All 15×43 observations are highly overlapping if used as 3/5/10-day forward labels. 43 days of minute coverage cannot support a standalone multi-year walk-forward test.

## Implications and blockers

1. Preserve exact entry cutoff and eligible market session when defining executable MAE. Compare 14:05-to-15:00 regular window separately from any post-close product-specific trading mechanism; do not assume a 15:30 print is an executable replacement for 14:05.
2. Missing historical PIT NAV/premium and minute data before 2026-09-14 still prevent certifying 2021–2025 V1/Void executable Top1 holdings. 19 daily-bar symbols do not constitute the full ETF universe.
3. Existing unified model Q90 tail calibration and portfolio benefits remain unproven for production. Do not tune an exit fraction or a return-to-market policy from this 43-day panel.
4. Next audit: validate post-15:00 bar source semantics against exchange documentation and instrument trading permissions; compare regular-close and after-session volume/price effects, then apply only to held-route validated observations.

No production code, trading parameters, PushPlus notifications, or holdings changed.
