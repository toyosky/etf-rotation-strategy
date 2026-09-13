# New Stage 3B — Conservative Size Fallback Audit

Date: 2026-09-14
Parent: New Stage3 frozen failure
Status: frozen design before Stage3B outcome inspection

## Purpose

Stage3 rejected low-DoF point-in-time prediction of next-month size direction. Stage3B does not add model capacity. It asks whether any conservative history-only size adaptation is worth preserving before member selection.

## Inputs

Use only the frozen New Stage1 base batch `monthly_k_distribution.csv` from run `34772895471`.

For each month and K=3..30, use the Stage1 Monte Carlo `return_mean` as the size-only expected value diagnostic. No new Monte Carlo samples, correlation threshold, seed, feature, or outcome definition is introduced.

## Policies / diagnostics

Evaluation begins only after 24 prior months.

1. `anchor_k15`
   - K=15 every month.
   - K=15 is pre-existing from the original Fix15 cardinality and Stage1 nested 15→3 design; it is not selected from Stage3 results.

2. `expanding_train_best_k`
   - before month t, compute each K's mean Stage1 `return_mean` over all prior months only;
   - choose the K with highest prior-history mean;
   - deterministic ties choose the smaller K;
   - evaluate that chosen K on month t.
   - This is a history-only benchmark, not a point-in-time state model.

3. `one_se_training_range`
   - over prior months only, compute mean and standard error of monthly `return_mean` for each K;
   - identify training-best K b;
   - threshold = mean_b - SE_b;
   - admissible set = all K whose training mean is at least that threshold;
   - report min K, max K, width, median K and month-to-month range stability;
   - the range is diagnostic only in Stage3B and is not optimized against current-month outcomes.

4. `hindsight_best_k`
   - per-month best K from the current month's Stage1 distribution;
   - diagnostic ceiling only, never executable.

## Primary comparisons

For the 44 expanding OOS months, compare:
- mean and median current-month return_mean;
- cumulative sum of log1p(return_mean), where valid;
- paired monthly delta of `expanding_train_best_k - anchor_k15`;
- month-cluster bootstrap confidence interval for that paired delta;
- chosen-K stability and turnover;
- one-SE range width/stability;
- results separately for 2023–24 and 2025–26 OOS periods.

## Interpretation rule

If expanding training-best K does not produce a stable positive paired advantage over the pre-existing K=15 anchor, freeze the size layer to the conservative K=15 anchor for the next member-selection stage. This is a weakened engineering choice, not a claim that K=15 is globally optimal.

If training-best K does show a stable advantage, retain only the history-only expanding selection or its one-SE range as the permitted size mechanism. Do not reopen Stage3 feature search.

Stage3B cannot promote hindsight best K or choose a new fixed K from the full sample.