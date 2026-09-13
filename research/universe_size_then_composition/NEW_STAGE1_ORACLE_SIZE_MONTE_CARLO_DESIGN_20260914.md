# New Stage 1 — Oracle Universe Size Monte Carlo

Date: 2026-09-14
Status: STARTED

## Purpose

Test a deliberately narrow hypothesis before any new membership model is built:

> Does Frozen OLS have a structurally favorable Universe-size range, independent of the exact ETF identities?

This stage does not seek a tradable strategy. Future one-month outcomes may be used for Oracle evaluation, but only to diagnose structure.

## Why this is a new stage lineage

The prior variable-size MUV line allowed size and membership to move together. That makes attribution difficult: an improvement may come from smaller K, better members, or their interaction.

This new line freezes the order of questions:

1. measure the size effect;
2. explain the size effect;
3. freeze a defensible K range;
4. only then study membership selection.

## Parent pool

For each month t:

- construct the point-in-time tradable representative ETF set using only metadata and market information available by t;
- do not require membership in Fixed15;
- avoid duplicate exposure inflation using the already-frozen representative-universe logic where possible;
- preserve the exact monthly parent-pool snapshot used for each run.

## K grid

Primary target: K = 3..30, clipped when the monthly parent pool is smaller.

Do not infer a preferred K from one period and then narrow the grid before the first complete Stage 1 run.

## Sampling design

### Primary evidence: independent same-K samples

For every month and every K:

- independently sample many Universes of exactly K ETFs;
- use fixed and recorded RNG seeds;
- sample count should be large enough for stable distribution summaries, subject to compute budget;
- where the combinatorial space is small, enumerate all subsets.

This is the main test of whether smaller/larger Universes are generally better.

### Secondary evidence: nested deletion paths

Generate multiple independent starting Universes and repeatedly delete one member until the lower K bound.

Use these only to estimate local K -> K-1 effects. Do not use one deletion path as evidence for a universal size effect.

## Frozen downstream evaluator

Every sampled Universe must use the same downstream OLS rotation logic. No changes to:

- OLS score construction;
- eligibility rules;
- ranking rule;
- signal execution convention;
- evaluation horizon.

The evaluator should be shared across all K values to avoid implementation drift.

## Required monthly-by-K outputs

For OLS portfolio value / return distribution:

- N sampled Universes;
- mean;
- median;
- P10 / P25 / P75 / P90;
- best and worst only as diagnostics, never primary evidence;
- probability that a random Universe at K lands in the month's top decile across all tested Universes;
- MDD distribution;
- switch count distribution;
- observed Top1 tenure distribution.

## Required set-state outputs

For each sampled Universe also capture:

- mean / median / high-quantile pairwise correlation;
- first principal-component variance share;
- effective N;
- asset-class breadth;
- region breadth;
- OLS score breadth and strong-trend count;
- Top1 switching rate;
- rank turnover;
- winner coverage;
- dormant-member share.

These variables are not assumed causal. They are collected so New Stage 2 can test mechanisms.

## Remaining-life data contract for Stage 2

Stage 1 should retain enough event-level history to reconstruct every Top1 admission later.

For each first Top1 admission event within a sampled monthly Universe, preserve at minimum:

- month;
- K;
- Universe id / seed;
- symbol;
- admission date;
- score;
- R2;
- slope;
- Top1 minus Top2 score gap;
- observed replacement date;
- forward 1/3/5/10/20-day returns when available.

Do not yet optimize the definition of the ETF's own trend episode. That definition must be frozen separately at the start of New Stage 2.

## Primary Stage 1 decision rule

A size effect is considered structurally interesting only if the distribution, not merely the best Oracle subset, shifts with K across a meaningful fraction of months/eras.

Evidence for an intermediate favorable range requires both:

- deterioration for materially larger K; and
- deterioration or materially worse opportunity coverage for sufficiently small K.

If the preferred K varies heavily across months, Stage 1 should report that instability rather than average it away. New Stage 2/3 may then test whether observable set/market state explains the variation.

## Existing precursor to reuse carefully

`research/universe/universe_width_oracle_v1.py` already contains useful mechanics for random/exhaustive width distributions and nested deletion logic. Reuse code where appropriate, but do not reuse its Fixed15-only/limited-period assumptions as the Stage 1 design.

## Stage 1 completion criteria

Stage 1 is frozen only when the repository contains:

- runnable code;
- fixed config and RNG seeds;
- input-data version / monthly parent-pool snapshots;
- monthly-by-K distribution tables;
- event-level Top1 admission dataset sufficient for Stage 2;
- a findings note stating whether a stable size effect is visible, without tuning K after seeing later stages.
