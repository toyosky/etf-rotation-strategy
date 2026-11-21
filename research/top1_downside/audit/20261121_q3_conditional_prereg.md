# Q3 preregistration: Top1 condition × Top2 opportunity

Research only, November 21, 2026. Protocol frozen before Q3 model/outcome analysis; no changes to production or existing Q90 logic.

## Decision
At the 119 previously frozen Q90+probability exit events, is the partial capital better placed in eligible Top2 instead of cash or restoring Top1? Unlike Q2, the target is **net economic return and adverse excursion**, not prediction of future Top1 ranking.

Read original historical daily proxy signals from Q90 OOS CSV, Q1 event-level pairs (116 complete 5-day pairs), and Q1 archived 2020–2026 OHLC for 14 risk ETFs + 511220. Rebuild Top1/Top2 with production 26-bar weighted log OLS score=max(annual,0)*R², q² effective weights with nominal half-life 10, past-3-day loss veto (<-3%), score > comparator. No hard R² >= 0.5 unless present in production. Score t only with as-of-t completed OHLC. Event start, Q90 reduction amount E, and 5-session mechanical allocation are unchanged.

## Ex-ante features
Top1 state: effective-weight 26-bar OLS log-price last residual z26 = (last log price - fitted) / sqrt(weighted residual SS/sum effective weights). Classify as positive-extension z>=1, negative-displacement z<=-1, central -1<z<1. Separately show negative displacement with trailing 3-session log return negative vs recovering. Prior vol20 and past3/5 log returns available at t. Keep frozen D90/Dnormal, P5_full-P5_vol, and exit fraction E as condition controls; do not redefine risk events.

Top2 opportunity: 3-session OLS score change for the **same symbol**; relative score-change advantage over same Top1; Top2 own 3-session R² change; past 5-session relative log return; Top2 past vol20 / Top1 past vol20. Classify active = positive Top2 3-session score change AND larger than Top1 3-session score change AND positive Top2 R² change. Others = non-active. The active gate is exploratory, not an adopted filter. Separately present each component. Recent rebuilding (annual cross from <=0 to >0 in past 1–3 sessions, with R² improvement since crossing and positive last change) is an optional annotation, NOT a hard restriction.

## Prespecified outputs
Primary 3x2 Top1-z-state × Top2-active cells, total n, 3/5/10 day raw and net event returns, Top2 - Top1 opportunity spread, Top2-vs-cash incremental return after 12bp round-trip friction, Top1/Top2 adverse excursion 5 days (MAE), P(MAE>=5%), event weight E, risk correlation. Flag cells n<15 as exploratory and not reliable.

Policies using **same frozen 119 events and same 5-session episodes**:
(1) Q90 E remains in cash;
(2) Original Top1 effectively remains fully invested;
(3) Q90 E to eligible Top2 on all complete eligible events;
(4) Active-only: E to Top2 when active Top2 else cash;
(5) Joint: E to Top2 only if active Top2 AND (Top1 positive extension z>=1 OR Top1 negative displacement z<=-1 AND trailing 3-session return<0); else cash.
No test-period selection/retuning. At unknown rank/features or missing reliable path, cash fallback (research complete-case limitation, may use hindsight availability; NEVER present as executable PIT). Return to baseline at fifth interval; original historical Top1 routing continues each day. If risk router goes cash, exit Top2. Buy/sell fees 6bp each side. Unavailable historical PIT NAV/premium, V1/Void, 09:31/14:05 and survivorship preclude deployment.

Report portfolio compounded net CAGR, MDD, Calmar, per year, exposure and trades. Compare paired annualized excess log returns via within-year 20-day block resampling. Include no-oil sensitivity. Do NOT infer forecasting skill or positive profits simply from ex-post subgroup means. All 2021–2026 data have already been studied repeatedly; this analysis is at best hypothesis-generating, not unseen external validation. If evidence fails, document the failure.
