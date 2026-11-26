# 2026-11-21 gap-adjacent price discontinuity diagnostic

Read-only Supabase public.daily_bars query, 2021-01-01 through 2026-11-19. Follows 20261121_calendar_gap_label_exposure.md. **These are vendor-adjusted daily prices, not independently verified executable quotes or evidence of suspension.** Gap-open percentage = (first observed open after missing session / last observed close before missing session - 1)*100. The percentage crosses a missing market session and therefore is not a one-day return. Corporate actions/adjustment discontinuity and vendor errors are not excluded.

| Symbol | Missing session | Prior close | Next open | Gap-open % |
|---|---|---:|---:|---:|
| 513100 | 2022-01-13 | 5.19 | 5.05 | -2.697 |
| 513500 | 2022-03-29 | 2.74 | 2.79 | +1.825 |
| 159529 | 2025-01-10 | 1.90 | 1.74 | -8.421 |
| 159529 | 2025-01-17 | 1.76 | 1.82 | +3.409 |
| 159529 | 2025-01-22 | 1.91 | 1.97 | +3.141 |
| 159529 | 2025-01-24 | 1.95 | 1.95 | 0.000 |
| 161226 | 2026-01-22 | 3.92 | 3.92 | 0.000 |
| 161226 | 2026-01-30 | 5.25 | 4.72 | -10.095 |
| 501018 | 2026-01-30 | 1.55 | 1.40 | -9.677 |
| 501018 | 2026-03-24 | 2.56 | 2.38 | -7.031 |

**Key finding:** Four gap-adjacent observations have next-open discontinuity below -7% (159529 Jan 10 2025; 161226 Jan 30 2026; 501018 Jan 30 and Mar 24 2026). The Jan 30 simultaneous 501018/161226 gaps warrant exchange halt-notice and raw vendor verification, not inferred tradability. The observed next-open values are on the following available session, not on the missing day. Do not impute missing lows or mark these as independently observed one-day drawdowns.

Reproducible read-only SQL:

```sql
WITH cal AS (SELECT DISTINCT date FROM public.daily_bars WHERE date BETWEEN '2021-01-01' AND '2026-11-19'),
spans AS (SELECT symbol,min(date) lo,max(date) hi FROM public.daily_bars GROUP BY symbol),
gaps AS (SELECT s.symbol,c.date FROM spans s JOIN cal c ON c.date BETWEEN s.lo AND s.hi LEFT JOIN public.daily_bars d ON d.symbol=s.symbol AND d.date=c.date WHERE d.symbol IS NULL)
SELECT g.symbol,g.date missing_date,p.date prior_date,p.close prior_close,n.date next_date,n.open next_open,n.close next_close,
round(((n.open/p.close-1)*100)::numeric,3) gap_open_pct
FROM gaps g
LEFT JOIN LATERAL (SELECT date,close FROM public.daily_bars WHERE symbol=g.symbol AND date<g.date ORDER BY date DESC LIMIT 1) p ON true
LEFT JOIN LATERAL (SELECT date,open,close FROM public.daily_bars WHERE symbol=g.symbol AND date>g.date ORDER BY date LIMIT 1) n ON true
ORDER BY g.date,g.symbol;
```

**Method gate:** keep the previously identified 42 five-session and 72 ten-session contaminated instrument-date windows flagged/censored pending official exchange halt checks and alternate raw prices. Do not count adjacent changes as future-low realizations during a missing day. Evaluate same-sample OOS ablations only after calendar validity and frozen-route PIT gates. No model fitting, portfolio PnL, production changes, or claims of real Top1 holdings in this diagnostic.
