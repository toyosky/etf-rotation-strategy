-- 2026-11-20 exploratory withdrawal pilot. Executed read-only on Supabase public.daily_bars.
-- Signal: t's daily log-return <= ln(0.98); features known at t close.
-- Baseline: FULL 100% exposure. Rules are triggered only after a down event.
-- Fixed 30% withdrawal at t+1 reference open; volatility-only 30% when past vol20 >=3%.
-- Dynamic withdrawal: 30% if exactly one of (vol20/vol120>=1.3, shock>=2),
--                     60% if both, 0% otherwise. Shock=-r_t/lagged vol20.
-- Flat cash on withdrawn sleeve; restore after t+5 close; 0.2% round-trip
-- assumed friction PER WITHDRAWN NOTIONAL for sensitivity, not an observed broker charge.
-- Counterfactual five-session terminal return close[t+5]/open[t+1]-1.
-- Five-session future-low adverse excursion low[t+1..t+5]/open[t+1]-1.
-- Greedy skip next 5 trading rows for same symbol and era; other ETFs may co-move.
-- NOT actual held Top1, NOT verified 14:05 execution, NOT time-purged OOS.
WITH RECURSIVE p AS (
 SELECT symbol,date,open,low,close,
 ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY date) idx,
 LN(close/NULLIF(LAG(close) OVER(PARTITION BY symbol ORDER BY date),0)) r
 FROM public.daily_bars WHERE close>0 AND open>0 AND low>0
),f AS (
 SELECT *,COUNT(r) OVER w120 n120,STDDEV_SAMP(r) OVER w120 vol120,
 STDDEV_SAMP(r) OVER w20 vol20,LEAD(open,1) OVER w op1,
 LEAD(close,5) OVER w cl5,LEAD(date,5) OVER w d5,
 MIN(low) OVER(PARTITION BY symbol ORDER BY date ROWS BETWEEN 1 FOLLOWING AND 5 FOLLOWING) low5
 FROM p WINDOW w AS(PARTITION BY symbol ORDER BY date),
 w120 AS(PARTITION BY symbol ORDER BY date ROWS BETWEEN 120 PRECEDING AND 1 PRECEDING),
 w20 AS(PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING)
),c AS (
 SELECT *, CASE WHEN date<'2025-01-01' THEN '2021-24' ELSE '2025-26' END era,
 CASE WHEN symbol='501018' THEN 'oil_501018'
 WHEN symbol='159981' THEN 'chemical_159981'
 WHEN symbol='513100' THEN 'nasdaq_513100' ELSE 'others' END bucket,
 -r/vol20 shock,vol20/vol120 expansion,
 cl5/op1-1 ret5,low5/op1-1 mae5
 FROM f WHERE date BETWEEN '2021-01-01' AND '2026-11-05' AND n120=120
 AND vol20>0 AND vol120>0 AND op1>0 AND d5 IS NOT NULL AND r<=LN(0.98)
),pick AS(
 SELECT symbol,era,idx FROM
 (SELECT DISTINCT ON(symbol,era) symbol,era,idx FROM c ORDER BY symbol,era,idx)s
 UNION ALL
 SELECT b.symbol,b.era,z.idx FROM pick b
 JOIN LATERAL
 (SELECT idx FROM c WHERE symbol=b.symbol AND era=b.era AND idx>b.idx+5 ORDER BY idx LIMIT 1)z ON true
),e AS(
 SELECT c.*,
 CASE WHEN c.vol20>=0.03 THEN 0.30 ELSE 0 END vol_exit,
 CASE WHEN c.expansion>=1.3 AND c.shock>=2 THEN 0.60
 WHEN c.expansion>=1.3 OR c.shock>=2 THEN 0.30 ELSE 0 END dyn_exit
 FROM c JOIN pick b ON b.symbol=c.symbol AND b.era=c.era AND b.idx=c.idx
)
SELECT era, COUNT(*) n, COUNT(DISTINCT symbol) funds,
 COUNT(*) FILTER(WHERE dyn_exit>0) risk_triggers,
 ROUND((100*AVG(ret5))::numeric,3) full_return,
 ROUND((100*AVG(0.7*ret5))::numeric,3) fixed30_return,
 ROUND((100*AVG(0.7*ret5-0.3*0.002))::numeric,3) fixed30_net20bp,
 ROUND((100*AVG((1-vol_exit)*ret5))::numeric,3) vol_only_return,
 ROUND((100*AVG((1-dyn_exit)*ret5))::numeric,3) dynamic_return,
 ROUND((100*AVG((1-dyn_exit)*ret5-dyn_exit*0.002))::numeric,3) dynamic_net20bp,
 ROUND((100*AVG(dyn_exit))::numeric,2) average_withdraw,
 ROUND((100*AVG(ret5) FILTER(WHERE dyn_exit>0))::numeric,3) triggered_asset_ret5,
 ROUND((100*AVG(ret5) FILTER(WHERE dyn_exit=0))::numeric,3) untriggered_asset_ret5,
 ROUND((100*AVG(mae5))::numeric,3) avg_mae5,
 ROUND((100*AVG((1-dyn_exit)*mae5))::numeric,3) avg_dyn_scaled_mae5
FROM e GROUP BY era ORDER BY era;
