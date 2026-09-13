# Stage25 Dynamic Opportunity Universe Identifiability Audit — Frozen Design

Date: 2026-09-13

## Motivation

Stage22 established a stable full-market opportunity-coverage gap relative to Fixed15. Stage23 rejected raw OLS score as a sufficient small-shortlist bridge. Stage24 found modest but cross-era incremental information in a fixed six-feature state, but its target still referenced Fixed15.

Stage25 removes Fixed15 from the target entirely and asks the more fundamental question: can a point-in-time full-market ETF state identify a broad future opportunity set without predicting the unique future winner?

## Frozen question

At each month-end, among the full-market non-cash ETFs that are point-in-time trend eligible, can information available at that month-end rank the ETFs that will belong to the strongest future-return opportunity set over the next 20 trading days?

This is an identifiability audit, not a trading backtest and not a final dynamic-pool policy.

## Point-in-time candidate universe

At each month-end:
- all ETFs available in the existing full-market point-in-time dataset;
- exclude cash symbol `511220`;
- require `trend_eligible == True` at the month-end;
- require a valid next-20-trading-day close return for label construction only.

No Fixed15 membership is used in the target or ranking.

## Frozen label

Within each month-end candidate cross-section, define `future_opportunity = 1` for ETFs in the top 20% of realized next-20-trading-day close return.

The 20% prevalence is frozen before execution. It is not a tuned strategy threshold; it defines a deliberately broad opportunity set rather than a unique winner.

## Frozen predictors

Use exactly the same six point-in-time state variables as Stage24:
- score
- r2
- score_delta
- current_resid
- efficiency20
- dist_high20

No additional hand-picked features.

## Models / rankings

Baseline:
- raw OLS `score` descending.

Low-DoF state model:
- LogisticRegression
- L2
- C=1
- class_weight=balanced
- median imputation with missing indicators
- StandardScaler

No hyperparameter search, feature search, window search, threshold search, or asset-class labels.

## Validation

Strict monthly expanding OOS.

- test begins 2023-01;
- train only on earlier months;
- require at least 12 distinct training months and both label classes;
- no random split.

Report overall and separately for:
- 2023-24
- 2025-26

## Frozen metrics

Primary:
- average precision (AP)
- recall when selecting the top 20% of the month-end candidate cross-section (`Recall@20%`)

Secondary diagnostics:
- recall when selecting top 40% (`Recall@40%`)
- mean candidate count
- mean realized positive share
- monthly Spearman between ranking score/probability and future 20-day return

The 40% diagnostic is not eligible for threshold selection in this stage.

## Predeclared interpretation

`dynamic_opportunity_state_supported = true` only if the low-DoF state model:
1. does not reduce AP overall;
2. does not reduce Recall@20% overall;
3. does not reduce both AP and Recall@20% in either era;
4. shows a positive overall improvement in at least one primary metric.

A pooled improvement with a clear era reversal is not sufficient for promotion.

## Branch rules

If supported:
- do not tune TopK on the same OOS history;
- proceed to a separately frozen variable-size opportunity-universe policy that uses calibration from prior data only.

If unsupported:
- do not add features or change the 20-day horizon on this OOS history;
- do not jump automatically to a neural network;
- perform a branch review between state-information insufficiency, nonlinear-capacity benchmark, and non-predictive coverage/diversity construction.

## Prohibited in Stage25

- Fixed15-relative labels
- unique future-winner labels
- strategy backtest
- TopK optimization
- threshold tuning
- feature subset search
- hyperparameter search
- neural network
