-- Exploratory robustness check, NOT a non-overlapping independent-event estimator.
-- Deterministic every-fifth qualifying event per ETF, rather than all events.
-- Event rank is calculated after filtering for >=2% down days.
-- The spacing between selected event dates is NOT guaranteed to be >=5 sessions.
-- This is only a thinning sensitivity test; do NOT use ordinary binomial SE as valid CI.
WITH x AS (
 SELECT symbol,date,close,open,low,amount,
 lag(close) over w c1,lag(close,5) over w c5,
 avg(amount) over (partition by symbol order by date rows between 20 preceding and 1 preceding) a20,
 count(amount) over (partition by symbol order by date rows between 20 preceding and 1 preceding) n20,
 lead(open,1) over w o1,
 lead(low,1) over w l1,lead(low,2) over w l2,lead(low,3) over w l3,
 lead(low,4) over w l4,lead(low,5) over w l5
 FROM public.daily_bars WINDOW w AS (PARTITION BY symbol ORDER BY date)
), e AS (
 SELECT *,row_number() over(partition by symbol order by date) AS seq
 FROM x WHERE date BETWEEN '2021-01-01' AND '2026-11-10'
 AND n20=20 AND a20>0 AND c5>0 AND c1>0 AND o1>0 AND l5 IS NOT NULL
 AND close/c1-1<=-0.02
), d AS (
 SELECT *,
 CASE WHEN amount/a20<0.8 THEN 'LOW' WHEN amount/a20>1.5 THEN 'HIGH' ELSE 'NORMAL' END grp,
 CASE WHEN least(l1,l2,l3,l4,l5)/o1-1<=-0.05 THEN 1 ELSE 0 END y,
 extract(year from date)::int yr
 FROM e
), keep AS (
 SELECT *,row_number() over(partition by symbol order by date) event_rank
 FROM d WHERE grp IN ('LOW','HIGH')
)
SELECT CASE WHEN yr<=2024 THEN '2021-24' ELSE '2025-26' END period,
 grp,count(*) n,round(avg(y)::numeric*100,2) risk_pct
FROM keep WHERE event_rank%5=1
GROUP BY 1,2 ORDER BY 1,2;
