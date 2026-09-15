# OURE Stage7C — Horizon vs History Decomposition

Date: 2026-09-15
Status: preregistered before outcome inspection

## Motivation
Stage7B rejected the natural quarterly formulation `3 x 63-session history -> next 63-session block` relative to the frozen Stage7A/7B `3 x 126-session history -> next 126-session block` baseline. However, Stage7B changes two things simultaneously:

1. the target/evaluation horizon (63 vs 126 sessions), and
2. the total historical robustness window used to score candidate Universes (3x63 = 189 sessions vs 3x126 = 378 sessions).

Stage7C isolates these components without tuning thresholds after outcome inspection.

## Frozen baseline
The authoritative comparator is Stage7B H126:

`3 x 126-session completed historical blocks -> same frozen robust score -> select K30 -> hold Universe for next 126 sessions -> frozen downstream OLS Top1 logic`

Stage7B authoritative run: `34921530265`.

All Stage7A/7B candidate-library semantics, random seed semantics, eligibility rules, K=30, robust score construction, and downstream OLS logic remain frozen.

## Core 2x2 experiment
Construct four preregistered variants by crossing robustness-estimation history block length with future holding/evaluation horizon:

- A — H126 / Hist126 (baseline): 3 completed 126-session history blocks; hold selected Universe 126 sessions.
- B — H63 / Hist63 (Stage7B quarterly): 3 completed 63-session history blocks; hold selected Universe 63 sessions.
- C — H63 / Hist126: every 63-session decision date, use the immediately preceding contiguous 3x126 sessions, split into three completed 126-session blocks; hold selected Universe 63 sessions.
- D — H126 / Hist63: every 126-session decision date, use the immediately preceding contiguous 3x63 sessions, split into three completed 63-session blocks; hold selected Universe 126 sessions.

This rolling-block definition ensures that each decision uses all information available through t while preserving the intended historical depth. No partial future block is used.

Interpretation:
- A vs C tests 126-session vs 63-session holding/refresh horizon while keeping 378-session robustness history.
- D vs B tests the same holding/refresh contrast while keeping 189-session robustness history.
- A vs D tests 378-session vs 189-session robustness history while keeping the 126-session holding horizon.
- C vs B tests the same history-depth contrast while keeping the 63-session holding horizon.

## Leakage and timing rules
1. For every decision date t, all features, candidate-set scores, member statistics, and robustness statistics must use information available at or before t.
2. Future block return is used only for evaluation.
3. Candidate-library generation must reproduce the frozen Stage7A/7B seed semantics for each holding grid. No extra horizon-specific seed offset may be introduced.
4. Historical blocks are contiguous, immediately precede t, and are fully completed at t.
5. Candidate family and robust scoring formula are frozen. No threshold or weighting changes are permitted inside Stage7C.
6. Downstream OLS Top1 rules and transaction-cost accounting are frozen to Stage7B semantics.
7. The two corner variants A and B must reproduce the authoritative Stage7B H126 and H63 results within a fixed implementation tolerance before C or D may be interpreted.

## Primary common-calendar comparison
Use the same frozen 756-session calendar as Stage7B whenever data availability permits: the interval beginning after 3x126 sessions from the 2022-01-01 anchor and ending after the next 6x126 sessions.

Primary outcomes:
1. Continuous-position path total return at 6bp per side.
2. Same path at 12bp and 20bp per side.
3. Same-calendar 126-session compounded return table for all variants.
4. Number of positive 126-session spans and worst 126-session span.

## Structural diagnostics
For each variant report:
- target/refresh count;
- median cross-sectional Spearman between robustness score and future set value;
- fraction of positive Spearman blocks;
- median Top50 actual percentile;
- median selected Top1 actual percentile;
- Universe-to-Universe Jaccard;
- mean members replaced at refresh;
- downstream OLS turnover sides;
- mean and median OLS Top1 tenure;
- frequency that Universe refresh changes the current OLS target;
- frequency that the previously held ETF is removed at refresh.

## Frozen factor-effect calculation
To avoid interpreting the four terminal paths post hoc, the causal verdict is based on an additive 2x2 decomposition of terminal log wealth.

For each frozen transaction-cost level c in {6bp, 12bp, 20bp}, let L_A(c), L_B(c), L_C(c), and L_D(c) be terminal log wealth of variants A-D.

Define:

- history-depth effect E_hist(c) = 0.5 * [(L_A - L_D) + (L_C - L_B)]
- holding-horizon effect E_hold(c) = 0.5 * [(L_A - L_C) + (L_D - L_B)]
- interaction I(c) = (L_A - L_D) - (L_C - L_B)

Positive E_hist means the longer 378-session robustness history helps on average. Positive E_hold means the 126-session holding/refresh horizon helps on average.

The frozen verdict rule is:

- `history_depth_dominant`: E_hist > 0 at all three cost levels and either E_hold is not > 0 at all three levels, or median(E_hist) >= 1.5 * median(E_hold).
- `holding_horizon_dominant`: E_hold > 0 at all three cost levels and either E_hist is not > 0 at all three levels, or median(E_hold) >= 1.5 * median(E_hist).
- `mixed`: both E_hist and E_hold are > 0 at all three cost levels, but neither median effect is at least 1.5x the other.
- `unresolved`: all remaining cases, including sign instability across transaction-cost levels.

Cross-sectional Spearman and Top-tail diagnostics are confirmatory diagnostics only; they do not override the frozen path-based verdict.

## Primary causal reading
- A history-depth-dominant verdict supports the hypothesis that Stage7B H63 failed mainly because 189 sessions do not provide enough robustness-history depth / regime coverage.
- A holding-horizon-dominant verdict supports the hypothesis that a 63-session target/refresh horizon is itself too noisy even when long history is preserved.
- A mixed verdict means both mechanisms materially contribute.
- An unresolved verdict means Stage7C does not cleanly separate them and no rescue tuning is allowed inside this stage.

## Guardrails against overfitting
- No intermediate horizons (84, 90, 100, etc.) are allowed in this stage.
- No alternative number of historical blocks is allowed in this stage.
- No alternative K is allowed in this stage.
- No feature additions or score-weight changes are allowed in this stage.
- No rescue thresholds after viewing outcomes.
- Any implementation defect may be repaired only to restore the preregistered semantics; the repaired run must invalidate prior affected results explicitly.

## Deliverables
- `oure_stage7c_horizon_history_decomposition.py`
- GitHub Actions workflow for a frozen run
- CSV artifacts for selections, cross-sectional metrics, continuous paths, paired 126-session returns, friction diagnostics, and daily paths
- frozen findings document with an explicit verdict among: `history_depth_dominant`, `holding_horizon_dominant`, `mixed`, `unresolved`

## Stage7C role
Stage7C is diagnostic. It does not replace the frozen Stage7B H126 Robust30 baseline unless a later, separately preregistered deployment stage establishes a superior specification.
