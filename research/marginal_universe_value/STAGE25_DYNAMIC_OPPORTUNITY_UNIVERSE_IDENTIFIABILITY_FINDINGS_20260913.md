# Stage25 Dynamic Opportunity Universe Identifiability — Findings

Date: 2026-09-13
Run ID: 34749858450
Artifact: `muv-stage25-dou-34749858450`
Artifact digest: `sha256:b84b93beb5222e9d16312e786ed5977acdadc57f1d285e77e4578ff83ff07d37`

## Frozen result

Stage25 is retained only as a side identifiability/coverage diagnostic. Its broad label is not aligned to downstream fixed-OLS set value and must not be used as the final Universe optimization target.

Overall, the six-state logistic representation modestly improved the broad top-20% future-return label versus raw OLS score:
- AP: 0.3325 -> 0.3548 (+0.0223)
- Recall@20%: 0.2886 -> 0.2977 (+0.0091)
- Recall@40%: 0.5122 -> 0.5188 (+0.0065)

However the result reversed across eras:
- 2023-24: AP +0.0676, Recall@20% +0.0825
- 2025-26: AP -0.0350, Recall@20% -0.0836

The frozen support rule therefore fails (`dynamic_opportunity_state_supported=false`).

## Branch review

1. The failure is not evidence for insufficient model capacity. The main issue is target/state mismatch and cross-era instability: a future-return Top20% label is only loosely related to whether a set improves downstream OLS value.
2. Do not rescue this branch by changing TopK, horizon, features, threshold, or classifier on the same OOS history.
3. The main line is rewritten from single-ETF opportunity classification to set-level downstream value: build a variable-size Universe and evaluate it only through the frozen OLS rule.
4. Stage26 therefore becomes an oracle structural audit, not a predictive model: use local set counterfactuals to study the endogenous Universe-size/value curve, composition stability, add/remove marginal value, path coverage, competition switching and realized fixed-OLS PnL.

Decision: branch. Stage25 remains side evidence only.