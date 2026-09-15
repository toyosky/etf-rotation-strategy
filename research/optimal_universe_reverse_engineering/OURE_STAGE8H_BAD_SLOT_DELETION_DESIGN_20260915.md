# OURE Stage8H — Bad-slot deletion counterfactual

Date: 2026-09-15
Status: preregistered before Stage8H return outputs are computed

## Question
Do the economically distinct but empirically poor OLS Top1 tools identified in frozen Stage8G materially drag the frozen Stage8E Economic Coverage portfolio?

## Frozen base
- Stage8E 27-slot economic taxonomy unchanged.
- Stage8E point-in-time representative selection unchanged.
- Same daily OLS engine, eligibility, next-open accounting, calendar and 6bp/side cost.
- No replacement is introduced in the primary deletion tests.

## Primary variants
1. `BASE_ECONOMIC` — unchanged Stage8E Economic Coverage.
2. `DROP_CN_FINANCIALS` — remove the selected representative of CN_FINANCIALS from each block.
3. `DROP_CN_HEALTHCARE` — remove CN_HEALTHCARE.
4. `DROP_CN_VALUE_DEFENSIVE` — remove CN_VALUE_DEFENSIVE.
5. `DROP_CN_CONSUMER` — remove CN_CONSUMER.
6. `DROP_TOP3_BAD_SLOTS` — remove FINANCIALS + HEALTHCARE + VALUE_DEFENSIVE together.
7. `DROP_TOP4_BAD_SLOTS` — remove the above three + CONSUMER.
8. `DROP_562500_ONLY` — remove symbol 562500 whenever it is the chosen CN_INDUSTRIAL_DEFENSE representative; do not replace it. This isolates the representative-level warning from deletion of the whole industrial slot.
9. `FIX15_BENCHMARK` — benchmark only; not used to select deletions.

These variants are fixed from Stage8G evidence before Stage8H returns are seen. No additional WATCH slot is deleted in this stage.

## Outputs
- full-period compounded return, MDD, turnover sides, mean Top1 tenure;
- annual returns 2021–2026 partial;
- block-level path comparison to identify whether gains/losses are broad or concentrated;
- actual removed symbol by block for each deletion rule.

## Interpretation
A deletion is not promoted merely because full-period return rises. It should improve economically meaningful robustness across years/blocks and should not simply remove a unique economic opportunity that happens to be dormant in the sample. Replacement, if warranted, is a separate later stage.
