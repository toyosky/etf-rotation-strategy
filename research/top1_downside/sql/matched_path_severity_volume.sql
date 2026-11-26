-- Exploration 5: volume association after joint matching on symbol, year, recent path and signal-day severity.
-- NOT a Top1 holding study, not OOS, not causal, not a trading signal.
-- Group size >=2 per side is deliberately permissive; tiny strata are a severe limitation.
WITH p AS (
 SELECT symbol,date,close,low,amount,
 LAG(close) OVER w c1,LAG(close,5) OVER w c5,
 AVG(amount) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) a20,
 COUNT(amount) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) n20,
 LEAD(low,1) OVER w l1,LEAD(low,2) OVER w l2,LEAD(low,3) OVER w l3,LEAD(low,4) OVER w l4,LEAD(low,5) OVER w l5
 FROM public.daily_bars WINDOW w AS (PARTITION BY symbol ORDER BY date)
),ev AS (
 SELECT symbol,extract(year from date)::int yr,
 CASE WHEN close/c5-1<=-.03 THEN 'prior5_down3' ELSE 'prior5_other' END path,
 CASE WHEN close/c1-1<=-.04 THEN 'down4plus' ELSE 'down2to4' END severity,
 CASE WHEN amount/a20<.8 THEN 'low' ELSE 'high' END vol,
 (LEAST(l1,l2,l3,l4,l5)/close-1<=-.05)::int hit
 FROM p WHERE date BETWEEN '2021-01-01' AND '2026-11-10'
 AND n20=20 AND a20>0 AND l5 IS NOT NULL AND c5>0 AND close/c1-1<=-.02
 AND (amount/a20<.8 OR amount/a20>1.5)
),strata AS (
 SELECT symbol,yr,path,severity,
 COUNT(*) FILTER(WHERE vol='low') nl,COUNT(*) FILTER(WHERE vol='high') nh,
 AVG(hit) FILTER(WHERE vol='low') pl,AVG(hit) FILTER(WHERE vol='high') ph
 FROM ev GROUP BY 1,2,3,4
 HAVING COUNT(*) FILTER(WHERE vol='low')>=2 AND COUNT(*) FILTER(WHERE vol='high')>=2
)
SELECT CASE WHEN yr<=2024 THEN '2021-24' ELSE '2025-26' END period,
 COUNT(*) strata,SUM(nl) nlow,SUM(nh) nhigh,
 ROUND((SUM(nl*pl)/SUM(nl)*100)::numeric,2) low_rate,
 ROUND((SUM(nh*ph)/SUM(nh)*100)::numeric,2) high_rate,
 ROUND((SUM(LEAST(nl,nh)*(pl-ph))/SUM(LEAST(nl,nh))*100)::numeric,2) matched_diff_pp
FROM strata GROUP BY 1 ORDER BY 1;
