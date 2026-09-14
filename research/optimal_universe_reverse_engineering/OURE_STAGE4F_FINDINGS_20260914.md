# OURE Stage4F — Domain Complementarity / Cross-Exposure Relay Findings

Date: 2026-09-14
Run: `34844096850`
Artifact: `oure-stage4f-domain-complementarity-34844096850`
Status: frozen
Decision: `domain_complementarity_not_established`

## Frozen question
Does the already replicated large-K relay mechanism arise because good Universes combine economically different ETF exposures whose trend opportunities occur at different times, reducing direct Top1 competition and producing cross-exposure leader handoffs?

Two independent samples were used without post-result filtering:
- Stage3B holdout elites ranks 26..100 versus exact same-K unused controls (`75 vs 75`);
- Stage3C external elites ranks 1..25 versus exact-K controls (`25 vs 25`).

Primary economic-domain label was frozen as `risk_bucket`; `exposure_level1` was secondary diagnostic only.

## Primary preregistered gate — FAIL
Strong support required, in both constructions:
1. lower `risk_bucket_hhi`;
2. lower `top2_same_risk_bucket_share`;
3. higher `cross_risk_bucket_transition_share`.

Observed full-history elite-minus-control effects:

### Stage3B holdout
- `risk_bucket_hhi`: `+0.00889` — opposite;
- `top2_same_risk_bucket_share`: `-0.01489` — supportive;
- `cross_risk_bucket_transition_share`: `-0.01632` — opposite.

Only `1/3` primary directions matched.

### Stage3C external
- `risk_bucket_hhi`: `+0.00253` — opposite;
- `top2_same_risk_bucket_share`: `-0.02362` — supportive;
- `cross_risk_bucket_transition_share`: `-0.00915` — opposite.

Again only `1/3` primary directions matched.

The mandatory cross-domain leader-transition condition failed in both constructions. Therefore neither strong nor partial support is allowed under the preregistered rule.

## What did survive diagnostically?
A weaker statement received repeated support: good relay Universes show less direct same-domain crowding near the top of the OLS ranking.

Full-history `top2_same_risk_bucket_share` is lower in both independent elite samples. This is consistent with reduced same-domain Top1/Top2 competition, but it does **not** imply that leader changes preferentially occur across risk buckets.

At the broader `exposure_level1` taxonomy, both constructions are also more diversified than controls:

Stage3B holdout:
- exposure1 HHI difference `-0.16566`;
- exposure1 unique-share difference `+0.03333`;
- same-exposure1 pair-share difference `-0.17094`.

Stage3C external:
- exposure1 HHI difference `-0.14662`;
- exposure1 unique-share difference `+0.03725`;
- same-exposure1 pair-share difference `-0.14924`.

These are secondary diagnostics and cannot rescue the failed primary gate. They suggest broad economic-exposure diversification may be a useful structural prior, but not a validated causal explanation of relay.

## Trend-overlap diagnostics
The external Stage3C sample shows clearly lower trend overlap relative to controls:
- mean pair trend Jaccard `-0.05642`;
- max pair trend Jaccard `-0.06768`.

Stage3B holdout is weaker/mixed:
- mean pair trend Jaccard `-0.00147`;
- max pair trend Jaccard `+0.03854` (opposite).

Therefore low trend overlap is not yet a cross-construction universal relay signature at this stage.

## Era diagnostic
Cross-domain transitions are not stable by era. In 2021-24 they are approximately neutral/slightly supportive, while in 2025-26 elite Universes have **lower** cross-risk-bucket transition share than controls in both constructions. This is decisive against the simple story that relay quality comes from leaders repeatedly handing off across different labeled domains.

## Frozen interpretation
Do **not** promote the statement:
> "Good relay Universes work because ETF industries are mutually exclusive and leaders take turns across industries."

What remains supported is narrower:
1. broad exposure diversification is present as a secondary structural pattern;
2. same-domain Top1/Top2 crowding is somewhat lower;
3. but the validated relay mechanism remains dynamic: `Opportunity Coverage + Replacement Quality - Harmful Competition`;
4. economic-domain labels alone do not explain the positive replacement quality.

The next X<=t stage may use broad exposure diversification only as a low-dimensional structural prior/constraint, not as the primary predictive mechanism. Dynamic historical proxies for coverage and replacement quality remain the main candidates.

Caveat: `instrument_metadata_current` is current structural metadata, not point-in-time historical metadata. Stage4F is explanatory only.