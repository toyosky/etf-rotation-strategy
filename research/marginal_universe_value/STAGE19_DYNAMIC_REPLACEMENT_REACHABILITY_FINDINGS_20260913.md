# MUV Stage 19 — Dynamic Replacement Reachability Findings

Date: 2026-09-13

## Status

Completed after one mechanical workflow fix. The initial run failed because `build_stage19_replacement_pairs.py` called `_db_url()` without its required raw URL argument. The rerun passed the database URL explicitly and completed successfully. The research design was unchanged.

## Frozen question

Can point-in-time incumbent-candidate OLS score/rank trajectory state rank the next-month realized dominant non-cash replacement better than static month-end score rank?

## OOS results

148 non-cash replacement events were evaluated from 2023-01 onward under strict monthly expanding OOS.

### Overall

- Static score rank: Hit@1 0.338, Hit@3 0.561, MRR 0.475, median rank 2.
- Dynamic pairwise trajectory model: Hit@1 0.223, Hit@3 0.446, MRR 0.413, median rank 4.

### 2023-24

- Static: Hit@3 0.597, MRR 0.487.
- Dynamic: Hit@3 0.468, MRR 0.428.
- Delta: Hit@3 -0.130, MRR -0.059.

### 2025-26

- Static: Hit@3 0.521, MRR 0.463.
- Dynamic: Hit@3 0.423, MRR 0.396.
- Delta: Hit@3 -0.099, MRR -0.067.

## Frozen interpretation

The pre-declared support rule fails decisively. Dynamic 20-day pairwise score/rank trajectory state does not provide stable incremental replacement reachability. It deteriorates both Hit@3 and MRR overall and in both time regimes.

Do not tune feature subsets, horizons, cutoffs, or hyperparameters on the same history to rescue this branch.

## New mechanism clue

Among the 148 OOS realized non-cash dominant replacements, 35 have no finite static score rank at the decision as-of. That is 23.65% overall:

- 2023-24: 16/77 = 20.78%
- 2025-26: 19/71 = 26.76%

Therefore a material fraction of realized replacements are not currently qualified at month-end. This suggests that the main unresolved mechanism may be **replacement emergence / admission into competition**, not fine ranking among already-qualified candidates.

## Next admissible stage

Stage 20 should be a no-new-model emergence audit. It should measure how often realized replacements are:

1. qualified at as-of;
2. unqualified at as-of but qualified at least once in the prior 20 trading days;
3. completely absent from qualification during the prior 20 days;
4. previously present in top-3 during the prior 20 days.

The purpose is to decide whether the retention problem should pivot toward admission/emergence modeling before any transition-value model is attempted.
