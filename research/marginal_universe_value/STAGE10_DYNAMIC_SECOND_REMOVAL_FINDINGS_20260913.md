# Stage 10 — Dynamic second-removal transport test findings

Date: 2026-09-13

## Frozen question

Can the Stage-7 first-order Fixed15 model be transported directly to a reduced universe (`Fixed15 - first removal`) if universe-dependent X features are recomputed, without retraining on reduced-universe labels or tuning a new threshold?

## Result: FAIL

The GitHub Actions run completed successfully, but the predictive transport test failed economically and against the random control.

### Policy outcome

- Stage-7 first-action months: 16
- Stage-10 second actions: 10 (62.5% of first-action months)
- Beneficial second actions: 1
- Harmful second actions: 2
- Zero-effect second actions: 7
- Sum realized second-step improvement: -11.45 percentage points
- Captured negative second-step retention value: +7.81 pp
- False-removal regret: -19.26 pp
- Maximum single false-removal regret: -18.36 pp

### Wealth

- Fixed15 final wealth: 6.8039
- Stage 7 final wealth: 8.8879
- Stage 10 final wealth: 8.0677
- Stage 7 vs Fixed15: +30.63%
- Stage 10 vs Fixed15: +18.57%
- Stage 10 incremental terminal wealth vs Stage 7: -9.23%

### Random second-removal control

5,000 random controls matched to the same 10 second-action months:

- Random mean incremental terminal wealth vs Stage 7: +4.47%
- Random median: +4.19%
- Probability random second deletion beats Stage 7: 72.22%
- Probability random matches or beats Stage 10: 91.36%
- Stage 10 percentile in random distribution: 8.64%

This is particularly important: Stage 10 did not merely fail to add value; its candidate ranking was materially worse than random in this test.

### Period split

2023–2024:
- second actions: 7
- incremental terminal wealth vs Stage 7: -16.00%
- false-removal regret: 19.26 pp

2025–2026:
- second actions: 3
- incremental terminal wealth vs Stage 7: +8.07%
- false-removal regret: 0

The result is therefore regime-unstable and cannot be rescued by aggregate performance.

## Dominant failure event

2024-09:

- first Stage-7 removal: 518880
- Stage-7 monthly return: +20.94%
- Stage-10 second removal: 159915
- Stage-10 monthly return: +2.58%
- false-removal regret: 18.36 pp

This single event is exactly the asymmetric tail-risk pattern Stage 7 was designed to prevent at the first step, showing that the original Fixed15 safety calibration does not transport to the reduced-universe domain.

## Interpretation

Stage 9 proved that a valuable second-removal opportunity usually exists. Stage 10 proves that the *first-order* Fixed15 mapping is not a valid estimator of the *conditional second-order* marginal value after another ETF has already been removed.

The failure is therefore not evidence that sequential universe reduction is useless. It is evidence of a target/domain mismatch:

`MUV(j | Fixed15)` is not interchangeable with `MUV(j | Fixed15 - i)`.

Recomputing only X after the first removal is insufficient, because the label-generating competition structure itself has changed.

## Frozen correction

Do **not** tune a new Stage-10 threshold on these results.

Next step: build a proper conditional second-order label panel:

`month × first_removed_i × second_candidate_j`

with label:

`MUV2(j | U-i) = V(U-i) - V(U-i-j)`

and X recomputed under `U-i`, using only decision-time information.

The immediate next stage is diagnostic only: quantify how much first-order and conditional second-order labels differ, including sign flips, zero/nonzero transitions, path activity, and within-month interaction dispersion. Only after that diagnostic should a new second-step predictive model be considered.
