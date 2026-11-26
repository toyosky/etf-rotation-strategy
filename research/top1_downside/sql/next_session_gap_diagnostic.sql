-- Down-day conditional next-session adjusted open/close gap; diagnostic ONLY.
-- Historical HFQ prices may create synthetic gaps at corporate actions.
-- Neither gap nor next-session open is available at signal-date close; never use as X_t.
WITH x AS (
 SELECT symbol,date,close,open,
 lag(close) OVER(PARTITION BY symbol ORDER BY date) prev_close,
 lead(open) OVER(PARTITION BY symbol ORDER BY date) next_open
 FROM public.daily_bars
),s AS (
 SELECT date,symbol,next_open/close-1 gap
 FROM x WHERE date BETWEEN '2021-01-01' AND '2026-11-10'
 AND prev_close>0 AND close/prev_close-1<=-0.02 AND next_open>0
)
SELECT EXTRACT(YEAR FROM date)::int yr,count(*) events,
 round(100*avg((gap<=-0.03)::int)::numeric,2) next_gap_down3_pct,
 round(100*avg((gap>=0.03)::int)::numeric,2) next_gap_up3_pct,
 round(100*avg(abs(gap))::numeric,3) mean_abs_gap_pct,
 round(100*min(gap)::numeric,2) worst_gap_pct,
 round(100*max(gap)::numeric,2) best_gap_pct
FROM s GROUP BY 1 ORDER BY 1;
