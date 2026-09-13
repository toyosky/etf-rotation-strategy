# Stage 13 — Bootstrap uncertainty / abstention design

Date frozen: 2026-09-13

## Motivation

Stage 12 shows that another point classifier does not solve the economically dominant failure mode. Some rare large future winners are assigned low `p(active)`, negative expected MUV, low safety risk, and low direct tail risk simultaneously.

The next hypothesis is therefore not "there is another better point predictor". It is:

> These apparently safe removals may still be epistemically uncertain because the fitted MUV model is unstable under plausible resampling of the limited historical months.

Stage 13 tests that hypothesis without changing the underlying Stage-A or pairwise model specification.

## Frozen bootstrap

For each OOS month `t` from 2023-01 onward:

1. Use only rows with `label_month < t`.
2. Resample prior **months as clusters** with replacement, preserving all ETF rows inside each sampled month.
3. For each bootstrap draw, refit the exact frozen Stage-A logistic and Stage-3 pairwise sign logistic.
4. Recompute the expanding positive/negative active-delta means inside the bootstrap sample.
5. Produce bootstrap expected MUV for every ETF in month `t`.

Number of draws: **300**.
Random seed is fixed and deterministic.

No feature search and no hyperparameter search.

## Uncertainty decision

For each ETF/month store:

- point expected MUV from frozen Stage 3
- bootstrap 10th percentile
- bootstrap median
- bootstrap 90th percentile
- bootstrap probability `MUV < 0`

Primary abstention rule, frozen before results:

`safe_to_remove_uncertainty = bootstrap_MUV_q90 < 0`

Interpretation: removal is allowed only if even the one-sided 90% upper uncertainty bound remains negative.

No optimized confidence level is tested.

## Evaluation

Primary diagnostics:

- share of realized positive-RV rows incorrectly classified safe
- share of Stage-12-style tail winners incorrectly classified safe
- share of realized negative-RV rows classified safe
- results for the known 2024-09 159915 and 2025-04 518880 cases
- uncertainty width for large hidden-winner failures vs ordinary rows

## Frozen policy overlays

Two policy diagnostics are allowed:

1. **Stage7 + uncertainty veto**: retain the exact Stage-7 selected symbol, but cancel the removal unless its bootstrap q90 < 0.
2. **UCB one-removal diagnostic**: among ETFs with point `muv_pairwise < 0` and q90 < 0, remove at most the one with the most negative point MUV. This is a diagnostic comparator, not a promoted production rule.

Success requires that the uncertainty rule materially reduces false-removal regret without eliminating most genuinely beneficial removals. If 2024-09 159915 still has q90 < 0, then the current state variables/model family are overconfident in a way that bootstrap resampling cannot detect; in that case the hard one-removal cap remains the main defensible safeguard.