# OURE Stage8B — Opportunity Coverage K Frontier Findings

Date: 2026-09-15
Authoritative run: `34929814412`
Artifact: `oure-stage8b-opportunity-k-frontier-34929814412`
Status: frozen historical diagnostic

## Integrity
- Stage8A Opportunity30 reproduced exactly at K=30.
- Only K changed: 8, 10, 12, 15, 20, 25, 30.
- Amount/volume features were excluded.
- Fix15 identity was benchmark-only and never used in selection.

## Frontier
| K | Mean historical best-two coverage | Coverage / K30 | Full return | Full MDD | Turnover sides | Mean Top1 tenure |
|---:|---:|---:|---:|---:|---:|---:|
| 8 | 0.9579 | 96.16% | +34.66% | -49.26% | 469 | 5.57 d |
| 10 | 0.9719 | 97.56% | +83.10% | -51.20% | 511 | 5.14 d |
| 12 | 0.9801 | 98.38% | +31.75% | -44.01% | 549 | 4.84 d |
| 15 | 0.9868 | 99.06% | +140.19% | -51.91% | 593 | 4.52 d |
| 20 | 0.9923 | 99.60% | +65.25% | -57.11% | 643 | 4.21 d |
| 25 | 0.9949 | 99.87% | +108.43% | -57.38% | 671 | 4.04 d |
| 30 | 0.9962 | 100.00% | +263.58% | -65.60% | 697 | 3.91 d |

The preregistered 99%-of-K30 mean-coverage diagnostic identifies K=15.

## Structural result
Opportunity coverage strongly saturates before 30:
- K10 -> K12 mean incremental coverage: +0.00812
- K12 -> K15: +0.00678
- K15 -> K20: +0.00542
- K20 -> K25: +0.00265
- K25 -> K30: +0.00130

Meanwhile competition proxies worsen monotonically with K:
- turnover sides: 469 -> 697 from K8 to K30;
- switch events: 257 -> 355;
- mean Top1 tenure: 5.57 -> 3.91 sessions.

Historical rank-profile mean pairwise Spearman also rises toward zero as K grows (-0.0626 at K8 to -0.0029 at K30), consistent with losing some anti-synchronous diversification, although this metric is weaker than the realized turnover/tenure evidence.

Per-block smallest tested K reaching 99% of that block's K30 coverage:
- K12: 1/12 blocks;
- K15: 6/12;
- K20: 5/12;
- K25/K30: 0/12.
Thus K30 is structurally redundant under the average-coverage objective.

## But the last small amount of coverage can carry large tail value
Economic returns are not monotonic in K. K30 still has the highest historical compounded return because some assets admitted only late in the greedy order subsequently captured large trends.

Most important example:
- At the 2025-08-25 selection, `161226` is absent from K8/K10/K12/K15/K20/K25 and appears only at K30.
- In the subsequent 2025 path, `161226` becomes the dominant positive contributor to Opportunity30.

Other examples of late admission:
- At 2026-03-09, `159516` first appears at K30 and contributes positively in 2026.
- At 2025-08-25, `513310` first appears at K25.

Therefore average coverage saturation is not sufficient to justify deleting the tail of the Universe. A low-average-marginal-contribution ETF can still be a valuable dormant option for a future regime.

## Interpretation
The evidence supports both sides of the user's hypothesis:
1. K30 is too large from a routine-competition perspective: after roughly K15–K20, average historical opportunity coverage adds little while turnover rises and Top1 tenure falls.
2. A hard smaller K is not yet a solution: the discarded tail can contain rare optionality that later dominates returns.

The problem is therefore better framed as `core + optionality reserve`, not simply `choose K=15 instead of K=30`.

A promising next architecture is:
- Core: approximately the first 12–20 Opportunity members, which capture almost all routine historical coverage and have lower competition.
- Reserve: later-ranked members retained for rare regime optionality, but not allowed to compete continuously. They become eligible only after a frozen point-in-time activation rule.

The activation rule must be designed without using the observed 2025 silver episode as a fitted threshold. Candidate information can include OLS acceleration/gap, persistence, and possibly amount/participation as an activation-quality signal rather than a long-horizon Universe quality score.

## Frozen decision
- Do not replace K30 with K15 solely from this historical frontier.
- Do not treat K30 as an efficient routine competitor set either.
- Stage8B supports moving to a two-layer Core + Optionality Reserve formulation.
- Amount remains excluded from long-horizon membership scoring; it may be reconsidered later only as a point-in-time reserve activation signal.
