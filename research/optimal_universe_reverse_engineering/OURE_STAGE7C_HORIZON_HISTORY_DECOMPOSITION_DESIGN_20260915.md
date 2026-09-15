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
- C — H63 / Hist126: use the same 3 completed 126-session robustness history blocks as the baseline, but refresh/hold the selected Universe every 63 sessions.
- D — H126 / Hist63: use only the most recent 3 completed 63-session robustness history blocks, but hold the selected Universe for 126 sessions.

Interpretation:
- A vs C primarily tests whether shorter refresh/target horizon helps or hurts when long robustness history is preserved.
- A vs D primarily tests whether shortening robustness history hurts when the 126-session holding horizon is preserved.
- B vs C isolates the effect of long vs short robustness history at the 63-session holding horizon.
- B vs D is secondary because both dimensions differ.

## Leakage and timing rules
1. For every decision date t, all features, candidate-set scores, member statistics, and robustness statistics must use information available at or before t.
2. Future block return is used only for evaluation.
3. Candidate-library generation must reproduce the frozen Stage7A seed semantics. No horizon-specific seed offsets may be introduced.
4. When a 63-session refresh occurs inside a 126-session historical block grid, the long-history variant may only use fully completed 126-session blocks available by that refresh date; no partial future block is allowed.
5. Candidate family and robust scoring formula are frozen. No threshold or weighting changes are permitted inside Stage7C.
6. Downstream OLS Top1 rules and transaction-cost accounting are frozen to Stage7B semantics.

## Primary common-calendar comparison
Use the maximal common calendar for which all four variants have valid predictions under the strict completed-block rules.

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

## Primary causal reading
The following interpretation is preregistered:

### History-window explanation supported
If C (H63 / Hist126) materially recovers the baseline ranking quality and performance relative to B (H63 / Hist63), while D (H126 / Hist63) materially degrades relative to A, then the dominant explanation is insufficient robustness-history depth / regime coverage.

### Holding-horizon explanation supported
If C remains materially weaker than A despite preserving long history, while D remains close to A despite short robustness history, then the dominant explanation is the shorter 63-session target/refresh horizon itself.

### Mixed explanation
If C partially recovers B but remains clearly below A, and D is also clearly below A, then both robustness-history depth and holding horizon matter.

### No clean decomposition
If differences are small, inconsistent across cost levels, or dominated by one or two periods, freeze the conclusion as unresolved rather than tuning a rescue specification.

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