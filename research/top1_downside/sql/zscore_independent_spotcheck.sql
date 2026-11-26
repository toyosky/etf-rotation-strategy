-- Independent audit for two Z-score features used in the 2021–2026 continuous withdrawal research.
-- Full 60 prior completed return observations; no use of future returns in features.
-- Weighted log-OLS 26 close prices incl signal date, with polyfit effective squared weights.
-- Safe to replace last WHERE to cover additional PIT signal dates. Read-only SQL.
WITH base AS (
 SELECT symbol,date,close,
 LN(close / NULLIF(LAG(close) OVER (PARTITION BY symbol ORDER BY date),0)) AS r
 FROM public.daily_bars
 WHERE symbol IN ('159981','512800')
), f AS (
 SELECT *,
 AVG(r) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING) avg60,
 STDDEV_SAMP(r) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING) std60
 FROM base
)
SELECT p.symbol,p.date,
 ROUND(((p.r-p.avg60)/NULLIF(p.std60,0))::numeric,5) AS z_return60,
 ROUND(((LN(p.close)-fit.alpha-fit.beta*25)/NULLIF(fit.rmse,0))::numeric,5) AS z_residual26,
 ROUND(fit.beta::numeric,6) AS beta
FROM f p
CROSS JOIN LATERAL (
 WITH q AS (
  SELECT ROW_NUMBER() OVER (ORDER BY u.date ASC)-1 AS x, LN(u.close) AS y
  FROM (SELECT date,close FROM public.daily_bars
   WHERE symbol=p.symbol AND date<=p.date ORDER BY date DESC LIMIT 26) u
 ), w AS (
  SELECT x,y,EXP(-2*LN(2)*(25-x)/10) wt FROM q
 ), sums AS (
  SELECT COUNT(*) n, SUM(wt) sw, SUM(wt*x) sx, SUM(wt*y) sy,
   SUM(wt*x*x) sxx,SUM(wt*x*y) sxy,SUM(wt*y*y) syy FROM w
 ), fitted AS (
  SELECT n,sw,sx,sy, (sxy-sx*sy/sw)/NULLIF((sxx-sx*sx/sw),0) beta,
   (syy-sy*sy/sw)-POWER(sxy-sx*sy/sw,2)/NULLIF((sxx-sx*sx/sw),0) sse FROM sums
 )
 SELECT beta,(sy-beta*sx)/sw alpha, SQRT(GREATEST(0,sse/sw)) rmse FROM fitted WHERE n=26
) fit
WHERE (p.symbol='159981' AND p.date='2026-09-17')
   OR (p.symbol='512800' AND p.date='2026-08-04')
ORDER BY p.symbol,p.date;
-- Expected confirmed independently against JS:
-- 159981 2026-09-17 Zreturn60 -1.64695, Zresidual26 -1.28982
-- 512800 2026-08-04 Zreturn60 -1.99932, Zresidual26 -1.88997
