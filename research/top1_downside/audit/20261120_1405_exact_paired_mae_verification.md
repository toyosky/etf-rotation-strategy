# 2026-11-20 exact paired 14:05 boundary MAE verification

Continuation of `20261120_1405_minute_boundary_sensitivity.md`. Read-only SQL executed against Supabase project `gsyziuzezmmnvgdoazkg`, `public.minute_bars`.

## Executed SQL

```sql
WITH d AS (
 SELECT symbol,trade_date,
 max(close) FILTER(WHERE bar_time::time='14:05') p1405,
 min(low) FILTER(WHERE bar_time::time>='14:05' AND bar_time::time<='15:00') low_in,
 min(low) FILTER(WHERE bar_time::time>'14:05' AND bar_time::time<='15:00') low_out
 FROM public.minute_bars WHERE interval_min=1 GROUP BY 1,2
)
SELECT count(*) n,
 count(*) FILTER(WHERE low_in<low_out) low_diff,
 count(*) FILTER(WHERE greatest(0,(p1405-low_in)/nullif(p1405,0)) >
 greatest(0,(p1405-low_out)/nullif(p1405,0))+1e-12) mae_diff,
 max(greatest(0,(p1405-low_in)/nullif(p1405,0))-
 greatest(0,(p1405-low_out)/nullif(p1405,0))) max_mae_diff,
 avg(greatest(0,(p1405-low_in)/nullif(p1405,0))-
 greatest(0,(p1405-low_out)/nullif(p1405,0))) avg_mae_diff
FROM d;
```

## Actual result

`n=645; low_diff=29; mae_diff=0; max_mae_diff=0; avg_mae_diff=0`.

Thus the earlier four-decimal equality was not a rounding artefact: **all 645 nonnegative same-day MAE labels are exactly identical** when using the 14:05 minute close as reference, whether including or excluding that minute's low. The 29 cases where the entry-minute low is lower than all subsequent lows do not produce a strictly positive additional loss relative to the 14:05 close. This is a precise paired test, not evidence that the 14:05 minute close is executable.

## Boundaries

This finding is limited to same-day low up to 15:00, 15 symbols and 43 sessions in September-November 2026. It is not a test of the full future-five-day MAE, historical Top1 route, PIT premium, or OOS risk forecast. Prior 5-day entry-price and pre-entry-low differences remain material. Keep minute timestamp/fill semantics unresolved; do not alter production trading rules.

CI status for previous commit `9fcc7f23`: no PR-triggered workflow runs returned by GitHub connector at audit time; no CI pass claim.
