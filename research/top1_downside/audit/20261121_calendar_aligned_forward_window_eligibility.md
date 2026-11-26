# Calendar-aligned forward-window eligibility (2026-11-21)

Read-only Supabase query against public.daily_bars, 2021-01-01 through 2026-11-20. This is **instrument-date coverage**, not Top1 holdings or OOS model results.

## Executed result

| Forward horizon (market sessions) | Full-horizon candidate windows | All future sessions present | Missing at least one session |
|---|---:|---:|---:|
| 3 | 21,185 | 21,158 | 27 |
| 5 | 21,147 | 21,105 | 42 |
| 10 | 21,052 | 20,980 | 72 |

The 42 and 72 figures reproduce earlier gap-exposure counts independently; 27 is newly computed for horizon 3. Windows near the dataset end without a complete *market-calendar* horizon are excluded from these denominators. Windows with a missing bar are flagged, **not imputed**. These are not independent events and cannot be used to claim a real executable Top1 sample. The market calendar is the union of dates present for the 19 instruments, not a separately validated exchange calendar. It cannot establish suspension status.

## Executed SQL

```sql
WITH cal AS (
 SELECT date,row_number() OVER (ORDER BY date) rn
 FROM (SELECT DISTINCT date FROM public.daily_bars
       WHERE date BETWEEN '2021-01-01' AND '2026-11-20') x
), bars AS (
 SELECT b.symbol,b.date,c.rn
 FROM public.daily_bars b JOIN cal c USING(date)
 WHERE b.date BETWEEN '2021-01-01' AND '2026-11-20'
), windows AS (
 SELECT b.symbol,b.date,h.horizon,
        count(f.date) observed,count(*) expected
 FROM bars b
 CROSS JOIN (VALUES (3),(5),(10)) h(horizon)
 JOIN cal c ON c.rn>b.rn AND c.rn<=b.rn+h.horizon
 LEFT JOIN bars f ON f.symbol=b.symbol AND f.date=c.date
 GROUP BY 1,2,3
 HAVING count(*)=h.horizon
)
SELECT horizon,count(*) total_windows,
 count(*) FILTER (WHERE observed=expected) complete_windows,
 count(*) FILTER (WHERE observed<expected) gap_windows
FROM windows GROUP BY horizon ORDER BY horizon;
```

## Next implementation gate

Use this market-session alignment in the feature/label builder and enforce exact future-session joins, rather than `LEAD(...,5)` over an individual instrument's rows. The forward MAE still needs next-session **executable** entry prices and valid future lows; missing or suspected suspended dates must be flagged, not converted to continuous returns. Validate listing dates, trading halts, unadjusted-vs-adjusted price consistency, PIT premium and the frozen strategy route before calling any such labels executable. Freeze feature sets, purged walk-forward folds, and all comparison-model hyperparameters before evaluating OOS. No production edits.
