# W research archival backfill — 2026-11-28

## Provenance and evidence grades
This is a retrospective archive of previously reported results, not a new backtest. Existing W3a/W3b/W4a/W6b.1 ledger entries remain intact. Historical report excerpts are distinguished from archived runnable artifacts. No raw paths, confidence bounds, asset identities, or parameters are invented. No production changes. All returns below are as reported, not independently recomputed in this archival session.

- A: recorded completed run with actual read-only SQL and reported rows; SQL and transcribed results archived.
- B: previously reported numerical experiment recovered from historical research summaries; exact underlying implementation, daily paths or raw results not yet recovered here.
- P: pending or partial, no completion claimed.

## W1 / W2 (B): initial results, frozen candidates
2021-01-04–2026-11-12: 1,419 signal days, 445 Void, 960 matched non-Void predictions. Sources: research/formal-void-q90-stateful-q10-20261121: research/top1_downside/audit/20261120_prob_opportunity_oos_predictions.csv and 20261121_q10_formal_void_q90_daily.csv; research/nonvoid-switch-audit-2021-2026-20261118: research/results/nonvoid_switch_audit_2021_2026/q5_ols_v1_void_baseline_path_2021_2026.csv. Prediction/baseline blob SHAs already in ledger: 3a93afe73e85448650ce0cd9f8c20ebe4b2bf304 / d373130b1ae56d6a3f60b22a7182c9ccfb5016d2. Historical open proxy, single-side 6bp; full PIT Premium10 and minute execution not established.
- Baseline CAGR 54.51%, MDD -37.64%; Q10 daily symmetric 5pp CAGR 57.87%, MDD -33.61%.
- W1 absolute inverse-risk sizing lost to equal-exposure comparators in nine groups. Relative risk A retained: clip(0.90/max(1,Q90/Dbase),0,1).
- W2 C retained: clip(0.80+0.5*(historical Score rank - historical relative risk rank),0,1). Existing ledger uses last 252 eligible observations, 60-observation warmup, past-only midranks. Higher trend rank improved return but increased drawdown; not deployment evidence.

## W3 / W4a (existing archive)
See W_RESEARCH_LEDGER.md and its referenced w3b_replay.mjs, w3b_results.json, w4a_execution.mjs, w4a_results.json. W3b opportunity rank variants F/V/I underperformed exposure-matched C at both costs. W4a center/edge bands tested 0/5/10pp. No need to repeat completed experiments without a specific discrepancy.

## W4b / W5a / W5b (B)
Previously reported results recovered from 2026-11-26/27 research outputs. W4b 16 replays; W5b 20 replays. These are summary-only until original code, full grids, daily paths and paired bootstrap intervals are recovered.

| C execution variant | CAGR | MDD | Other reported results |
|---|---:|---:|---|
| Symmetric 5pp | 51.59% | not recovered | 307 adjustments (reported W4) |
| Reduce 10pp / increase 5pp | 51.96% | -35.14% | W4b equal-exposure advantage approx +0.46pp; bootstrap crosses zero |
| Simple delayed reduction | 52.92% | -35.14% | W5b equal-exposure advantage +0.76pp; adjustments -34.53%; bootstrap crosses zero |
| Trend-aware | 52.85% | not recovered | no independent deployment evidence |

W5a persistence: reduction signals persisted to day 3 in 46.00%, increase signals in 70.33%; reduction reversed within five days in 67.86%. Exact event counts and definitions not recovered. Do not infer a statistical advantage merely from headline CAGR. Full W4b/W5a/W5b artifacts remain a recovery task, not a reason to re-optimize.

## W6 (B + existing archive)
W6a reported separation of non-Void target exposure from Void holdings: freeze actual holdings and cash in Void, except formal routing changes. No recovered full W6a replay metrics. W6b.1 has an existing reproduction function and exact counts in ledger (C cut 105 / other 643; A cut 108 / other 640). These event analyses do not prove a deployable exit filter. Preserve formal routing, do not change production. Weak-trend gate follow-up remains subject to evidence recovery/verification.

## W7a (B): Q10 exact replay reported on 2026-11-27
Recovered formulas: R=Q90/Dbase; K=clip(1+2*(Pfull-Pvol),0,1.8); rawE=clip((1-1.1/R)*K,0,1); Ef=rawE if rawE>=0.05 else 0. Symmetric 5pp execution threshold is separate from the 5% reduction filter. Full original implementation required for exact holdings/route logic and boundary behavior; Pfull/Pvol are the original model inputs, not replacements for P-All.
- Reported 1,419-day exact reproduction: CAGR 57.87%, MDD -33.61%, maximum relative daily error 5.11e-15, 0/1,419 mismatches.
- Remove K: 56.72%, -34.98%.
- Remove 5% small-reduction filter: 57.73%, -33.64%.
Original code and daily comparison output not recovered here; do not treat this summary as independently re-executed.

## W8d.1 / W8d.1b (B): fixed exposure control
Reported 2026-11-28 05:03 UTC and 06:07 UTC. Fixed five-asset pool, daily-price proxy, continuous cash accounting, 6bp one-way base case. Exact pool membership, daily routes, SQL/code and output hashes not recovered in this archive; do not conflate with full 14-asset formal baseline.

| Period | Days | Target | CAGR 6bp | MDD 6bp | Cumulative return 10bp | Reported actual exposure (10bp) |
|---|---:|---:|---:|---:|---:|---:|
| 2018–2020 | 730 | 80% | 14.39% | -15.35% | 44.05% | 56.329% |
| 2018–2020 | 730 | 90% | 15.96% | -17.21% | 49.35% | 63.370% |
| 2018–2020 | 730 | 100% | 17.47% | -19.06% | 54.53% | 70.411% |
| 2021–2025 | 1212 | 80% | 19.61% | -18.07% | 129.92% | 62.508% |
| 2021–2025 | 1212 | 90% | 22.00% | -20.26% | 151.91% | 70.322% |
| 2021–2025 | 1212 | 100% | 24.37% | -22.43% | 175.21% | 78.135% |

This control does not establish dynamic sizing superiority; W8d.2 remains pending.

## W8a (A): early daily-bar structural audit
Source: completed 2026-11-28 13:06 UTC automated research report; Supabase daily_bars read-only query. See w8a_early_history_quality.sql and w8a_early_history_quality_20261128.csv (reported result transcription, not fresh database export).
- 10,284 rows across 11 of 15 formal risk/defensive symbols before 2021; zero reported bad OHLC and duplicate symbol-dates.
- Date-union reference calendar: 511220 six internal gaps; 164824 one; other nine zero. All 11 extend through 2020-12-31.
- This is not an official exchange calendar: days missing from all symbols are undetected. Do not fill or trade across missing prices without checking suspension/omission. Confirm date grain, actual listing dates, adjusted prices/dividends, turnover, preheat, time-known premium.
- SQL and CSV preserve the run evidence. No PIT-safe premium claim, no minute execution reconstruction.

## Current authoritative work queue (2026-11-28)
W1–W6 first round reported complete; some evidence is only grade B. W7a reported reproduced. W7b common sample real equity replay of continuous H-DV, H-MAE and Q90 remains pending after repeated unsuccessful dynamic replay attempts; W7c minimum commission/round lot, W7d robustness pending. W8a structural subtask complete, adjusted/PIT audit pending; W8b 2015–2020 dynamic eligible-pool benchmark and 2018–2020 common-pool reconstruction not complete; W8c freeze protocol partial; W8d.1 fixed controls reported complete, W8d.2 dynamic replay pending; W8e cross-asset non-Top1, W8f multi-period robustness, W8g final frozen selection and forward simulation gates pending. P-All source availability unresolved; no substitution.

Use 2013–14 warmup where available; 2015–20 backward historical validation (not true forward OOS), 2021–25 original research sample, 2026 separate stress test only. No parameter search on new sample; predeclare candidate Q10/A/C and fixed/execution comparators, same routing, PIT, past-only mature labels, rolling original prediction protocol, 6/10bp, matched exposure and volatility (ex-post only for attribution), block bootstrap, asset/year/market/tail decomposition, survivorship and overlapping-label limitations. Missing early prediction input: report unavailable rather than fabricate. No repeat of structural/fixed-control work unless warranted. If exact replay remains blocked, advance independent cross-asset or data tasks, then return. Stop only after W7b/c/d and W8a–g and material branches complete or explicitly non-verifiable and final report produced.

## Archival gaps
This backfill records the most specific historical evidence recovered, not a claim that all research has reproducible artifacts. Original W4b/W5a/W5b/W6a/W7a/W8d.1 scripts, full results, exact parameter manifests and daily path checks should be located and linked in a subsequent archive; do not invent missing details. No database writes, main changes, or trades.
