# 2026-11-20 14:05 boundary sensitivity (read-only)

## Context
Continuation after `20261120_post1500_price_volume_semantics.md`. Data: Supabase `gsyziuzezmmnvgdoazkg`, `public.minute_bars`, 15 symbols × 43 sessions (2026-09-14 to 2026-11-19). This is a **same-day diagnostic**, not 5-day OOS, and **not** certified historical executable Top1 positions.

## Executed SQL
```sql
WITH d AS (
 SELECT symbol,trade_date,
 max(close) FILTER (WHERE bar_time::time='14:05') AS p1405,
 min(low) FILTER (WHERE bar_time::time>='14:05' AND bar_time::time<='15:00') AS low_after,
 min(low) FILTER (WHERE bar_time::time>'14:05' AND bar_time::time<='15:00') AS low_strict,
 min(low) FILTER (WHERE bar_time::time<'14:05') AS low_before
 FROM public.minute_bars WHERE interval_min=1 GROUP BY 1,2
)
SELECT symbol,count(*) n,
 count(*) FILTER(WHERE low_after<low_strict) affected_days,
 round(avg(greatest(0,(p1405-low_after)/nullif(p1405,0))*100)::numeric,4) avg_mae_inclusive_pct,
 round(avg(greatest(0,(p1405-low_strict)/nullif(p1405,0))*100)::numeric,4) avg_mae_strict_pct
FROM d GROUP BY symbol ORDER BY symbol;
```

## Result
Each of 15 symbols has 43 observations, 645 symbol-days total. 14:05 minute low is strictly below every later minute low on 29 symbol-days (sum of affected_days), with 511220 zero. Nevertheless, **mean nonnegative same-day MAE rounded to four decimal percentage points is identical** under inclusive (>=14:05) and strict (>14:05) definitions for all 15 symbols. This is expected if the 14:05 low is not below the 14:05 *close* reference, or differences are too small for reported precision; do not infer identical individual labels without an exact paired-difference check.

Representative inclusive / strict mean percentages: 501018 0.6033/0.6033; 159981 0.3045/0.3045; 513100 0.2113/0.2113; 511220 0.0295/0.0295.

## Interpretation and limitations
This check isolates whether including the entry-minute low changes the **same-day** post-entry downside label. It does not prove that 14:05 close is a fillable price, that the 14:05 minute was available at execution, or that the future five-day label is unaffected. OHLC timestamps may denote minute start/end, and low within the minute can precede its close. For conservative PIT treatment, explicitly define execution at minute close and count only later bars, subject to exchange timestamp validation. No production rule changes. The principal research bottlenecks remain PIT premium, historical frozen route, all-exposure-day OOS ablations and calibrated continuous exit.
