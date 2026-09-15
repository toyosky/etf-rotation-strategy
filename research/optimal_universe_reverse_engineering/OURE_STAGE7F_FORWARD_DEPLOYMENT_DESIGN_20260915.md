# OURE Stage7F — Frozen Robust30 Prospective Walk-Forward Monitor

Date: 2026-09-15
Status: preregistered before prospective outcome accumulation

## Purpose
Stage7F operationalizes the frozen Robust30 specification for forward monitoring. It is not an optimization stage.

Frozen deployment specification:

`3 x 126-session completed history blocks -> frozen candidate family and seed semantics -> 0.5*median historical rank + 0.5*q25 historical rank -> select K30 Universe -> freeze for 126 sessions -> frozen downstream OLS Top1`.

## Research freeze boundary
The mechanism and model were frozen on 2026-09-15 after Stage7E.

Therefore:
- data through 2026-09-15 may be used to establish current state and current OLS target;
- **new prospective performance evidence begins only on sessions strictly after 2026-09-15**;
- already-observed sessions between the Stage7B evaluation end and 2026-09-15 must not be counted as new prospective evidence.

## Universe refresh schedule
Keep the original Stage7A calendar anchor and 126-session block schedule. Do not re-anchor to the Stage7F start date.

At each scheduled Universe decision boundary t:
1. use only the three fully completed 126-session history blocks before t;
2. reproduce frozen Stage7A candidate-family generation with seed `20260914 + block_no*1009`;
3. apply the frozen robust score;
4. select one K30 Universe and keep it fixed until the next scheduled 126-session boundary.

No quarterly maintenance, ad-hoc replacement, or mid-block member changes are allowed.

## Downstream portfolio path
Within each frozen K30 Universe, apply the same Stage7B daily OLS Top1 target logic.

For prospective monitoring report:
- daily target;
- target changes / turnover sides;
- gross daily return of the held target under the frozen research return convention;
- net path at 6bp, 12bp and 20bp per turnover side;
- cumulative return;
- Top1 tenure.

This is a research baseline path, not a replacement for the user's intraday execution filters or live brokerage execution logic.

## Current-state output
Every run writes:
- latest available market-data date;
- active 126-session Universe block and decision date;
- current frozen Robust30 members;
- current OLS Top1 research target;
- sessions remaining until next scheduled refresh when calculable from observed calendar;
- prospective sample size accumulated after 2026-09-15.

## Persistence
The GitHub workflow may rerun on weekdays and overwrite deterministic state files reconstructed from the database:
- `forward_monitor/stage7f_current_universe.csv`
- `forward_monitor/stage7f_snapshot.json`
- `forward_monitor/stage7f_forward_daily.csv`

Because the full forward path is reconstructed under frozen logic on every run, no mutable model state is required.

## Guardrails
1. No changes to K, horizons, features, candidate generation, seed, robust score, or downstream OLS based on forward outcomes.
2. Any code correction must be documented and must not use future return information to choose the correction.
3. Pre-freeze observations never become prospective evidence on reruns.
4. New ETFs may enter only through the frozen eligibility and scheduled Universe construction process at a future 126-session boundary.
5. Forward results are reported as monitoring evidence, not used to tune Stage7F.

## Interpretation checkpoints
No minimum sample is required to run the monitor, but deployment confidence should not be upgraded from a handful of days.

Formal reviews should be done at frozen milestones:
- 21 prospective sessions;
- 63 prospective sessions;
- 126 prospective sessions / first full post-freeze Universe horizon.

At each checkpoint compare the forward baseline against its own historical Stage7A-7C behavior, without changing the model.
