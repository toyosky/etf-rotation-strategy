# Stage24 Admission Worthiness State Audit — Frozen Design

Date: 2026-09-13

## Motivation

Stage22 showed a stable Fixed15 opportunity-coverage gap. Stage23 showed that current OLS score rank does not compress missed outsiders into a sufficiently small shortlist. The next step should lower the target difficulty rather than predict the unique future best ETF.

## Frozen question

Using a small fixed point-in-time trend-health state, can we rank external trend-eligible ETFs that will expand the contemporaneous Fixed15 20-day opportunity frontier better than OLS score alone?

## Candidate universe

At each trading month-end:

- point-in-time `trend_eligible == True`;
- non-cash ETF;
- outside Fixed15;
- forward 20-day close return available for label construction.

No asset-class filtering, ETF subset selection, or Cluster90 restriction.

## Label

For each month-end, compute the best forward-20-day close return among point-in-time trend-eligible Fixed15 non-cash ETFs.

For every eligible outsider candidate j:

`y_frontier_expander = 1` iff `fwd20(j) > fixed15_oracle_best_fwd20`.

This is label-side only and is intentionally weaker than predicting the unique full-market winner. It asks only whether admitting j could expand the opportunity frontier available to OLS.

Months with no eligible Fixed15 comparator are excluded.

## Frozen point-in-time features

Exactly six existing features from the full-market OLS pipeline:

- `score`
- `r2`
- `score_delta`
- `current_resid`
- `efficiency20`
- `dist_high20`

No feature subset search and no added asset identity, asset class, future return, future rank, or replacement information.

## Models / ranking rules

Baseline:

- raw OLS `score`, descending.

Low-DoF state model:

- `LogisticRegression`
- L2 penalty
- C = 1
- class_weight = balanced
- median imputation + missing indicators
- StandardScaler
- no hyperparameter search.

## Time split

Strict monthly expanding OOS.

- test starts 2023-01;
- training uses only months strictly before test month;
- skip test months until training contains at least 12 months and both target classes.

No random split.

## Primary evaluation

For each OOS month containing at least one frontier-expanding outsider, rank candidates by baseline score and model probability.

Primary metrics:

- Hit@5: whether at least one frontier expander appears in top 5;
- first-positive MRR: reciprocal rank of the first frontier-expanding outsider;
- median first-positive rank.

Report overall, 2023–24, and 2025–26.

Secondary diagnostics:

- number of OOS months;
- mean number/share of frontier expanders among outsiders;
- candidate count.

## Predeclared interpretation

Treat the low-DoF admission state as supported only if:

1. Hit@5 does not deteriorate vs score baseline overall;
2. first-positive MRR does not deteriorate overall;
3. both Hit@5 and MRR deltas are non-negative separately in 2023–24 and 2025–26.

No cutoff, feature, horizon, or ETF-universe tuning on this OOS history.

If supported:

- next admissible stage is a conservative admission-shortlist mechanism audit without a trading-policy backtest.

If unsupported:

- do not add more hand-picked state variables on the same sample;
- branch to a fixed-feature nonlinear-capacity benchmark to distinguish state-information insufficiency from linear-model capacity insufficiency, or to a non-predictive coverage/diversity mechanism if sample support is too weak.

## Explicit non-goals

Stage24 does not:

- optimize portfolio return;
- choose an admission threshold;
- backtest a dynamic Universe;
- tune TopK;
- predict the unique future winner;
- use neural networks;
- search features or hyperparameters.