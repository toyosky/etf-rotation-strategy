# OURE Stage8R — Breadth Divergence Findings

Date: 2026-09-16
Authoritative run: `35107261714`
Artifact: `oure-stage8r-breadth-divergence-35107261714`
Status: diagnostic complete; no map-axis replacement

## Frozen definitions

- **Internal Breadth** = fixed-13 share of risky raw 26-day OLS scores > 0.
- **Risk-over-Defense Breadth** = fixed-13 share of risky raw 26-day OLS scores > raw `511220` OLS score.
- **Breadth Divergence** = Internal Breadth - Risk-over-Defense Breadth.
- Rolling percentiles use only prior 252 sessions with minimum 60 observations.

## Main result

Both breadth definitions carry useful state information. Across full history, Internal Breadth is marginally stronger on future return, while Risk-over-Defense Breadth is comparably strong and has a clearer risk/defense interpretation.

Spearman correlation with future FixV2+V1 return:

| Segment | Feature | 5d | 10d | 20d |
|---|---|---:|---:|---:|
| Full | Internal Breadth | 0.095 | 0.165 | 0.198 |
| Full | Risk-over-Defense | 0.092 | 0.160 | 0.188 |
| Post-2023 | Internal Breadth | 0.054 | 0.088 | 0.136 |
| Post-2023 | Risk-over-Defense | 0.061 | 0.104 | 0.138 |

Thus neither should be described as wrong. They answer different questions and retain similar predictive ordering information.

## Divergence is not a strong continuous predictor

Breadth Divergence by itself has near-zero monotonic correlation with future return across the full sample:

- 5d: -0.014
- 10d: -0.006
- 20d: ~0.000

Post-2023 it is mildly negative at 5/10d (-0.057 / -0.053) and ~0 at 20d.

Therefore it should **not** replace either breadth measure as a primary map axis.

## But the upper-tail divergence state is economically interpretable

Using a prior-only rolling percentile, `HIGH_DIVERGENCE` (top 20% of its own trailing-252 distribution) shows lower subsequent FixV2+V1 outcomes than non-extreme/balanced states:

| Horizon | Balanced mean return | High-divergence mean return | Balanced win rate | High-divergence win rate |
|---|---:|---:|---:|---:|
| 5d | 0.93% | 0.42% | 51.2% | 46.4% |
| 10d | 1.81% | 1.10% | 57.6% | 52.6% |
| 20d | 3.56% | 2.72% | 60.3% | 56.1% |

The high-divergence state does not exhibit worse average forward drawdown, so the evidence is more consistent with **weak/low-quality trend diffusion** than with an immediate crash-warning variable.

Economic interpretation:

> Many risky assets can still have positive OLS trends while relatively few are strong enough to beat the defensive comparator. This is a weaker quality of breadth: apparent participation remains broad, but the opportunity cost versus defense has deteriorated.

## Current state (2026-09-15)

- Internal Breadth: 30.77% (4/13)
- Risk-over-Defense Breadth: 30.77% (4/13)
- Divergence: 0.00pp
- Internal Breadth trailing percentile: 20.63%
- Risk-over-Defense Breadth trailing percentile: 31.35%
- Divergence trailing percentile: 71.43%

The current weakness is therefore **not** a high-divergence case. Both definitions are simultaneously low. This supports interpreting the present lower-left map position as genuine broad weakness rather than a cosmetic disagreement between the two breadth concepts.

## Frozen recommendation

1. Keep `Risk-over-Defense Breadth` as the main Market Regime Map x-axis because it has explicit risk-vs-defense meaning and performs slightly better post-2023 at 10/20-day horizons.
2. Preserve `Internal Breadth` as a secondary state metric because it remains independently interpretable and is marginally stronger over the full historical sample.
3. Add `Breadth Divergence` only as an auxiliary warning/annotation, preferably using a rolling percentile rather than a hard raw threshold.
4. Do not create a 3D map. A 2D map plus a small auxiliary breadth-quality indicator is easier to interpret and avoids overfitting the visualization.
5. Before using divergence in trading rules, perform a frozen out-of-sample / non-overlapping-event validation. Stage8R is descriptive, not a promotion test.
