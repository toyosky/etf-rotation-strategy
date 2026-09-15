# OURE Stage7H — Fix15 vs dynamic Robust30 same-engine comparison

Date: 2026-09-15
Status: preregistered before run

Question: under the exact same daily OLS engine, execution convention, calendar and costs used by Stage7G, does dynamic Robust30 actually outperform the original fixed Fix15?

Frozen comparison:
- Fix15 = 518880,159985,159825,161226,513100,159915,511220,159509,513290,159529,159981,501018,513920,511380,164824.
- Dynamic Robust30 construction is unchanged from Stage7G/Stage7F.
- No V1 overlay in the primary comparison; compare raw OLS baseline to raw OLS baseline.
- Same frozen OLS eligibility and cash-proxy logic.
- Same signal-date to next-open return matrix.
- Costs: 6 bp/side primary; 12 and 20 bp sensitivities.
- Annual attribution by execution date, 2021 through 2026 partial.
- Also report compounded full-period return, maximum drawdown and turnover.

Interpretation: Fix15 is the benchmark. Robust30 is not promoted merely because its selection mechanism is explainable. If it fails to beat or materially improve risk relative to Fix15 under identical accounting, it remains an experimental alternative rather than the primary strategy.
