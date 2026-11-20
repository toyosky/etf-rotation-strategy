# 2026-11-20 15:30 bar semantic diagnostic (read-only)

## Scope
Continuation of `20261120_minute_session_integrity_43days.md`. Read-only Supabase project `gsyziuzezmmnvgdoazkg`, `public.minute_bars`, 1-minute rows, 2026-09-14 through 2026-11-19. These are **not** verified tradable Top1 route observations. No model refit or OOS result is claimed.

## Executed SQL
```sql
WITH d AS (
 SELECT symbol,trade_date,
 max(close) FILTER(WHERE bar_time::time='15:00') c1500,
 max(close) FILTER(WHERE bar_time::time='15:30') c1530,
 sum(volume_shares) FILTER(WHERE bar_time::time>'15:00') vpost,
 sum(volume_shares) FILTER(WHERE bar_time::time<='15:00') vregular,
 min(low) FILTER(WHERE bar_time::time>'15:00') lowpost
 FROM public.minute_bars WHERE interval_min=1 GROUP BY 1,2
)
SELECT symbol,count(*) n,count(*) FILTER(WHERE c1530 IS NOT NULL) n1530,
 round(avg(abs(c1530/c1500-1)*100)::numeric,5) avg_abs_close_change_pct,
 round(max(abs(c1530/c1500-1)*100)::numeric,5) max_abs_close_change_pct,
 count(*) FILTER(WHERE abs(c1530/c1500-1)>0.001) n_gt_10bp,
 round(avg(vpost/nullif(vregular,0)*100)::numeric,4) avg_post_volume_pct,
 round(max(vpost/nullif(vregular,0)*100)::numeric,4) max_post_volume_pct,
 count(*) FILTER(WHERE lowpost<c1500*0.999) post_low_below_close_10bp
FROM d GROUP BY symbol ORDER BY symbol;
```

```sql
WITH a AS (
 SELECT symbol,trade_date,
 max(close) FILTER(WHERE bar_time::time='15:00') c0,
 max(close) FILTER(WHERE bar_time::time='15:30') c1,
 count(*) FILTER(WHERE bar_time::time>'15:00' AND
   (open<>close OR high<>low OR open<>high)) varied,
 count(*) FILTER(WHERE bar_time::time>'15:00' AND volume_shares>0) positive,
 count(*) FILTER(WHERE bar_time::time>'15:00') bars
 FROM public.minute_bars WHERE interval_min=1 GROUP BY 1,2
)
SELECT count(*) FILTER(WHERE bars>0) etf_days,
 sum(varied) varying_post_bars,
 sum(positive) positive_volume_bars,
 sum(bars) total_post_bars,
 count(*) FILTER(WHERE bars>0 AND c0=c1) unchanged_close_days
FROM a;
```

## Measured observations
- All 12 ETF symbols have 43 days with 15:30 bars (516 ETF-days). Three LOFs have no 15:30 bars.
- On **all 516 ETF-days**, 15:30 close equals 15:00 close exactly. Mean and maximum absolute difference both 0.00000% for every ETF.
- Across 12,900 post-15:00 minute bars, **zero** have unequal OHLC values within the bar, but **5,256** have positive reported volume; the other 7,644 have zero volume.
- Post-15:00 reported volume divided by volume through 15:00 averages 0.0055% (511380) to 0.1689% (513100), by ETF. Maximum observed ETF-day ratio is 0.8191% (513100).
- These observations strongly suggest post-15:00 rows have different source semantics from normal continuous-auction minute bars, but cannot by themselves distinguish genuine fixed-price after-hours trades from synthetic/vendor bar transformations.

## Modeling decision and remaining verification
For future MAE and executable entry-price proxies, **exclude post-15:00 rows pending exchange/source validation**. For volume-based predictive features, compute a strict <=15:00 baseline; treat post-15:00 volume separately and only include it if its point-in-time publication and execution semantics are proven. Do not treat 15:30 close as an independent price discovery point. This is a conservative *research data-processing recommendation*, not a production rule change.

Historical PIT premium data, frozen Top1 executable route reconstruction, five-group OOS ablation and calibrated continuous exit performance remain unresolved. No production modifications.
