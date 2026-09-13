# Stage20 Replacement Emergence Audit — Findings

Date: 2026-09-13
Run: 34740735444
Status: completed / branch

## Frozen question

How often does the next-month realized dominant non-cash replacement emerge from outside the currently qualified set, and was it already intermittently visible in the prior 20 trading days?

No new model, feature search, threshold search, horizon tuning, or policy backtest was used.

## Results

Overall OOS non-cash replacement events: 148.

- Qualified at month-end: 76.35%
- Unqualified at month-end but qualified at least once in the prior 20 trading days: 15.54%
- Fully dormant for the prior 20 trading days: 8.11%
- Visible in Top3 at least once in the prior 20 days: 70.95%
- Visible as Top1 at least once in the prior 20 days: 40.54%

By era:

2023–24:
- qualified now: 79.22%
- emergent recent: 15.58%
- dormant 20: 5.19%

2025–26:
- qualified now: 73.24%
- emergent recent: 15.49%
- dormant 20: 11.27%

Conditional on the realized replacement already being qualified at month-end (113 events), the frozen static score baseline was materially stronger than its unconditional result:

- Hit@1: 44.25%
- Hit@3: 73.45%
- MRR: 0.6228
- Median rank: 2

The same pattern holds in both eras: qualified-now Hit@3 was 75.41% in 2023–24 and 71.15% in 2025–26.

## Interpretation

Stage20 does not support the hypothesis that replacement identity is mainly difficult because future replacements are completely invisible at month-end. Most realized replacements are already qualified, and only 8.1% are fully dormant over the preceding 20 trading days.

The 15.5% recent-emergence group is material and can later motivate an admission/qualification-transition branch, but it is not large enough to explain most replacement-ranking difficulty.

Combined with Stage19, the evidence is more specific:

1. Static current score is already a useful reachability heuristic among currently qualified candidates.
2. Adding the frozen 20-day pairwise trajectory model degraded ranking in both eras.
3. Therefore the next step should not add capacity to replacement prediction merely because exact identity remains imperfect.
4. The research target should weaken from exact future replacement / signed MUV toward structural Universe improvements that require less future-price prediction.

## Branch decision

Move to a low-DoF competition-structure audit before any new predictive model.

First weak target: identify whether a persistent `competition nuisance` phenotype exists — an ETF whose presence increases Top1 switching/turnover without delivering positive marginal return. This is a mechanism audit only; it does not yet define a deletion policy.

Admission/emergence remains a secondary branch because 23.65% of realized replacements are unqualified at month-end, but only 8.11% are fully dormant. A future admission model should therefore focus on qualification transition rather than unconstrained winner prediction.
