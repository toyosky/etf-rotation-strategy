# OURE Stage6D — Fixed-K30 Member Marginal-Value Findings

Date: 2026-09-14
Run: `34852348851`
Artifact: `oure-stage6d-fixed-k30-member-marginal-34852348851`
Status: frozen_failed_primary_gate
Decision: `member_marginal_value_not_lowdim_identifiable`

## Frozen question
With non-cash K fixed at 30, can a small set of X<=t mechanism variables identify which ETF will add future conditional set value in different market environments?

The experiment was preregistered before outcome inspection. Fix15 membership was not used. Each era built its own point-in-time candidate pool and hindsight-searched K30 elite ensemble. K30 is an engineering anchor, not a claimed exact/global optimum.

Forward eras:
- 2022–2024: 265 point-in-time candidates; 25 searched elite K30 Universes; 16 deterministic K29 contexts.
- 2025–2026 through 2026-09-09: 711 point-in-time candidates; 25 searched elite K30 Universes; 16 deterministic K29 contexts.

For every K29 context U and admissible candidate i, the forward target was `future_delta_log(i|U) = log V(U+i) - log V(U)` under the frozen downstream OLS evaluator.

## Primary gate result: FAIL
Frozen core X<=t proxies were:
1. prior new-coverage share;
2. prior replacement counterfactual-gain mean;
3. prior productive-challenge share.

The preregistered gate required at least 2/3 core proxies to have positive median context-level Spearman association with future marginal set value in both eras, plus a positive equal-weight mechanism score in both eras.

Observed median context-level Spearman correlations:

| proxy | 2022–24 | 2025–26 |
|---|---:|---:|
| prior new-coverage share | not identifiable (constant zero) | not identifiable (constant zero) |
| prior replacement-gain mean | +0.008 | -0.010 |
| prior productive-challenge share | **-0.291** | **-0.337** |
| prior challenge share | **-0.332** | **-0.404** |
| fixed equal-weight mechanism score | +0.085 | +0.003 |

Core positive count:
- 2022–24: `1/3`;
- 2025–26: `0/3`.

The fixed mechanism score is technically positive in both eras but extremely weak, especially in 2025–26. The primary gate therefore fails. Do not tune windows, weights, thresholds or add a high-capacity model to rescue this stage.

## Strong stable secondary finding: historical challenge frequency is harmful
The clearest cross-era X<=t relation is **not** past replacement quality. It is raw historical leader-challenge frequency.

`prior_challenge_share -> future_delta_log`:
- 2022–24 median context Spearman: `-0.332`; positive-context share `0/16`; candidate-level Spearman `-0.331`.
- 2025–26 median context Spearman: `-0.404`; positive-context share `0/16`; candidate-level Spearman `-0.413`.

Thus candidates that historically spent more time beating an already-active leader in a near-elite K29 context tended to have **lower** future marginal set value when admitted.

This is consistent with a stable harmful-competition effect: frequent challengers are not automatically productive additions.

The preregistered hypothesis that the raw challenge penalty would be stronger in 2022–24 than in 2025–26 is rejected. It is actually more negative in the later era under this conditional-admission experiment.

## Why historical productive-switch statistics did not help
`prior_productive_challenge_share` is negatively associated with future marginal value in both eras, despite being a count-based historical success fraction. Meanwhile `prior_replacement_gain_mean` is near zero/inconsistent.

Additional decomposition shows that higher prior challenge share predicts more future challenge activity, but also worse future **magnitude-weighted** replacement gain. A candidate can win a reasonable fraction of challenge events while still destroy set value through larger adverse replacements. Therefore historical win-rate alone is not a reliable admission signal.

## Coverage is already saturated at K29
`prior_new_coverage_share` is exactly zero for all tested context-candidate pairs in both eras. At K29, the elite-derived contexts already had essentially complete historical risk-leader coverage over the frozen 126-session X window, so a 30th member almost never supplied a previously uncovered historical window.

This is an important structural result: once K is near 30, the admission problem is no longer primarily about adding raw coverage. It is dominated by **which existing leaders the candidate will challenge and whether those challenges are worth the disruption**.

Future new coverage is also very small on average, although not always zero. Hence the Stage4 relay decomposition remains useful at the whole-Universe level, but raw coverage gain has little discriminatory power for the *30th-member admission* problem.

## Member composition changes sharply across eras
The two independently searched K30 champions share only 5 of 30 members:
`159806, 159981, 159985, 515030, 515880`.

Champion member Jaccard = `0.0909`.

This supports the user's hypothesis that the desirable member identities change substantially with environment, even though K≈30 can remain a useful engineering anchor.

Examples of high elite-inclusion / deletion-value members:

2022–24:
- `159985`: elite inclusion 100%, mean elite drop delta log +0.494;
- `513520`: 100%, +0.359;
- `159941`: 100%, +0.310;
- `515880`: 92%, +0.307;
- `159981`: 92%, +0.126.

2025–26:
- `161226`: 100%, +1.115;
- `513310`: 100%, +0.579;
- `515880`: 100%, +0.349;
- `517520`: 100%, +0.254;
- `501018`: 100%, +0.251.

These are hindsight descriptions only and must not be used as production identities.

## Important interpretation
Stage6D rejects a simple rule of the form:

`past coverage + past productive-switch quality - past competition -> future member value`

with fixed low-dimensional weights.

What survives is narrower:

> **Conditional on already having a strong K29 context, historical crowding/challenge intensity is a robust warning signal.**

This does not yet tell us how to construct the first 29 members. It is more naturally an **admission / redundancy veto** than a complete member-ranking model.

The finding also refines the earlier regime story. Different eras clearly choose very different member identities, but the data do not support the preregistered claim that the three frozen historical mechanism proxies simply receive different weights and thereby identify those identities. Replacement quality is not stable enough across eras in the 126-session window.

## Frozen conclusion
1. K30 remains a useful fixed research anchor; this stage does not prove K30 is universally optimal.
2. The two eras' desirable K30 memberships differ strongly.
3. The preregistered low-dimensional member-marginal identification gate fails.
4. Raw historical challenge intensity is a strong, directionally stable **negative** conditional-admission signal in both eras.
5. At K29/K30, historical raw coverage is saturated and cannot discriminate candidates.
6. Historical productive-challenge rate and replacement-gain mean do not reliably identify future marginal set value.
7. Do not escalate to a larger predictor. A next-stage construction, if pursued, should treat challenge intensity as a preregistered redundancy/admission veto and solve the separate problem of how to form a good core set without future identity information.

## Limitations
- K30 elite Universes are heuristic hindsight search results, not exact global optima.
- K29 contexts are derived from hindsight elite K30 sets, so the challenge-share result is conditional on having a strong near-complete core; it is not yet a from-scratch construction rule.
- Current metadata flags are used for leverage/inverse/data guards, retaining the previously noted survivorship-metadata risk.
