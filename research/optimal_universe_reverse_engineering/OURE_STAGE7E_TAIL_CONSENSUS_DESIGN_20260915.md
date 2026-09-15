# OURE Stage7E — Tail-Consensus Mechanism Test

Date: 2026-09-15
Status: preregistered before Stage7E outcome inspection

## Motivation
Stage7D found that broad candidate rankings across the three 126-session history blocks are weakly related, while the frozen Robust30 winner is simultaneously extreme in all three histories. Stage7E tests whether future Universe value is concentrated among candidates that remain strong even in their weakest historical block.

This stage is diagnostic only. It does not change the frozen deployment baseline:

`3 x 126-session history -> frozen robust score -> K30 -> hold Universe 126 sessions -> downstream OLS Top1`.

## Frozen data and candidate semantics
- same six Stage7A/7B/7C OOS 126-session target blocks;
- same eligible pools;
- same candidate-family generation;
- same seed `20260914 + block_no*1009`;
- same K=30;
- same future set-value definition;
- no new asset filters, no alternative K, no alternative horizon.

## Signals compared
For every candidate Universe in each target block, compute from the three past-only historical rank percentiles r1, r2, r3:

1. `robust_score` — frozen score: 0.5 * median(r) + 0.5 * q25(r).
2. `rank_mean` — mean(r1,r2,r3).
3. `min_rank` — min(r1,r2,r3), the weakest historical block.
4. `q25_rank` — 25th percentile of the three ranks.
5. `second_worst_rank` — middle order statistic of the three ranks.
6. `all3_strength` — geometric mean of clipped ranks, used only as a continuous consensus diagnostic.

No signal replaces the frozen robust score in Stage7E.

## Primary mechanism test: monotonic tail-consensus gradient
Within each target block, sort candidates by `min_rank` and divide them into fixed deciles (D1...D10, D10 strongest weakest-block rank). For each decile compute:
- mean future rank percentile;
- median future rank percentile;
- mean future log growth;
- share of candidates in the future top decile.

Then aggregate decile statistics equally across target blocks.

Primary support criteria are preregistered as:
1. pooled decile-level Spearman between decile number and mean future-rank percentile > 0;
2. D10 mean future-rank percentile > D1 mean future-rank percentile;
3. D10 future-top-decile hit share > D1 hit share;
4. at least 4 of 6 target blocks have positive candidate-level Spearman between `min_rank` and future value.

If all four hold, `tail_consensus_supported`; if exactly two or three hold, `partial_support`; otherwise `not_supported`.

## Secondary signal comparison
For each signal report per-block and median:
- Spearman with future log growth;
- mean future rank percentile of signal Top50;
- mean future rank percentile of signal top decile;
- actual future percentile of the signal-selected Top1.

This comparison is descriptive. Stage7E must not promote another scoring formula merely because it has a higher median on the same six blocks.

## Robust-score alignment
Measure how the frozen robust score relates to tail consensus:
- Spearman(robust_score, min_rank);
- overlap between robust Top50 and min_rank Top50;
- percentile of the frozen robust winner under min_rank;
- fraction of robust Top50 candidates that are also in min_rank top decile.

Purpose: determine whether the frozen score works partly by enforcing a strong lower bound across regimes rather than only rewarding average historical strength.

## Guardrails
- No threshold tuning based on Stage7D's observed ~0.90 winner floor.
- Fixed deciles are used instead of a chosen percentile cutoff.
- No changes to frozen Stage7C/A deployment specification.
- No rescue variants after outcome inspection.
- Findings must distinguish mechanism evidence from independent deployment validation.

## Deliverables
- `oure_stage7e_tail_consensus.py`
- frozen GitHub Actions workflow
- candidate-level diagnostics and decile table
- signal-comparison table
- frozen findings with verdict: `tail_consensus_supported`, `partial_support`, or `not_supported`.
