# OURE Stage8I — Fix15 Pruning / Economic Replacement Findings

Date: 2026-09-15
Authoritative run: `34976572473`
Artifact: `oure-stage8i-fix15-prune-replace-34976572473`
Status: frozen historical repair diagnostic

## Frozen setup
Fix15, frozen daily OLS engine, next-open accounting and 6bp/side cost were unchanged. Stage8I tested no-replacement pruning plus one-for-one economic-slot replacement after deleting `159825`. Replacement representatives used the frozen Stage8E point-in-time prior-60d median-amount rule, not historical return selection.

Fix15 is itself a hindsight-influenced seed universe. Stage8I therefore tests historical repair, not unbiased universe discovery.

## Base
BASE_FIX15, 2021–2026 partial:
- cumulative return +902.19%
- MDD -44.72%
- turnover sides 505
- switch events 260
- mean Top1 tenure 5.31d

## Primary pruning results
### `159825` agriculture-equity removal
`DROP_159825`:
- cumulative +1,091.60%
- MDD -42.88%
- turnover 495
- mean tenure 5.41d
- better/worse/tied years: 4/1/1
- better/worse/tied 126-session blocks: 4/2/6

This independently confirms that the prior Asset Health WARNING is economically relevant to the Fix15 path.

### `159981` energy-chemical removal
Despite formal Asset Health HEALTHY, `DROP_159981` improves the portfolio:
- cumulative +1,006.10%
- MDD -39.79%
- turnover 489
- better/worse years 4/2
- better/worse/tied blocks 7/4/1

This distinguishes own-asset continuation from portfolio marginal value: an asset can have positive future return after Top1 and still be harmful if it displaces an even better alternative.

### Remove both `159825` and `159981`
`DROP_159825_159981` is the strongest preregistered simple pruning variant:
- cumulative +1,216.68%
- MDD -38.63%
- turnover 481
- switch events 249
- mean tenure 5.56d
- better/worse years 5/1
- better/worse/tied blocks 8/3/1

Annual return vs BASE_FIX15:
- 2021: +15.17% vs +20.19% (worse)
- 2022: +21.17% vs +18.57%
- 2023: +28.24% vs +26.34%
- 2024: +26.72% vs +16.51%
- 2025: +139.26% vs +124.50%
- 2026 partial: +142.68% vs +112.80%

This is important because both return and risk improve while K and competition are reduced; no new asset is required to obtain the improvement.

### Soymeal `159985`
`DROP_159985` also improves cumulative return to +1,071.75%, but evidence is less clean than `159825`/`159981`. `159985` has positive all-Top1 continuation in the original Asset Health diagnostics. Removing `159825 + 159985` reaches +1,187.90%, MDD -42.51%, but it is not as attractive as dropping `159825 + 159981` on risk/turnover/breadth.

## Full leave-one-out diagnostic
The largest positive single-member deletion effects are:
- `164824` India LOF: +1,119.32% cumulative, +217.13pp delta vs base; all 6 annual slices improve, but block breadth is only 5 better / 4 worse / 3 tied.
- `159825`: +1,091.60%.
- `159985`: +1,071.75%.
- `159981`: +1,006.10%.
- `513290`: +977.82%, but MDD worsens to -48.62%.

The most indispensable members by leave-one-out damage are:
- remove `161226` silver -> only +344.85%
- remove `501018` crude oil -> +473.73%
- remove `159915` ChiNext -> +786.25%
- remove `513100` Nasdaq -> +873.76%

Gold `518880` and several other members have small positive leave-one-out deltas, but same-sample marginal diagnostics are not sufficient to remove structural optionality tools.

## Replacement matrix after deleting 159825
The strongest missing-slot replacement is EUROPE:
`REPLACE_159825_WITH_EUROPE`:
- cumulative +1,248.85%
- MDD -42.10%
- turnover 485
- mean tenure 5.53d
- versus `DROP_159825`, better/worse years 5/1 and blocks 5/2/5

The historical representative is almost always `513030` Germany ETF; one block uses `513080` France ETF under the frozen point-in-time liquidity rule.

Other positive replacements vs `DROP_159825`:
- CREDIT: +1,149.70%, but almost all historical difference occurs in limited later availability; weak breadth.
- GOV_DURATION: +1,119.21%, small improvement.
- JAPAN: +1,114.35%, but aggregate block delta is unstable despite 6/2/4 block win/loss/tie counts and later listing availability.
- CN_FINANCIALS: only slight return increase and materially worse MDD; reject as attractive replacement.

Most A-share sector additions are harmful: CN_TECH_DIGITAL, CN_INDUSTRIAL_DEFENSE, CN_RESOURCES_ENERGY, CN_HEALTHCARE, CN_MID_SMALL and CN_CONSUMER all underperform `DROP_159825` while generally increasing competition/turnover. This reinforces the hypothesis that Fix15's sparse cross-asset structure is more valuable than broad sector coverage.

## Main interpretation
Stage8I supports pruning before expansion.

The simplest historically attractive repair is:
`Fix15 - 159825 - 159981`.
It materially improves total return, MDD, turnover and Top1 tenure with broad annual/block support.

A Europe replacement after removing `159825` is also promising, but it adds a new selection layer and has worse MDD than the two-member pure-pruning variant. Therefore addition is not necessary to obtain a strong historical improvement.

The result also changes the interpretation of Asset Health: member health should not be based only on the asset's own forward return after Top1. Portfolio marginal opportunity cost matters. `159981` is the clearest example: individually HEALTHY, yet deletion improves the portfolio broadly.

## Caution / next step
All pruning candidates and replacement comparisons use the same historical sample in which Fix15 and its problems were observed. Do not label `Fix15 - 159825 - 159981` as clean OOS proof.

The next clean step should be either:
1. point-in-time historical health-gated pruning (at each date, a member can be excluded only using health evidence available before that date), or
2. prospective monitoring from the frozen 2026-09-15 decision.

If another exploratory stage is run, the most important unresolved question is whether `164824` should also be pruned and whether EUROPE adds value on top of the already-pruned `159825 + 159981` base; those combinations were deliberately not searched post hoc in Stage8I.
