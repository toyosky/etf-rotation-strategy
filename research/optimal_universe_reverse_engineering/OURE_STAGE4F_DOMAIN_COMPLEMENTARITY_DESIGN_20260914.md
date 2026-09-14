# OURE Stage4F — Domain Complementarity / Cross-Exposure Relay Test

Date: 2026-09-14
Status: preregistered

## Question
Does the already replicated large-K relay mechanism arise because good Universes combine economically different ETF exposures whose trend opportunities occur at different times, thereby reducing direct Top1 competition and producing cross-exposure leader handoffs?

This stage is explanatory only. It does not search for a better Universe, alter OLS, tune thresholds, or use these features to construct X<=t Universes.

## Frozen samples
Two independent relay samples are used.

1. Stage3B internal holdout: elite ranks 26..100, with the exact same same-K unused-control construction as Stage4D.
2. Stage3C external construction: elite ranks 1..25, with the exact same exact-K lexicographic controls as Stage4E.

A claim must replicate across both constructions. No post-result subgrouping is allowed.

## Taxonomy
Primary economic-domain label: `risk_bucket` from `instrument_metadata_current`.
Secondary robustness label: `exposure_level1`.

Metadata are current structural labels, not historical point-in-time labels. Therefore Stage4F may explain the hindsight relay mechanism but cannot itself be treated as an executable X<=t rule.

Missing/UNKNOWN labels are reported and never silently dropped.

## Frozen metrics
Static domain structure:
- unique risk-bucket share = unique buckets / K;
- risk-bucket HHI;
- maximum bucket member share;
- same-risk-bucket pair share;
- analogous exposure_level1 measures.

Dynamic opportunity / competition structure, separately full / 2021-24 / 2025-26:
- mean and max pair trend-eligible Jaccard;
- mean trend Jaccard among same-risk-bucket pairs and cross-risk-bucket pairs;
- Top1/Top2 same-risk-bucket share on days with >=2 eligible members;
- cross-risk-bucket leader-transition share on non-cash leader changes;
- active-leader risk-bucket diversity share.

## Primary hypothesis
If economic-domain complementarity is an important source of relay quality, good relay Universes should not merely have many labels. Relative to same-K controls they should show a chain:

1. less concentration in the same economic domain;
2. less same-domain competition near the top of OLS rankings;
3. more leader handoffs across economic domains.

## Frozen primary gate
For each of the two independent constructions, using full-history medians:
- `risk_bucket_hhi` must be lower;
- `top2_same_risk_bucket_share` must be lower;
- `cross_risk_bucket_transition_share` must be higher.

Strong support requires all three directions in both constructions (6/6).
Partial support requires at least 2/3 in both constructions, including `cross_risk_bucket_transition_share` in both.
Otherwise freeze the domain-complementarity hypothesis as not established.

Secondary metrics and era splits are diagnostic only and cannot rescue a failed primary gate.

## Interpretation discipline
- Passing does not prove industry labels cause returns; it supports a structural explanation of relay as cross-exposure opportunity handoff.
- Failing means relay should remain described in dynamic terms (Opportunity Coverage / Replacement Quality / Effective Competition), not forced into an industry-diversification story.
- No return-correlation threshold or taxonomy level may be changed after seeing results.