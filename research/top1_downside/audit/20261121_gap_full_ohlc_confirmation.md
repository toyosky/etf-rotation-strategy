# 2026-11-21 gap-adjacent full OHLC verification

Read-only follow-up to `20261121_gap_cross_section_next_session_liquidity.md`. Direct SQL on Supabase `public.daily_bars`, vendor-adjusted prices. This audit tests the previously **unqueried HIGH** rather than inferring a flat candle from O=L=C.

## Verified results

- 161226 on 2026-02-02: O=H=L=C=4.72; volume 13,941,700 vs 584,322,300 on 2026-01-29. Missing 2026-01-30.
- 501018 on 2026-02-02: O=H=L=C=1.40; volume 17,572,100 vs 213,768,500 on 2026-01-29. Missing 2026-01-30.
- 501018 on 2026-03-25: O=2.38, H=2.62, L=C=2.30; **not** flat. Missing 2026-03-24.
- 159529 on 2025-01-13: O=1.74, H=1.98, L=C=1.71; **not** flat. Missing 2025-01-10.
- 159529 on 2025-01-27: O=1.95, H=1.96, L=C=1.75; **not** flat. Missing 2025-01-24.

All ten surrounding rows (prior and next for these five gaps) have `ingested_on IS NULL`; therefore this field cannot establish historical as-of availability for these records.

## Reproducible SQL

```sql
WITH targets(symbol,missing_date) AS (
 VALUES ('161226',date '2026-01-30'),('501018',date '2026-01-30'),
 ('501018',date '2026-03-24'),('159529',date '2025-01-10'),
 ('159529',date '2025-01-24')
), pairs AS (
 SELECT t.*,p.date prior_date,p.open prior_open,p.high prior_high,
 p.low prior_low,p.close prior_close,p.volume prior_volume,
 p.ingested_on prior_ingested,n.date next_date,n.open next_open,
 n.high next_high,n.low next_low,n.close next_close,
 n.volume next_volume,n.ingested_on next_ingested
 FROM targets t
 LEFT JOIN LATERAL (
  SELECT * FROM public.daily_bars
  WHERE symbol=t.symbol AND date<t.missing_date
  ORDER BY date DESC LIMIT 1
 ) p ON true
 LEFT JOIN LATERAL (
  SELECT * FROM public.daily_bars
  WHERE symbol=t.symbol AND date>t.missing_date
  ORDER BY date LIMIT 1
 ) n ON true
)
SELECT *, (next_open=next_high AND next_high=next_low
 AND next_low=next_close) flat_ohlc
FROM pairs ORDER BY missing_date,symbol;
```

## Interpretation / gating

The two identical-price candles with sharply reduced volume are compatible with severely constrained trading, but **do not prove limit-down, executable exit liquidity, or a suspension**. The missing prior session is still unresolved; do not impute prices, compress the market calendar, or use the five-day future-low label as if these observations were verified. Cross-check exchange halt notices, raw unadjusted OHLC and actual tradable volume. Keep affected 42 future-5 and 72 future-10 instrument-date windows flagged. No PIT holdings reconstruction, model OOS result or portfolio claim follows from this check. No production changes.
