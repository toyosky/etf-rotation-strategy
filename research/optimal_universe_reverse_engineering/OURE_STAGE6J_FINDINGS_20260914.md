# OURE Stage6J — Chronological Mapping Transfer Findings

Date: 2026-09-14
Run: `34863742504`
Artifact: `oure-stage6j-chronological-mapping-transfer-34863742504`
Status: frozen formal non-pass
Decision: `chronological_mapping_transfer_not_supported_primary_rule`

## Frozen question
Can the half-year K30 value mapping established by Stage6I be estimated from completed historical half-years and transferred to the next half-year using only X<=t?

The experiment preserved Stage6I's K=30, 19 whole-set features, 126-session X lookback, 126-session future-Y horizon, deterministic family-library construction, fixed RF parameters and downstream OLS. Current-period future labels were used only for final evaluation.

Primary chronological targets were six periods with at least three fully completed predecessors: 2023H2, 2024H1, 2024H2, 2025H1, 2025H2, 2026H1.

## Preregistered primary rule: FAIL
The primary rule was the equal-weight rank ensemble of three separately fitted RFs from the previous three completed half-years.

Across the six chronological OOS targets:
- median period Spearman = **+0.1088**;
- positive IC periods = **6/6**;
- median predicted-Top50 actual percentile = **0.4602**;
- early block (2023H2–2024H2) median IC = **+0.0743**;
- late block (2025H1–2026H1) median IC = **+0.1432**;
- median top-decile future-log lift = **+0.01088**.

Frozen gates:
1. median IC > +0.10: PASS;
2. at least 4/6 positive periods: PASS;
3. median predicted-Top50 actual percentile > 0.55: **FAIL**;
4. early-block median IC > 0: PASS;
5. late-block median IC > 0: PASS.

Because all gates were required, Stage6J is a formal non-pass. The failed top-tail gate is especially relevant because any later combinatorial optimizer would concentrate precisely where surrogate ranking error is most exploitable.

## Period-level primary behavior
The last-3 RF rank ensemble ICs were:
- 2023H2: +0.0384;
- 2024H1: +0.2812;
- 2024H2: +0.0743;
- 2025H1: +0.0235;
- 2025H2: +0.1432;
- 2026H1: +0.3318.

Thus broad cross-sectional direction is consistently positive, but top-tail ordering is not reliable enough under the preregistered standard.

## Diagnostic R1 — previous-period RF
This rule was preregistered as a diagnostic and cannot rescue the primary gate.

Across the six targets:
- median Spearman = **+0.1959**;
- positive periods = **6/6**;
- median predicted-Top50 actual percentile = **0.5119**;
- median top-decile future-log lift = **+0.03896**.

The immediately previous mapping transfers better than averaging three full nonlinear mappings. This is evidence that mapping drift is material and that stale mappings can dilute useful recent structure. It is not a promoted production rule because Stage6J did not preregister R1 as the pass/fail rule.

## Diagnostic R3 — unanimous directional sub-mapping
This low-DoF rule retained only frozen features whose feature-vs-future-value Spearman sign agreed in all previous three completed half-years; it used only the sign and equal weights.

Across the six targets:
- median Spearman = **+0.1802**;
- positive periods = **5/6**;
- median predicted-Top50 actual percentile = **0.5856**;
- median top-decile future-log lift = **+0.02012**.

Period ICs:
- 2023H2: +0.1081;
- 2024H1: +0.2069;
- 2024H2: +0.3259;
- 2025H1: -0.0131;
- 2025H2: +0.1534;
- 2026H1: +0.5157.

Retained feature counts were 5, 6, 7, 7, 6 and 7 respectively. The retained set changed over time, but several interpretable local components repeatedly appeared, including tenure/short-run structure in earlier windows and past126 growth/drawdown plus productive-switch/counterfactual-gain components in later windows.

Again, this is diagnostic evidence only. It cannot retroactively become the primary Stage6J rule.

## Frozen interpretation
Stage6I showed that the current half-year's K30 value surface often exists. Stage6J adds a sharper result:

> **Historical mapping transfer contains broad ranking signal, but the preregistered multi-period nonlinear ensemble is not reliable in the extreme top tail. The mapping appears to drift, and local directional components transfer better than averaging stale full mappings.**

This resolves part of the Stage6I/Stage6E tension without authorizing RF-guided combinatorial search.

The current bottleneck is no longer whether a 126-session value surface exists. It is whether its locally transferable component can be estimated with enough top-tail reliability before the period begins.

## What is not allowed next
- Do not change the Stage6J primary gate or promote R1/R3 retroactively.
- Do not tune last-3 weights, RF hyperparameters, features, 126-session horizon, Top50 threshold, or target periods.
- Do not run RF argmax / K30 combinatorial optimization on the strength of this result.
- Do not use member identity.

## Next valid step
There is no untouched complete post-2026H1 half-year label in the current dataset. Therefore a confirmatory promotion of the previous-period RF or unanimous-direction rule requires a genuinely later completed 126-session period. Until that exists, the strongest defensible state is:

- same-period value-surface learnability: supported (Stage6I);
- broad chronological mapping signal: supported diagnostically;
- preregistered deployable top-tail mapping transfer: not yet supported;
- RF-guided K30 search: still not authorized.

A future clean-forward stage should freeze one low-DoF mapping-transfer rule before the new period's labels exist and evaluate it without further historical tuning.
