# OURE Stage6H — Point-in-Time Transfer-State Gate Findings

Date: 2026-09-14
Run: `34861108018`
Artifact: `oure-stage6h-point-in-time-state-gate-34861108018`
Status: frozen_failed
Decision: `low_dof_state_gate_failed`

## Frozen question
Can a strictly X<=t, low-DoF market-state rule identify when historical Universe ranking information will transfer positively into the next half-year?

Frozen trailing-126 state variables:
- OLS eligible fraction: higher than expanding prior median votes transfer-on;
- Top1-Top2 gap median: higher votes on;
- leader switch rate: higher votes on;
- mean leader tenure: lower votes on.

With at least 3 prior decision states available, transfer-on required 3/4 votes. Thresholds were strictly expanding medians of prior decision-state values. The primary target was the frozen Stage6 robust historical-set score -> next-half-year library-rank Spearman.

## Result: primary gate FAIL
Six complete decision periods were evaluable (2023H2 through 2026H1):
- transfer-on: 3;
- transfer-off: 3;
- sign accuracy on robust future Spearman: 50%;
- transfer-on median robust future Spearman: +0.0487;
- transfer-off median: +0.2219;
- on-minus-off: **-0.1732**, opposite desired direction;
- bootstrap mean on-off difference: -0.1815, 95% interval [-0.4672, +0.0824].

Preregistered gates:
1. both states at least 2 observations: PASS;
2. sign accuracy > 60%: FAIL;
3. transfer-on median positive and transfer-off nonpositive: FAIL;
4. on-off median gap >= +0.20: FAIL.

Secondary past6M-rank transfer also did not improve under transfer-on: +0.176 on versus +0.203 off.

## Period diagnostics
- 2023H2: transfer-on, robust future Spearman +0.036;
- 2024H1: transfer-off, +0.222;
- 2024H2: transfer-on, +0.049;
- 2025H1: transfer-off, +0.143;
- 2025H2: transfer-on, +0.353;
- 2026H1: transfer-off, +0.617.

Thus the frozen state vote notably labels 2026H1 as off despite very strong forward rank transfer, and labels 2023H2/2024H2 on despite weak transfer.

## Frozen conclusion
The four-variable trailing-126 expanding-median state rule is insufficient to identify future Universe-rank transfer. Do not tune the variables, thresholds, lookback, or 3-of-4 rule to rescue it.

Stage6I subsequently shows that same-period 126-session K30 RF value ranking is broadly learnable even in 2022-24; therefore Stage6H failure should be interpreted narrowly: the current simple market-state rule cannot tell us whether a historical mapping will transfer to the next period. It does not mean the next period lacks cross-sectional K30 structure.
