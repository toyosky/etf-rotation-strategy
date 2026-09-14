# OURE Stage4B — K30 Pruning Audit Findings

Date: 2026-09-14
Status: frozen
Run: `34830273878`
Artifact: `oure-stage4b-k30-pruning-34830273878`

## Frozen question

Is the Stage3B large-K champion merely a redundant representation, such that several members can be removed without loss, or does its value depend on a genuinely distributed relay architecture?

The audit did not re-search the full market. It only pruned the frozen Stage3B K30 risk-member champion under the same Frozen OLS evaluator.

## Base K30

- Risk members: 30, plus cash 511220.
- Full-history log growth: 3.623785.
- Total return multiple: 36.4792.
- Max drawdown: -21.75%.
- Switch events: 248.
- Mean observed Top1 tenure: 5.447 days.
- All 30 risk members became Top1 at least once.
- Top-5 leaders account for 53.37% of leader days; top-10 for 74.75%.

This already differs from the Stage1 small K7 architecture, where six risk assets carry a much more concentrated and persistent leadership structure.

## Exact deletion shells

Every removal combination was evaluated exactly for depths 1, 2 and 3.

### Delete one

- 30 combinations.
- Improving combinations: 0.
- Least harmful deletion: 159535.
- Best remaining terminal wealth change vs K30: -2.88%.
- Switches: 246.
- Mean Top1 tenure: 5.494 days.

### Delete two

- 435 combinations.
- Improving combinations: 0.
- Least harmful pair: 159535, 159629.
- Best remaining terminal wealth change vs K30: -4.93%.
- Switches: 246.
- Mean Top1 tenure: 5.494 days.

### Delete three

- 4,060 combinations.
- Improving combinations: 0.
- Least harmful triple: 159237, 159535, 159629.
- Best remaining terminal wealth change vs K30: -8.50%.
- Switches: 246.
- Mean Top1 tenure: 5.489 days.

Therefore the earlier observation that no single deletion helps was not merely a one-step local artifact: no two- or three-member deletion improves the frozen champion either.

## Forced downward pruning

After the exact depth-1/2/3 audit, greedy forced pruning repeatedly removed the least damaging remaining member. This path is diagnostic only; below K27 it is not a global cardinality optimum.

Selected checkpoints relative to original K30 terminal wealth:

- K27: -8.50%; 246 switches; tenure 5.49 days.
- K25: -17.06%; 242 switches; tenure 5.58 days.
- K20: -34.92%; 236 switches; tenure 5.74 days.
- K15: -52.15%; 198 switches; tenure 6.73 days.
- K10: -66.86%; 156 switches; tenure 8.84 days.
- K6: -73.40%; 143 switches; tenure 9.79 days.

There is one local non-monotone step on the forced path: K9 -> K8 improves log growth by about 0.063. However K8 remains roughly 69% below the original K30 terminal wealth. This does not rescue a compressed representation.

## Leader occupation

The large-K champion has no dormant risk member in the strict leadership sense: every one of the 30 members becomes Top1 at least once.

Leadership is distributed rather than uniform. The largest contributors include:

- 513500: 228 leader days, 17.66% of invested leader days.
- 513030: 134 days, 10.38%.
- 161631: 133 days, 10.30%.
- 513530: 110 days, 8.52%.
- 160632: 84 days, 6.51%.

The long tail still matters because exact deletion shows that even apparently low-occupation members cannot be removed in combinations of up to three without lowering total value. Their contribution is therefore contextual: they need not dominate leader-day share to alter which leader wins at specific times and how the relay sequence evolves.

## Frozen interpretation

Stage4B supports the relay-architecture hypothesis and rejects the simple redundancy explanation.

The supported statement is deliberately limited:

> The Stage3B K30 champion is not explained by a few trivially removable passengers. Its value is distributed across the member set strongly enough that every exact deletion of one, two or three members reduces frozen downstream value, and forced compression causes progressively large economic loss.

Stage4B does **not** prove that K30 is the minimum-cardinality representation of this value. Exact search beyond delete-3 was not performed, and the deeper forced path is greedy rather than globally optimal.

## Consequence for the main research line

Nominal K is no longer an adequate mechanism variable.

The evidence now supports testing two distinct elite architectures without assuming either is universally superior:

1. **Persistence architecture** — small set, concentrated leaders, longer Top1 tenure, fewer rank crossings/switches.
2. **Relay architecture** — broad opportunity coverage, distributed temporal leadership, more switches, but switches must be productive rather than nuisance churn.

The next stage must compare these architectures against same-K random controls and Fix15 using frozen low-dimensional mechanism metrics. It must test whether the two-state description is actually reproducible across elite sets, not merely visible in the two champions.