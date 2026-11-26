-- Next-open MAE sensitivity screen, 2026-11-20.
-- Signal t: close-to-close drop <= -2%; previous 20-session mean amount.
-- Alternative outcome: min low(t+1..t+5) / open(t+1) - 1.
-- NOT a true executable Top1 return: 14:05 intraday execution, premium and V1/Void are absent.
-- Events overlap; asset membership, point-in-time adjustments and confounding not resolved.
WITH p AS (
 SELECT symbol,date,open,low,close,amount,
 lag(close) OVER w AS c1, lag(close,5) OVER w AS c5,
 avg(amount) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) a20,
 count(amount) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) ct20,
 lead(open,1) OVER w AS o1,
 lead(low,1) OVER w AS l1,lead(low,2) OVER w AS l2,
 lead(low,3) OVER w AS l3,lead(low,4) OVER w AS l4,lead(low,5) OVER w AS l5
 FROM public.daily_bars WINDOW w AS (PARTITION BY symbol ORDER BY date)
), s AS (
 SELECT symbol,date,amount/nullif(a20,0) ar,
 LEAST(l1,l2,l3,l4,l5)/close-1 close_mae,
 LEAST(l1,l2,l3,l4,l5)/o1-1 open_mae,
 o1/close-1 gap
 FROM p
 WHERE date BETWEEN '2021-01-01' AND '2026-11-10'
 AND ct20=20 AND a20>0 AND c5>0 AND o1>0 AND l5 IS NOT NULL
 AND close/c1-1<=-.02
)
SELECT CASE WHEN date<'2025-01-01' THEN '2021-24' ELSE '2025-26' END period,
 CASE WHEN ar<.8 THEN 'low' WHEN ar<=1.5 THEN 'normal' ELSE 'high' END amount_group,
 count(*) n,
 round(avg(close_mae)::numeric*100,2) close_mae_pct,
 round(avg(open_mae)::numeric*100,2) nextopen_mae_pct,
 round(avg(gap)::numeric*100,2) avg_gap_pct,
 round(avg((close_mae<=-.05)::int)::numeric*100,2) close_p5,
 round(avg((open_mae<=-.05)::int)::numeric*100,2) nextopen_p5
FROM s GROUP BY 1,2 ORDER BY 1,2;
