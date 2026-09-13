# MUV Stage 20 — Replacement Emergence Audit

Date: 2026-09-13

## Motivation

Stage 18 showed that retention MUV is almost entirely generated on direct displacement days. Stage 19 then showed that a fixed 20-day dynamic pairwise score/rank trajectory model performs worse than static month-end score rank when ranking the realized dominant replacement.

A new clue is that 23.65% of Stage-19 OOS realized non-cash dominant replacements have no finite static score rank at the decision as-of. This rate rises from 20.78% in 2023-24 to 26.76% in 2025-26.

The next lowest-degree-of-freedom question is therefore whether replacement identity failure is primarily an **emergence/admission** problem rather than a ranking problem among already-qualified candidates.

## Frozen Stage-20 question

> How often does the next-month realized dominant replacement emerge from outside the currently qualified set, and was that future replacement already intermittently visible in the prior 20-trading-day competition path?

Stage 20 is a mechanism audit only. No model is trained.

## Inputs

Reuse Stage-19 candidate-pair rows and Stage-19 OOS event IDs. The realized dominant replacement remains label-side only.

For the realized replacement row of each OOS event, inspect only point-in-time variables already frozen in Stage 19:

- `x_pair_j_qualified_now`
- `x_pair_j_qualified_frac20`
- `x_pair_j_top3_frac20`
- `x_pair_j_top1_frac20`
- `static_score_rank`

## Frozen categories

No fitted threshold is introduced.

1. `qualified_now`: replacement has a finite current score / static rank.
2. `emergent_recent`: unqualified now, but `qualified_frac20 > 0`.
3. `dormant_20`: unqualified now and `qualified_frac20 == 0`.
4. `top3_visible_recent`: `top3_frac20 > 0`.
5. `top1_visible_recent`: `top1_frac20 > 0`.

The `> 0` tests mean literal historical occurrence at least once, not tuned cutoffs.

## Outputs

Report overall and separately for 2023-24 / 2025-26:

- share qualified now;
- share emergent recent;
- share dormant 20;
- share top3-visible recent;
- share top1-visible recent;
- median/mean prior-20 qualification fraction;
- median/mean prior-20 top3 fraction.

Also report static baseline Hit@1 / Hit@3 / MRR restricted to `qualified_now` events, to separate ranking quality from emergence coverage.

## Interpretation rule frozen before results

- If most failures are `qualified_now`, the problem remains ranking among known competitors; do not pivot to admission solely from Stage 19.
- If a material and persistent share is unqualified now but recently visible, prioritize a transition-to-qualification / admission model.
- If many realized replacements are `dormant_20`, recent score/rank state is structurally insufficient; a different state representation or broader admission process is required.

No policy backtest, feature search, threshold search, or horizon tuning is allowed in Stage 20.
