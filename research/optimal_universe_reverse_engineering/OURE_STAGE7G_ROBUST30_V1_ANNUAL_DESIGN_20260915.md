# OURE Stage7G — Robust30 + frozen V1 annual backtest design

Date: 2026-09-15
Status: preregistered before run

## Question
Does the previously frozen Fix15 V1 switch veto improve the current frozen Robust30 + OLS process on a 2021–2026 year-by-year basis?

## Frozen Robust30 construction
Robust30 itself is unchanged:
- K=30.
- 126-session deployment horizon.
- Three immediately preceding completed 126-session history blocks.
- Candidate-library construction unchanged from Stage7A–7F.
- Robust score = 0.5 * median(history percentile ranks) + 0.5 * q25(history percentile ranks).
- Highest robust-score K30 is frozen for the next 126 sessions.
- The current Stage7F grid remains anchored at the first trading session on/after 2022-01-01. For 2021 diagnostics only, this exact 126-session grid is extended backward in 126-session increments. This does not alter any 2022+ deployment date or any current B10 result.

## Baseline
Within each frozen Robust30, use the existing OLS target-state rule exactly as Stage7A–7F:
- eligible risk leader = highest frozen OLS score in the current Robust30;
- cash-proxy comparison remains 511220 through the existing Eval target-state logic;
- signal date t maps to the next-open holding return already encoded in the frozen `gross` matrix.

## Frozen V1 overlay
V1 changes only rank-switch execution; it does not change Robust30 construction or OLS scores.

For a new non-cash challenger B on signal date t:
- Daily Volume Profile proxy uses prior 120 trading days.
- Historical amount is spread uniformly across each day's [low, high].
- UpperShare = amount in [P,1.05P] / amount in [0.95P,1.05P], P=current close.
- ResistancePct252 = current UpperShare point-in-time percentile versus strictly prior max252 UpperShare observations for the same ETF.
- Minimum profile history = 60 observations.
- ScoreDelta_new = raw OLS score_t - raw OLS score_{t-1}, computed before trend-eligibility masking.
- Veto only if ResistancePct252 >= 75% AND ScoreDelta_new <= 0.

Safety adaptation, frozen before run:
- V1 may veto only a pure ranking switch.
- If the incumbent is removed from the new Robust30, loses OLS trend eligibility, or fails the cash-proxy investability comparison, it cannot be retained by V1.
- Cash exits are never vetoed.
- Initial entries are never vetoed.

## Backtest window and accounting
Requested calendar years: 2021, 2022, 2023, 2024, 2025, 2026 partial through the latest fully evaluable signal date.

Because the frozen `gross` matrix is signal-date indexed and represents next-open to following-open return, annual attribution uses the execution date (the next trading session after the signal) rather than the signal date.

Primary cost: 6 bp per side, matching the frozen V1 diagnostic. Sensitivity paths: 12 bp and 20 bp per side.

For each calendar year report:
- baseline total return;
- V1 total return;
- V1 minus baseline percentage-point difference;
- baseline and V1 maximum drawdown;
- turnover sides;
- V1 veto count;
- covered execution-session count.

Also report full-period compounded return and divergence-event diagnostics.

## Interpretation rule
This is a historical diagnostic, not fresh OOS. No V1 threshold, Robust30 formula, candidate-library parameter, horizon, or cost assumption will be tuned after observing results.
