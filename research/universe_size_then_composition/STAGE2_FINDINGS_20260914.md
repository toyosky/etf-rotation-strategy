# New Stage 2 — Intrinsic Trend Episode Remaining-Life Findings

Date: 2026-09-14
Source run: `34778676590`
Artifact: `universe-size-stage2-34778676590`
Status: frozen

## Executive conclusion

The frozen intrinsic-lifetime mechanism is only **partially supported**.

Larger Universe size K does systematically admit Top1 ETFs later within their own intrinsic trend episodes and leaves fewer intrinsic active days afterward. This relation is strong and survives both eras.

However, the second half of the proposed chain fails: shorter remaining episode life does **not** translate into systematically lower remaining intrinsic return. In 2021–24 the remaining-return relation is essentially flat; in 2025–26 larger K is associated with a materially higher remaining intrinsic return.

Therefore New Stage2 rejects the strong mechanism:

`K up -> later trend age -> less remaining life -> lower remaining return`

The supported weaker structure is:

`K up -> later normalized trend age -> fewer remaining active days`

while the economic payoff remains governed by a separate coverage-versus-competition trade-off.

The frozen trend-episode definition must not be changed to rescue the rejected return link.

## Frozen evidence

### Trend age

2021–24:
- mean month-level Spearman(K, age_days): +0.472
- K30-K3 age_days: +0.29 days, bootstrap interval crosses zero
- mean month-level Spearman(K, trend_age_ratio): +0.656
- K30-K3 trend_age_ratio: +0.145
- month bootstrap 95%: about [+0.099, +0.189]

2025–26:
- mean month-level Spearman(K, age_days): +0.484
- K30-K3 age_days: +2.70 days
- month bootstrap 95%: about [+0.55, +4.71]
- mean month-level Spearman(K, trend_age_ratio): +0.627
- K30-K3 trend_age_ratio: +0.125
- month bootstrap 95%: about [+0.054, +0.187]

Normalized trend age is therefore the cleaner structural signal than raw age_days.

### Remaining intrinsic life

2021–24:
- mean month-level Spearman(K, remaining_days): -0.462
- negative relation in 75% of months
- K30-K3 remaining_days: -4.73 days
- bootstrap 95%: about [-6.94, -2.64]

2025–26:
- mean month-level Spearman(K, remaining_days): -0.613
- negative relation in 85% of months
- K30-K3 remaining_days: -3.99 days
- bootstrap 95%: about [-6.05, -1.91]

The admission-timing / remaining-days link is therefore robust across eras.

### Remaining intrinsic return — strong mechanism rejected

2021–24:
- mean month-level Spearman(K, remaining_close_return): +0.085
- K30-K3 remaining_close_return: +0.26 percentage points
- bootstrap interval crosses zero

2025–26:
- mean month-level Spearman(K, remaining_close_return): +0.338
- K30-K3 remaining_close_return: +1.74 percentage points
- bootstrap 95%: about [+0.85, +2.84] percentage points

Thus fewer remaining active days do not imply lower remaining return. The 2025–26 result points in the opposite direction.

Within-month relation of trend_age_ratio to remaining_days is strongly negative:
- 2021–24 mean monthly Spearman about -0.573
- 2025–26 about -0.746

But trend_age_ratio to remaining_close_return is approximately flat / weakly positive:
- 2021–24 mean monthly Spearman about +0.020
- 2025–26 about +0.116

This directly separates duration from payoff.

## Coverage and competition structure

The Stage1 structural geometry remains strong:

2021–24, K30-K3:
- winner coverage: +0.202
- switches: +3.36
- observed Top1 tenure: -4.03 days

2025–26, K30-K3:
- winner coverage: +0.094
- switches: +3.45
- observed Top1 tenure: -5.10 days

All corresponding month-level K relations are strong and directionally stable.

The same K increase therefore raises opportunity coverage and downstream competition in both eras. What changes across eras is the economic payoff of that trade-off, not the basic geometry.

## Stage1 pairwise-correlation supplement

The Stage2 artifact also completed the missing Stage1 correlation diagnostics. Mean pairwise correlation and effective N both rise mechanically with K under random same-K sampling, but their cell-level relation with realized return reverses across eras and is not a stable standalone explanation.

Do not reopen Stage1 or reinterpret this supplement as a new K-selection rule.

## Decision

Freeze New Stage2 with decision `reject_strong_lifetime_return_mechanism`.

Proceed to New Stage3 as a low-DoF **conditional size-direction identifiability** audit. Stage3 should ask whether point-in-time coverage/competition state can predict whether expanding K is beneficial next month. It must not select a precise K from this history.

The initial Stage3 target should remain the already-used future size contrast `mean_return(K30) - mean_return(K3)` / its sign. The executable question is only `lean smaller` versus `lean larger`, not an exact cardinality.
