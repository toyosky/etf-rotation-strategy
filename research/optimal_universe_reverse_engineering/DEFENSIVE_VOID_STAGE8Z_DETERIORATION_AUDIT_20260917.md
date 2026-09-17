# Stage8Z — DEFENSIVE_VOID deterioration / incumbent-freeze audit

Date: 2026-09-17
Authoritative Actions run: `35165006199`
Artifact: `oure-stage8z-35165006199` (ID `10474089656`)

## Frozen base
- Stage8M FixV2/V1(75)
- 26d weighted log-price OLS, half-life 10
- 6bp per side
- Strict historical availability

## Hypothesis
Entering `DEFENSIVE_VOID` is not itself sufficient evidence that the incumbent trend has failed. Treat Void entry as a warning/freeze state. Only consider leaving the incumbent when the Void state keeps deteriorating and the incumbent itself no longer beats the 511220 hurdle.

## Frozen deterioration rule
During a contiguous Void episode:
1. On entry, freeze the incumbent; do not switch merely because the Map entered Void.
2. Define `deepening` as BOTH `breadth_511220` and `gap_percentile` being below their values on the Void-entry signal day for 2 consecutive Void signal days.
3. A pool switch is permitted only if the frozen incumbent also no longer beats the 511220 OLS score.
4. If deepening + incumbent invalidation occurs, route to 513500 if it is >=365 days old and its OLS score beats 511220; otherwise route to 511220.
5. Once routed inside that Void episode, hold the routed target until Void exits.

No threshold optimization was performed in this stage.

## Full-period results

| Variant | Total return | CAGR | MDD | Sharpe | Calmar | Turnover sides | Switches |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original V1 | +4483.5% | 40.58% | -38.59% | 1.167 | 1.052 | 749 | 408 |
| Void immediate US carrier | +2686.7% | 34.49% | -29.28% | 1.071 | 1.178 | 931 | 479 |
| Freeze incumbent until invalid, then cash | +5476.8% | 43.06% | -32.20% | 1.236 | 1.337 | 635 | 334 |
| Deepening + incumbent invalid -> route | **+5720.8%** | **43.60%** | **-31.98%** | **1.238** | **1.363** | **589** | **307** |

## Interpretation
This stage strongly supports the distinction between `Void entry` and `persistent/deepening Void`.

Immediate routing is too aggressive and destroys a large amount of the original OLS/V1 return. By contrast, simply freezing the incumbent during Void and waiting for self-invalidation already improves both return and drawdown versus Original V1. Adding the parameter-light persistence/deepening requirement improves the result further.

The best Stage8Z candidate improves CAGR by about +3.0pp versus Original V1 while reducing MDD by about 6.6pp, and it reduces switches from 408 to 307 rather than increasing turnover.

## Route rarity
For `DEEPEN_AND_INVALID_THEN_ROUTE` across 160 Void entries:
- `VOID_DEEP_INVALID_TO_CASH`: 16 trigger days
- `VOID_DEEP_INVALID_TO_CARRIER`: 7 trigger days

Thus only 23/160 Void episodes reached the strict route trigger. Most Void episodes are treated as warning/freeze states rather than mandatory exits.

## Selected annual results: deepening route vs Original V1
- 2016: 22.82% vs 10.68%
- 2019: 31.99% vs 27.54%
- 2021: 30.31% vs 34.93%
- 2024: 91.43% vs 65.57%
- 2025: 125.57% vs 115.42%
- 2026*: 164.73% vs 139.88% in this run

The rule does not win every year; 2021 and some earlier years remain counterexamples. This is preferable to a mechanically dominant same-sample rule and requires further robustness checks.

## Important implementation caveat
In this first Stage8Z implementation, the frozen incumbent at Void entry is the Stage8M V1 target on the Void-entry signal day. A follow-up audit should distinguish this from freezing the *pre-Void previous-day incumbent*, because the latter is conceptually closer to “do not react merely because we just entered Void.” This must be checked before promotion.

## Required next checks
1. Pre-Void incumbent vs same-day V1 target at Void entry.
2. Persistence neighborhood: 1 / 2 / 3 consecutive deepening days; no retuning from best historical result.
3. Component ablation: map deepening only vs incumbent invalidation only vs both.
4. 2015-2022 vs 2023-2026 and leave-year-out stability.
5. QDII premium/availability stress for the 7 historical carrier triggers.
6. Confirm the 23 route episodes and examine whether gains are concentrated in a handful of episodes.

## Current status
Promising, not yet promoted. The evidence favors treating `DEFENSIVE_VOID` as a state that freezes new competition first, with switching reserved for persistent map deterioration plus incumbent failure.