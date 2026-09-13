# Stage21 Competition Nuisance Audit — Findings (2026-09-13)

## Frozen question
Does a persistent competition-nuisance phenotype exist: keeping an ETF adds Top1 switching without adding marginal return?

Frozen nuisance outcome: `delta_switches > 0 and delta_return <= 0`.
Frozen structural nuisance by symbol-era: `sum(delta_switches) > 0 and sum(delta_return) <= 0`.
No predictive model, threshold search, feature search, or policy backtest was used.

## Verified run
GitHub Actions run: `34742072152` (success).

## Results
Overall, 578 symbol-month rows were audited. Extra switching occurred in 12.98% of rows. Among rows with extra switching, 70.67% were nuisance outcomes. Nuisance rows accumulated +85 switches and -1.7431 marginal return, while productive extra-switch rows accumulated +28 switches and +0.8001 marginal return.

The nuisance phenomenon exists in both eras:
- 2023-24: nuisance given extra switch = 65.85%; nuisance delta return sum = -0.8522.
- 2025-26: nuisance given extra switch = 76.47%; nuisance delta return sum = -0.8909.

However, nuisance identity is not persistent enough for prospective deletion:
- 14 symbols appear in both eras.
- Cross-era Spearman of symbol-level switch burden = +0.3105.
- Cross-era Spearman of symbol-level marginal return = -0.3890.
- Structural-nuisance flag agreement = 35.71%.
- Only `159981` and `164824` are structural nuisance in both eras.

## Frozen interpretation
Stage21 satisfies the first half of the hypothesis (competition nuisance is economically non-trivial) but fails the persistence requirement needed to proceed to a prospective nuisance-risk deletion model.

This is evidence against treating nuisance identity as a stable ETF trait. The likely failure mode is conditional/state dependence: an ETF can be nuisance in one market regime and productive in another. Selecting favorable symbols or tuning nuisance thresholds on this same history would be hindsight optimization and is prohibited.

## Decision
Close the prospective nuisance-identification branch for now. Branch to the weaker `opportunity coverage` question before considering admission gating.

Next question: does Fixed15 materially fail to cover point-in-time qualified trends that subsequently deliver strong continuation, and is that coverage gap present across eras? This should be audited as an opportunity-set property, not as a prediction model or trading policy.
