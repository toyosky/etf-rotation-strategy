# Stage21 Competition Nuisance Audit — Frozen Design

Date: 2026-09-13
Parent: Stage20
Label version: V1.6
Target scope: retention / competition structure
Model role: mechanism audit

## Question

Does the Fixed15 remove-one counterfactual history contain a persistent competition-nuisance phenotype: ETFs whose presence adds Top1 switching without adding marginal return?

This is deliberately weaker than predicting future replacement identity or signed MUV.

## Frozen definitions

Retention convention in V1.6:

- `delta_return = base_keep_return - remove_one_return`
- `delta_switches = base_keep_switches - remove_one_switches`

Therefore:

- `extra_switch = delta_switches > 0`: keeping the ETF caused more Top1 switches than removing it.
- `nuisance_outcome = delta_switches > 0 AND delta_return <= 0`: keeping the ETF added switching and did not improve return.
- `productive_competition = delta_switches > 0 AND delta_return > 0`: extra switching was accompanied by positive marginal return.

Zero is the only cutoff. No percentile, optimized threshold, or fitted rule is allowed.

## Audit outputs

Report overall, 2023–24, and 2025–26:

- number of ETF-month rows
- share with extra_switch
- share with nuisance_outcome
- nuisance share conditional on extra_switch
- aggregate delta_switches and delta_return for nuisance_outcome rows
- aggregate delta_switches and delta_return for productive_competition rows

For each ETF and era report:

- row count
- sum and mean delta_switches
- sum and mean delta_return
- extra-switch share
- nuisance-outcome share
- literal structural-nuisance flag: sum(delta_switches) > 0 AND sum(delta_return) <= 0

Cross-era stability is evaluated without threshold search using:

- Spearman correlation of per-symbol aggregate delta_switches between 2023–24 and 2025–26
- Spearman correlation of per-symbol aggregate delta_return between eras
- agreement rate of the literal structural-nuisance flag among symbols observed in both eras
- identities of symbols flagged structural nuisance in both eras

## Interpretation

Stage21 supports further competition-nuisance work only if the phenotype is not merely episodic: there should be non-trivial nuisance prevalence and at least some cross-era persistence in either aggregate switching burden or literal structural-nuisance identity.

A weak or unstable result means do not tune nuisance thresholds on the same sample. Branch instead to opportunity-coverage or admission-gate audits.

A supportive result still does NOT authorize a deletion policy. The next admissible stage would test whether nuisance risk can be identified prospectively using only prior information, with strict forward-time validation and asymmetric false-removal protection.

## Prohibited

- No predictive model
- No feature engineering
- No threshold search
- No asset deletion backtest
- No selecting a subset of ETFs after seeing results
- No redefining nuisance after seeing results
