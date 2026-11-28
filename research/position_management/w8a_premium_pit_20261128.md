# W8a PIT premium audit — 2026-11-28
Read-only Supabase ETF_daily_bars project gsyziuzezmmnvgdoazkg, public fund_premium_history, all symbols. No production changes.
```sql
select case when nav_date<'2021-01-01' then 'pre2021' when nav_date<'2026-01-01' then '2021-25' else '2026' end period,count(*) n,count(*) filter(where pit_safe is true) safe,count(*) filter(where first_seen_at is null) missing_seen,count(*) filter(where (first_seen_at at time zone 'Asia/Shanghai')::date<=nav_date) same_or_earlier,count(*) filter(where premium is not null) premium_n,count(*) filter(where backfilled is true) backfilled,min(nav_date) first_nav,max(nav_date) last_nav,min(first_seen_at) earliest_seen,max(first_seen_at) latest_seen from fund_premium_history group by 1 order by 1
```
Actual returned counts:
| period | n | safe | missing_seen | same_or_earlier | premium_n | backfilled |
|---|---:|---:|---:|---:|---:|---:|
| pre2021 |11648|0|11648|0|11648|11648|
| 2021-25 |17351|0|17351|0|17351|17351|
| 2026 |6745|0|3584|106|6745|6745|
Pre2021 NAV dates 2014-01-02 to 2020-12-31; 2021-25 2021-01-04 to 2025-12-31; 2026 2026-01-05 to 2026-11-27. Only 2026 has observed timestamps, earliest 2026-11-10 06:46:10.110329 UTC, latest 2026-11-27 17:35:35.085056 UTC. Same-day observation is not proof of pre-signal availability. All 35744 rows backfilled, zero PIT-safe; no exact Premium10 reconstruction from this table alone. Do not block daily proxy studies on this. No dynamic replay performed. Next independent work: W8e or W8b if original H-DV/H-MAE specs remain unavailable.