# 2026-11-20 PIT coverage and continuous-overlay audit (run 11)

## Live SQL executed
```sql
select 'daily_bars' source,count(*) n,count(distinct symbol) symbols,min(date)::text start_date,max(date)::text end_date from public.daily_bars
union all select 'minute_bars',count(*),count(distinct symbol),min(trade_date)::text,max(trade_date)::text from public.minute_bars
union all select 'premium',count(*),count(distinct symbol),min(nav_date)::text,max(nav_date)::text from public.fund_premium_history;

select count(*) total,count(*) filter(where pit_safe) pit_safe,
count(*) filter(where first_seen_at is not null) with_first_seen,
count(*) filter(where backfilled) backfilled
from public.fund_premium_history;
```

Returned: daily_bars 33,205 rows / 19 symbols / 2013-05-15..2026-11-19; minute_bars 168,990 rows / 15 symbols / 2026-09-14..2026-11-19; premium 4,090 rows / 176 symbols / 2026-02-24..2026-11-19. Premium pit_safe=0, first_seen_at nonnull=3,055, backfilled=4,090. Note first_seen_at does **not** by itself prove a given historical NAV was available before decision time. Full historical PIT route cannot currently be certified. Historical dates in daily table do not imply all 19 instruments existed from 2013.

## Review of existing computed OOS overlay report
Read `audit/20261120_continuous_exit_held_proxy_oos.md` and preregistration before extending. Prior computed 41 MODEL periods baseline -7.5823% / MDD -15.8531%, conditional B=2% overlay -3.1971% / MDD -10.9509%. **Critical concentration:** disable oil 501018 overlay -> -7.6760% / MDD -16.2886%; disable just 2026-11-03 signal -> -9.1684% / MDD -16.4439%. This is not diversified predictive evidence. Proxy held-risk 2025-26 q90 coverage only 84.85% (2026:76.32%), conditional pinball 0.0072462 worse than vol-only 0.0072401. No deployment evidence.

## Newly flagged specification issues, to resolve before any executable sizing
1. Formula `E=G?clip(1-B/max(D,eps),0,1):0` is continuous **in D for fixed G=true**, but not necessarily continuous over time as binary G toggles. Evaluate soft gate / pre-registered smoothing or cost-aware hysteresis strictly within training folds; compare to exact unsmoothed specification and report transition costs. Do not falsely label the overall policy temporally continuous.
2. Quantile `D90` is a one-sided **forecast** of a five-session asset excursion, not a guaranteed bound on portfolio loss; repeated daily resizing, overnight execution, premium gaps, and route switching can exceed B.
3. Previous report's 41 periods use recorded MODEL daily returns scaled ex-post, **not executable 09:31/14:05/PIT fills**. The 2025-26 ranking-only proxy's large gains are not official strategy returns. Must preserve these labels in all comparisons.
4. 2025-26 was previously inspected during exploratory feature selection; time holdout is **not untouched blind OOS**. Need nested walk-forward, embargo, clustered intervals and external future holdout.
5. Next priority: reconstruct frozen state/route as-of for all possible historical dates, then B0..B4 sequential OOS ablation; quantify calibration by ETF/year and leave-one-oil-event-out. Do not spend another cycle optimizing volume or fixed bands on the all-ETF event sample.

Status: methodological/coverage audit only, no new forecast performance metric, no production changes. Research incomplete; automation should continue.
