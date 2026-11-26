# Run 11: reproducibility and PIT eligibility gate (2026-11-20)

Scope: read-only connector inspection; **not a new OOS model experiment**.

## Verified current state
- PR #7 branch `research/top1-downside-20261120` already contains the unified-model preregistration, OOS exploratory reports, and minute-label audits. Do not rerun the already completed 645-pair 14:05 boundary test.
- Supabase `public.daily_bars`: 33,205 rows; `public.minute_bars`: 168,990 rows; `public.fund_premium_history`: **4,093 rows** at this check, up from the prior documented 4,090. Explicit read-only SQL `SELECT count(*) total, count(*) FILTER (WHERE pit_safe IS TRUE) pit_safe FROM public.fund_premium_history` returned `total=4093, pit_safe=0`.
- GitHub connector returned **zero PR-triggered workflow runs** for preceding commit `302925bf`. This is not proof that no workflow exists under other triggers.
- Existing `20261120_unified_ml_first_oos_2021_2026.md` reports 1,390 risk-asset proxy days, 2026 unified Q90 coverage 85.29%, and admits the executable V1/Void/premium route and full reproducible code are not available. These numbers are prior research, **not recomputed in this run**.

## Hard interpretation gates
1. No historical PIT-safe premium observation is currently flagged. The full 2021–2026 historical executable route cannot be certified by assuming retrospectively known NAV. Mark route as **candidate-only daily proxy** unless independently timestamped source and matching as-of rules exist.
2. The unified OOS report says 2018–2026 proxy training and six annual holdouts, but the exact data snapshot and one-command reproducible executable are missing. A markdown model description does not suffice for independent reproduction.
3. 2026 Q90 coverage below 90% is a **calibration failure** for that year, even if aggregate pinball improves. Do not use the model to set live withdrawal fractions.
4. A fixed 5-session mechanical cash interval is a performance-accounting convention only. No re-entry optimizer may be tuned on the same OOS years.
5. Earlier single-event oil and 14:05 minute diagnostics are separate from all-held-day, production-routed OOS evidence.

## Next execution priority
- Retrieve and freeze actual strategy route code and historical execution state; generate as-of date-by-date audit columns: candidate, route, V1/Void/premium evidence, decision timestamp, execution timestamp, reason code, tradability, and missing-data flag. Produce explicit counts for **certified** versus **proxy** days.
- Recover immutable input snapshots or versioned release artifacts, implement a one-command training/prediction/metric pipeline, save per-day OOS predictions, and test 2026 coverage with block bootstrap.
- Run OLS/vol, overheat-only, decline-only, unified, unified+volume/market ablations on **identical held-day rows**. Stratify ETF/year/regime, and exclude the 2026 501018 oil episode as a sensitivity test.
- Only after passing prediction and route gates, test continuous exit against normal ETF/regime risk, with frozen 5-day cash accounting, realistic costs and missed upside.

No production strategy, notification, position or scheduled workflow was changed.
