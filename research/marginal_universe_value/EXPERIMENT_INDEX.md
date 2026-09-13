# MUV Experiment Index

This file is the human-readable companion to `experiment_registry.yaml`.

## Current lineage

```text
Stage3 pairwise sign
  -> Stage7 asymmetric safety
      -> Stage13 bootstrap uncertainty
          -> Stage14 residual stress

Stage3
  -> Stage15 hurdle identifiability
      -> Stage16 activity-conditional sign
          -> Stage17 local relational state (labels v1.5)
              -> Stage18 explicit displacement mechanism (labels v1.6)
                  -> Stage19 branch decision
```

## What changed conceptually

### Stage13-14: uncertainty and robustness
The question was not yet “which ETF belongs in the Universe?” but whether estimated retention effects survive month-level uncertainty and residual stress.

### Stage15-16: identifiability and activity
The research then tested whether a usable retention sign/gate is identifiable, and whether predictability improves when conditioning on actual OLS competition activity.

### Stage17: local competition state
The representation moved from mainly ETF-level state toward relational state: incumbent, candidate and nearby OLS competitors.

### Stage18: explicit displacement mechanism
Stage18 does not fit a new model. It asks whether remove-one MUV is mechanically concentrated on direct displacement days, and whether the replacement that actually appears is already present in the point-in-time local competing set.

The Stage18 script freezes the branch rule:

- if local-set coverage is high and direct-day deltas explain most monthly MUV with little spillover -> proceed to pairwise transition-value modeling;
- otherwise -> expand the state representation before adding more sign features.

## Stage19 rule

Do not choose Stage19 by whichever branch produces a higher full-sample backtest.

First read the Stage18 report and apply its pre-declared mechanism rule. Then register Stage19 in `experiment_registry.yaml` before adding a workflow.

## Required fields for every new experiment

Every new Stage must record at least:

```text
stage_id
parent_stage
hypothesis
label_version
target_scope
model_role
scripts
workflow
primary_outputs
status
decision
```

If a Stage changes label semantics, increment `label_version`. If it only changes the model/audit while using identical labels, reuse the existing label version so Actions cache remains reusable.

## Promotion rule

Research stages remain under `research/` until evidence supports promotion.

```text
exploratory/completed
  -> provisional
  -> validated
  -> strategy candidate
  -> frozen strategy Release
```

A good historical backtest alone is not sufficient for promotion.
