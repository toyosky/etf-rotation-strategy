# OURE Stage6L — RF False-Positive Matched Structural Audit Findings

Date: 2026-09-14
Run: `34869360796`
Artifact: `oure-stage6l-rf-false-positive-structure-34869360796`
Status: frozen
Decision: `stable_internal_structure_but_second_layer_not_oos_supported`

## Executive result
The user's two-layer hypothesis receives a clear split result.

1. **Mechanism / structural hypothesis: PASS.** Among K30 sets already ranked in the previous-block RF's top 20%, future winners and future false positives with closely matched RF predictions have repeatable internal structural differences. Twelve of 47 preregistered new internal features satisfy the full B02..B09 stability rule, spanning four distinct feature families.
2. **Chronological second-layer detector: FAIL.** A frozen low-complexity Ridge residual model using only historically stable traits fails all four preregistered OOS gates across B05..B09. Stable hindsight-matched differences therefore do not yet provide a deployable method for identifying which current RF-high K30 is internally good.

This stage supports the conceptual decomposition `coarse RF class -> internal quality`, but freezes the current algorithmic implementation as non-deployable.

## Design recap
- First layer is frozen Stage6K: K=30, past126 X, future126 Y, frozen 19 features and RF parameters, previous fully completed block -> next block.
- In each B02..B09 target block, only RF-predicted top 20% K30s are studied.
- RF-high sets are split into ten prediction strata.
- Within each stratum, top and bottom residual quartiles are nearest-neighbor matched on first-layer RF prediction rank.
- Residual is `future_rank_pct - rf_pred_rank_pct`.
- All new structural X uses only past126 information.
- Future outcomes are used only to define good/bad residual labels.

## Stage 1 — stable internal structure PASS
47 new past-only internal features were tested. Twelve satisfy the frozen rule: finite in >=6 blocks, same sign in >=6/8 blocks, median absolute standardized matched effect >=0.15. They span families A, B, C and D, so the gate of >=3 features from >=2 families passes comfortably.

### A. Member standalone harvestability — strongest and broadest signal
True future winners inside the RF-high class tend to have stronger **lower and middle parts of the 30-member standalone-quality distribution**, not merely one or two standout members.

Stable positive matched effects:
- `member_singleton_log_p10`: 7 positive / 1 negative block; median standardized effect +0.275; median |effect| 0.325.
- `member_singleton_log_p25`: 7/1; +0.303; |effect| 0.354.
- `member_singleton_log_p50`: 7/1; +0.261; |effect| 0.279.
- `member_singleton_log_p75`: 7/1; +0.205; |effect| 0.258.
- `member_singleton_positive_frac`: **8/8 positive**; +0.231; |effect| 0.231.

Interpretation: among two K30s that the first-layer RF regards as similarly attractive, the better future set more often contains a broad base of individually harvestable members. This is materially different from a set whose attractive aggregate statistics are produced by a small strong subset plus many weak passengers.

### B. Eligibility participation breadth — stable positive signal
Future winners also tend to have broader member participation in OLS eligibility during the current past126 window:
- `elig_participation_ge50_frac`: 7/1; median effect +0.393.
- `elig_participation_p10`: 6/2; +0.316; median |effect| 0.451.
- `elig_participation_p75`: 6/2; +0.197.
- `elig_participation_p90`: 7/1; +0.277; median |effect| 0.447.

This suggests that a genuinely good RF-high K30 is more often supported by many members that repeatedly obtain competition eligibility, rather than by aggregate coverage produced by sparse or episodic members.

### C. Leader participation shape — partial distributed-relay support
Two leader-shape features are stable:
- `leader_share_nonzero_median`: 6/2 positive; median effect +0.202.
- `leader_share_top5`: 6/8 blocks negative; median effect -0.089 with median |effect| 0.208.

Taken together, true winners tend to distribute useful leader participation somewhat more broadly across members: members that do become leaders have a higher typical participation share, while the top five collectively are less dominant. This is directionally consistent with the earlier distributed-relay mechanism, but the effect is not strong enough to claim that concentration alone identifies winners.

### D. Pair geometry — naive maximum diversification is not supported
`pair_return_corr_p90` is stable **positive**: 6/2 positive blocks; median effect +0.252; median |effect| 0.312.

Thus true RF-high winners are not simply the most internally uncorrelated sets. Some coherent upper-tail pair structure appears beneficial. This rejects a simple 'lower pair correlation is always better' interpretation and is consistent with the idea that a useful Universe can contain related members as long as the overall competition/replacement structure is productive.

### E. Leave-one-out robustness — no full-history stable trait
No leave-one-out damage feature survives the full 6-of-8 stability gate. Some LOO variables looked stable in early historical blocks and entered early chronological feature selections, but they did not persist through all blocks. The preregistered evidence therefore does not establish deletion robustness as a stable false-positive discriminator.

## Stage 2 — chronological residual detector FAIL
Because Stage 1 passed, the preregistered conditional second layer was allowed to run.

For each B05..B09 test block, feature selection used only earlier target blocks and the frozen 75%-sign-consistency / |effect|>=0.15 rule. Ridge(alpha=10) then predicted residual rank only inside the current RF-high top20% population.

Results:

| Test block | Selected features | residual IC | second-layer Top50 future pct | RF Top50 future pct | delta |
|---|---:|---:|---:|---:|---:|
| B05 | 12 | -0.226 | 0.519 | 0.442 | +0.077 |
| B06 | 25 | -0.061 | 0.463 | 0.529 | -0.066 |
| B07 | 16 | +0.138 | 0.602 | 0.454 | +0.148 |
| B08 | 12 | -0.219 | 0.404 | 0.503 | -0.099 |
| B09 | 8 | -0.059 | 0.310 | 0.447 | -0.138 |

Aggregate primary metrics:
- median residual Spearman = **-0.0611**;
- positive residual IC = **1/5**;
- median second-layer Top50 future percentile within RF-high = **0.4627**;
- median Top50 gain versus first-layer RF = **-0.0659**.

All four preregistered Stage-2 gates fail:
1. median residual IC > +0.10: FAIL;
2. positive IC >=4/5: FAIL;
3. median second-layer Top50 percentile >0.60: FAIL;
4. median Top50 improvement vs RF >=+0.05: FAIL.

The simple current past126-set-return Top50 is also often competitive or better (for example 0.627 in B05, 0.611 in B07 and 0.559 in B09), so there is no hidden practical victory for the second layer.

## What this means
Stage6L materially sharpens the current model of the problem.

The Stage6K top-tail failure is **not** because all RF-high K30s are internally indistinguishable. They are distinguishable ex post in a structured way. In particular, genuinely successful high-RF sets tend to have:
- stronger broad member-level standalone harvestability;
- broader member eligibility participation;
- somewhat more distributed leader participation;
- a nontrivial coherent upper-tail return-correlation structure.

However, these stable matched group differences do **not** translate into a stable per-combination residual predictor when learned only from prior blocks. Group-level structural regularities and deployable individual ranking are different requirements.

A plausible reason is mapping drift at the second layer as well: the direction of several structural families is broadly repeatable, but their relative magnitudes, interactions and which candidate is the false positive vary enough that a fixed low-DoF linear residual map cannot identify the next block's extreme tail.

## Frozen conclusion
The user's proposed decomposition is useful and receives partial validation:

`RF coarse good-looking class -> real internal good/bad structure exists` **PASS**.

`past-only algorithm can currently identify the internally good members of that class in the next block` **FAIL** under the preregistered low-complexity second layer.

Therefore:
- do not discard the internal-structure hypothesis;
- do not claim a deployable second-stage selector;
- do not tune the Ridge, thresholds or feature list on B05..B09;
- do not escalate to CEM/GA/RF-guided argmax from this result;
- a future continuation would require a genuinely new algorithmic hypothesis for converting stable group structure into individual out-of-period ranking, or new forward data.

Per the one-shot rule, the research automation is stopped after this frozen result is recorded.