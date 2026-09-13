# New Stage 4 — Fixed-K15 Composition Structure Audit

Date frozen: 2026-09-14

## Purpose

Stage1–3B show that Universe size has real hindsight effects but no stable low-DoF point-in-time size selector. Stage3B therefore freezes K=15 as an engineering anchor only.

Before training a member selector, Stage4 asks whether **composition at fixed K=15** has enough downstream Frozen-OLS value headroom and enough structural stability to justify learnability work.

This is a structure/oracle audit, not an executable strategy.

## Frozen data

Use only the already-generated New Stage1 base artifact from run `34772895471`:

- `sampled_universe_detail.parquet`
- `monthly_k_distribution.csv`

Filter to `source == same_k_mc` and `k == 15`.

No new Monte Carlo draws, parent-pool rules, seeds, correlation thresholds, K search, OLS changes, or future-return labels are allowed in Stage4.

## Primary diagnostics

### 1. Composition headroom

For each month report the existing K15 randomized distribution:

- mean, median, P10, P90, best, worst
- P90 minus mean
- best sampled minus mean
- P90 minus P10

The sampled best is a finite-MC hindsight ceiling diagnostic only. It is not called the exact optimum.

### 2. Randomized member inclusion contrast

For each month and ETF symbol, use the random K15 assignments to calculate:

`inclusion_contrast = mean(return | symbol included) - mean(return | symbol excluded)`

Because K is fixed, this is interpreted as a **randomized replacement/inclusion contrast**, not an add-value Δ at variable set size and not an independent ETF-quality label.

Membership is parsed from the frozen `members` field. No symbol feature is used.

### 3. Split-half stability

Deterministically split each month's existing random universes by sorted `universe_id` alternating A/B. Recompute symbol inclusion contrasts separately in A and B.

For symbols with at least 3 included observations in each half, calculate within-month Spearman rank correlation between A and B contrasts. The support threshold 3 is frozen before results and is only a minimum mechanical stability requirement.

### 4. Adjacent-month stability

For consecutive months, compare full-sample inclusion contrasts for symbols present with at least 5 included observations in both months. Report Spearman correlation on the common symbols. The threshold 5 is frozen before results.

This tests whether composition value is persistent enough for a past-information member model to have plausible signal. Low adjacent-month stability is evidence against symbol-identity learning, not a reason to tune thresholds.

### 5. Era robustness

Summarize all diagnostics separately for 2021–24 and 2025–26. Month is the inference unit.

## Decision rule

Stage4 does not select members and does not optimize a threshold.

Proceed to Stage5 only if both conditions are qualitatively supported:

1. K15 composition headroom is economically nontrivial across many months/eras; and
2. inclusion-value structure has some reproducibility, either split-half within month or adjacent-month persistence, sufficient to justify a low-DoF X<=t identifiability test.

If headroom is small, stop composition optimization. If headroom is large but stability is weak, freeze the conclusion as a **composition identifiability bottleneck** and Stage5 must use a conservative/simple same-K baseline rather than escalating model capacity.

No post-result search over K, support thresholds, random seeds, member-count cutoffs, or model families is allowed in this stage.