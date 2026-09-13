# New Stage 1 bootstrap — 2026-09-14

Status: RUNNING

This note marks the operational start of the new `Universe size -> composition` lineage.

## First batch to execute

The first batch deliberately separates the two ideas discussed with the user:

1. **Independent same-K Monte Carlo**
   - Monthly point-in-time representative ETF parent pool.
   - Frozen OLS downstream rule.
   - K grid initially 3..30, clipped by monthly parent-pool size.
   - For every month/K, draw independent random Universes rather than deriving all smaller Universes from one deletion path.
   - Primary evidence is the whole return distribution by K, not the best subset.

2. **Nested deletion check starting from K=15**
   - For each month, draw multiple random 15-ETF Universes (cash signal retained consistently with prior width research).
   - Randomly delete one non-cash member at a time: 15 -> 14 -> ... -> 3.
   - Record the paired marginal return change K -> K-1 on each path.
   - This is secondary evidence and directly tests the user's original intuition without letting one path determine the conclusion.

## Frozen parent-pool rule for first batch

Reuse the existing point-in-time representative-universe implementation in `research/walk_forward_dedup.py`:

- eligibility and liquidity measured on the prior trading day;
- 120-trading-day close-return correlation;
- liquidity-first greedy representative selection;
- primary near-duplicate threshold fixed at 0.95 for the first batch;
- 0.90 is predeclared as a later sensitivity check, not something to choose after seeing results.

Do not use Fixed15 as the parent pool. Fixed15 remains a benchmark/history reference only.

## Frozen OLS evaluation convention

Reuse the current OLS feature construction and D2/trend ranking code. Monthly Universe admission is decided at month start; once an ETF is admitted for that month, do not re-run the broad full-market liquidity/listing admission filter every day. Within the fixed monthly Universe, OLS ranking uses the frozen score/trend/D2 logic.

`511220` remains the explicit cash signal and should be handled consistently across K so the experiment does not confound Universe width with whether a cash option exists.

## First-batch outputs

At minimum produce:

- monthly parent-pool snapshots;
- sampled-Universe detail with deterministic IDs/seeds;
- monthly x K distribution: mean, median, P10/P25/P75/P90, best/worst diagnostics;
- probability that a random same-K Universe enters the month's pooled top decile;
- MDD, switch count, observed Top1 tenure;
- winner coverage and dormant-member share;
- prior-120d pairwise-correlation summary and effective independent count;
- nested 15->3 paired deletion deltas;
- Top1 admission event table retaining score, R2, slope, Top1-Top2 gap, replacement date and forward 1/3/5/10/20-day returns for Stage 2.

## Interpretation contract

Do not select a precise historical optimum K from the first run. A size effect is interesting only if the **distribution** shifts across many months/eras. In particular test both possible forces:

- large K may intensify ranking competition and cause late trend admission / short remaining life;
- very small K may lose winner coverage or allow mediocre trends to win.

If no stable K range appears, record that result rather than forcing an inverted-U story.

## Next operational step

Implement the monthly Monte Carlo runner and GitHub Actions workflow using the existing `full_market_ols_storage.py`, `walk_forward_dedup.py`, and earlier `universe_width_oracle_v1.py` mechanics. The first Action should be sized as a long batch: full available monthly history, full K grid, many same-K samples plus multiple nested K=15 deletion paths. After the artifact arrives, analyze it before changing any thresholds or definitions.
