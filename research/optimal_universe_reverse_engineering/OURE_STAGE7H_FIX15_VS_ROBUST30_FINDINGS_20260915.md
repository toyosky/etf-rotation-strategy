# OURE Stage7H — Fix15 vs dynamic Robust30 same-engine findings

Date: 2026-09-15
Authoritative run: `34928080171`
Artifact: `oure-stage7h-fix15-vs-robust30-34928080171`
Status: frozen historical diagnostic

## Design
Same daily OLS engine, same execution convention, same costs, same calendar. Primary comparison excludes V1. Dynamic Robust30 is rebuilt point-in-time with the frozen 3x126 -> robust score -> K30 -> freeze126 rule. Fix15 is the original fixed 15-asset pool.

## Year-by-year, 6 bp per side
| Year | Robust30 | Fix15 | Robust30 - Fix15 | Robust30 MDD | Fix15 MDD |
|---|---:|---:|---:|---:|---:|
| 2021 | +1.58% | +20.26% | -18.68 pp | -16.30% | -17.33% |
| 2022 | -26.42% | +18.57% | -44.99 pp | -49.58% | -32.47% |
| 2023 | -9.74% | +26.34% | -36.08 pp | -25.63% | -11.59% |
| 2024 | +15.03% | +16.51% | -1.48 pp | -27.09% | -33.16% |
| 2025 | +73.38% | +124.50% | -51.12 pp | -17.21% | -22.64% |
| 2026 partial | +28.94% | +112.80% | -83.86 pp | -28.61% | -44.72% |

Full-period compounded return:
- Robust30: +73.48%
- Fix15: +902.79%

Full-period MDD:
- Robust30: -52.34%
- Fix15: -44.72%

Turnover sides:
- Robust30: 596
- Fix15: 504

The result is robust to higher assumed friction: Fix15 still dominates at 12 bp and 20 bp per side.

## Main conclusion
The current dynamic Robust30 method does not beat Fix15 under identical accounting. It is not merely a lower-return/lower-risk alternative: over the full period it has lower return, worse full-period MDD, and higher turnover.

Therefore Robust30 should not currently be treated as the primary replacement for Fix15. It remains a research candidate with an interpretable selection mechanism, but its economic objective has not been met relative to the existing benchmark.

## Structural clue: Robust30 repeatedly excludes the important Fix15 assets
Overlap between each dynamic Robust30 and Fix15 is extremely low:
- B-01 2020-12-21: 2 Fix15 assets
- B00 2021-06-30: 1
- B01 2022-01-04: 3
- B02 2022-07-14: 2
- B03 2023-01-17: 0
- B04 2023-07-27: 2
- B05 2024-01-30: 2
- B06 2024-08-09: 2
- B07 2025-02-21: 0
- B08 2025-08-25: 1
- B09 2026-03-09: 1
- B10 2026-09-08: 2

This matters because Fix15's gains are repeatedly carried by assets that dynamic Robust30 omitted. Same-engine target-level attribution shows examples:
- 2021: 159981 and 501018 were major positive contributors;
- 2022: 501018 was the strongest positive contributor;
- 2023: 159985 and 513100 were major contributors;
- 2025: 161226 was exceptionally important, followed by 159509 and 159915;
- 2026 partial: 161226 and 501018 were dominant contributors.

The dynamic selector often failed to retain exactly these cross-asset trend opportunities.

## Interpretation
Stage7E's tail-consensus result is still statistically valid within its candidate-library framework, but it answers a narrower question: among the K30 candidate sets being considered, which set tends to transfer better? It does not establish that this candidate-generation/search framework spans the economically best Universe relative to Fix15.

The likely failure is upstream: candidate generation and the robustness objective favor broad historical consistency, while Fix15 benefits from retaining rare, heterogeneous assets that may be dormant for long periods but become dominant in specific regimes.

## Frozen decision
- Fix15 remains the benchmark and should not be displaced by Robust30.
- Stage7F forward monitoring may continue as a research monitor, but not as evidence that Robust30 is the preferred live Universe.
- Do not tune Robust30 parameters to chase Fix15 after seeing this result.
- Next research question: identify which structural properties of Fix15 create its large advantage (asset-class coverage, rare-optionality/dormancy, low correlation, or persistent inclusion of commodities/QDII), then test whether those properties can be imposed ex ante without hindsight.
