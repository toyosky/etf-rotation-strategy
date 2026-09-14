# OURE Stage6K — Strict Adjacent 126→126 RF Transfer

Date: 2026-09-14
Status: preregistered

## Question
Can a K30 value mapping learned from one fully completed 126-trading-session block guide the immediately following 126-session block?

This is the first direct test of the user's deployability question: previous block -> next block.

## Time construction / no label overlap
Use consecutive, non-overlapping 126-session future blocks beginning at the first trading session on/after 2022-01-01.

For block b starting at t_b:
- X_b uses exactly [t_b-126, t_b);
- Y_b is frozen downstream OLS log wealth over exactly [t_b, t_b+126);
- block b+1 starts at t_b+126, after every Y_b observation is fully realized.

Thus the previous-block model is actually trainable at the next decision time. Calendar H1/H2 boundaries are deliberately avoided because a 126-session January target can finish after July 1.

## Frozen model/data definitions
- K=30 noncash members; downstream cash semantics frozen.
- Candidate pool: frozen Stage5 point-in-time availability rule.
- Candidate K30 library: frozen Stage6G/6I family library generator.
- Features: exactly the frozen Stage6G/6I 19 whole-K30 features from trailing126.
- RF: exactly Stage6G/6I parameters: 800 trees, max_depth=7, min_samples_leaf=10, max_features=sqrt, bootstrap=True, seed=20260914.
- Target: continuous future126 log wealth.
- No symbol/name/sector identity features.
- No tuning after outcomes.

## Primary rule
For each transition b -> b+1:
1. fit RF on all K30 samples and realized labels from block b only;
2. compute X<=t features for the block b+1 candidate library;
3. predict block b+1 K30 values;
4. after block b+1 is realized, evaluate ranking.

Metrics per transition:
- Spearman rank IC;
- predicted Top50 mean realized percentile;
- predicted top-decile realized-log lift over test-library mean.

## Frozen primary gate
PASS only if all hold across all available adjacent transitions:
1. median Spearman > 0.10;
2. positive Spearman share >= 2/3;
3. median predicted-Top50 realized percentile > 0.60;
4. median predicted-top-decile log lift > 0.

## Secondary diagnostics
- expanding-history RF trained on all previous fully completed blocks;
- current-block past126_log_growth ranking as a simple X<=t benchmark;
- per-transition feature importance drift from the previous-block RF, descriptive only.

Secondary diagnostics cannot rescue a failed primary previous-block-only gate.

## Interpretation
PASS permits preregistration of an RF-guided combinatorial K30 search with OOD safeguards and later truly unseen evaluation.
FAIL means Stage6I proves within-period/oracle cross-sectional structure, but not historical deployability. Do not tune RF/features/horizon to rescue this stage.
