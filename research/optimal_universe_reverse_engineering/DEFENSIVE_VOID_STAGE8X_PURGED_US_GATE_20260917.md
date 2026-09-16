# Stage8X — Purged US second-layer gate validation — 2026-09-17

## Purpose
Stage8W found a strong chronological ret3 admission effect, but nearby Defensive/Void re-entry events share overlapping 10/20/40-day outcome windows. Stage8X removes this dependence by greedily retaining only non-overlapping events for each horizon and recomputing the expanding admission threshold from prior **purged** events only.

## Frozen mechanism
- Broad US region gate: 513500 OLS Score > 511220 Score.
- OLS: frozen 26-day weighted log-price regression, half-life 10.
- Second layer: 513100 / 159509 / 513290 / 159529, highest eligible Score above 511220.
- Admission: current selected sub-exposure ret3 <= expanding median ret3 of prior purged active events.
- Rejected sub-exposure falls back to 513500.
- 511220 is the outer hurdle.
- No full-sample threshold fitting.

## Purging rule
For each horizon independently, retain the first active event, then retain the next event only if its signal date is later than the previous retained event's forward-return end date.

This leaves:
- 10d: 14 purged active episodes total; after 4 seed episodes, 10 evaluation episodes.
- 20d: 12 total; 8 evaluation episodes.
- 40d: 10 total; 6 evaluation episodes.

The reduced sample is intentional: it is closer to the number of independent market episodes than the nominal event count.

## 10-day purged result (n=10)
Excess versus 511220:

### Gate: ret3 admission, otherwise 513500
- mean +3.69%
- median +2.94%
- win rate 80.0%
- 10% tail -0.69%
- worst -5.11%

### Always buy selected US sub-exposure
- mean +3.92%
- median +1.80%
- win rate 50.0%
- 10% tail -3.86%
- worst -4.82%

### Always use 513500 broad US
- mean +1.15%
- median +1.82%
- win rate 60.0%
- 10% tail -1.45%
- worst -5.11%

Interpretation: at 10d the gate materially improves median, win rate and left-tail quality versus always taking the US sub-exposure, while retaining much more upside than broad US alone.

## 20-day purged result (n=8)
### Gate
- mean +3.38%
- median +2.84%
- win rate 87.5% (one exactly-zero event)
- 10% tail +0.18%
- worst 0.00%

### Always selected sub-exposure
- mean +1.01%
- median -0.22%
- win rate 37.5%
- 10% tail -5.08%
- worst -9.30%

### Always 513500
- mean +3.02%
- median +3.05%
- win rate 100%
- 10% tail +0.36%
- worst +0.25%

Interpretation: after purging, the broad-US fallback itself is exceptionally strong on these independent 20d episodes. The admission gate adds modest mean (+0.36pp) but no distributional advantage versus simply holding 513500; its main value is avoiding the severe left tail of unconditional US sub-exposure chasing.

## 40-day purged result (n=6)
### Gate
- mean +4.37%
- median +3.62%
- win rate 100%
- 10% tail +0.48%
- worst +0.20%

### Always selected sub-exposure
- mean +6.66%
- median +3.34%
- win rate 66.7%
- 10% tail -6.26%
- worst -8.14%

### Always 513500
- mean +3.63%
- median +2.65%
- win rate 100%
- 10% tail +0.48%
- worst +0.20%

Interpretation: the gate lifts mean/median over broad US while preserving the broad-US left-tail profile in this very small purged sample. The selected sub-exposure has larger upside but materially worse downside.

## Main update to the architecture
Stage8X changes the interpretation of the second layer.

The evidence no longer supports:

`US region healthy -> replace broad US with sub-exposure Top1`.

A better description is:

`US region healthy -> 513500 is the default carrier -> selectively upgrade to a US sub-exposure only when a non-overextension/pullback admission gate passes`.

In other words, the second layer behaves more like an **alpha enhancer over a robust regional carrier** than a replacement Universe.

This is especially important because the 20d/40d purged samples show that broad US itself already beats the 511220 hurdle with unusually good distribution quality. The ret3 gate is useful primarily because it preserves that defensive distribution while occasionally capturing sub-exposure upside.

## Remaining caveats
- Purging reduces effective sample size to only 10/8/6 evaluation episodes for 10/20/40d.
- 20d/40d results are therefore encouraging but statistically fragile.
- 513500 itself may be benefiting from the particular post-2023 US regime; longer-history broad-US representatives should be used to extend the same test backward where possible.
- QDII premium/NAV-lag and explicit switching friction have not yet been imposed on the enhancer decisions.

## Next stage
Stage8Y should test the **carrier + enhancer** architecture rather than a replacement architecture:
1. extend the broad-US carrier history using historical-safe S&P500/Nasdaq broad representatives where available, preserving point-in-time availability;
2. construct an episode-level strategy where Void + US healthy defaults to broad US, and only ret3-gated events upgrade to sub-exposure;
3. charge switching costs for 511220 -> carrier and carrier -> enhancer transitions;
4. audit QDII premium/NAV-lag exposure;
5. compare complete routed equity curve and MDD versus Void -> 511220 and Void -> broad-US-only;
6. if this survives, transfer the same carrier/enhancer concept to Japan/Europe rather than copying US sub-exposure labels mechanically.

Status: meaningful progress, but no promotion yet. The second-layer mechanism survived a purged-event test in the form of `broad regional carrier + selective sub-exposure enhancer`.