# OURE Stage7A — Robust K30 Across Prior Regimes, Strict OOS

Date: 2026-09-15
Status: preregistered before outcome inspection

## Question
Can a K30 Universe selected for **robust performance across several already-completed 126-session market blocks** generalize better to the next 126-session block than a K30 selected by the latest block alone or by the previous-block RF?

This stage deliberately changes the objective. It does **not** attempt to predict the next regime or the next exact winner. It asks whether a Universe that preserves value across several different historical regimes is a better opportunity set for the frozen downstream OLS.

## Frozen chronology
Reuse the strict non-overlapping Stage6K calendar blocks B01..B09 (126 sessions each).

Targets are B04..B09. For target block Bj, only the immediately preceding three fully completed blocks are used:
- B01+B02+B03 -> select for B04;
- B02+B03+B04 -> select for B05;
- ...;
- B06+B07+B08 -> select for B09.

No target-block outcome may enter candidate generation, scoring, filtering, or model training.

## Candidate maturity / common-pool rule
For each target Bj, define a common candidate pool as the intersection of the point-in-time available ETF pools at the starts of the three training blocks and the target block. This ensures every member of every tested K30 was actually available throughout all three historical robustness blocks and at the target decision date.

All compared rules operate on the **same target-specific K30 library**. This maturity restriction is part of Stage7A and must not be relaxed after inspecting results.

## Target-specific K30 library
Using only target-decision past data and the common pool, build the same deterministic Stage6G/6K family library machinery:
- K=30 noncash ETFs;
- same singleton-past shortlist logic;
- same diverse family bases, mutations, and broad random controls;
- same frozen seed 20260914.

The library is generated without target future outcomes.

## Historical block values
For every candidate K30 U in a target library, replay the frozen downstream OLS separately over each of the preceding three complete blocks and record log-growth:

`V1(U), V2(U), V3(U)`.

Within each historical block, convert values to cross-sectional percentile ranks among the same candidate library:

`Pj(U) = RankPct(Vj(U))`, where 1 is best.

## Primary robust score
Freeze the score before results:

`Robust(U) = 0.5 * median(P1,P2,P3) + 0.5 * Q25(P1,P2,P3)`.

This rewards typical quality while penalizing a weak regime without using a pure minimum, which would be excessively sensitive to one block.

No alternate weights, windows, quantiles, or thresholds are authorized in Stage7A.

## Baselines
All baselines rank the exact same K30 target library.

1. `latest126`: log-growth in the most recent completed block only (V3).
2. `previous_block_rf`: the frozen Stage6K first-layer RF trained only on the immediately previous completed standard Stage6K block, applied to target-decision 19-feature rows for this target library.
3. `random`: random choice from the same K30 library, summarized through a fixed-seed path simulation; random is descriptive, not a model-selection benchmark.

## OOS evaluation on target block
For robust, latest126, and previous-block RF report per target:
- Spearman(score, target future log-growth);
- Top50 mean target actual percentile;
- top-decile target log-growth lift vs full target library;
- selected Top1 target actual percentile;
- selected Top1 target total return;
- selected Top1 target log-growth.

Across B04..B09 also report:
- median Spearman and positive-block count;
- median Top50 actual percentile;
- median selected-Top1 actual percentile;
- compounded selected-Top1 path return/log-growth;
- worst selected-Top1 block return;
- random-path percentile of the robust path.

## Frozen primary support gate
Stage7A is considered `robust_selection_supported` only if ALL hold across B04..B09:
1. robust median Spearman > +0.10;
2. robust Spearman positive in at least 4/6 target blocks;
3. robust median Top50 actual percentile > 0.55;
4. robust median selected-Top1 actual percentile > 0.60;
5. robust selected-Top1 compounded log-growth exceeds BOTH latest126 and previous-block-RF paths, AND its worst target-block return is less negative / more positive than BOTH baselines' worst blocks.

If 3-4 conditions pass, classify `mixed_robust_signal`; if <=2 pass, classify `robust_objective_not_supported`.

## Interpretation constraints
- A pass would support the new objective: construct a robust opportunity set rather than forecast the exact next regime. It would not yet authorize tuning K, the 3-block window, the 50/50 score, or adding Qualified Challenger features.
- A broad-rank pass with Top1 failure would be interpreted as another optimizer/top-tail problem, not as evidence to tune the score.
- A fail would mean that simple cross-regime historical robustness, as frozen here, is insufficient; do not rescue it by trying many windows/weights on the same history.
