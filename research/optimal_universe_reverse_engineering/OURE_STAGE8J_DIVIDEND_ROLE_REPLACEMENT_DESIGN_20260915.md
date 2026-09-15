# OURE Stage8J — Dividend Role Replacement

Date: 2026-09-15
Status: preregistered before Stage8J returns are computed

## Question
The original Fix15 member `513920` was intended to provide dividend exposure, but economically it is a Hong Kong central-SOE dividend product rather than a generic dividend factor. Does replacing it with a cleaner dividend role improve the already-pruned Fix13 path?

## Frozen base
`Fix13 = Fix15 - 159825 - 159981`.

Frozen OLS engine, next-open accounting, 6bp/side cost, calendar, and cash handling are unchanged from Stage8I.

## Variants
1. `BASE_FIX13`: retain 513920.
2. `DROP_513920`: remove 513920 with no replacement.
3. `REPLACE_513920_510880`: replace with 510880, broad Shanghai dividend exposure; PRIMARY test.
4. `REPLACE_513920_515080`: replace with 515080, broad CSI dividend exposure; sensitivity.
5. `REPLACE_513920_512890`: replace with 512890, CSI dividend low-volatility exposure; sensitivity.
6. `REPLACE_513920_513530`: replace with 513530, broad Hong Kong Connect dividend exposure; sensitivity preserving HK region but removing central-SOE restriction.
7. `BASE_FIX15`: original Fix15 benchmark only.

Candidates were frozen by economic role and product maturity/clarity, not by historical backtest return. No threshold or candidate will be changed after outputs are seen.

## Evaluation
Report full-period cumulative return, MDD, turnover sides, switch count, mean Top1 tenure, annual results, and 126-session block breadth versus BASE_FIX13. Primary interpretation follows 510880; other replacements are structural sensitivities, not a winner-search exercise.

## Interpretation discipline
This is still historical repair of a hindsight-influenced seed universe. A better backtest is not clean OOS proof. Replacement is preferred only if it improves portfolio economics broadly rather than merely maximizing same-sample return.
