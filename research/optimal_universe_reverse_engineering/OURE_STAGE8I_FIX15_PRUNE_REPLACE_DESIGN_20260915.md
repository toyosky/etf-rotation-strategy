# OURE Stage8I — Fix15 Pruning / Economic Replacement Matrix

Date: 2026-09-15
Status: preregistered before Stage8I returns are computed

## Question
Treat the historically strong Fix15 as a seed universe. Can limited pruning of empirically poor members and/or one-for-one addition of missing economic exposures improve the same frozen OLS engine without increasing universe size?

## Important bias statement
Fix15 itself is not a clean ex-ante discovery result; it contains human historical selection. Stage8I therefore does NOT claim to discover an unbiased optimal universe. It asks a narrower practical question: can a successful existing seed universe be repaired with simple, interpretable changes?

## Frozen base
Fix15 symbols are unchanged from prior OURE studies. `511220` remains the cash comparator and is not counted as a risky member.

Same frozen daily OLS engine, next-open accounting, and 6bp/side transaction cost as Stage7H/Stage8E.

## Phase A — pruning
Run the following without replacement:
1. BASE_FIX15.
2. Leave-one-out for every non-cash Fix15 risk member (exploratory marginal diagnostic).
3. Explicit preregistered focal variants:
   - DROP_159825 (old agriculture-equity Asset Health WARNING).
   - DROP_159985 (soymeal Asset Health WATCH; overall Top1 continuation is positive, so this is diagnostic only).
   - DROP_159981 (energy-chemical; user-nominated concern despite formal Asset Health HEALTHY).
   - DROP_159825_159981.
   - DROP_159825_159985.

No post-run greedy deletion or combinatorial search is allowed inside Stage8I.

## Phase B — economic replacement after removing 159825
Use `DROP_159825` as the replacement base. Determine which frozen Stage8E economic slots are not represented by the remaining Fix15 risk assets.

For every missing slot, create one replacement variant:
- at each 126-session decision date, use the frozen Stage8E point-in-time eligible common pool;
- fill that one slot with the Stage8E frozen representative rule: highest median trading amount over the immediately prior 60 completed sessions, ties by symbol;
- if the slot has no eligible representative at that historical decision, add nothing for that block;
- add at most one representative, so risky K never exceeds original Fix15 risky K.

No historical return, Asset Health result, future performance, or Fix15 benchmark return is used to choose the representative within a slot.

This tests the value of the missing economic exposure, not a hand-picked ETF code.

## Required outputs
For all variants report:
- full-period compounded return, MDD, turnover sides, switch events, mean Top1 tenure;
- annual 2021–2026 partial returns;
- 126-session block returns;
- for every pruning variant, delta vs BASE_FIX15;
- for every replacement variant, delta vs DROP_159825;
- replacement slot and actual point-in-time representative by block.

## Interpretation gates
A proposed pruning/replacement is more credible when improvement is broad across years and 126-session blocks and does not materially worsen MDD/turnover.

A high full-period return driven by one late block is insufficient evidence.

Stage8I is historical repair research only. No live Fix15 change is authorized solely from this same-sample result.
