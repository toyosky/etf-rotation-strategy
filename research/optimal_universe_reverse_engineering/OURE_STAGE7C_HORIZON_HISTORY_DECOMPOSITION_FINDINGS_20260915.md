# OURE Stage7C — Horizon vs History Decomposition Findings

Date: 2026-09-15
Authoritative run: `34922521349`
Artifact: `oure-stage7c-horizon-history-decomposition-34922521349`
Status: frozen diagnostic
Preregistered verdict: `history_depth_dominant`

## Validity checks
The two frozen Stage7B corner variants reproduced successfully on the same 756-session calendar (2023-07-27 through 2026-09-07):

- A = H126 / Hist126: +117.7263% at 6bp/side, matching Stage7B H126.
- B = H63 / Hist63: -16.6313% at 6bp/side, matching Stage7B H63.

Therefore the mixed variants C and D are interpretable under the preregistered design.

## 2x2 terminal-path result

| Variant | Hold horizon | Robustness history block | 6bp/side | 12bp/side | 20bp/side |
|---|---:|---:|---:|---:|---:|
| A H126/Hist126 | 126 | 126 | +117.73% | +76.95% | +34.16% |
| B H63/Hist63 | 63 | 63 | -16.63% | -33.37% | -50.61% |
| C H63/Hist126 | 63 | 126 | +61.83% | +26.87% | -8.34% |
| D H126/Hist63 | 126 | 63 | +28.28% | +1.65% | -25.48% |

Two direct observations are robust:

1. Preserving long robustness history while shortening refresh/holding from 126 to 63 sessions (A -> C) causes a material loss, but C remains dramatically better than the natural quarterly B.
2. Preserving the 126-session holding horizon while shortening robustness history from 378 total sessions to 189 total sessions (A -> D) also causes a large loss.

Thus both dimensions matter. Under the preregistered additive 2x2 rule, history depth is the larger average effect.

## Frozen factor decomposition
Terminal log-wealth effects:

| Cost | History-depth effect | Holding-horizon effect | Interaction |
|---|---:|---:|---:|
| 6bp | +0.5962 | +0.3638 | -0.1342 |
| 12bp | +0.5992 | +0.3776 | -0.0898 |
| 20bp | +0.6032 | +0.3961 | -0.0304 |

Both main effects are positive at all three cost levels. Median history-depth effect exceeds median holding-horizon effect by more than the preregistered 1.5x threshold, so the formal verdict is `history_depth_dominant`.

Interpretation: the Stage7B quarterly failure is explained more by insufficient robustness-history depth / regime coverage than by quarterly refresh itself, although the 126-session holding/refresh horizon also contributes materially.

## Cross-sectional diagnostics

| Variant | Median Spearman | Positive IC | Median Top50 actual pct | Median selected actual pct |
|---|---:|---:|---:|---:|
| A H126/Hist126 | +0.2028 | 5/6 | 0.6239 | 0.7443 |
| B H63/Hist63 | -0.0062 | 6/12 | 0.5243 | 0.6768 |
| C H63/Hist126 | +0.1299 | 9/12 | 0.5617 | 0.4461 |
| D H126/Hist63 | +0.1662 | 6/6 | 0.6133 | 0.4050 |

The broad robust ranking recovers substantially when long history is restored at the 63-session horizon: median Spearman rises from approximately zero in B to +0.130 in C, and positive IC blocks rise from 6/12 to 9/12. However, selected Top1 tail quality does not recover in the same way. This is an important limitation: long history helps broad ranking, but the final extreme-tail selection remains noisy in the mixed variants.

## Same-calendar 126-session spans at 6bp/side

| Span | A H126/Hist126 | B H63/Hist63 | C H63/Hist126 | D H126/Hist63 |
|---|---:|---:|---:|---:|
| 2023-07-27 to 2024-01-29 | -15.28% | -19.27% | -26.29% | -20.21% |
| 2024-01-30 to 2024-08-08 | +14.32% | +2.44% | +12.72% | -8.42% |
| 2024-08-09 to 2025-02-20 | +7.31% | -2.92% | +11.51% | -18.59% |
| 2025-02-21 to 2025-08-22 | +27.22% | -14.30% | -9.01% | +6.43% |
| 2025-08-25 to 2026-03-06 | +25.19% | +16.19% | +140.08% | +76.46% |
| 2026-03-09 to 2026-09-07 | +31.53% | +4.28% | -20.04% | +14.82% |

Positive half-years:
- A: 5/6
- B: 3/6
- C: 3/6
- D: 3/6

Worst half-year:
- A: -15.28%
- B: -19.27%
- C: -26.29%
- D: -20.21%

This table prevents over-reading the aggregate factor verdict. C's aggregate recovery is partly concentrated in 2025-08 to 2026-03 (+140.08%), while C is negative in three of six half-years. D likewise has one unusually strong +76.46% half-year. Therefore the aggregate `history_depth_dominant` verdict is valid under the preregistered terminal-path rule, but it is not a claim that the history-depth effect is uniformly positive in every regime.

For reference, pair-level 6bp factor effects are:
- history-depth effect positive in 4/6 half-years;
- holding-horizon effect positive in 3/6 half-years.

## Friction

| Variant | Turnover sides | Annualized sides | Mean Top1 tenure | Median tenure |
|---|---:|---:|---:|---:|
| A | 345 | 115.0 | 4.24d | 3d |
| B | 373 | 124.3 | 3.90d | 3d |
| C | 405 | 135.0 | 3.58d | 2d |
| D | 387 | 129.0 | 3.77d | 3d |

C incurs the most downstream turnover, but the cross-cost factor effects are very stable. The history-depth conclusion is therefore not a transaction-cost artifact.

## Frozen conclusion
Stage7C resolves the main Stage7B ambiguity as follows:

`Robust30 quality depends more on having a sufficiently long robustness-estimation history than on the refresh horizon alone.`

But the strongest supported formulation is more nuanced:

`Long history is the dominant average factor; the 126-session holding/refresh horizon is a second, still material factor.`

The fully long specification A remains the strongest and most stable tested corner:

`3 x 126-session robustness history -> Robust30 -> freeze Universe for 126 sessions -> downstream OLS Top1`

Stage7C does not justify switching to quarterly maintenance. C is a useful mechanism probe, not a superior deployment candidate.

## Recommended next diagnostic
Do not optimize intermediate horizons. The next useful question is why long history helps: does it work because it averages across multiple regimes / reduces variance of set-value estimates, or because particular historical blocks contribute persistent information?

A clean next stage should decompose the 3x126 robust score itself without changing the deployed A specification, for example by measuring block-to-block score variance, rank persistence, and leave-one-history-block-out sensitivity. This would test the regime-coverage / variance-reduction mechanism without reopening horizon tuning.
