# OURE Stage7B — Quarterly Robust30 Horizon and Friction Audit Findings

Date: 2026-09-15
Authoritative run: `34921530265`
Artifact: `oure-stage7b-quarterly-robust-horizon-friction-34921530265`
Status: frozen diagnostic
Decision: `halfyear_preferred`

Implementation note: run `34921217226` is invalidated by `OURE_STAGE7B_IMPLEMENTATION_CORRECTION_20260915.md` because it did not reproduce the frozen Stage7A candidate-library seed semantics. The authoritative run restores Stage7A seed `20260914` and exact target-library seed rule `SEED + block_no*1009`.

## Question
Compare the frozen Stage7A H126 Robust30 with a natural quarterly variant H63: three completed 63-session blocks -> same robust score -> fix selected K30 for next 63 sessions. Audit whether more frequent Universe refresh creates material transaction friction.

## Common comparison window
2023-07-27 through 2026-09-07, exactly 756 sessions:
- H126: 6 selected Universes;
- H63: 12 selected Universes.

The H126 independent-block returns reproduce Stage7A: approximately -15.28%, +14.39%, +7.38%, +27.30%, +25.27%, +31.61%.

## Primary result — H126 clearly preferred
Continuous-position path, charging costs only when the actual OLS target changes:

| Variant | 6bp/side | 12bp/side | 20bp/side |
|---|---:|---:|---:|
| H126 | +117.73% | +76.95% | +34.16% |
| H63 | -16.63% | -33.37% | -50.61% |

H63 loses at every frozen cost level. Formal Stage7B decision: `halfyear_preferred`.

## Same-calendar 126-session paired comparison
Each pair of H63 quarters is compounded and compared with the corresponding H126 block at 6bp/side.

| 126-session span | H126 | H63 |
|---|---:|---:|
| 2023-07-27 to 2024-01-29 | -15.28% | -19.27% |
| 2024-01-30 to 2024-08-08 | +14.32% | +2.44% |
| 2024-08-09 to 2025-02-20 | +7.31% | -2.92% |
| 2025-02-21 to 2025-08-22 | +27.22% | -14.30% |
| 2025-08-25 to 2026-03-06 | +25.19% | +16.19% |
| 2026-03-09 to 2026-09-07 | +31.53% | +4.28% |

H63 beats H126 in **0/6** same-calendar half-year spans. Positive half-years: H126 5/6, H63 3/6. Worst paired half-year: H126 -15.28%, H63 -19.27%.

## Why quarterly fails: robustness signal degrades at 63 sessions
Cross-sectional OOS diagnostics:

| Metric | H126 | H63 |
|---|---:|---:|
| target blocks | 6 | 12 |
| median Spearman | +0.2028 | -0.0062 |
| positive IC | 5/6 | 6/12 |
| median Top50 actual percentile | 0.6239 | 0.5243 |
| median selected Top1 actual percentile | 0.7443 | 0.6782 |

The key failure is not mainly the selected Top1 tail; the **broad robust ranking itself nearly disappears** at the 63-session horizon. This is consistent with the hypothesis that 63-session set value is substantially noisier and that three 63-session training blocks (about nine months total) span less regime diversity than three 126-session blocks (about eighteen months).

Stage7B changes both the evaluation block length and the total historical robustness window, so it does not identify which of those two components is causal. It only rejects this natural `3x63 -> next63` quarterly formulation.

## Friction audit — more frequent refresh is not the main problem

| Metric | H126 | H63 |
|---|---:|---:|
| turnover sides / 756 sessions | 345 | 373 |
| annualized sides | 115.0 | 124.3 |
| mean Top1 tenure | 4.24d | 3.90d |
| median Top1 tenure | 3d | 3d |
| Universe refreshes | 5 | 11 |
| mean successive Universe Jaccard | 0.035 | 0.027 |
| mean members replaced / refresh | 28.0 | 28.45 |
| refresh changes same-day OLS target | 5/5 | 10/11 |
| previously held ETF removed | 5/5 | 9/11 |

The selected K30 membership is highly unstable at refresh boundaries in both variants: roughly 28 of 30 members change. However, because the portfolio only holds one OLS leader, this does **not** mean trading 28 positions. H63 adds only 28 turnover sides over three years relative to H126 (about +8.1%, or +9.3 sides/year).

Cost stress confirms that friction is not the explanation for H63 underperformance: the quarterly path is already much worse at 6bp and remains worse at 12bp and 20bp.

Operationally, the high member turnover is still worth addressing later because most refreshes change the OLS target and often remove the existing holding. But it is a Universe-stability / maintenance issue, not a 30-position bulk-rebalance issue.

## Frozen conclusion
The natural quarterly variant `3 x 63-day robust history -> hold Universe 63 days` is not supported. The frozen 126-session Stage7A formulation remains the preferred horizon.

Supported interpretation:
- Robustness appears to require a sufficiently long horizon to distinguish durable opportunity-set quality from short-window noise;
- six-month Universe refresh does not appear too slow on the tested 2023-07 to 2026-09 path;
- quarterly refresh increases boundary interventions, but actual OLS transaction friction rises only modestly because capital remains concentrated in a single leader;
- do not infer that every possible quarterly-maintenance scheme fails. A later decomposition could separately test refresh frequency versus robustness-estimation horizon, but no rescue tuning is allowed inside Stage7B.
