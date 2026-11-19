WITH d AS (
SELECT symbol,date,close,open,low,amount,
lag(close) OVER w c1,lag(close,5) OVER w c5,
avg(amount) OVER(PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) a20,
count(amount) OVER(PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) n20,
lead(open,1) OVER w o1,lead(low,1) OVER w l1,lead(low,2) OVER w l2,
lead(low,3) OVER w l3,lead(low,4) OVER w l4,lead(low,5) OVER w l5
FROM public.daily_bars WINDOW w AS (PARTITION BY symbol ORDER BY date)),
e AS (
SELECT symbol,date,close/c1-1 r1,close/c5-1 r5,amount/a20 ar,
LEAST(l1,l2,l3,l4,l5)/NULLIF(o1,0)-1 mae
FROM d WHERE date BETWEEN '2021-01-01' AND '2026-11-10'
AND n20=20 AND a20>0 AND o1>0 AND l5 IS NOT NULL AND close/c1-1<=-.02)
SELECT extract(year from date)::int yr,
CASE WHEN r5<=-.03 THEN 'prior_down' ELSE 'prior_notdown' END path,
CASE WHEN ar<.8 THEN 'low' WHEN ar>1.5 THEN 'high' ELSE 'mid' END amount_group,
count(*) n,
round(100*avg((mae<=-.05)::int)::numeric,2) risk5_pct,
round(100*avg(mae)::numeric,2) mean_mae_pct
FROM e GROUP BY 1,2,3 ORDER BY 1,2,3;
