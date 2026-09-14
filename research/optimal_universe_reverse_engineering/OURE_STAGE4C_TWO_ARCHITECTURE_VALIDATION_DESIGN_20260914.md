# OURE Stage4C — Two-Architecture Mechanism Validation

Date: 2026-09-14
Status: preregistered
Parent evidence: Stage1, Stage4, Stage4B

## Question

Do high-value OLS Universes exhibit two reproducible structural architectures — persistence and relay — or are the champion examples idiosyncratic?

This stage is descriptive/mechanistic. It does not train a return classifier and does not select new Universes from the full market.

## Frozen comparison groups

1. `small_k_elite`: Stage1 exhaustive K7 top 25, where K includes cash and therefore each set has six non-cash members.
2. `small_k_random`: 50 K7 sets sampled with seed 20260914 from the remaining Stage1 exhaustive K7 sets, excluding the top-25 elite.
3. `large_k_elite`: Stage3B top 25 elite Universes.
4. `large_k_random`: up to 50 Stage3B same-K random controls, using the existing frozen controls only.
5. `fix15`: original Fix15 as external benchmark.

The exact Stage1 K7 champion and Stage3B champion are rank 1 of their elite groups; no separate tuning is permitted.

## Frozen metric families

### Persistence

- mean and median Top1 tenure;
- short-run share: fraction of leader runs <=2 days;
- leader HHI and effective leader count;
- Top1-Top2 score gap mean/median;
- pairwise score-crossing rate while both members are trend-eligible.

### Relay

- active leader share;
- productive-switch share;
- counterfactual switch gain sum and mean;
- leader-year specialization: weighted mean share of each leader's leader-days occurring in its dominant calendar year;
- temporal leader span: median days between first and last leader occurrence;
- late-arriving leader share: fraction of active leaders whose first leadership occurs after 2024-12-31;
- leader transition diversity: unique directed non-cash leader transitions divided by observed non-cash switch count.

### Coverage / competition

- coverage share;
- mean eligible count;
- coverage efficiency = active leader count / mean eligible count;
- mean and max pairwise trend-eligible Jaccard;
- score-crossing rate rather than raw return correlation.

## Eras

Metrics are computed for full history, 2021–24 and 2025–26 when meaningful. Temporal first/last-leader metrics are reported full-history and also summarized by era-specific active leader count.

## Primary validation logic

No high-capacity classifier is allowed.

The two-architecture hypothesis is supported only if:

1. `small_k_elite` separates from `small_k_random` in a coherent persistence direction on several metrics, not one isolated metric;
2. `large_k_elite` separates from `large_k_random` in a coherent relay/productive-replacement direction on several metrics;
3. the mechanisms can coexist: high value does not require both groups to share the same nominal K, switch rate or leader concentration;
4. the differences are not solely a 2021–24 artifact; at least part of each architecture remains interpretable in 2025–26.

If only the two champions look distinct but the top-25 elite groups do not separate from controls, freeze the two-state story as anecdotal and do not promote it into a point-in-time rule.

## Outputs

- `stage4c_universe_metrics.csv`
- `stage4c_group_medians.csv`
- `stage4c_group_effects.csv`
- `stage4c_champions.csv`
- `oure_stage4c_summary.json`

## Next gate

Only if Stage4C shows repeatable group-level structural separation may the next stage freeze a low-dimensional architecture score/rule and test it on different Universes/eras. No X<=t walk-forward construction is allowed before that cross-Universe validation.