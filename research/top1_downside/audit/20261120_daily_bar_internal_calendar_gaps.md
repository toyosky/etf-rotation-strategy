# 2026-11-20 daily-bar internal-calendar continuity audit

Status: read-only Supabase execution; research only. This is a **new check** following annual coverage audit; no model fitting or live strategy modification.

## Method
Reference calendar is the union of observed `public.daily_bars.date` between 2021-01-01 and 2026-11-19. For each symbol, compare all calendar dates between max(first observed symbol date, 2021-01-01) and min(last observed date, 2026-11-19) to symbol's actual observed rows. This detects internal gaps only, **not** pre-listing eligibility, suspensions, exchange-calendar discrepancies, late vendor inception or survivorship. No imputation performed.

Executed SQL:

```sql
WITH cal AS (
 SELECT DISTINCT date FROM public.daily_bars
 WHERE date BETWEEN '2021-01-01' AND '2026-11-19'
), spans AS (
 SELECT symbol, MIN(date) first_date, MAX(date) last_date
 FROM public.daily_bars GROUP BY symbol
), missing AS (
 SELECT s.symbol, c.date FROM spans s
 JOIN cal c ON c.date BETWEEN GREATEST(s.first_date, DATE '2021-01-01')
 AND LEAST(s.last_date, DATE '2026-11-19')
 LEFT JOIN public.daily_bars b ON b.symbol=s.symbol AND b.date=c.date
 WHERE b.symbol IS NULL
)
SELECT symbol, COUNT(*) missing_days,
 STRING_AGG(date::text, ', ' ORDER BY date) dates
FROM missing GROUP BY symbol ORDER BY missing_days DESC;
```

## Actual results

Ten missing symbol×calendar dates, across five of 19 symbols:
- 159529: 2025-01-10, 2025-01-17, 2025-01-22, 2025-01-24 (4).
- 161226: 2026-01-22, 2026-01-30 (2).
- 501018: 2026-01-30, 2026-03-24 (2).
- 513100: 2022-01-13 (1).
- 513500: 2022-03-29 (1).
- Other 14 symbols: no internal gaps against this calendar.

## Interpretation / methodological gate

Existing rows have non-null volume/amount, but this **does not** imply complete tradability. Missing dates may be trading suspensions or data ingestion omissions; do not auto-forward-fill lows/volume, assume execution possible, or silently compress missing trading sessions into five observations. Verify each date against exchange announcements and vendor source. Use common market calendar for horizon construction and mark unresolved missing/suspension days as censored or excluded with counts. In particular 501018 and 161226 gaps in 2026 can alter oil/silver 5-day MAE and purported execution routes.

This finding does not prove a model gain, fix PIT premium (currently zero PIT-safe rows), or authenticate executable historical Top1. Next: verify the ten dates, add calendar-aware label eligibility and re-run ablation on identical eligible OOS sample. No production changes.
