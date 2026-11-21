# Q7B supplementary preregistration: single-ticket confirmed reentry, before Q7B outcomes
**2026-11-21**, explicitly responsive to Q7 observed failure: capped 10pp/day buybacks generated MORE adjustments than the Q6 daily baseline (371 vs 331), despite lower weight turnover. These are new **exploratory** structural interventions after reading Q7 C/D results, not independent validation of the optimal strategy. Do not silently replace prereg Q7.

Frozen Q90 2021-01-04 through 2026-11-12 source, original Top1 dynamic route/ret, unchanged daily E, same daily T floor5, 5pp fast-sell trigger, cash-only, transaction fees and comparison periods as Q7.

Three fixed added execution controls, now frozen before their results:
- **S1**: worsening target >= current E +5pp → immediately change to target E. Lower target <= current E-5pp on two consecutive signal dates → restore entire difference in *one ticket* (not a 10pp/day ladder), then reset confirmation. If risk remains relieved with residual, re-confirm anew. No full-size hold/lock.
- **S2**: same instant worsening sells; only if target at least10pp below current E for 2 consecutive closes, buy entire desired reduction in a single ticket. If raw target exactly zero for three consecutive days and E>0, clear all leftover, including sub10pp dust. All decisions on signal close for next-open execution. Trade minimum 10pp corresponds to nominal >=2000 yuan at 20k initial account.
- **S3**: S1 but require three consecutive confirmation closes. Do not tune beyond these options.
- **Fixed 8.673607% cash overlay**: constant risk reduction on all days with nonempty Top1 (equal to Q7 C's observed average E, *a descriptive comparator*, NOT a prospective deployable rule), for assessing whether C risk reduction mostly follows larger cash budget. Constant alpha expectation unknown. 8.6736% is picked after Q7 results, explicitly not pre-registered financial strategy; descriptive only.

Report C and D unchanged from Q7 alongside S1/2/3 and original 5day/daily; compare same 6bp costs, 20,000 yuan account min5 tickets, and additional 4bp per side. Capital and max DD by year, changes and ticket count, average E, stale cash duration. Use yearly 20 trading-day moving-block 2000+ replications. Don't treat pre-seen 2021–26 as a blind backtest; no production changes.
