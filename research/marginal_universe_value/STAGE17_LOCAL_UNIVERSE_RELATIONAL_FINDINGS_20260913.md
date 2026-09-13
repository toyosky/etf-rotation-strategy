# MUV Stage 17 — Local-Universe Relational Findings

Date: 2026-09-13

## Result

Stage 17 completed successfully under the frozen expanding-window OOS design.

Overall active-row conditional sign discrimination improved from AUC 0.5472 to 0.5768 after adding the frozen local-Universe relational features, a +0.0295 change.

By period:

- 2023–24: AUC 0.5331 -> 0.5714 (+0.0383)
- 2025–26: AUC 0.5588 -> 0.5635 (+0.0047)

The direction is non-negative in both frozen periods, so the result supports a weak relational signal rather than a pure period-specific reversal.

However calibration did not improve:

- overall Brier 0.2661 -> 0.2731
- 2023–24 Brier 0.2826 -> 0.2907
- 2025–26 Brier 0.2476 -> 0.2533

## Interpretation

The evidence is therefore narrower than "local relational state solves signed MUV".

It supports the statement that the ETF's relation to the current local competing set contains incremental ranking information about the sign of conditional MUV. The effect is materially stronger in 2023–24 than 2025–26 and does not improve probability calibration.

This is not sufficient evidence for a retention policy or a threshold. No subset of the nine relational variables will be selected post hoc.

## Mechanistic implication

The next minimum-free-degree step is to stop compressing the counterfactual into a single signed monthly MUV target and audit the displacement mechanism directly:

1. when incumbent i is selected in the baseline path, which asset/cash state replaces it in the remove-one counterfactual;
2. whether the current as-of local top-1 / top-3 competitor set contains that realized replacement;
3. how concentrated the realized replacement identity is over the affected path segment;
4. how much of monthly MUV is attributable to those direct displacement days versus spillover days.

This uses future identity only as a label-side diagnostic, never as an input feature.

## Decision

Proceed to Stage 18 explicit path-displacement label audit. Do not tune Stage 17 features or decision thresholds.