# OURE Stage8H — Bad-slot deletion findings

Date: 2026-09-15
Authoritative run: `34954930707`
Artifact: `oure-stage8h-bad-slot-deletion-34954930707`
Status: frozen historical counterfactual

## Frozen setup
Stage8E Economic Coverage, representative selection, OLS engine, execution calendar and 6bp/side costs were unchanged. Stage8G-defined poor tools were deleted without replacement. Variants were preregistered before Stage8H returns were seen.

## Full-period results, 2021–2026 partial
- BASE_ECONOMIC: +213.34%, MDD -54.81%, turnover 643, mean Top1 tenure 4.25d.
- DROP_CN_FINANCIALS: +255.09%, MDD -51.52%, turnover 647.
- DROP_CN_HEALTHCARE: +282.88%, MDD -49.24%, turnover 639.
- DROP_CN_VALUE_DEFENSIVE: +196.02%, MDD -55.57%, turnover 637.
- DROP_CN_CONSUMER: +238.10%, MDD -51.24%, turnover 647.
- DROP_562500_ONLY: +257.29%, MDD -53.13%, turnover 639.
- DROP_TOP3_BAD_SLOTS (FINANCIALS + HEALTHCARE + VALUE_DEFENSIVE): +316.16%, MDD -46.13%, turnover 641.
- DROP_TOP4_BAD_SLOTS (+ CONSUMER): +377.89%, MDD -42.21%, turnover 631, mean Top1 tenure 4.31d.
- FIX15_BENCHMARK: +902.19%, MDD -44.72%, turnover 505.

## Annual breadth of cumulative deletion
DROP_TOP4_BAD_SLOTS vs BASE_ECONOMIC:
- 2021: +7.34% vs +10.95% (worse)
- 2022: -19.56% vs -25.78% (better)
- 2023: +2.65% vs -5.75% (better)
- 2024: +5.10% vs -8.96% (better)
- 2025: +110.01% vs +99.71% (better)
- 2026 partial: +144.29% vs +122.06% (better)
Thus the gain is not solely a 2025–2026 effect; 5 of 6 annual slices improve.

## 126-session block robustness
Relative to BASE_ECONOMIC over 12 blocks:
- DROP_CN_HEALTHCARE: better 7, worse 1, tied 4; mean block return delta +1.95pp.
- DROP_CN_FINANCIALS: better 5, worse 2, tied 5; mean delta +1.22pp.
- DROP_CN_CONSUMER: better 4, worse 1, tied 7; mean delta +0.68pp.
- DROP_CN_VALUE_DEFENSIVE: better 3, worse 2, tied 7; mean delta -0.45pp.
- DROP_562500_ONLY: better 1, worse 1, tied 10; mean delta +1.33pp, reflecting that 562500 was selected only in blocks 7–9.
- DROP_TOP3_BAD_SLOTS: better 8, worse 2, tied 2; mean delta +3.07pp.
- DROP_TOP4_BAD_SLOTS: better 9, worse 1, tied 2; mean delta +4.23pp.

## Interpretation
1. CN_HEALTHCARE deletion has the strongest single-slot support: higher total return, materially lower MDD, lower turnover, and broad block-level improvement.
2. CN_FINANCIALS deletion is also supported, though less strongly than healthcare.
3. CN_CONSUMER deletion is modestly positive and broad enough to remain a candidate.
4. CN_VALUE_DEFENSIVE is NOT validated as a standalone deletion: removing it alone reduces return and worsens MDD. Its presence in the successful cumulative TOP3/TOP4 variants reflects interaction and must not be interpreted as proof that value/defensive should be deleted by itself.
5. Removing 562500 improves the full path, but the evidence is concentrated in only three blocks and is not enough to condemn the whole CN_INDUSTRIAL_DEFENSE slot.
6. The cumulative TOP4 deletion is the strongest historical variant tested here: +377.89% with MDD -42.21% versus +213.34%/-54.81% base. It improves 5/6 years and 9/12 blocks, while also reducing turnover.
7. Fix15 remains far ahead in return (+902.19%), so bad-slot deletion closes part of the gap but does not explain the full Fix15 advantage.

## Frozen decision
Stage8H supports promoting CN_HEALTHCARE and CN_FINANCIALS to high-priority exclusion/replacement research, with CN_CONSUMER secondary. CN_VALUE_DEFENSIVE remains unresolved and should not be dropped on standalone evidence. 562500 should be treated as a representative-selection problem, not a whole-slot deletion conclusion.

A live/practical universe change is not authorized by this historical counterfactual alone because Stage8G generated the deletion candidates on the same historical sample. A proper point-in-time health-gated or separate prospective validation is still required to eliminate hindsight in the deletion decision.
