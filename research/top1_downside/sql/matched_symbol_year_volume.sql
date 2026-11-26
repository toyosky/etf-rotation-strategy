-- Exploratory matched ETF-year composition test; NOT OOS, NOT actual held Top1, dependent events.
WITH p AS (
 SELECT symbol,date,close,low,amount,
 lag(close) OVER w c1,lag(close,5) OVER w c5,
 avg(amount) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) a20,
 count(*) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) n20,
 lead(low,1) OVER w l1,lead(low,2) OVER w l2,lead(low,3) OVER w l3,lead(low,4) OVER w l4,lead(low,5) OVER w l5
 FROM public.daily_bars WINDOW w AS (PARTITION BY symbol ORDER BY date)
),s AS (
 SELECT symbol,extract(year from date)::int yr,date,close/c1-1 r1,close/c5-1 r5,
 amount/nullif(a20,0) vr,(least(l1,l2,l3,l4,l5)/close-1<=-.05)::int y
 FROM p WHERE date BETWEEN '2021-01-01' AND '2026-11-10'
 AND n20=20 AND a20>0 AND l5 IS NOT NULL AND close/c1-1<=-.02
),g AS (
 SELECT symbol,yr,count(*) n,
 count(*) FILTER(WHERE vr<.8) nl,count(*) FILTER(WHERE vr>1.5) nh,
 avg(y::numeric) FILTER(WHERE vr<.8) pl,
 avg(y::numeric) FILTER(WHERE vr>1.5) ph
 FROM s GROUP BY 1,2
),matched AS (SELECT * FROM g WHERE nl>=3 AND nh>=3)
SELECT CASE WHEN yr<=2024 THEN '2021-24' ELSE '2025-26' END period,
 count(*) strata,sum(nl) low_events,sum(nh) high_events,
 round((sum(nl*pl)/sum(nl)*100)::numeric,2) pooled_low_pct,
 round((sum(nh*ph)/sum(nh)*100)::numeric,2) pooled_high_pct,
 round(avg((pl-ph)*100)::numeric,2) avg_within_symbol_year_diff_pp,
 round((sum(least(nl,nh)*(pl-ph))/sum(least(nl,nh))*100)::numeric,2) matched_weighted_diff_pp
FROM matched GROUP BY 1 ORDER BY 1;
