-- Exploratory historical volatility conditioning; no trained model, no actual held Top1.
-- Prior 20 trading sessions' realized log-return stddev, excluding signal day t.
-- Events: signal-day close <= -2% vs prior close; future five daily lows / t+1 open.
-- HFQ adjusted OHLC and next-open proxy are NOT exact executable 14:05 fills.
-- Per-symbol-year every-fifth event thinning is NOT a non-overlap guarantee.
WITH x AS (
 SELECT symbol,date,close,low,open,
 lag(close) OVER w AS c1,
 stddev_samp(ln(close/lag_close)) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS vol20,
 lead(open,1) OVER w AS entry,
 lead(low,1) OVER w AS l1,lead(low,2) OVER w AS l2,lead(low,3) OVER w AS l3,lead(low,4) OVER w AS l4,lead(low,5) OVER w AS l5
 FROM (SELECT *,lag(close) OVER (PARTITION BY symbol ORDER BY date) lag_close FROM public.daily_bars) z
 WINDOW w AS (PARTITION BY symbol ORDER BY date)
), s AS (
 SELECT symbol,date,vol20,least(l1,l2,l3,l4,l5)/entry-1 AS mae,
 row_number() OVER(PARTITION BY symbol,date_trunc('year',date) ORDER BY date) AS k
 FROM x WHERE date BETWEEN '2021-01-01' AND '2026-11-10'
 AND c1>0 AND close/c1-1<=-.02 AND vol20 IS NOT NULL AND entry>0 AND l5>0
)
SELECT CASE WHEN date<'2025-01-01' THEN '2021-24' ELSE '2025-26' END period,
 CASE WHEN vol20<.015 THEN 'low_lt1.5pct' WHEN vol20<.03 THEN 'mid_1.5to3pct' ELSE 'high_ge3pct' END vol_bin,
 count(*) n, round(avg(mae)::numeric*100,2) mean_mae_pct,
 round(avg((mae<=-.05)::int)::numeric*100,2) deep5_pct,
 count(*) FILTER (WHERE k%5=1) thin_n,
 round(avg((mae<=-.05)::int) FILTER (WHERE k%5=1)::numeric*100,2) thin_deep5_pct
FROM s GROUP BY 1,2 ORDER BY 1,2;
