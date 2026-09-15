# OURE Stage8F Challenger Oracle + Event Study
Date: 2026-09-15
Status: preregistered before results.

Frozen: Stage8E 27-slot Economic Base, repaired Opportunity Core15, frozen OLS/cash, next-open accounting, 6bp/side cost, and Stage8E prior-60-session amount representative rule.

Daily challenger = highest-score Economic Base representative outside Core15. Executable only when its raw OLS score strictly exceeds both the highest Core15 risk score and cash score. Future returns never choose the challenger.

Primary oracle ceiling: future information may choose only between the normal Core15 target and this single executable challenger based on next-session realized gross return; normal 6bp/side target-change costs apply. It cannot search the full market or choose a lower-ranked outsider.

Event X<=t: score gap, gap change, challenger score delta, same-challenger persistence, challenger R2/slope, amount_t / median amount of strictly prior 60 sessions, Core leader R2/slope.

Future labels only: challenger minus Core-leader compounded open-to-open alpha over 1/3/5/10 sessions and useful_h=alpha_h>0. Produce daily and episode-start samples.

Decision: small Oracle gain => stop. Material Oracle gain but little stable feature separation => opportunity is not currently predictable. Only material gain plus stable simple separation justifies a separately preregistered gate test. No taxonomy/Core retuning in Stage8F.