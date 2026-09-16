# Stage8W — US second-layer walk-forward admission gate — 2026-09-17

## Starting point
Stage8V found that, conditional on the broad US region being healthy during FixV2 `DEFENSIVE_VOID`, winning US sub-exposure entries tended to have a softer very-short-term path (lower ret3/ret5 and more negative current residual). This stage tests whether that information survives a chronological walk-forward rule without selecting a threshold on the full sample.

## Frozen setup
- Defensive/Void events: existing 2023–2026 first-entry State Map events.
- OLS: 26 trading days, weighted log-price regression, half-life 10.
- Score: positive annualized slope × weighted R², otherwise 0.
- Broad US gate: 513500 Score > 511220 Score.
- Second-layer candidates: 513100, 159509, 513290, 159529; candidate must beat 511220.
- Historical availability: candidate must satisfy the previously frozen availability rule.
- Admission feature: ret3 only for the primary walk-forward test. No Score/R² re-optimization.
- Primary threshold: expanding median of **prior active events only**. At each event, admit the US sub-exposure if current ret3 <= the median ret3 of all earlier active events.
- Fallback when rejected: 513500 broad-US. 511220 remains the outer hurdle.
- Parameter-neighborhood check: expanding ret3 40th/50th/60th percentiles; these are robustness checks, not separately optimized rules.

## Evaluation sample
The first six active events are used only to seed the expanding historical threshold. The walk-forward evaluation therefore starts at 2023-12-19 and contains 16 subsequent active events through 2026-05-18.

The median rule admitted 7/16 events (43.75%).

## Main walk-forward result
All returns below are excess returns versus 511220.

### Raw US sub-exposure Top1 on the same 16 events
- 5d mean +1.06%, median -0.82%, win rate 43.8%, 10% tail -2.18%.
- 10d mean +3.69%, median +2.76%, win rate 62.5%, 10% tail -3.77%.
- 20d mean +4.26%, median +3.74%, win rate 56.3%, 10% tail -8.48%.
- 40d mean +6.42%, median +4.05%, win rate 62.5%, 10% tail -7.39%.

### Broad US 513500 fallback-only baseline
- 5d mean +0.12%, median ~0.00%, win rate 43.8%, 10% tail -3.36%.
- 10d mean +0.89%, median +0.73%, win rate 62.5%, 10% tail -1.04%.
- 20d mean +1.63%, median +1.02%, win rate 68.8%, 10% tail -2.47%.
- 40d mean +3.30%, median +1.56%, win rate 75.0%, 10% tail -1.17%.

### Walk-forward ret3 median gate, rejected events -> 513500
- 5d mean +1.50%, median +1.66%, win rate 62.5%, 10% tail -3.36%.
- 10d mean +3.10%, median +2.49%, win rate 81.3%, 10% tail -0.48%.
- 20d mean +4.98%, median +3.73%, win rate 81.3%, 10% tail -2.13%.
- 40d mean +6.20%, median +4.70%, win rate 81.3%, 10% tail -1.25%.

The principal improvement is not a higher 40d mean versus always taking the sub-exposure; it is distribution quality. At 20d, the gate raises win rate from 56.3% to 81.3% while shrinking the 10% left tail from about -8.5% to -2.1%. At 10d the 10% tail improves from -3.8% to about -0.5%.

## Parameter-neighborhood robustness
Using the same strictly historical expanding threshold and broad-US fallback:

### ret3 40th percentile
- Admission 37.5%.
- 10d: mean +2.48%, median +1.82%, win rate 75.0%, 10% tail -0.89%.
- 20d: mean +4.26%, median +2.84%, win rate 75.0%, 10% tail -2.34%.
- 40d: mean +5.71%, median +2.96%, win rate 81.3%, 10% tail -1.25%.

### ret3 50th percentile
- Admission 43.75%.
- 10d: mean +3.10%, median +2.49%, win rate 81.3%, 10% tail -0.48%.
- 20d: mean +4.98%, median +3.73%, win rate 81.3%, 10% tail -2.13%.
- 40d: mean +6.20%, median +4.70%, win rate 81.3%, 10% tail -1.25%.

### ret3 60th percentile
- Same decisions as the median rule in this small sample; metrics are therefore identical.

The sign and distribution improvement are not confined to one exact threshold. The 40th percentile is weaker than the median but still materially improves the 20d/40d win rate and left tail relative to always buying the sub-exposure.

## Interpretation
This is the first evidence in the Defensive/Void cross-region branch that a **chronological** second-layer admission rule improves not only mean return but also median, win rate, and left-tail behavior. The mechanism is economically coherent: after the US broad region passes the trend gate, the sub-exposure is admitted only when its very-short-term path is not extended relative to previously observed active events.

The correct interpretation is not `ret3 <= 0` as a magic threshold. In the expanding walk-forward history the median itself moves and is determined only by prior events. In later years it happens to sit near zero, which is why the rule resembles a pullback gate.

## Important remaining limitation: overlapping outcome windows
Several Void re-entry events occur close together (for example 2024-01-15/18/24 and 2024-07-01/05/17). Their 20d and 40d forward windows overlap, so the nominal 16 observations are not 16 independent market episodes. This can overstate confidence and win-rate precision.

Therefore this stage is **not promoted** to a production rule yet.

## Next strict test
Stage8X should use purged/non-overlapping events and/or episode-level grouping:
1. greedily retain a new event only after the prior event's chosen forward horizon has ended, separately for 10d/20d/40d; or aggregate tightly clustered Void re-entries into one episode;
2. recompute the expanding ret3 gate using only prior purged episodes;
3. report mean, median, win rate and left tail versus both 513500 and 511220;
4. test year/episode leave-out sensitivity;
5. only if the distribution benefit survives this purge should the same gate concept be transferred to Japan/Europe second layers.

Status: substantive progress. The walk-forward admission mechanism is promising, but overlapping-event dependence remains a material unresolved robustness issue. Automation/research should continue.