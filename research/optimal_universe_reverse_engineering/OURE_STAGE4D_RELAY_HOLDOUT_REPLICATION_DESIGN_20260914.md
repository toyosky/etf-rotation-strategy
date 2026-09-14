# OURE Stage4D — Relay Holdout Replication

Date: 2026-09-14
Status: preregistered
Parent: Stage4C (`partial_support_relay_only`)

## Question

Does the relay/productive-replacement structure discovered in Stage4C replicate on completely disjoint Stage3B Universes that were not used in the Stage4C elite or control groups?

This stage does not search for a better hindsight Oracle, does not train a classifier, and does not change nominal-K rules.

## Frozen holdout groups

### Holdout elite

Use Stage3B elite ranks `26..100` inclusive. These 75 Universes were not used in the Stage4C top-25 discovery group.

### Holdout controls

Use Stage3B same-K random controls that were not used in the Stage4C large-K random group.

Match the holdout elite nominal non-cash K counts exactly. For each K, choose the lexicographically first unused random controls after sorting by `members`. This removes a new random-seed degree of freedom.

The expected holdout mix from the frozen Stage3B ranking is 71 K30 and 4 K29 Universes; the script verifies rather than assumes this.

## Frozen relay signature directions

Stage4C supports the following six low-dimensional structural directions. No weights are fitted.

Elite versus matched random should show:

1. `coverage_efficiency` higher;
2. `productive_switch_share` higher;
3. `switch_counterfactual_gain_mean` higher;
4. `leader_year_specialization` higher;
5. `leader_transition_diversity` higher;
6. `switch_rate` lower.

The sixth direction is retained because it was strong in full history and 2021–24, but Stage4C already showed it can become nearly neutral in 2025–26. Therefore failure of switch-rate reduction alone does not reject relay replication.

`active_leader_share`, `mean_top1_tenure`, score crossing and trend Jaccard are reported as diagnostics but are not part of the six-direction gate.

## Eras

Compute all metrics for:
- full history;
- 2021–24;
- 2025–26.

## Frozen replication gate

Relay replication is supported only if:

- full history: at least 5 of 6 frozen directions match Stage4C;
- 2021–24: at least 4 of 6 match;
- 2025–26: at least 4 of the first 5 non-switch-rate directions match.

Additionally, both `productive_switch_share` and `switch_counterfactual_gain_mean` must be positive elite-minus-control differences in full history and in both eras. These two are mandatory because they are the economically central replacement-quality mechanism.

No threshold is changed after results.

## Interpretation limits

Passing this stage validates a cross-Universe relay mechanism inside the frozen Stage3B search family. It is not yet a point-in-time executable rule and not fully independent of Stage3B search construction.

Failing this stage freezes relay as discovery-sample specific and ends the discrete-architecture branch. The next fallback would be a continuous Effective Competition / Opportunity Coverage description, not a higher-capacity model.

## Outputs

- `stage4d_holdout_universe_metrics.csv`
- `stage4d_group_medians.csv`
- `stage4d_effects.csv`
- `oure_stage4d_summary.json`
