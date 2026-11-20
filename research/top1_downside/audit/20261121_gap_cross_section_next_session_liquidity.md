# 2026-11-21 calendar-gap cross-sectional and next-session liquidity audit

Read-only query against Supabase public.daily_bars (vendor-adjusted, not independently executable prices). Continuation of 20261121_gap_adjacent_price_discontinuities.md. All 10 missing symbol-sessions have other symbols trading on the same calendar day (11 to 17 symbols), ruling out a market-wide holiday in this database but **not** establishing whether the affected symbol was suspended, omitted by vendor, or misadjusted.

New finding: comparing next available CLOSE against prior CLOSE, four gaps cross -10% (159529 on 2025-01-10: -10.000%; 159529 on 2025-01-24: -10.256%; 161226 on 2026-01-30: -10.095%; 501018 on 2026-03-24: -10.156%). The 2026-01-30 501018 gap is -9.677% on this metric. These are **multi-session observed-record differences**, not proven single-day limit-down moves. Prices are rounded vendor-adjusted series; avoid inferring exchange price limits.

On the first available session after the missing 2026-01-30 records (2026-02-02), 161226 shows O=H? not tested; O=L=C=4.72 and volume 13,941,700 vs preceding observed volume 584,322,300 (~2.39%). 501018 shows O=L=C=1.40 and volume 17,572,100 vs 213,768,500 (~8.22%). High was not queried, so **do not claim flat OHLC**. These patterns are consistent with constrained liquidity but do not prove an exchange halt or limit-down. 159529 2025-01-24 gap next observed session 2025-01-27 close=1.75 vs prior close=1.95 (-10.256%).

Reproducible read-only SQL:
```sql
WITH cal AS (SELECT DISTINCT date FROM public.daily_bars WHERE date BETWEEN '2021-01-01' AND '2026-11-19'),
spans AS (SELECT symbol,min(date) lo,max(date) hi FROM public.daily_bars GROUP BY symbol),
gaps AS (SELECT s.symbol,c.date FROM spans s JOIN cal c ON c.date BETWEEN s.lo AND s.hi LEFT JOIN public.daily_bars d ON d.symbol=s.symbol AND d.date=c.date WHERE d.symbol IS NULL)
SELECT g.symbol,g.date missing_date,
 (SELECT count(*) FROM public.daily_bars x WHERE x.date=g.date) other_symbols_present,
 p.date prior_date,p.close prior_close,p.volume prior_volume,
 n.date next_date,n.open next_open,n.low next_low,n.close next_close,n.volume next_volume,
 round((100*(n.close/p.close-1))::numeric,3) cross_gap_close_pct
FROM gaps g
LEFT JOIN LATERAL (SELECT date,close,volume FROM public.daily_bars WHERE symbol=g.symbol AND date<g.date ORDER BY date DESC LIMIT 1) p ON true
LEFT JOIN LATERAL (SELECT date,open,low,close,volume FROM public.daily_bars WHERE symbol=g.symbol AND date>g.date ORDER BY date LIMIT 1) n ON true
ORDER BY g.date,g.symbol;
```

Research consequence: keep 42 future-5 and 72 future-10 instrument-date windows flagged pending official suspension records and raw unadjusted OHLC cross-check. A gap is not a zero-return day and must not be filled with an invented low. A suspended asset can remain a risk exposure, but the executable sale price cannot be assumed. This check does not reconstruct PIT Top1 holdings or validate any OOS model, so no portfolio inference or production changes.
