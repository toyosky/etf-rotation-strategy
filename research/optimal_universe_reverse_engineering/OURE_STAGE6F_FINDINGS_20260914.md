# OURE Stage6F — Fixed-K30 Core Formation + Challenge Veto Findings

Date: 2026-09-14
Run: `34854924714`
Artifact: `oure-stage6f-core-plus-veto-34854924714`
Status: frozen failed
Decision: `core_and_veto_primary_gates_failed`

## Frozen result
The preregistered two-layer X<=t construction did not pass either primary gate.

### Core formation
Completed periods: 9.

Linked total returns:
- Core A current-score K29 + neutral 30th member: `+76.3%`;
- Core B robust 3/6/12 transfer K29 + neutral 30th member: `+309.3%`;
- Core C state-gated A/B K29 + neutral 30th member: `+441.3%`.

Core C had positive aggregate increments:
- mean paired log delta vs Core A: `+0.12465` per period;
- bootstrap 95%: `[0.0000, +0.30751]`;
- mean paired log delta vs Core B: `+0.03107`;
- bootstrap 95%: `[-0.10072, +0.15798]`.

However the preregistered core gate failed because Core C beat both Core A and Core B in the same period **0%** of the completed periods. Core C beat the same-K30 random median in `55.6%` of periods, but that alone is insufficient.

Interpretation: the frozen low-DoF state-gated core has encouraging aggregate wealth but does not show the required period-level dominance and therefore cannot be promoted as a validated from-scratch K29 constructor.

### Stage6D challenge-share admission veto
The veto also failed.

- neutral Core C linked return: `+441.3%`;
- veto Core C linked return: `+434.6%`;
- mean paired veto-minus-neutral log delta: `-0.00139`;
- bootstrap 95%: `[-0.03090, +0.02675]`;
- veto triggered in `44.4%` of periods;
- veto improved the period in only `22.2%` of periods;
- median veto delta by era: `0.0` in both 2022–24 and 2025–26.

Thus the Stage6D conditional warning does not translate into a useful fixed-form admission veto on this X<=t core.

## Frozen conclusion
1. Do not promote Core C despite its higher linked return; the preregistered period-level gate failed.
2. Do not promote the 126-session median-relative challenge veto; its gate failed and aggregate effect was slightly negative.
3. Do not retune the Stage5 windows/top20, Stage6 state thresholds, challenge lookback, veto threshold, weights, or fallback.
4. Stage6F therefore does not solve from-scratch fixed-K30 construction.
5. The remaining informative direction is the separate Stage6G observation that whole-K30 value learnability is strongly regime-dependent. The next test should isolate an X<=t market-state gate before any state-conditioned surrogate/search is allowed.
