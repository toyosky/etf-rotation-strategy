# 2026-11-21 OHLC and key-integrity audit (research only)

Source: Supabase project gsyziuzezmmnvgdoazkg, public.daily_bars. Executed 2026-11-21 (Asia/Tokyo). This is a **live mutable-table snapshot**, not a frozen PIT extract.

```sql
WITH x AS (
 SELECT symbol,date,open,high,low,close,volume,amount
 FROM public.daily_bars WHERE date >= '2021-01-01'
)
SELECT COUNT(*) total,
 COUNT(*) FILTER (WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL OR open<=0 OR low<=0 OR high<low OR open<low OR open>high OR close<low OR close>high) invalid_ohlc,
 COUNT(*) FILTER (WHERE volume IS NULL OR amount IS NULL OR volume<0 OR amount<0) invalid_liquidity,
 (SELECT COUNT(*) FROM (SELECT symbol,date FROM x GROUP BY 1,2 HAVING COUNT(*)>1) d) duplicate_keys
FROM x;
```

Observed: total=21242, invalid_ohlc=0, invalid_liquidity=0, duplicate_keys=0.

Previous audit reported 21223 rows. Difference +19 rows. **Do not attribute to a particular date or source without a dated diff.** The mutable input must be snapshotted and hashed before OOS experiments; otherwise historical results may silently drift.

Zero invalid OHLC rows is a *syntactic* check only: it does not establish market-calendar completeness, true tradeability, adjusted-price comparability, historical availability, premium PIT, or absence of suspended trading. The previously identified ten calendar gaps remain separately unresolved.

Next gates: freeze immutable data extract + hash; verify last dates and changed rows; connect calendar-forward labels to the all-exposure-day Top1 proxy separately from executable reconstructed holdings; run OOS feature ablations before any position sizing. No production changes.
