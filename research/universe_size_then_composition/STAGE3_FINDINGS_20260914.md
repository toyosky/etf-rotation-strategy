# New Stage 3 — Conditional Size-Direction Identifiability Findings

Date: 2026-09-14
Source run: `34780943967`
Artifact: `universe-size-stage3-34780943967`
Status: frozen
Decision: reject low-DoF point-in-time size-direction identifiability

## Frozen question

Using only five pre-registered point-in-time features, can a fixed low-DoF expanding logistic model identify whether next-month Stage1 size contrast `mean_return(K30)-mean_return(K3)` is positive?

The five features, target, C=1.0, 24-month minimum training history, training-only standardization, and simple baselines were frozen before viewing the outcome.

## OOS result

There are 44 expanding OOS months.

Overall frozen model:
- sign accuracy: 45.45%
- balanced accuracy: 42.08%
- ROC AUC: 0.4625
- Brier: 0.2854

Baselines:
- expanding majority sign accuracy: 54.55%, balanced accuracy 50.0%, AUC 0.50
- previous-month sign accuracy: 47.73%, balanced accuracy 47.50%, AUC 0.475

The model does not improve on either simple baseline on discrimination/sign prediction.

## Era split

2021–24 OOS, n=24:
- model sign accuracy 45.83%
- balanced accuracy 38.89%
- AUC 0.4593
- majority accuracy 62.5%

2025–26 OOS, n=20:
- model sign accuracy 45.0%
- balanced accuracy 50.0%
- AUC 0.4545
- previous-month sign accuracy 60.0%, balanced accuracy 59.60%, AUC 0.5960

The later era does not rescue the frozen point-in-time model.

## Continuous diagnostic associations

Full-sample Spearman association with continuous size contrast is weak for every frozen feature:
- active_share_t: +0.061
- score_iqr_t: -0.123
- prior20_switch_rate_t: -0.017
- prior20_top1_tenure_t: +0.017
- mean_pairwise_corr120_t: +0.134

These are diagnostics only and are not used to select or replace features.

## Frozen conclusion

Stage1's regime-dependent size effect is real as a hindsight structural result, but the first pre-registered low-DoF point-in-time state does not identify its next-month direction in expanding OOS.

Do not rescue this result by feature search, threshold search, nonlinear models, neural networks, or alternative era cutoffs on the same history.

The research line therefore weakens the size problem before member selection. New Stage3B will test a conservative history-only fallback: retain pre-existing K=15 as the anchor, compare it with an expanding training-history best-K rule, and construct a one-standard-error historical admissible K range. This is a size-layer feasibility audit, not a claim that any exact K is known.