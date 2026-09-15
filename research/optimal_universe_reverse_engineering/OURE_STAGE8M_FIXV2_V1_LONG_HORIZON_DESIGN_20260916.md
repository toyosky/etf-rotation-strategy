# OURE Stage8M — FixV2 + V1 Long-Horizon Audit

Date: 2026-09-16
Status: preregistered before return outputs are computed

## Frozen main universe
Start from original Fix15 and apply only previously frozen structural/carrier conclusions:
- remove `159825` (asset-health failure)
- retain `159981` (pre-2021 evidence conflicts with permanent deletion)
- replace `513920 -> 513530` (Stage8J dividend-role repair)
- replace `518880 -> 159934` (Stage8L exact GOLD_SPOT carrier)
- replace `159915 -> 159957` (Stage8L exact standard-ChiNext carrier)
- retain all other Fix15 members
- `511220` remains the cash comparator, not a risky competitor

Main risky set:
`159934,159985,161226,513100,159957,159509,513290,159529,159981,501018,513530,511380,164824`
plus cash comparator `511220`.

No pre-listing proxy or backfill is allowed. A member becomes usable only after its real history makes the frozen OLS score finite.

## Frozen OLS / accounting
Use the same daily OLS feature engine and next-open-to-following-open gross return mapping used in Stage8K/Stage8L.
Start at the first signal date on/after 2015-01-01 for which the cash comparator has a finite frozen OLS score. Keep warm state naturally from that first date; do not fabricate earlier positions.

## Frozen V1 overlay
Use the already-frozen Resistance + ScoreDelta V1:
- prior 120 daily bars build an amount-weighted volume-profile proxy, distributing each day's amount uniformly across [low, high]
- `UpperShare = amount[P,1.05P] / amount[0.95P,1.05P]`
- `ResistancePct252` is the current UpperShare empirical percentile versus strictly prior max-252 UpperShare observations for the same ETF, minimum 60 valid profile observations
- `ScoreDelta_new = raw OLS score_t - raw OLS score_{t-1}` before trend/cash masking
- veto only a pure ranking switch when `ResistancePct252 >= 75% AND ScoreDelta_new <= 0`
- never veto exit to cash, initial entry, or switch forced because incumbent is no longer a valid risk candidate above cash

## Primary comparison
A. `FIXV2_RAW`: frozen new universe without V1.
B. `FIXV2_V1_75`: same universe with frozen V1.
Primary transaction cost: 6 bp per side.

## Predefined stress tests
No threshold will be selected post hoc.
1. Cost stress: 6, 12, 20, 30 bp per side for RAW and V1-75.
2. V1 resistance threshold sensitivity: 70, 75, 80 with ScoreDelta<=0 unchanged, at 6 bp/side.
3. Universe sensitivity: remove `159981` and repeat RAW/V1-75 at 6 bp/side. This is a sensitivity only, not the main version.
4. Tail-risk stress: worst daily return, worst rolling 5-session and 20-session compounded return, full and annual MDD, and major drawdown episodes.

## Required detailed outputs
- full-period stats: cumulative return, CAGR, MDD, annualized vol, Sharpe(0 rf), Calmar, turnover sides, switches, mean/median Top1 tenure
- yearly stats for every calendar year: return, MDD, turnover, switches, holding tenure, veto count, worst/best day, worst 5d/20d
- exact log-wealth contribution by symbol, both full-period and year x symbol; holding days, switch-ins, daily win rate
- V1 event log and divergence-episode alpha versus RAW
- member real availability / first finite OLS score
- cost stress, threshold stress, and 159981 universe sensitivity tables
- drawdown episode table

## Interpretation discipline
This is a historical audit of a manually seeded and subsequently repaired universe. It is not clean out-of-sample proof. Stage8M must not search additional ETFs, alter the V1 rule, or combine further post-hoc carrier replacements after seeing outputs. The purpose is to characterize robustness and return sources of the frozen candidate system.
