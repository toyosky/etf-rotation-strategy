# 2026-11-21 execution-time leakage audit (research only)

Status: **blocking for executable MAE labels**. Reviewed `code/calendar_forward_excursion.mjs` at branch `research/top1-downside-20261120` after commit fc4613cd.

## Finding
The helper accepts an independently supplied `executionDate` and `entryPrice`, but computes the minimum daily low over **all** of the first execution session. A strategy executing at 09:31 or 09:35 cannot experience a low printed before execution. Similarly the maximum high used for MFE may have occurred before entry. Thus `price_proxy_only` is appropriately named: even when executionDate matches the next session, the resulting MAE/MFE is not an executable entry-to-future-path label. A daily-open proxy is also not an exact 09:31 fill. For 14:05 gating the decision time and eligible price path require separate treatment.

## Required implementation gate
1. Maintain `proxy_daily_ohlc` as a separate cohort. Explicitly label it as **conservative full-session extrema proxy**, not actual fill-based MAE/MFE. Its first-session low can overstate adverse excursion, and first-session high can overstate favorable excursion. Direction of bias in a fitted prediction is not assured.
2. Build `executable_intraday` only with PIT minute/tick data at and after the actual fill time on the entry session; subsequent sessions may use complete OHLC if holding continuously, subject to routing, gaps and corporate-action basis.
3. Confirm the router's sell/defense/void transitions. A future excursion on the original ETF is a **counterfactual asset risk** label, not necessarily the realized strategy drawdown when the original Top1 exits or switches during the horizon.
4. Keep raw/adjusted OHLC and fill price on the same adjustment basis. Record `price_basis`, `execution_time`, `entry_source`, `route_version`, `pit_premium_status`, `data_snapshot_hash`, and `cohort` for every label.
5. Do not merge proxy and executable labels into one OOS score; report coverage separately. Do not present model calibration on proxy labels as proof of a live withdrawal policy.

## Experiment dependency
Before five-group OOS ablations: freeze market calendar and data snapshot; reconstruct historical risk-exposure days from the frozen strategy, then build executable labels where intraday/PIT history exists, and independently build daily candidate Top1 proxy elsewhere. Evaluate only common rows within each ablation and purge overlapping forward windows. No production rule changes.

This is a code-path audit, not an empirical backtest or CI result.
