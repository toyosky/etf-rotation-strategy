-- Standardized 5-day future downside: diagnostic, not OOS or executable Top1.
-- Same event universe as volatility20_nextopen_mae.sql; all signal days t with return <= -2%.
-- vol20 is previous 20 completed trading sessions' log-return stddev, excludes t.
-- MAE uses adjusted t+1 open and adjusted lows t+1..t+5; actual strategy buys at 14:05.
-- Labels overlap and may reflect adjusted-price distortions; no independent-event inference.
WITH z AS (
 SELECT *, lag(close) OVER (PARTITION BY symbol ORDER BY date) lag_close
 FROM public.daily_bars
), x AS (
 SELECT symbol,date,close,open,low,
 lag(close) OVER w c1,
 stddev_samp(ln(close/lag_close)) OVER
   (PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) vol20,
 lead(open,1) OVER w entry,
 lead(low,1) OVER w l1, lead(low,2) OVER w l2, lead(low,3) OVER w l3,
 lead(low,4) OVER w l4, lead(low,5) OVER w l5
 FROM z WINDOW w AS (PARTITION BY symbol ORDER BY date)
), s AS (
 SELECT symbol,date,vol20,least(l1,l2,l3,l4,l5)/entry-1 mae
 FROM x
 WHERE date BETWEEN '2021-01-01' AND '2026-11-10'
 AND c1>0 AND close/c1-1<=-.02 AND vol20>0 AND entry>0 AND l5>0
)
SELECT CASE WHEN date<'2025-01-01' THEN '2021-24' ELSE '2025-26' END period,
 CASE WHEN vol20<.015 THEN 'low' WHEN vol20<.03 THEN 'mid' ELSE 'high' END vol_bin,
 count(*) n,
 round(avg(mae)::numeric*100,2) mean_mae_pct,
 round(avg((mae/vol20)::numeric),2) mean_mae_in_vol_units,
 round(avg((mae<=-2*vol20)::int)::numeric*100,2) p_2vol,
 round(avg((mae<=-3*vol20)::int)::numeric*100,2) p_3vol,
 round(avg((mae<=-.05)::int)::numeric*100,2) p_5pct
FROM s GROUP BY 1,2 ORDER BY 1,2;
