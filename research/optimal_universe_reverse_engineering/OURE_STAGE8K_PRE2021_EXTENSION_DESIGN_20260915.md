# OURE Stage8K — Pre-2021 Historical Extension

Date: 2026-09-15
Status: preregistered before Stage8K outputs are computed

## Question
Does the current repaired universe continue to behave well when the same frozen daily OLS engine is extended before 2021 using only ETF price history that actually existed at each date?

## Universes
- `BASE_FIX15`: original Fix15.
- `FIX13_PRUNED`: Fix15 - 159825 - 159981.
- `FIX13_HK_DIV`: Fix15 - 159825 - 159981 - 513920 + 513530.

## Historical availability
No synthetic backfill and no proxy data. A symbol that had not listed yet has no score and cannot be selected. It becomes eligible to compete only when the frozen 26-session OLS score is naturally available from its own observed daily bars. This preserves the same Stage8J engine behavior while respecting actual listing dates.

The test starts on the first calendar date on/after 2015-01-01 for which cash comparator 511220 has a finite OLS score, so the same `risk score > cash score` decision rule is valid from the first tested signal.

## Frozen engine
- same weighted 26-session OLS score as Stage8J;
- daily Top1 among available universe members;
- risk target only when its score exceeds cash comparator 511220;
- same next-open to following-open gross mapping;
- 6bp per side costs;
- no new filters or thresholds.

## Outputs
- annual return/MDD/turnover for every year from first valid start through 2026 partial;
- cumulative results for pre-2021 (through 2020-12-31), post-2021, and full history;
- annual average/min/max number of members with finite scores, to show how the universe naturally grows as ETFs list;
- daily target path.

## Interpretation
The pre-2021 segment is useful robustness evidence, but it is not clean prospective OOS because the present-day universe identities were still chosen with hindsight. Results before each member's listing do not use that member, but knowing the eventual set today remains a survivorship/selection caveat.
