# OURE Stage4D — Relay Holdout Replication Findings

Date: 2026-09-14
Run: 34837591862
Artifact: `oure-stage4d-relay-holdout-34837591862`

## Frozen question

Does the relay signature discovered in Stage4C top25 repeat in completely unused Stage3B elite Universes (ranks 26–100) against new same-K matched random controls, under the six pre-registered directions and gate?

## Cohorts

- Holdout elite: Stage3B ranks 26–100, n=75.
- K composition: 71 at noncash K=30, 4 at K=29.
- Controls: n=75 new same-K random Universes, excluding Stage4C controls and matched exactly by K.
- No new search, feature selection, classifier, seed selection, or metric selection.

## Pre-registered gate result

Replication passed strongly.

Direction matches:
- Full history: 6/6 (required >=5/6).
- 2021–2024: 6/6 (required >=4/6).
- 2025–2026: 6/6; the five non-switch-rate directions are 5/5 (required >=4/5).
- Mandatory productive-switch share and counterfactual-gain mean are positive in all three eras.

## Frozen median elite-control differences

### Full history
- coverage_efficiency: +0.5014
- productive_switch_share: +0.09844
- switch_counterfactual_gain_mean: +0.007087
- leader_year_specialization: +0.05630
- leader_transition_diversity: +0.03856
- switch_rate: -0.02830

### 2021–2024
- coverage_efficiency: +0.36199
- productive_switch_share: +0.09074
- switch_counterfactual_gain_mean: +0.007345
- leader_year_specialization: +0.06957
- leader_transition_diversity: +0.00832
- switch_rate: -0.04240

### 2025–2026
- coverage_efficiency: +0.21339
- productive_switch_share: +0.10374
- switch_counterfactual_gain_mean: +0.006962
- leader_year_specialization: +0.02470
- leader_transition_diversity: +0.03685
- switch_rate: -0.00488

## Interpretation frozen

Stage4D upgrades the relay mechanism from a Stage4C top25 discovery pattern to a Stage3B-internal cross-Universe repeatable structure.

The most stable core is not low switching frequency. The cross-era core is:

opportunity coverage efficiency -> productive replacement -> positive switch counterfactual quality, with temporal specialization / transition diversity as supporting relay structure.

The switch-rate reduction is large in 2021–2024 and nearly disappears in 2025–2026, yet replacement quality remains strongly positive. Therefore `few switches` is not part of the invariant relay definition.

This result does not yet establish external generality because discovery and holdout Universes still come from the Stage3B search construction/member family. The next required test is a frozen-signature replication in a different construction/member family before any X<=t proxy or executable Universe builder is attempted.

Persistence remains unvalidated as a repeatable elite class; Stage4D does not reopen that branch.
