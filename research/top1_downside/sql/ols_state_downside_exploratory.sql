-- Exploratory weighted OLS vs future 5-day adverse excursion, NOT actual held Top1.
-- Universe: all 19 symbols present in public.daily_bars, 2021-01-01..2026-11-10.
-- Signal: daily return <= -2%; 26 trailing observations incl. signal date.
-- Weighted log-price OLS: weight exp(-ln(2)*age/10), age 0 at t.
-- Outcome: min(low t+1..t+5)/open(t+1)-1; adjusted-price proxy, NOT 14:05 fill.
-- Includes overlapping events, not PIT-premium gated, not walk-forward.
WITH base AS (
 SELECT symbol,date,open,low,close,LAG(close) OVER w AS pc,
 LEAD(open) OVER w AS op1,LEAD(low,1) OVER w AS l1,
 LEAD(low,2) OVER w AS l2,LEAD(low,3) OVER w AS l3,
 LEAD(low,4) OVER w AS l4,LEAD(low,5) OVER w AS l5
 FROM public.daily_bars
 WINDOW w AS(PARTITION BY symbol ORDER BY date)
), events AS (
 SELECT symbol,date,close,op1,LEAST(l1,l2,l3,l4,l5)/NULLIF(op1,0)-1 AS mae5
 FROM base WHERE date BETWEEN '2021-01-01' AND '2026-11-10'
 AND pc>0 AND close/pc-1<=-.02 AND op1>0 AND l5>0
), fitted AS (
 SELECT e.*, fit.beta,fit.r2,fit.n
 FROM events e CROSS JOIN LATERAL (
  WITH seq AS (
   SELECT LN(d.close) AS y, ROW_NUMBER() OVER (ORDER BY d.date ASC)-1 AS x,
   COUNT(*) OVER () AS n
   FROM (SELECT date,close FROM public.daily_bars WHERE symbol=e.symbol AND date<=e.date ORDER BY date DESC LIMIT 26) d
  ), sums AS (
   SELECT COUNT(*) AS n, SUM(w) sw,SUM(w*x) sx,SUM(w*y) sy,
   SUM(w*x*x) sxx,SUM(w*y*y) syy,SUM(w*x*y) sxy
   FROM (SELECT x,y,EXP(-LN(2)*(25-x)/10.0) AS w FROM seq) z
  )
  SELECT n,(sxy-sx*sy/sw)/NULLIF(sxx-sx*sx/sw,0) beta,
  POWER(sxy-sx*sy/sw,2)/NULLIF((sxx-sx*sx/sw)*(syy-sy*sy/sw),0) r2
  FROM sums
 ) fit WHERE fit.n=26
)
SELECT CASE WHEN date<'2025-01-01' THEN '2021-24' ELSE '2025-26' END period,
 CASE WHEN beta<=0 THEN 'beta_nonpositive' WHEN r2<.5 THEN 'beta_pos_r2_low' ELSE 'beta_pos_r2_high' END ols_state,
 COUNT(*) n,ROUND(AVG(beta)::numeric,5) mean_beta,
 ROUND(AVG(r2)::numeric,3) mean_r2,
 ROUND(AVG(mae5)::numeric*100,2) mean_mae5_pct,
 ROUND(AVG((mae5<=-.05)::int)::numeric*100,2) p_mae5_5pct
FROM fitted GROUP BY 1,2 ORDER BY 1,2;
