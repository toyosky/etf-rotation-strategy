# OURE Stage8D — Competition-state novelty add-one findings

Date: 2026-09-15
Authoritative run: `34933675463`
Artifact: `oure-stage8d-competition-novelty-add1-34933675463`
Status: frozen historical diagnostic

## Design
The repaired point-in-time OLD_SAFE Opportunity K15 is the Core. Exactly one outside ETF is added using no return magnitude and no Fix15 identity.

For outside ETF i, using the preceding 377 fully-realized historical OLS signal days:
`Novelty_i = mean_t[ active_i(t) / (1 + N_core_active(t)) ]`.

Thus selection rewards trend-eligible states that occur when relatively few Core assets are simultaneously trend-eligible. No fitted threshold is used.

Comparators are CORE15, ordinary repaired Opportunity K16, Novelty K16, and Fix15 benchmark-only.

## Full-period 2021–2026 partial
| Variant | Total return | MDD | Turnover sides | Switches | Mean Top1 tenure |
|---|---:|---:|---:|---:|---:|
| CORE15 | +114.62% | -44.54% | 571 | 300 | 4.68 d |
| NOVELTY_K16 | +102.47% | -43.32% | 585 | 306 | 4.60 d |
| OPPORTUNITY_K16 | +52.77% | -44.67% | 581 | 305 | 4.60 d |
| FIX15 benchmark | +902.19% | -44.72% | 505 | 260 | 5.31 d |

Novelty K16 therefore does not improve the Core15 return, although it loses far less than simply taking the 16th Opportunity-ranked asset and slightly improves full-period MDD versus Core15.

## Year-by-year Novelty K16
- 2021 +67.57% vs Core15 +66.93%
- 2022 +2.54% vs +7.67%
- 2023 -10.96% vs -10.94%
- 2024 +40.84% vs +45.82%
- 2025 +39.95% vs +39.95%
- 2026 partial -32.86% vs -34.30%

There is no broad annual dominance.

## What the selector actually chose
The Novelty rule repeatedly chose structurally different fixed-income / gold-like exposures rather than recent high-return leaders:
- 2020-12-21: 511010
- 2021-06-30 through 2023-07-27: repeatedly 511260
- 2024-01-30: 518800
- 2024-08-09: 511010
- 2025-02-21: 159972
- 2025-08-25: 511260
- 2026-03-09 and 2026-09-08: 511010

This confirms that the rule is mechanically finding different competition states rather than reproducing the Opportunity-return ranking: in all 12 deployment blocks, the Novelty add-one differed from the ordinary Opportunity 16th member.

However, difference alone is insufficient. The added Novelty asset became OLS Top1 only sparsely. Block-level paired impact versus Core15 was positive in only two historical blocks, negative in four, and exactly zero in the remainder. The most important failure for the dormant-optionality question is 2025-08-25: Core15 did not contain 161226, yet the Novelty rule selected 511260 rather than silver. Thus frequency-weighted competition-state novelty still favors assets that are often active in quieter Core states; it does not preserve a deeply dormant but potentially explosive regime tool.

## Interpretation
Stage8D rejects the simple hypothesis that adding the single ETF with the highest frequency-weighted competition-state novelty is enough to improve Core15.

But it also provides useful evidence:
1. competition-state structure can select genuinely different exposures without return-based selection;
2. this structural add-one is materially less destructive than blindly taking the next Opportunity-ranked member;
3. the current Novelty definition over-rewards frequent low-competition activity (especially bond ETFs), so it is closer to `routine diversification` than `latent optionality`.

The unresolved target is therefore narrower: measure distinct *regime exposure* without requiring frequent activation. A next test should separate `state distinctness` from `activation frequency` rather than multiplying them into one score. In particular, a dormant asset should not receive almost zero structural value merely because it rarely enters a trend state.

## Frozen decision
- Do not promote NOVELTY_K16.
- Keep CORE15 as the smaller repaired Opportunity comparator.
- Preserve the result that pure competition-state novelty is more sensible than ordinary K16 extension but still insufficient.
- Do not add amount/volume here; the failure is upstream in how latent distinctness is valued.
