# OURE Stage6K — Prospective 2026H2 Directional Transfer Design

Date: 2026-09-14
Status: preregistered prospective / label-blind

## Purpose
Stage6J formally failed its primary last-3 RF ensemble top-tail gate, while the preregistered diagnostic `last3_unanimous_direction` showed stronger broad ranking and Top50 behavior. Because all complete periods through 2026H1 have now been inspected, none of them can serve as a clean confirmatory sample.

Stage6K converts that diagnostic into a genuinely prospective test by freezing the rule and storing the full 2026H2 K30 candidate ranking **before the 2026H2 future-126-session label is complete**.

All data through 2026H1 are development data. 2026H2 is the first promotion test.

## Decision point and horizon
- decision point: first trading session on or after 2026-07-01;
- K = 30;
- X window = 126 sessions strictly before the decision date;
- future evaluation horizon = next 126 sessions from the decision point;
- downstream OLS remains frozen;
- evaluation must not occur until all 126 future sessions exist.

## Frozen candidate library
At the 2026H2 decision point:
- use the same point-in-time eligible-pool logic as Stage6I;
- use the same Stage6G/6I K30 family-library construction constants and seed 20260914;
- compute the same frozen 19 whole-Universe features from the past 126 sessions;
- store members and X values now.

The stored candidate file, not a later regenerated library, is the evaluation universe.

## PRIMARY mapping rule — frozen Stage6J R3
Historical mapping periods are exactly:
- 2025H1;
- 2025H2;
- 2026H1.

For each of the frozen 19 features:
1. calculate feature-vs-future-126 log-wealth Spearman within each of those three completed historical periods;
2. retain the feature only if all three finite correlations have the same strict sign;
3. use only the sign, never correlation magnitude;
4. on the stored 2026H2 candidate cross-section, percentile-rank each retained feature and center it at 0.5;
5. equally average signed centered ranks.

No minimum-correlation threshold, importance filter, feature search, weighting, or state gate is allowed.

The retained features/signs and every candidate's score are written to the prospective artifact now, before future labels complete.

## Frozen secondary benchmark
Also store a `previous_period_rf` prediction trained only on completed 2026H1 using the exact frozen Stage6I RF parameters. This is secondary and cannot rescue the primary rule.

## Prospective primary gate
Once the next 126 sessions are fully available, evaluate the already-stored primary ranking. Stage6K passes only if all three hold:
1. Spearman(primary score, future126 log wealth) > +0.10;
2. predicted Top50 mean actual future percentile > 0.55;
3. predicted top-decile mean future log wealth minus all-candidate mean future log wealth > 0.

No threshold may be changed after the prediction artifact is created.

## Search authorization
Even a Stage6K pass does not retroactively validate Stage6J. It would provide the first genuinely prospective evidence that a low-DoF transferable component of the K30 value surface can be estimated at t.

Only after Stage6K passes may a separate later stage preregister an RF/directional-surrogate-guided K30 combinatorial search. The searcher, multistart/swap mechanics and OOD penalties must be frozen before its own future-period evaluation.

If Stage6K fails, freeze current data/history as insufficient for dynamic K30 construction under low-DoF mapping transfer and do not increase model capacity.
