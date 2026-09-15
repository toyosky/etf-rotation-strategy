# OURE Stage8G — Economic Asset Health Audit

Date: 2026-09-15
Status: preregistered before Stage8G outputs are computed

## Question
Among the frozen Stage8E 27 economic slots, which slots/representatives are structurally useful but empirically poor OLS Top1 tools, using the same diagnostic idea as the pre-existing Asset Health Monitor V1 that flagged 159825?

## Frozen base
- Economic taxonomy: Stage8E 27 frozen slots, unchanged.
- Representative selection: Stage8E point-in-time highest prior-60d median amount within each slot, unchanged.
- OLS engine and Economic Coverage Top1 path: unchanged.
- No slot is removed or replaced inside Stage8G.

## Event definition
For every mature Economic Coverage Top1 signal date t with risky target i:
1. Use i's own trading-day close sequence.
2. Require at least 20 closes through t and at least 10 future closes.
3. Compute fwd5 = close[t+5]/close[t]-1.
4. Compute fwd10 = close[t+10]/close[t]-1.
5. near_high = close[t] >= 0.995 * max(close[t-19:t]).
6. Tag the event by the economic slot occupied by i at that block.

Report both:
- all daily Top1 observations (same philosophy as Asset Health V1), and
- episode-first observations (first day after Economic Coverage target changes), as a dedup robustness view.

## Frozen V1 classification
Apply the existing Asset Health V1 rules without retuning, at slot level and symbol level:
- minimum all-history near-high n >= 10;
- minimum recent-2y near-high n >= 5;
- WARNING iff all-history and recent-2y near-high 10d mean < 0 AND both 10d win rates < 35%;
- WATCH iff both means are negative but WARNING is not met, OR recent-2y mean < 0 and recent-2y win rate < 40%;
- otherwise HEALTHY; insufficient samples -> INSUFFICIENT_DATA.

Recent-2y is defined relative to the latest mature signal-date cutoff in this dataset.

## Outputs
- event-level CSV with slot, symbol, date, episode_start, near_high, fwd5/fwd10;
- slot-level V1 health table;
- symbol-level V1 health table;
- episode-first robustness table;
- ranked slot diagnostic by all-Top1 and near-high continuation.

## Interpretation discipline
- A bad Stage8G status is diagnostic evidence, not automatic deletion authority.
- Economic distinctness and OLS suitability are separate properties.
- A slot is a deletion/replacement candidate only after a separately preregistered counterfactual removal/replacement test.
- Stage8G must not change the frozen 27-slot taxonomy after seeing these results.
