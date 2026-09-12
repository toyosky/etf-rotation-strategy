# MUV Stage 10 — Dynamic Second-Removal Transport Test Design

Date: 2026-09-12
Status: frozen before Stage-10 results

## Motivation

Stage 9 found substantial future-aware second-removal headroom after the frozen Stage-7 first removal:

- positive second-step Oracle in 14 / 16 Stage-7 action months;
- Stage-7 final wealth 8.8879;
- Stage-7 + Oracle second removal 19.6705;
- Oracle incremental terminal wealth vs Stage 7 +121.3%.

This justifies a predictive second-step test, but not a new tuned model.

## Frozen experiment

The first removal is exactly the frozen Stage-7 primary action and is never reconsidered.

After that first removal:

```text
Fixed15
  -> frozen Stage7 first removal
  -> reduced universe U1 = Fixed15 - {first}
  -> recompute only universe-dependent point-in-time features under U1
  -> reuse historical Stage3 expected-MUV models
  -> reuse historical Stage7 magnitude-weighted safety model
  -> reuse 90% past-only positive-regret coverage cutoff
  -> optionally remove at most one additional ETF
```

## What is recomputed under the reduced universe

For each remaining incumbent, at the same month-end decision date:

Stage A universe-dependent variables:

- `own_score_ratio_top1`
- `top3_freq20`
- `days_since_top1`

The ETF's own price-state variables are unchanged:

- `x_score`
- `x_r2`
- `x_score_delta`

Pairwise variables are recomputed against the strongest currently qualified alternative inside `U1`:

- score gap
- R² gap
- residual gap
- ret10 / ret20 gap
- efficiency10 gap
- vol20 gap
- MA10-distance gap
- 120-day correlation with alternative
- Top3-frequency gap

The three safety regime variables are recomputed over the reduced incumbent set:

- qualified risk-candidate count
- risk-ETF 20-day positive fraction
- risk-ETF 20-day median return

All features remain point-in-time.

## Models are NOT retuned

For each test month, using only earlier original Fixed15 labels:

- Stage A: same L2 LogisticRegression C=1 specification;
- Stage B sign: same pairwise L2 LogisticRegression C=1;
- expected MUV magnitude: same expanding historical positive/negative active means;
- safety: same `|delta_return|`-weighted pairwise+regime L2 LogisticRegression C=1;
- safety cutoff: same 90% past positive-RV mass coverage based only on earlier OOS Stage-7 safety predictions.

No reduced-universe labels are used to train or tune the model.

This is intentionally a **transport / generalization test** from Fixed15 contexts to Fixed15-minus-one contexts.

## Second-action rule

Among remaining non-cash ETFs after the frozen first removal:

```text
predicted expected MUV < 0
AND
safety score < same past-only 90% regret-protection cutoff
```

If multiple candidates qualify, remove the one with the most negative expected MUV.

Maximum removals per month:

```text
1 frozen Stage7 first removal + at most 1 Stage10 second removal
```

If no second candidate passes, keep the Stage-7 one-removal universe.

## Evaluation

Compare:

- keep-all Fixed15;
- frozen Stage 7 one-removal policy;
- Stage 10 dynamic two-step policy;
- random second removal on the same Stage-10 second-action months;
- Stage-9 future-aware second-removal Oracle upper bound.

Report:

- final wealth and incremental terminal wealth vs Stage 7;
- 2023–24 / 2025–26 split;
- number of second actions;
- beneficial / harmful / zero second actions;
- cumulative second-step improvement;
- cumulative and maximum second-step false-removal regret;
- fraction of Stage-9 Oracle second-step headroom captured;
- random-control percentile.

## Anti-overfitting boundary

- first action frozen;
- second-step features frozen above;
- no new feature search;
- no regularization search;
- 90% regret coverage remains primary;
- no second-step threshold tuning;
- no retraining on reduced-universe outcomes;
- if transport fails, do not rescue it by choosing a new cutoff from Stage-10 results.
