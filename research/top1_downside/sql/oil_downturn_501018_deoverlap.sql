-- 501018 oil LOF case study. Read-only PostgreSQL / Supabase.
-- Signal is daily close <= -2%; all features known as of signal close.
-- Historical HFQ OHLC data, not executable 14:05 fills or PIT-premium-cleared trades.
-- Greedy no-overlap: retain earliest signal and skip the following five trading rows.
-- 2021-24 and 2025-26 restart the selection independently.
WITH RECURSIVE
prices AS (
 SELECT symbol,date,open,high,low,close,
  ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date) AS idx,
  LN(close/NULLIF(LAG(close) OVER (PARTITION BY symbol ORDER BY date),0)) AS r
 FROM public.daily_bars
 WHERE symbol='501018' AND close>0 AND open>0 AND low>0
),f AS (
 SELECT *, COUNT(r) OVER w120 n120,
  STDDEV_SAMP(r) OVER w120 v120,
  STDDEV_SAMP(r) OVER w20 v20,
  LEAD(open,1) OVER w next_open,
  LEAD(close,5) OVER w close5,
  LEAD(date,5) OVER w date5,
  MIN(low) OVER (ORDER BY date ROWS BETWEEN 1 FOLLOWING AND 5 FOLLOWING) low5
 FROM prices
 WINDOW w AS (PARTITION BY symbol ORDER BY date),
 w120 AS (PARTITION BY symbol ORDER BY date ROWS BETWEEN 120 PRECEDING AND 1 PRECEDING),
 w20 AS (PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING)
), candidates AS (
 SELECT CASE WHEN date<'2025-01-01' THEN '2021-24' ELSE '2025-26' END era,
  idx,date,r, v20/v120 AS expansion,-r/v20 AS shock,
  low5/next_open-1 AS mae5,close5/next_open-1 AS ret5
 FROM f
 WHERE date BETWEEN '2021-01-01' AND '2026-11-05'
 AND n120=120 AND date5 IS NOT NULL AND v20>0 AND v120>0
 AND next_open>0 AND r<=LN(0.98)
), picked AS (
 SELECT era,idx FROM (
  SELECT DISTINCT ON (era) era,idx FROM candidates ORDER BY era,idx
 ) seed
 UNION ALL
 SELECT p.era,c.idx
 FROM picked p JOIN LATERAL (
  SELECT idx FROM candidates WHERE era=p.era AND idx>p.idx+5
  ORDER BY idx LIMIT 1
 )c ON true
)
SELECT c.era,
 CASE WHEN c.expansion>=1.3 THEN 'expands>=1.3' ELSE 'stable<1.3' END vol_state,
 CASE WHEN c.shock>=1.5 THEN 'shock>=1.5' ELSE 'shock<1.5' END shock_state,
 COUNT(*) n,
 COUNT(*) FILTER (WHERE c.mae5<=-0.05) deep_n,
 ROUND((100*AVG((c.mae5<=-0.05)::int))::numeric,2) deep_pct,
 COUNT(*) FILTER (WHERE c.ret5>0) win_n,
 ROUND((100*AVG(c.ret5))::numeric,2) avg_ret5_pct,
 ROUND((100*AVG(c.mae5))::numeric,2) avg_mae5_pct
FROM picked p JOIN candidates c ON c.era=p.era AND c.idx=p.idx
GROUP BY 1,2,3 ORDER BY 1,2,3;
