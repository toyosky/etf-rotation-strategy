# OURE Stage7A — Robust K30 Across Prior Regimes, Strict OOS Findings

Date: 2026-09-15
Run: `34916978106`
Artifact: `oure-stage7a-robust-k30-oos-34916978106`
Status: frozen PASS
Decision: `robust_selection_supported`

## Question
Instead of predicting the exact next regime / next best ETF set, can we construct a K30 opportunity set that was consistently useful across several already-completed market regimes and thereby generalize better to the next 126-session block?

Stage7A was preregistered before outcome inspection. The 3-block window, candidate maturity rule, 50/50 robust-score formula, baselines, and five support gates were frozen in advance.

## Frozen setup
For each target B04..B09:
- use only the immediately preceding three fully completed 126-session blocks;
- define the ETF pool as the intersection of point-in-time available pools at all three training-block starts and the target start;
- generate one target-specific 2496-K30 family library using only X<=t data and the frozen Stage6G/6K family machinery;
- replay each candidate K30 with the frozen downstream OLS separately over all three historical blocks;
- convert each historical block value to a percentile rank within the same target library;
- score:

`Robust(U) = 0.5 * median(P1,P2,P3) + 0.5 * Q25(P1,P2,P3)`.

Baselines use exactly the same K30 target library:
- latest126: most recent completed block value;
- previous-block RF: frozen Stage6K RF trained on the immediately previous completed standard block;
- random: fixed-seed random selection from each same target library.

## Primary result — all five frozen gates PASS

Aggregate B04..B09:

| Rule | Median OOS Spearman | Positive blocks | Median Top50 actual pct | Median selected Top1 actual pct | Compounded selected path | Worst block |
|---|---:|---:|---:|---:|---:|---:|
| **robust 3-block** | **+0.2028** | **5/6** | **0.6239** | **0.7443** | **+118.38%** | **-15.28%** |
| latest126 | +0.1802 | 6/6 | 0.5519 | 0.4296 | +25.91% | -19.00% |
| previous-block RF | +0.1018 | 6/6 | 0.4496 | 0.1593 | -37.32% | -20.36% |

Robust median top-decile future log-growth lift is **+0.0603**, versus +0.0072 for latest126 and approximately zero (+0.0003) for previous-block RF.

Frozen gates:
1. median robust Spearman > +0.10: **PASS** (+0.2028);
2. positive robust IC >=4/6: **PASS** (5/6);
3. median robust Top50 actual percentile >0.55: **PASS** (0.6239);
4. median robust selected-Top1 actual percentile >0.60: **PASS** (0.7443);
5. robust path beats both baselines on compounded log-growth and on worst block: **PASS**.

Formal decision: **`robust_selection_supported`**.

## Per-target selected Top1 results

| Target | Robust future return | Robust actual pct | Latest126 future return | RF future return |
|---|---:|---:|---:|---:|
| B04 | -15.28% | 0.246 | -19.00% | -20.36% |
| B05 | +14.39% | 0.934 | +18.82% | -12.83% |
| B06 | +7.38% | 0.488 | +7.99% | -20.10% |
| B07 | +27.30% | 0.772 | +4.24% | +12.40% |
| B08 | +25.27% | 0.717 | -14.66% | -17.23% |
| B09 | +31.61% | 0.890 | +36.18% | +21.47% |

The robust Top1 is not the best next-period set in every block. It is notably weak in B04 and merely median in B06. Its advantage comes from avoiding repeated severe failures while retaining strong upside in B05/B07/B08/B09.

## What the selected robust sets looked like historically
The chosen robust K30s were genuinely strong across all three completed training regimes rather than being latest-block winners with one weak historical regime.

Historical percentile triplets for the selected robust Top1:
- B04 target: 0.925 / 0.930 / 0.970;
- B05: 0.906 / 0.991 / 0.969;
- B06: 0.986 / 0.983 / 0.969;
- B07: 0.956 / 0.976 / 0.915;
- B08: 0.957 / 0.967 / 0.960;
- B09: 0.950 / 0.926 / 0.903.

So the frozen score is selecting a very different object from `past126 Top1`: it favors K30s that remained in roughly the top decile across three distinct historical blocks.

## Random benchmark
Across 10,000 fixed-seed paths that choose one random K30 from each identical target library:
- median compounded return: **+27.73%**;
- p10: -25.18%;
- p90: +144.01%;
- median worst-block return: -16.45%.

The robust path (+118.38%) is at approximately the **86.49th percentile** of random paths. Thus it is clearly above random median, but not an extreme random-tail impossibility. With only six independent target blocks, this distinction matters.

## Important interpretation
This is the first strict chronological result in the OURE line that directly supports the new objective:

`do not forecast the next regime -> prefer a K30 that was useful across several completed regimes -> let frozen OLS choose the realized leader after the market unfolds`.

The evidence is stronger than the earlier one-block transfer approaches in two ways:
1. broad OOS ranking improves materially (median IC +0.203, Top50 pct 0.624);
2. unlike prior RF/past126 work, the extreme Top1 does not collapse on aggregate: median Top1 actual percentile is 0.744 and the six-block path beats both frozen baselines while improving the worst block.

This supports the conceptual shift from **future-winner prediction** to **robust opportunity-set design**.

## Limitations / scope
Do not overstate Stage7A.

1. Only six independent target blocks B04..B09 are available. A 5/6 positive result is promising but still a small time sample.
2. Each target searches only the frozen 2496-candidate family library, not the full combinatorial K30 space. This is evidence for the robust scoring objective within that search family, not a proof of a globally optimal K30.
3. The common-pool rule intentionally favors mature ETFs that existed through all three historical blocks; newly listed ETFs are excluded. That may sacrifice new opportunity coverage.
4. Candidate generation itself uses frozen past-only family machinery that includes strong historical bases plus mutations/random controls. All rules share it, so the rule comparison is fair, but the result is conditional on this candidate generator.
5. No alternative robust window, weight, quantile, K, maturity horizon, or regime definition has been tested. They must not be tuned retrospectively from this result.

## Frozen conclusion
**Stage7A PASS.**

Current strongest working hypothesis:

`Robust Universe value is more predictable than exact next-regime winner value: a K30 that repeatedly allows the frozen OLS to work well across several completed regimes is more likely to remain a useful opportunity set in the next regime.`

This does not mean the future regime is predicted. The point is precisely the opposite: the Universe is selected for **optionality and resilience across different realized environments**, after which OLS reacts to the next environment dynamically.

Recommended next research layer is explanatory, not tuning: inspect why Stage7A robust winners remain robust — opportunity coverage, productive relay, harmful competition, member/challenger structure — and test whether those mechanisms replicate without changing the frozen Stage7A selector.
