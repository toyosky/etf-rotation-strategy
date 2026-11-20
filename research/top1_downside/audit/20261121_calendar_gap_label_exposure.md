# Calendar-gap impact on forward MAE labels (2026-11-21)

Read-only Supabase SQL execution; no production changes. Continuation of 20261120_daily_bar_internal_calendar_gaps.md.

Reference calendar is the union of observed daily_bars dates during 2021-01-01 through 2026-11-19. For each observed symbol-day t, flag if at least one missing symbol calendar date lies within the next H market sessions. Count each affected symbol-day once per horizon.

| Symbol | 5-session affected | 10-session affected |
|---|---:|---:|
| 159529 | 12 | 17 |
| 161226 | 10 | 15 |
| 501018 | 10 | 20 |
| 513100 | 5 | 10 |
| 513500 | 5 | 10 |
| TOTAL | 42 | 72 |

These are observed instrument×signal-day windows, not independent events, nor verified historical Top1 positions. The 10 known missing dates may be trading halts or vendor omissions. No imputation. This audit does not measure MAE changes, model skill, or portfolio performance.

Reproducible query:

```sql
WITH cal AS (SELECT date,ROW_NUMBER() OVER(ORDER BY date) rn FROM (SELECT DISTINCT date FROM public.daily_bars WHERE date BETWEEN '2021-01-01' AND '2026-11-19') t),
b AS (SELECT symbol,MIN(date) lo,MAX(date) hi FROM public.daily_bars GROUP BY symbol),
gaps AS (SELECT b.symbol,c.rn,c.date FROM b JOIN cal c ON c.date BETWEEN b.lo AND b.hi LEFT JOIN public.daily_bars d ON d.symbol=b.symbol AND d.date=c.date WHERE d.symbol IS NULL),
impacted AS (SELECT DISTINCT g.symbol,c.date,c.rn FROM gaps g JOIN cal c ON c.rn BETWEEN g.rn-10 AND g.rn-1 JOIN public.daily_bars d ON d.symbol=g.symbol AND d.date=c.date)
SELECT symbol,COUNT(DISTINCT date) FILTER (WHERE EXISTS(SELECT 1 FROM gaps g WHERE g.symbol=impacted.symbol AND g.rn BETWEEN impacted.rn+1 AND impacted.rn+5)) impacted_5day_signal_dates,COUNT(DISTINCT date) impacted_10day_signal_dates FROM impacted GROUP BY symbol ORDER BY symbol;
```

Next: adjudicate missing dates using exchange halt notices and alternative vendor data. Use common market-session indexing, flag and censor unresolved future-low labels, preserve affected counts by year and ETF, then rerun identical-sample purged OOS feature ablations. In particular 501018 and 161226 both miss 2026-01-30, making shared event dependence important. Existing PIT premium limitations and frozen-route reconstruction still block executable Top1 conclusions. No evidence yet for continuous withdrawal deployment.
