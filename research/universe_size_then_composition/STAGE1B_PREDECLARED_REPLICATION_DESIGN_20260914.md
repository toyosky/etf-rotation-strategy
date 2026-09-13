# New Stage 1B — Predeclared replication batch

Date: 2026-09-14
Parent: New Stage 1 / Stage1A

## Why this batch exists

The first successful corr=0.95, seed=20260914 batch shows a descriptive era reversal: increasing K is broadly unfavorable in 2021–24 and broadly favorable in 2025–26. This is not yet a stable-K conclusion.

Only two previously allowed robustness checks are run here. No threshold grid, K tuning, OLS change, horizon change, or feature search is permitted.

## Replication A — alternative seed

Purpose: test Monte Carlo convergence under the same parent pool.

- corr_threshold: 0.95
- seed: 20260915
- independent samples per K per month: 120
- K: 3..30, subject to monthly availability
- nested deletion paths: 0; the paired-delete evidence is already supplied by the frozen primary batch and is not needed for seed replication
- Frozen OLS and execution semantics: unchanged

## Replication B — predeclared correlation sensitivity

Purpose: test whether the K/return shape and era reversal depend materially on the representative-pool dedup threshold.

- corr_threshold: 0.90
- seed: 20260914
- independent samples per K per month: 120
- K: 3..30, subject to monthly availability
- nested deletion paths: 0
- Frozen OLS and execution semantics: unchanged

## Required comparison

For each replication compare against the primary batch using equal-month-weighted K curves:

- year-by-year K slope;
- 2021–24 and 2025–26 K slope;
- broad bands K=3..7, K=8..15, K=16..30;
- sign of high-minus-low return difference;
- switching, observed Top1 tenure, winner coverage, dormant share and effective N by K.

Alternative-seed replication is considered convergent if the broad shape/era sign is preserved; no numerical cutoff will be fitted after the fact.

The corr=0.90 run is a sensitivity check, not a candidate threshold selection. A favorable result at 0.90 cannot be used to replace 0.95 on this history.

## Branch rule

- If the era reversal survives both replications, do not freeze one global K range. Proceed to Stage2 mechanism analysis with regime dependence treated as a primary hypothesis.
- If seed replication fails, keep Stage1 open and diagnose Monte Carlo instability before any mechanism conclusion.
- If seed replication succeeds but corr=0.90 reverses the result, keep Stage1 open and classify parent-pool construction sensitivity as a major uncertainty.
