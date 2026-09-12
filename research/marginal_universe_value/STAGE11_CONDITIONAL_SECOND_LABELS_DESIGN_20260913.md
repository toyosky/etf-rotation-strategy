# Stage 11 — Conditional second-order retention labels

Date frozen: 2026-09-13

## Motivation

Stage 9 showed large second-removal Oracle headroom. Stage 10 showed that transporting the first-order Fixed15 model into `Fixed15-1` fails badly and ranks second removals worse than random.

Therefore the next correction is to change the label domain, not tune the Stage-10 threshold.

## Unit of observation

`label_month × first_removed_i × second_candidate_j`

where both `i` and `j` are non-cash Fixed15 constituents and `i != j`.

The first-removal state is hypothetical for label generation. It is allowed only if `i` was a valid first-order retention sample in that month. This avoids manufacturing removal states for instruments that had not accumulated sufficient point-in-time history.

## Conditional label

Let `U = Fixed15`, with cash signal 511220 always retained.

After hypothetical first removal `i`:

`U1 = U - {i}`

For second candidate `j`:

`MUV2(j | U1) = V(U1) - V(U1 - {j})`

Positive means retaining `j` helped the next-month portfolio; negative means deleting `j` would have improved it.

All portfolio execution conventions, transaction costs and OLS ranking rules remain frozen from V1.

## Features

All X variables are recomputed under `U1` using information available on the month-end as-of date only.

The Stage-10 reduced-universe X representation is reused so that Stage 11 changes the target domain rather than simultaneously inventing a new feature search.

Additionally store three execution-state variables known at decision time:

- `prev_target`
- `first_removed_is_prev_target`
- `second_candidate_is_prev_target`

These are stored because conditional deletion value can include forced-switch transaction-cost effects.

## Path labels

Reuse V1.2 path diagnostics for the second candidate under `U1`:

- direct selection days / episodes
- target-changed days
- beneficial / harmful changed days
- spillover diagnostics

These are outcomes and must never enter same-date X.

## Stage-11 objective

Stage 11 is diagnostic only. Do not fit or tune a second-step production policy yet.

Primary diagnostics:

1. conditional second-order zero / positive / negative mass;
2. path-active rate;
3. sign flip between `MUV(j | Fixed15)` and `MUV2(j | Fixed15-i)` where both are non-zero;
4. first-order zero -> conditional non-zero transitions;
5. first-order non-zero -> conditional zero transitions;
6. within `month × second_candidate`, dispersion across different first removals;
7. same diagnostics restricted to the actual Stage-7 first-removal states.

## Anti-overfitting constraints

- No random train/test split.
- No feature search in Stage 11.
- No Stage-10 threshold tuning.
- No policy selection based on Stage-11 outcomes.
- Future modeling must use time-forward validation.
- Because many rows share the same month, future model fitting must use month-level weighting or clustering so the expanded counterfactual panel does not create fake sample size.
