# OURE Stage8D — Competition-state novelty add-one test

Date: 2026-09-15
Status: preregistered before run

## Question
Can a smaller Opportunity Core be improved by adding exactly one ETF chosen only because its OLS trend-eligibility states are structurally different from the Core, without using historical return magnitude, Fix15 identity, amount/volume, or future target-block data?

## Frozen base
At every 126-session Universe decision date, construct the repaired point-in-time OLD_SAFE Opportunity order from Stage8C using the preceding 377 fully-realized historical signals. The first 15 members form `CORE15`.

## Competition-state novelty rule
For each eligible ETF outside CORE15, define `active_i(t)=1` when its frozen OLS pool score is finite on historical signal day t. Let `N_core(t)` be the number of CORE15 members active on t.

Define:

`Novelty_i = mean_t[ active_i(t) / (1 + N_core(t)) ]`

This score uses no returns. It rewards an ETF for having a meaningful number of trend-eligible states, but gives most weight to states in which few Core members are simultaneously eligible. A permanently dormant ETF scores near zero; a redundant ETF active whenever many Core members are active is discounted.

Choose exactly one outside ETF with the largest Novelty score. Stable symbol order breaks ties. Do not impose a fitted threshold.

Diagnostics only, not used in selection: candidate activity share, exclusive-active share (active while no Core member is active), mean/max pairwise trend-state Jaccard with Core, historical days on which the candidate would outrank the current Core leader.

## Frozen comparison
Using the same OOS deployment calendar, frozen OLS target rule, next-open accounting and 6 bp per-side cost, compare:
- `CORE15`: repaired OLD_SAFE K15.
- `OPPORTUNITY_K16`: first 16 members of the same repaired OLD_SAFE order.
- `NOVELTY_K16`: CORE15 plus the one competition-state Novelty ETF.
- `FIX15_BENCHMARK`: benchmark only; never used in selection.

Report annual and full-period return, MDD, turnover sides, switch events and Top1 tenure. Also report by deployment block which Novelty ETF was added, how often it actually became OLS Top1, and the paired log-wealth increment of NOVELTY_K16 versus CORE15.

## Interpretation
This is not a search for the best K16. It is a direct test of the user's hypothesis that a structurally different asset can add latent optionality without being chosen for past profits. Evidence in favor requires the added asset to improve OOS economics or valuable tail capture often enough that the effect is not dominated by one accidental episode. Do not tune the Novelty formula after observing this run.