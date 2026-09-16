# Stage8Y — Carrier + Enhancer executable episode portfolio — 2026-09-17

## Purpose
Upgrade the prior event study into an executable Defensive/Void branch portfolio. Only the Defensive/Void branch is changed; non-Void FixV2/V1 logic is conceptually held fixed.

## Frozen execution
- Regime source: exact Stage8Q daily State Map artifact, 160 Defensive/Void episodes from 2015-02-05 through 2026-09-15.
- Signal: first day of each Defensive/Void episode.
- Execution: enter on the next trading-day open.
- Exit: because the regime exit is only known after the first non-Void close, exit on the **second** trading-day open after the last Void signal date.
- OLS: 26 trading days, weighted log-price regression, half-life 10, frozen positive annualized slope × weighted R² Score.
- US carrier: 513500, only when Score(513500) > Score(511220) and historical availability >=365 days; otherwise 511220.
- US enhancer candidates: 513100 / 159509 / 513290 / 159529, point-in-time availability >=365 days and Score > 511220.
- Enhancer admission: selected sub-exposure ret3 <= expanding median ret3 of prior active US events; at least four prior active events required. Rejected enhancer falls back to 513500.
- No intravoid daily reranking: one routing decision per episode.

## Cost convention
A uniform 24bp round-route friction is charged to every episode branch for this first executable comparison. This is intentionally conservative for the outer enter/exit transition and keeps the number of transitions comparable across 511220, carrier and enhancer branches. QDII-specific extra friction is not hard-coded; instead a break-even stress margin is reported below.

## First-pass executable results
One final 2026 episode lacks a complete post-exit execution bar in the current database, so the executable sample is 120 episodes in 2015-2022 and 39 episodes in 2023-2026.

### 2015-2022
- US healthy episodes: 70 / 120
- enhancer used: 23 episodes
- 511220 branch compounded net return: **-11.35%**
- US carrier branch: **+21.07%**
- carrier + enhancer branch: **+31.00%**
- mean episode excess vs 511220: carrier **+0.288pp**, enhancer architecture **+0.354pp**
- enhancer 10% episode excess tail vs 511220: **-0.85%**

### 2023-2026
- US healthy episodes: 22 / 39
- enhancer used: 10 episodes
- 511220 branch compounded net return: **-8.27%**
- US carrier branch: **+2.58%**
- carrier + enhancer branch: **+4.08%**
- mean episode excess vs 511220: carrier **+0.293pp**, enhancer architecture **+0.338pp**
- enhancer 10% episode excess tail vs 511220: **-0.75%**

These are branch-only compounded returns over Defensive/Void episodes, not the full master FixV2/V1 equity curve. Since non-Void days are common by construction, they measure the incremental value of replacing the Void branch, but they must still be spliced into the complete strategy before promotion.

## QDII extra-friction break-even diagnostic
All US carrier/enhancer holdings are QDII exposures. Relative to the 511220 branch, approximate additional round-trip friction per US-routed episode required to erase the observed cumulative advantage is:

- 2015-2022 carrier: **~44bp** additional per US episode
- 2015-2022 carrier+enhancer: **~56bp**
- 2023-2026 carrier: **~51bp**
- 2023-2026 carrier+enhancer: **~57bp**

This is an approximate stress margin, not a premium model. The result is therefore not immune to QDII premium/NAV effects, but the edge is larger than a trivial few basis points.

## Important correction during Stage8Y
An earlier internal calculation exited on the first open after the final Void signal, which made one-day episodes mechanically zero-return. That is not executable because the regime exit is only observed after the next close. The results above use the corrected next-open entry / second-open-after-final-signal exit convention.

## MDD status
The first SQL pass computed a cumulative-return difference rather than standard peak-to-trough NAV drawdown, so those provisional MDD numbers are rejected and intentionally not reported here. Standard NAV MDD must be recomputed from the episode equity series before promotion.

## Interpretation
The carrier architecture survives the move from fixed-horizon event returns to an executable episode branch. The main effect is already present in broad US routing; the enhancer adds incremental return but is not the primary source of robustness.

This strengthens the architecture:

`Defensive/Void -> if US broad trend is healthy, use 513500 as carrier -> selectively upgrade to a US sub-exposure only when the chronological non-overextension gate passes -> otherwise 511220.`

The finding is stronger than the earlier naive country-Top1 router because it uses one stable carrier rather than a broad country competition pool and limits second-layer concentration.

## Remaining strict work
1. Recompute standard episode NAV MDD and left-tail statistics.
2. Splice the branch into the complete FixV2/V1 daily equity curve so annual return/MDD/turnover are directly comparable.
3. Stress QDII-specific extra friction at nearby levels (e.g. +20/+40/+60bp per US episode) rather than relying only on break-even arithmetic.
4. Audit premium-sensitive execution days and NAV-lag exposure; do not infer premium from ETF price alone.
5. Run year-level and leave-one-year-out contribution audit on the executable branch.
6. If the US carrier result survives, test transfer of the **carrier/enhancer architecture** to Japan/Europe rather than adding all foreign assets into one Top1 pool.

Status: substantive progress; no promotion yet. Stage8Y supports `regional carrier + selective enhancer` as a serious candidate Defensive/Void architecture, but full master-strategy splice and corrected MDD remain mandatory.