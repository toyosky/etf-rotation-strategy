# Stage 17 — Local Relation Structure Audit

Date: 2026-09-13

## Question

Stages 15–16 established a hurdle:

1. point-in-time state can identify whether an ETF is likely to matter to the next-month OLS path;
2. conditional on path activity, signed MUV remains weakly identified.

Stage 17 tests a narrower mechanism suggested by the conditional-value interpretation:

> Is the sign of active MUV better identified when the candidate/incumbent is represented **relative to the local alternative it competes with**, and when the meaning of state gaps is explicitly conditioned on redundancy with that alternative?

This is not a new strategy backtest and does not change retention/admission policy.

## Frozen data contract

Use the existing V1.3/V1.4 retention-label panel and only point-in-time columns already present before the next-month label is observed.

Restrict sign modeling to rows with `path_direct_selection_days > 0`.

Walk-forward remains monthly expanding, with OOS evaluation beginning 2023-01.

## Frozen baseline

Reproduce Stage 3's fixed pairwise sign model using the existing ten local-alternative features:

- pair_score_exact_gap_alt
- pair_r2_gap_alt
- pair_current_resid_gap_alt
- pair_ret10_gap_alt
- pair_ret20_gap_alt
- pair_efficiency10_gap_alt
- pair_vol20_gap_alt
- pair_ma10_dist_gap_alt
- pair_corr120_with_alt
- pair_top3_freq20_gap_alt

Model: LogisticRegression, L2, C=1.0, fixed.

No hyperparameter search.

## Frozen mechanism interactions

Add exactly four interactions, chosen ex ante from the economic mechanism rather than from outcome inspection:

1. `score_gap_x_corr` = pair_score_exact_gap_alt × pair_corr120_with_alt
2. `resid_gap_x_corr` = pair_current_resid_gap_alt × pair_corr120_with_alt
3. `ret20_gap_x_corr` = pair_ret20_gap_alt × pair_corr120_with_alt
4. `top3_gap_x_corr` = pair_top3_freq20_gap_alt × pair_corr120_with_alt

Interpretation:

- when correlation is high, an apparent score/trend advantage is more likely to be a substitution contest;
- when correlation is low, the same gap may represent differentiated exposure rather than direct displacement;
- the interactions therefore test whether relation structure changes the sign meaning of otherwise identical local gaps.

No other interactions may be added in Stage 17.

## Evaluation

Report, OOS and separately for 2023–24 / 2025–26:

- active sign ROC AUC;
- Brier score;
- false-negative positive-regret sum using the model-native 0.5 probability split;
- correct-negative value sum;
- largest positive miss;
- prediction count.

Also report the delta of the relation-interaction model versus the frozen pairwise baseline.

## Pre-frozen interpretation rule

Evidence for the relation-structure hypothesis requires:

1. sign AUC improvement in **both** 2023–24 and 2025–26;
2. false-negative positive-regret sum not worsening in either period;
3. no reliance on selecting a subset, cutoff, asset class, or favorable month after seeing outcomes.

If only full-sample AUC improves, or one period improves while the other degrades, conclude that these low-order local interactions do not stably identify signed MUV.

If the test fails, do not add more interactions immediately. The next research decision should instead ask whether the relevant state is a broader local-neighborhood / path-displacement object rather than a single incumbent-vs-alternative pair.

## Anti-overfitting constraints

- no new label definition;
- no future realized replacement identity in X;
- no threshold search;
- no interaction search;
- no model-class search;
- no policy backtest;
- no conclusion from historical wealth alone.
