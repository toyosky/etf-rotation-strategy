# OURE Stage6D — Fixed-K30 Member Marginal-Value Identification

Date: 2026-09-14
Status: preregistered before outcome inspection

## Question
With nominal Universe size frozen at 30 non-cash ETFs, what makes an ETF a valuable member in different market environments? Can a small set of information available before each era hint at the ETF's future conditional marginal set value?

This stage does **not** optimize K. It treats K=30 as an engineering anchor motivated by Stage6C's broad K20–30 2022–24 plateau and the previously observed large-K relay solutions. It does not claim K30 is a universal/global optimum.

## Eras
Two hindsight laboratories are frozen:
- Era A: 2022-01-01 through 2024-12-31.
- Era B: 2025-01-01 through 2026-09-09.

For each era, the candidate pool is point-in-time availability at the era start: non-leveraged/non-inverse ETFs with sufficient price history before the start. Fix15 membership and identity are not used.

## Hindsight K30 elite construction
For each era independently:
1. Search only fixed non-cash K=30 Universes with the frozen downstream OLS evaluator.
2. Use multiple singleton-seeded greedy starts, fixed-K swap refinement, and deterministic-seed stochastic restarts.
3. Retain the top 25 unique searched K30 Universes as an explanatory elite ensemble.
4. Results are a **heuristic searched elite set**, never an exact/global optimum.

## Conditional marginal-value label
Create deterministic K29 contexts from the elite K30 ensemble by dropping one member from each selected elite using an index rule fixed independently of the member's measured contribution.

For every point-in-time eligible candidate `i` not already in a K29 context `U`, define the forward label:

`future_delta_log(i|U) = log V(U + i) - log V(U)`

where V is the frozen downstream OLS portfolio wealth over the corresponding forward era.

Also record forward decomposition quantities: new-coverage share, challenge/competition share, replacement counterfactual-gain mean, and productive-challenge share. These are explanatory labels, not predictors.

## Frozen X<=t proxies
All predictors use only the 126 completed signal sessions before the era start. The window ends early enough that any realized counterfactual return used in a predictor is fully known before the decision boundary.

Only four mechanism-mapped predictors are allowed:
1. `prior_new_coverage_share`: share of prior days on which candidate i would become the risk leader while U otherwise has no risk leader.
2. `prior_challenge_share`: share of prior days on which i would beat an already-active risk leader in U.
3. `prior_replacement_gain_mean`: historical mean next-period gross return advantage of i over the displaced leader on those prior challenge days.
4. `prior_productive_challenge_share`: historical fraction of those challenge days with positive counterfactual return advantage.

No broad technical-indicator feature search, identity variables, sector labels, or future-return-based feature selection is allowed.

A fixed equal-weight mechanism score is also preregistered for diagnostics only:
- higher prior new coverage = better;
- higher historical replacement gain = better;
- higher productive-challenge share = better;
- lower raw challenge share = better.

The score is the mean of within-context percentile ranks with the challenge percentile reversed. It is not fitted.

## Primary tests
For every K29 context, rank all admissible candidates by each X<=t proxy and compare that ranking with `future_delta_log(i|U)` using Spearman correlation. Report the median context-level correlation and positive-correlation share, plus candidate-level context-averaged association.

Frozen core directional hypotheses:
- prior new-coverage share -> future marginal value: positive;
- prior replacement-gain mean -> future marginal value: positive;
- prior productive-challenge share -> future marginal value: positive.

The raw challenge-share effect is explicitly allowed to be regime dependent. Based on already-frozen market-state evidence, the preregistered comparison is that its marginal penalty should be stronger in 2022–24 than in 2025–26; no sign is forced for the later era.

## Pass/fail gate
Promote an X<=t member-selection signal only if:
1. at least 2 of the 3 frozen core proxies have positive median context-level Spearman correlation in **both** eras; and
2. the equal-weight mechanism score has positive median context-level Spearman correlation in both eras.

If this gate fails, freeze the result as `member_marginal_value_not_lowdim_identifiable` and do not rescue it with more features, tuned weights, alternate windows, or a higher-capacity model.

If it passes, the next stage may use the frozen proxies to construct a strict walk-forward K30 Universe. No production rule is authorized by this stage alone.

## Secondary outputs
- elite K30 member inclusion frequencies by era;
- elite-set overlap between eras;
- forward marginal-value distribution by candidate;
- relationship between elite inclusion frequency and context-averaged marginal value;
- mechanism decomposition of the highest- and lowest-marginal candidates.

These are descriptive and cannot alter the preregistered gate.
