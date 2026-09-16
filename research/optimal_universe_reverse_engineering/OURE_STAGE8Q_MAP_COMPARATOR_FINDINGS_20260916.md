# OURE Stage8Q — Market Regime Map Comparator Robustness

Date: 2026-09-16
Authoritative run: `35106287880`
Artifact digest: `sha256:6ee0e894c8cbf27e37e196d777c08fde1eb94c2c60f1fb5e357a6cd61e9c588f`
Status: exploratory diagnostic; no comparator replacement

## Question
The website Market Regime Map defines horizontal Breadth as the fixed-13 share of risky FixV2 OLS scores above the defensive comparator OLS score. The live baseline is `511220`.

This stage asks whether `511220` is merely an arbitrary low-volatility bond benchmark or whether it materially defines the state map.

The authoritative rerun uses the website's raw 26-day OLS score definition and deliberately does NOT reuse the strategy `pool_score` / recent_drop3 eligibility mask.

## Post-2023 state-map agreement versus 511220

| Comparator | Breadth Spearman | Breadth MAE | 50% side agreement | Quadrant agreement | Transition agreement |
|---|---:|---:|---:|---:|---:|
| 511220 城投债 | 1.000 | 0.00pp | 100.0% | 100.0% | 100.0% |
| 511010 国债 | 0.874 | 6.53pp | 85.9% | 85.9% | 89.8% |
| 511260 10年国债 | 0.844 | 7.55pp | 84.2% | 84.2% | 89.8% |
| 511360 短融 | 0.869 | 5.35pp | 90.2% | 90.2% | 94.2% |
| 511520 政金债 | 0.837 | 7.02pp | 86.5% | 86.5% | 91.9% |
| 511580 国债政金债 | 0.859 | 5.87pp | 88.2% | 88.2% | 93.4% |

Interpretation: the map is structurally robust to the broad concept of a defensive fixed-income comparator, but the exact comparator is not irrelevant. Replacing 511220 changes the horizontal side of the map on roughly 10-16% of post-2023 sessions depending on the alternative.

`511360` is the closest substitute by state-path stability, consistent with Stage8P, but it is not identical.

## Predictive utility of Breadth for the fixed FixV2+V1 path

Spearman correlation of Breadth with future strategy return:

### Full available history
| Comparator | 5d | 10d | 20d |
|---|---:|---:|---:|
| 511220 | 0.092 | 0.160 | **0.188** |
| 511010 | 0.085 | 0.140 | 0.151 |
| 511260 | 0.080 | 0.129 | 0.128 |
| 511360 | 0.094 | 0.135 | 0.122 |
| 511520 | 0.066 | 0.089 | 0.122 |
| 511580 | 0.030 | 0.058 | 0.101 |

### Post-2023
| Comparator | 5d | 10d | 20d |
|---|---:|---:|---:|
| 511220 | 0.061 | **0.104** | **0.138** |
| 511010 | 0.034 | 0.057 | 0.078 |
| 511260 | 0.033 | 0.069 | 0.113 |
| 511360 | **0.073** | 0.084 | 0.100 |
| 511520 | 0.061 | 0.081 | 0.120 |
| 511580 | 0.030 | 0.058 | 0.101 |

This is same-sample diagnostic evidence, not a tuned forecast model. Still, 511220 is notably strong at the 10-20 day horizons in both full history and post-2023. There is no evidence here that replacing it would improve the map.

## Current state robustness
On 2026-09-15:
- 511220 Breadth = 4/13 = 30.77%
- Gap percentile = 2.38%
- quadrant = `DEFENSIVE_VOID`
- Top1 = 501018; Top2 = 159981

Five of the six tested comparators also produce Breadth 4/13 and all six classify the current state as `DEFENSIVE_VOID`; 511260 produces 3/13. Therefore the current weak/left-lower state is not an artifact of 511220 alone.

## Architecture conclusion
511220 has three distinct roles and they should remain separated explicitly:
1. strategy defensive comparator / gate;
2. optional defensive carrier when risk is rejected;
3. Market Regime Map horizontal benchmark.

Stage8P found that 511220's strategy value is primarily the gating role rather than the held carry. Stage8Q now shows that its map-benchmark role also carries non-trivial information.

Do not replace 511220 in the map from the current same-sample audit. If a future replacement is considered, the frozen candidate is 511360 because it is the closest state-path substitute, but it would require forward / walk-forward confirmation.

## Implementation note
The historical Stage8N diagnostic script used a different `breadth` implementation from the website map. The website definition (`share(raw risky OLS score > raw 511220 OLS score)`) is now treated as the authoritative Market Regime Map definition. Future regime research should use that definition explicitly.
