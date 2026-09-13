# MUV Stage 18 — Explicit Path-Displacement Audit

Date: 2026-09-13

## Motivation

Stage 17 showed a weak but time-consistent ranking improvement from local-Universe relational state, while calibration worsened. The next step therefore changes the target representation rather than tuning features.

## Frozen question

> When an incumbent actually matters to the next-month OLS path, does the point-in-time local competing set identify who replaces it under remove-one, and is monthly MUV mainly the value of those direct displacement segments?

## Label-side additions

For every incumbent-month, using the already-generated baseline and remove-one daily paths:

- direct displacement days: baseline target equals the incumbent;
- realized counterfactual replacement identity on each direct day;
- dominant realized replacement and its share of direct days;
- number of distinct realized replacements;
- cash replacement days;
- sum / mean of baseline-net minus counterfactual-net on direct days;
- spillover changed days and spillover net-delta sum.

Future replacement identity is an outcome label only. It is forbidden as X.

## Prospective competitor mapping

Reuse the V1.5 point-in-time local set, frozen at the decision date:

- current strongest alternative;
- current top-3 alternatives by exact as-of OLS score after excluding the incumbent.

Audit whether the realized dominant replacement:

1. matches as-of alt1;
2. belongs to the as-of top3.

No score-gap threshold is introduced.

## Economic decomposition audit

Compare monthly `delta_return` with direct displacement net-delta sum:

- Spearman association;
- sign agreement;
- mean absolute monthly delta;
- mean absolute direct-day delta;
- mean absolute residual `monthly delta - direct delta`;
- absolute spillover contribution.

## Frozen interpretation

If the current local set usually contains the realized replacement and direct displacement accounts for most monthly MUV with little spillover, the next admissible stage is a pairwise transition-value model:

`incumbent i + prospective alternative j + Universe local state -> value of i rather than j on the affected path`

If replacement coverage is weak or spillover is material, do not tune Stage 17 features. The representation must first include a broader dynamic competing set or path-state transition mechanism.

## Restrictions

- no new predictive model;
- no threshold search;
- no feature selection;
- no strategy backtest;
- no use of future identity as a predictor;
- report full sample and frozen 2023–24 / 2025–26 periods.