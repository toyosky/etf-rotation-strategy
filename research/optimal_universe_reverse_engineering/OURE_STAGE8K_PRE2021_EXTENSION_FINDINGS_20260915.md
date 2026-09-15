# OURE Stage8K — Pre-2021 Historical Extension Findings

Date: 2026-09-15
Authoritative run: `34993951893`
Artifact: `oure-stage8k-pre2021-extension-34993951893`
Status: frozen historical robustness diagnostic

## Historical availability
Same-engine history can be extended to signal 2015-01-23 / execution 2015-01-26, when cash comparator 511220 first has a finite frozen OLS score.

The current repaired universe is not fully available before 2021. Important listing / first finite score dates include:
- 159915 first finite score 2012-02-09
- 513100 2013-07-05
- 518880 2013-09-02
- 511220 2015-01-23
- 161226 2015-09-25
- 501018 2016-08-18
- 164824 2018-11-06
- 159985 2020-02-20
- 511380 2020-06-19
- 513530 2022-06-02
- 513290 2022-10-11
- 159509 2023-09-12
- 159529 2024-03-18

No proxy or synthetic pre-listing history was used.

## Pre-2021 results (2015-01-26 through 2020-12-31)
- BASE_FIX15: cumulative +191.73%, MDD -31.84%, turnover 313, switches 187, mean Top1 tenure 7.70d, approximate CAGR 19.79%.
- FIX13_PRUNED (drop 159825 + 159981): +166.64%, MDD -31.84%, turnover 313, switches 187, tenure 7.70d, CAGR about 17.98%.
- FIX13_HK_DIV (also replace 513920 with 513530): identical to FIX13_PRUNED before 2021, because neither 513920 nor 513530 was then available.

Annual:
- 2015 +51.49% for all variants
- 2016 -5.03% for all
- 2017 +3.41% for all
- 2018 +9.55% for all
- 2019 +25.07% for all
- 2020 BASE_FIX15 +43.12% vs both repaired variants +30.80%

Thus all pre-2021 difference is concentrated in 2020 and is attributable to removing 159981. 159825 had not yet formed a usable OLS score before year-end 2020, and the dividend replacement is not available until 2022.

In late 2020, 159981 became BASE_FIX15 Top1 for 26 signal days. Its own target-day net returns compound to about +7.13%. From 2020-11-16 onward, BASE_FIX15 compounds about +7.05% while the pruned path is about -2.16%. This directly shows that 159981 was useful in that regime.

## Post-2021 / full-history context
2021 onward through 2026 partial:
- BASE_FIX15 +902.79%, MDD -44.72%
- FIX13_PRUNED +1217.47%, MDD -38.63%
- FIX13_HK_DIV +1453.14%, MDD -34.78%

Full 2015-2026 partial:
- BASE_FIX15 +2825.47%
- FIX13_PRUNED +3412.88%
- FIX13_HK_DIV +4041.25%

The repaired variants still dominate full-history accumulation because their 2021-2026 advantage is large, but the pre-2021 evidence weakens the claim that 159981 is structurally bad.

## Main interpretation
1. Dropping 159825 remains supported by its independent Asset Health WARNING, but this pre-2021 extension cannot test it because the ETF only became usable in 2021.
2. Permanent deletion of 159981 is not robust across regimes. It harms 2020 substantially even though it helps the 2021-2026 sample. 159981 should be treated as a regime-dependent opportunity tool rather than a proven bad member.
3. Replacing 513920 with 513530 cannot be validated before 2021 because 513530 did not exist; its evidence begins in 2022.
4. Therefore the attractive `FIX13_HK_DIV` historical total should not be interpreted as twelve years of independent validation. Before 2020 it is effectively the same smaller subset; the key modifications become testable only later.

## Research implication
The most defensible current structural change is removal of 159825. The 159981 deletion should be downgraded from candidate permanent pruning to unresolved / regime-dependent. The 513530 replacement remains a frozen post-2022 candidate for prospective validation.
