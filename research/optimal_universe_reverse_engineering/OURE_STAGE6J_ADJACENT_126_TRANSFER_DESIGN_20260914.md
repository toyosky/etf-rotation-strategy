# OURE Stage6J — Adjacent 126-Session RF Mapping Transfer

Date: 2026-09-14
Status: preregistered

## Question
Stage6I showed that within a fixed future 126-session block, the frozen whole-K30 feature map is often learnable by family-grouped RF. This does **not** imply deployability. Stage6J asks the strict chronological question:

> After one 126-session block has completely finished and its labels are known, can the RF learned from that block rank K30 Universes in the immediately following 126-session block?

## Leakage control
Calendar half-years are not used because 126 trading sessions starting in January can end after July 1. Instead, create consecutive non-overlapping 126-session future blocks beginning on the first trading session on/after 2022-01-01. Block `b+1` starts only after block `b` has completely finished. Thus all labels used to train the previous-block model are known before the next decision date.

At each block start `t`:
- candidate pool is point-in-time available via the frozen Stage5 availability rule;
- X uses exactly the trailing 126 completed sessions `[t-126,t)`;
- Y is frozen downstream OLS log wealth over exactly the next 126 sessions `[t,t+126)`;
- K=30 noncash members; cash handling remains frozen downstream;
- candidate K30 library generation and the 19 whole-set features are exactly the Stage6I definitions;
- RF parameters are exactly Stage6I: 800 trees, depth 7, min leaf 10, sqrt max_features, bootstrap, seed 20260914;
- no symbol/name/sector identity features.

## Primary transfer
For every test block after the first:
1. train one RF on **all** K30 samples from the immediately preceding completed block;
2. freeze it;
3. score all K30 samples generated at the next block start from that next block's X<=t features;
4. only then compare predictions with the next block's realized future126 Y.

Primary metrics per transition:
- Spearman rank IC between RF prediction and realized future log wealth;
- mean realized percentile of predicted Top50;
- predicted top-decile realized-log lift over the test-library mean.

## Frozen aggregate gate
The adjacent-transfer hypothesis passes only if all hold:
1. median transition Spearman > 0.10;
2. at least 2/3 of transitions have Spearman > 0;
3. median predicted-Top50 realized percentile > 0.60;
4. median predicted-top-decile log lift > 0.

No threshold may be changed after results are seen.

## Secondary diagnostics
- expanding-history RF: train on all fully completed prior blocks and test the next block;
- current-block `past126_log_growth` ranking as a simple X<=t benchmark;
- feature importance drift, descriptive only.

Secondary results cannot rescue a failed primary adjacent-transfer gate.

## Interpretation
- PASS: the previous block contains enough mapping information to guide the next block; only then may an RF-guided K30 combinatorial search be preregistered.
- FAIL: Stage6I remains an oracle/within-period structure result, not a deployable selector. Do not tune RF parameters/features/horizon to rescue Stage6J; next work, if any, must isolate genuinely cross-period-stable submappings with strict chronological OOS.
