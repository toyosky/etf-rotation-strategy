# Stage23 Coverage-to-Score Bridge Findings — 2026-09-13

## Frozen question

When the full-market ex-post best 20-day continuation is outside Fixed15, was that missed outsider already near the top of the point-in-time OLS score ordering at month-end?

## Verified run

- Workflow: `MUV Stage23 Coverage-to-Score Bridge Audit`
- Run ID: `34746462867`
- Conclusion: success
- Artifact: `muv-stage23-coverage-to-score-bridge-34746462867`

## Result

The predeclared bridge condition failed clearly.

Overall, among 55 missed full-market oracle-best outsider events:

- OLS score Top1 capture: 7.27%
- Top3 capture: 12.73%
- Top5 capture: 20.00%
- Top10 capture: 27.27%
- Median all-market score rank: 23
- Median rank percentile: 29.85%

By era:

### 2021–24

- n = 40
- Top10 capture: 30.0%
- Median score rank: 21.5
- Median rank percentile: 36.24%

### 2025–26

- n = 15
- Top10 capture: 20.0%
- Median score rank: 32
- Median rank percentile: 18.60%

Frozen support required Top10 capture >= 50% and median rank percentile <= 15%, overall and in both eras. None of the three scopes satisfy both conditions.

## Interpretation

Stage22 established a stable opportunity-coverage gap: Fixed15 misses meaningful future continuation opportunities. Stage23 shows that the existing OLS score cannot compress those missed opportunities into a small conservative shortlist.

Therefore the problem is not solved by simply taking a larger OLS-score TopK. Searching Top20/Top30 or retuning the cutoff on the same history is prohibited.

This is evidence against the current score state as an admission gate, not evidence that admission itself is impossible.

## Branch decision

Reject the score-only bridge and move to a lower-difficulty admission-worthiness target:

- do not predict the unique future best outsider;
- instead ask whether an outsider is strong enough to expand the contemporaneous Fixed15 opportunity frontier;
- use a small fixed point-in-time state representation and strict expanding OOS;
- no hyperparameter search, feature subset search, cutoff search, or policy backtest.

If this low-DoF state cannot improve on score ranking consistently across eras, the next branch should distinguish state-information failure from model-capacity failure with a preregistered nonlinear-capacity benchmark rather than adding ad hoc features.