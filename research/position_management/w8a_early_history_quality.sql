-- Archived query from 2026-11-28 13:06 UTC completed run; read-only.
-- This query audits structure, not adjustments, listings, PIT or exchange calendar completeness.
WITH b AS (
  SELECT symbol,date,open,close,high,low
  FROM daily_bars
  WHERE date < '2021-01-01'
    AND symbol IN (
      '159934','159985','161226',
      '513100','159957','159509',
      '513290','159529','159981',
      '501018','513530','164824',
      '511380','512800','511220'
    )
),
cal AS (
  SELECT DISTINCT date FROM b
),
a AS (
  SELECT symbol,
    min(date) AS first,
    max(date) AS last,
    count(*) AS n,
    count(DISTINCT date) AS nd,
    count(*) FILTER (
      WHERE open IS NULL
         OR close IS NULL
         OR high IS NULL
         OR low IS NULL
         OR least(open,close,high,low)<=0
         OR high<greatest(open,close,low)
         OR low>least(open,close,high)
    ) AS bad
  FROM b GROUP BY symbol
)
SELECT a.*,
  (SELECT count(*) FROM cal
   WHERE date BETWEEN a.first AND a.last)
   - nd AS gaps
FROM a ORDER BY symbol;
