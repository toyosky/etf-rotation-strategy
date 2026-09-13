# MUV Stage 19 — Dynamic Replacement Reachability Audit

Date: 2026-09-13

## Motivation

Stage18 established two mechanism facts:

1. monthly remove-one MUV is almost entirely generated on direct displacement days;
2. the month-end static local top-3 contains the realized dominant replacement only about half the time.

Therefore the next uncertainty is not primarily high-order spillover. It is replacement identity: which competitor will actually inherit the incumbent's winning days during the next month.

## Frozen Stage19 question

> Using only information available at the month-end decision time, can the recent pairwise OLS competition trajectory between incumbent `i` and candidate `j` rank the next-month realized dominant non-cash replacement better than the static month-end OLS-score ranking?

Stage19 is an identifiability audit. It is not a retention-policy backtest.

## Label

Reuse the V1.6 Stage18 outcome label:

`disp_direct_dominant_replacement`

No label semantics are changed. Future replacement identity remains outcome-only and never enters predictors.

Cash-dominant events are reported as coverage diagnostics but excluded from candidate-ranking evaluation in this first audit. They are a distinct `no risky replacement` outcome and will not be silently forced into an ETF candidate class.

## Candidate set

For every active incumbent-month event, rank every other non-cash Fixed15 risk ETF as a candidate replacement.

## Frozen predictor family

Use only the previous 20 trading days through the as-of close:

- current OLS score gap `score(j)-score(i)`;
- current qualification indicators for `i` and `j`;
- 20-day qualification fractions for `i`, `j`, and jointly;
- pairwise score-gap mean, standard deviation and slope;
- score-gap zero-crossing count;
- fraction of jointly qualified days on which `j` outranks `i`;
- fraction of days both are Top3;
- candidate `j` Top1 and Top3 frequency.

No asset-class label, future return, realized replacement identity, future path statistic, tuned horizon, or hand-picked threshold is used.

## Model and split

- fixed `LogisticRegression(L2, C=1, class_weight=balanced)`;
- median imputation with missing indicators;
- standardization;
- strict monthly expanding-window OOS;
- OOS evaluation starts 2023-01;
- no random split;
- no hyperparameter search;
- no feature-subset search;
- no policy threshold;
- no strategy backtest.

## Baseline

The frozen baseline is the exact month-end static OLS-score ranking among alternatives. A realized replacement that is not currently qualified receives no finite static rank and counts as a miss.

## Primary metrics

At the event level:

- Hit@1;
- Hit@3;
- mean reciprocal rank (MRR);
- median realized-replacement rank.

Report overall and separately for 2023–24 and 2025–26.

## Predeclared interpretation rule

Dynamic replacement reachability is considered supported only if both Hit@3 and MRR do not deteriorate overall and improve or remain non-worse in both time regimes.

A pooled gain accompanied by a period reversal is not sufficient evidence.

If supported, the next admissible stage is pairwise transition-value modeling conditional on replacement reachability. If unsupported, do not tune this feature family on the same sample; retention-side state representation is not yet sufficient and the project should reconsider admission or a different path-state representation.
