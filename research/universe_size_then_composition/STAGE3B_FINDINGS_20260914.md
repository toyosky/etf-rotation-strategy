# New Stage 3B — Conservative Size Fallback Findings (2026-09-14)

## Status

Frozen. Source run: `34783843851`; artifact: `universe-size-stage3b-34783843851`.

The first run failed only because the downloaded Stage1 artifact path had one extra directory component. The repair changed only that path and did not change the registered Stage3B design.

## Primary result

The history-only expanding best-K rule does **not** show stable incremental value over the pre-existing K=15 engineering anchor.

Across 44 OOS months:

- expanding train-best mean monthly return: 0.6300%
- fixed K15 mean monthly return: 0.7549%
- paired train-best minus K15 mean: -0.1249 percentage points/month
- paired median: +0.5026 percentage points/month
- month-bootstrap 95% interval: [-1.1044, +0.7795] percentage points/month

The interval is wide and crosses zero. The history-only K selector therefore does not establish a stable size-layer advantage.

## Era split

2023–24 (24 months):

- train-best minus K15 mean: +0.7064 percentage points/month
- bootstrap 95%: [-0.2778, +1.6295]

2025–26 (20 months):

- train-best minus K15 mean: -1.1225 percentage points/month
- bootstrap 95%: [-2.9099, +0.5499]

The sign reverses across eras, matching the Stage1 finding that the economic effect of Universe size is regime-dependent. A purely history-averaged best-K rule adapts too slowly to that reversal.

## Chosen K and one-SE range

The expanding train-best rule selected very small K almost all the time:

- mean chosen K: 3.45
- median chosen K: 3
- only 3 changes over the 44 OOS months

This is not evidence that K=3 is universally optimal. It is the mechanical consequence of accumulating the earlier-era negative size effect in the expanding training history.

The one-SE training range also became progressively weak as a constraint:

- overall mean width: 11.39 K units; median width: 8
- 2023–24 mean width: 4.88
- 2025–26 mean width: 19.20
- by late 2025/2026 the range often expanded to K=3..30

Thus the conservative history-only uncertainty range becomes least informative precisely when the size regime changes.

## Frozen decision

Reject dynamic size selection as an independently useful layer on this history.

For the next composition stage, use **K=15 only as a conservative engineering anchor**, because it was fixed before Stage3/3B from the original Fix15 cardinality and the Stage1 nested 15→3 design. This decision does **not** claim that K=15 is globally or historically optimal.

The research question now moves from `which K?` to `given a fixed K=15, does composition have enough downstream set-value headroom and stable structure to be learnable?`

Do not reopen Stage1–3B, search for another fixed K on the same full history, or rescue the failed size layer with additional state features/models.