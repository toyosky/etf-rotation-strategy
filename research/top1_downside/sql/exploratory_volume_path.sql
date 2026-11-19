-- Top1 downside project: exploratory non-held ETF down-day screen.
-- READ-ONLY; NOT an executable Top1 event sample, NOT OOS, NOT a position-sizing recommendation.
-- Dataset: public.daily_bars, 19 symbols, adjusted HFQ prices and raw daily turnover amount.
-- Uses strictly prior 20 sessions for mean amount. Includes overlapping forward windows.
WITH p AS (
  SELECT symbol,date,close,low,amount,
    LAG(close) OVER w AS c1,
    LAG(close,5) OVER w AS c5,
    AVG(amount) OVER (
      PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
    ) AS a20,
    COUNT(amount) OVER (
      PARTITION BY symbol ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
    ) AS ct20,
    LEAD(low,1) OVER w AS l1,
    LEAD(low,2) OVER w AS l2,
    LEAD(low,3) OVER w AS l3,
    LEAD(low,4) OVER w AS l4,
    LEAD(low,5) OVER w AS l5
  FROM public.daily_bars
  WINDOW w AS (PARTITION BY symbol ORDER BY date)
),
s AS (
  SELECT symbol,date,
    close/c1-1 AS r1,
    close/c5-1 AS r5,
    amount/NULLIF(a20,0) AS a_ratio,
    LEAST(l1,l2,l3,l4,l5)/close-1 AS fwd_low5
  FROM p
  WHERE date BETWEEN DATE '2021-01-01' AND DATE '2026-11-10'
    AND ct20=20 AND a20>0 AND l5 IS NOT NULL
    AND c5>0 AND close/c1-1<=-0.02
)
SELECT
  CASE WHEN date<DATE '2025-01-01' THEN '2021-24' ELSE '2025-26' END AS period,
  CASE WHEN r5<=-0.03 THEN 'prior5_down3' ELSE 'prior5_notdown3' END AS path,
  CASE WHEN a_ratio<0.8 THEN 'low'
       WHEN a_ratio<=1.5 THEN 'normal' ELSE 'high' END AS amt,
  count(*) AS n,
  round(avg(r1)::numeric*100,2) AS signal_day_pct,
  round(avg(fwd_low5)::numeric*100,2) AS fwd5_worst_pct,
  round(100*avg((fwd_low5<=-0.05)::int)::numeric,2) AS pct_fwd5_worst_below5
FROM s
GROUP BY 1,2,3
ORDER BY 1,2,3;
