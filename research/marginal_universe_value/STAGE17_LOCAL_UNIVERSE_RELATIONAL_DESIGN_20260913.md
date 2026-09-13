# MUV Stage 17 — Local-Universe Relational Identifiability Audit

Date: 2026-09-13

## Motivation

Stages 11–16 narrowed the retention problem substantially:

- conditional second-order labels are mostly stable, so the system is not globally chaotic after one removal;
- path activity is predictably identifiable OOS;
- conditional on activity, signed MUV remains weakly identified;
- stricter activity filtering does not repair that weakness consistently across time;
- rare false removals have strongly asymmetric regret.

The remaining mechanistic hypothesis is that signed MUV depends on the ETF's **relationship to the current competing set**, not only ETF own state, one strongest alternative, or coarse Universe-wide regime summaries.

## Frozen Stage-17 question

> Conditional on future path activity, does point-in-time local-Universe relational state add stable expanding-window OOS information about `sign(delta_return)` beyond the existing Stage-3 context + strongest-alternative pairwise representation?

Stage 17 is an identifiability audit, not a policy backtest.

## Representation

For incumbent `i` at month-end `t`, rank currently qualified alternatives by the exact as-of OLS score after excluding `i`. Freeze the strongest three as the local competing set.

Add only the following point-in-time summaries:

1. `i` score minus mean score of local top-3 alternatives;
2. score dispersion of local top-3 alternatives;
3. alt1 minus alt3 score depth;
4. 120-day return-correlation of `i` with local top-3: mean / max / std;
5. 120-day return-correlation of `i` with the rest of the risk Universe: mean / max;
6. local-top3 mean correlation minus rest-Universe mean correlation.

No threshold defines a "near competitor". No future realized replacement identity is used.

## Baseline

Baseline features remain exactly the Stage-3 conditional sign representation:

- context features;
- strongest-current-alternative pairwise features.

The baseline and Stage-17 models use the same fixed logistic specification:

`LogisticRegression(L2, C=1)`

with median imputation, missing indicators, and standardization.

## Evaluation contract

- train only on months strictly before the test month;
- test starts 2023-01;
- use only `path_active == True` rows because the target is conditional sign identifiability;
- no random split;
- no feature subset search;
- no hyperparameter search;
- no threshold search;
- no strategy backtest;
- report AUC and Brier score overall and separately for 2023–24 / 2025–26.

## Interpretation rule frozen before results

Evidence for the relational hypothesis requires **broad, time-consistent OOS improvement** over the Stage-3 baseline.

An attractive pooled average is insufficient if the period effects reverse sign.

If this small relational family fails, do **not** search combinations or tune cutoffs on the same history. The next admissible step is to change the representation toward explicit path-displacement labels, i.e. model *which incumbent/path segment is displaced and what that displacement contributes*, rather than adding more generic state variables.

## Why this is the minimum-free-degree next stage

Stage 17 changes only one dimension: representation of the current Universe relationship.

It does not change:

- MUV label definition;
- OLS selection logic;
- horizon;
- train/test protocol;
- model family;
- hyperparameters;
- decision threshold;
- execution rules.

Therefore any stable OOS gain can be attributed much more cleanly to relational information itself.
