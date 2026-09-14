# OURE Stage4 — Effective Competition Decomposition

Date: 2026-09-14
Status: preregistered mechanism audit

## Question
Why can the Fix15-derived K7 elite and the Stage3B large-K elite both produce high frozen-OLS portfolio value despite very different nominal cardinality?

This stage does **not** search for a better Universe and does not use Stage3C results. Stage3B is used only as an explanatory large-K sample; its taxonomy leakage prevents treating it as final exposure-disjoint replication evidence.

## Frozen comparison groups

A. `small_k_elite`: top 25 K=7 subsets from frozen OURE Stage1 exhaustive Fix15 subset results.
B. `large_k_elite`: top 25 Stage3B elite Universes.
C. `large_k_random`: 50 Stage3B same-K random controls, sampled deterministically and approximately matched to B cardinality.

Separate named diagnostics are retained for:
- exact Stage1 K7 champion;
- original full Fix15;
- exact Stage3B champion.

## Mechanism metrics

For each Universe and separately for 2021–2024 / 2025–2026 / full sample:

1. nominal non-cash K;
2. opportunity coverage: share of days at least one non-cash member is OLS-eligible;
3. mean eligible count and eligible count conditional on coverage;
4. active leader count: number of members that ever become Top1;
5. active leader share = active leader count / nominal K;
6. leader HHI and `effective_leader_count = 1 / HHI`;
7. switch events, leader switch rate, mean/median Top1 tenure, short-run share <=2 days;
8. mean and max pairwise trend-eligible Jaccard;
9. pairwise score-crossing rate while both members remain eligible;
10. Top1-vs-Top2 raw score gap diagnostics;
11. switch productivity: on each leader change, compare the new leader's next open-to-open return with the counterfactual return from keeping the prior leader for that same holding interval; report productive-switch share and aggregate counterfactual switch gain before costs.

No threshold is tuned from realized return. Pairwise crossing uses sign changes of score differences while both members remain eligible. `productive_switch` is simply `new_return > old_return` on the same one-day mark.

## Primary hypotheses

H1. Nominal K is not the direct competition state. Large-K elites may have many nominal members but only a much smaller effective leader set.

H2. The relevant competition variable is rank instability near the top (leader replacement / pair score crossing), not raw member count or raw eligible count alone.

H3. Large-K elite turnover can remain economically useful if a materially higher fraction of switches are productive. Thus `more switches` is not equivalent to `harmful premature exits`.

H4. If K7 and large-K elites share low effective competition relative to their respective random controls, the structural target becomes `coverage with controlled effective competition`, not a universal optimal K.

## Decision rule

Promote the mechanism only if at least one effective-competition metric separates both elite groups from the random control in the same economically coherent direction. A metric that only explains K7 or only explains Stage3B will not be promoted as a cross-Universe construction principle.
