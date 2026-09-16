# OURE Stage8S — Breadth Divergence Validation Findings

Date: 2026-09-16
Authoritative run: `35107850817`
Frozen rule: `breadth_divergence_pct252 >= 80%`
Forward horizon: 20 sessions
Non-overlap gap: 20 sessions

## Purpose

Validate whether the Stage8R observation — high `Breadth Divergence = Internal Breadth - Risk-over-Defense Breadth` being associated with weaker subsequent FixV2+V1 returns — is stable enough to promote into the Market Regime Map as an operational warning.

No threshold tuning is allowed in this stage.

## Validation designs

1. 20-session non-overlapping grids.
2. All 20 possible grid offsets, so the result cannot depend on an arbitrary sampling phase.
3. Time segmentation: PRE2021, 2021–2022, POST2023.
4. High-divergence onset events with a 20-session cooldown.
5. Bootstrap on the offset-0 grid as a secondary diagnostic only.

## Key results

### Grid-offset robustness

| Segment | Mean High-minus-NotHigh 20d return | Median | Share of offsets with negative return difference | Mean win-rate difference |
|---|---:|---:|---:|---:|
| PRE2021 | -1.96pp | -2.03pp | 95% | -8.10pp |
| 2021–2022 | -1.35pp | -1.19pp | 70% | -5.08pp |
| FULL | -0.80pp | -0.39pp | 60% | -4.13pp |
| POST2023 | +2.25pp | +4.57pp | 30% | +5.58pp |

The sign is not stable through time. The historical negative effect reverses after 2023.

### High-divergence onset events

Non-overlapping entry/onset events do not support a consistently bearish interpretation:

- FULL: n=71, mean forward 20d return +2.51%, win rate 57.7%.
- PRE2021: n=38, +0.64%, win rate 52.6%.
- 2021–2022: n=11, +3.71%, win rate 63.6%.
- POST2023: n=22, +5.13%, win rate 63.6%.

Therefore high divergence should not be interpreted as a simple sell/risk-off trigger.

### Bootstrap diagnostic

For one arbitrary 20-day grid offset (offset 0):

- High-divergence n=37; Not-high n=101.
- Observed return difference = -3.30pp.
- 95% bootstrap CI = [-6.43pp, -0.11pp].
- Bootstrap probability(diff >= 0) = 2.18%.

This looks statistically negative in that particular grid phase, but the all-offset and time-segment tests show that it is not temporally robust. The bootstrap result must not override the robustness failure.

## Decision

**Do not promote Breadth Divergence to an operational Market Regime warning or trading rule.**

Keep it as a descriptive diagnostic only.

Interpretation:

- `Internal Breadth` remains useful as a measure of internal trend diffusion.
- `Risk-over-Defense Breadth` remains the preferred main Map x-axis because it expresses risk assets' strength versus the 511220 defensive comparator and has stable recent explanatory value.
- `Breadth Divergence` measures the difference between those concepts, but its relationship to future returns is regime-dependent rather than stable.

The Market Regime Map should therefore remain two-dimensional for now:

- X = Risk-over-Defense Breadth
- Y = Leadership Gap percentile

Internal Breadth may be displayed as an auxiliary descriptive metric. Breadth Divergence may be displayed only as context, without a red/green warning label or direct trading interpretation.
