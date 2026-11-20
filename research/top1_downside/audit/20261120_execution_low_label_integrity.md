# 2026-11-20 unified OOS label/execution audit (run 11)

Status: methodological audit; no new model fit or performance claim. Read existing PREREGISTRATION, unified ML first OOS, experimental plan and held-proxy report before this audit. Do not overwrite their historical results.

## Verified live data
Supabase project gsyziuzezmmnvgdoazkg public.fund_premium_history query on 2026-11-20:
total=4090, pit_safe=true=0, first_seen_at non-null=3055, backfilled=true=4090, nav_date 2026-02-24..2026-11-19.
Schema public.daily_bars describes HFQ Tencent prices, 33205 rows / 19 symbols; minute_bars 168990 rows and begins 2026-09-14. instrument_metadata has zero rows. These counts are database snapshots, not evidence of full-market PIT membership.

## Blocking label/execution discrepancy
The unified OOS pilot explicitly labels L5=max(0,1-min(low[t+1:t+5])/open[t+1]). This is a valid **next-open daily-bar proxy**, but the frozen strategy's executable buying can be delayed to 14:05, rejected by 09:31 gap and 14:05 drawdown gates, blocked by premium/Void, or never occur. In particular, low[t+1] may have occurred **before 14:05**; such a pre-entry low cannot be counted as a realized adverse excursion of an actual 14:05 purchase. The target may consequently include a counterfactual pre-entry trough. Neither sign nor size of this bias is known without minute timestamps and executable route reconstruction.

Required next experiment:
1. For minute-covered 2026 dates, reconstruct actual routing state as-of decision; on eligible 14:05 buys define execution-price reference from the executable timestamp, and restrict the first session's low to bars **at/after execution**; for 09:31 positions apply corresponding eligible timestamp.
2. Compare same-symbol/date next-open L5 and execution-timestamp L5 only on paired, route-eligible observations, with counts by ETF, and 501018 versus 159981; separately show no-fill/rejection cases.
3. Until validated, label all 2021–2026 models and portfolio curves as DAILY_PROXY, not real frozen-route MAE or implementable CAGR.
4. Keep original full-sample unified overheat/decline learner and 5-session mechanical cash return. Do not tune buyback timing. Check Q90 2026 coverage (reported 85.29% unified, 86.27% +volume/market), nested OOS calibration and block-bootstrap before portfolio conclusions.

## Additional source restriction
The 3055 first_seen_at timestamps do not certify PIT eligibility: all 4090 rows remain backfilled and pit_safe=false. Never convert historical NAV presence into as-of premium trading eligibility. Historical 2018–2026 selection still suffers present-day fixed-pool survivorship and lacks historical category metadata.

## Decision
No model accepted, no live parameter approved, no production edits. Next priority: executable timestamp/low audit and reproducible code archive; only then robust nested walk-forward OOS and portfolio attribution. Existing 2021–2026 pilot is useful exploratory evidence but not completion of research criteria.
