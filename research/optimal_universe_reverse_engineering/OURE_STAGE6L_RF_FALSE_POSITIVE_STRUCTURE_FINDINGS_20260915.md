# OURE Stage6L — RF False-Positive Matched Structural Audit Findings

Date: 2026-09-15
Status: frozen
Run: 34869360796
Design: `research/optimal_universe_reverse_engineering/OURE_STAGE6L_RF_FALSE_POSITIVE_STRUCTURE_DESIGN_20260914.md`
Artifact: `oure-stage6l-rf-false-positive-structure-34869360796`

## Frozen decision
**Stage 1 matched structural audit PASSED. Stage 2 chronological residual ranker FAILED.**

Decision: `stable_internal_structure_but_second_layer_not_oos_supported`.

The user's false-positive hypothesis receives an important partial confirmation: among K30 sets that receive nearly the same high first-layer RF score, future true-good and future false-positive sets do show repeatable past-only internal structural differences. However, the preregistered low-complexity chronological second layer cannot exploit those differences reliably in later blocks. Therefore this stage does **not** authorize higher-capacity models, CEM/GA/swap search, or RF-guided combinatorial construction.

## Matched audit construction actually evaluated
- Strict Stage6K non-overlapping 126-session blocks.
- Target blocks: B02..B09 (8 blocks).
- First layer unchanged from Stage6K: frozen 19 features + frozen RF.
- RF-high population: fixed top 20% of first-layer predictions; 500 K30 sets per target block.
- Ten prediction strata inside RF-high.
- Good/bad defined from future rank residual only after realization.
- Nearest-neighbor matching is within prediction stratum and without replacement.
- 130 matched good-vs-bad pairs per block, 1,040 pairs total.
- Matching is tight: median absolute RF-prediction-rank gap is roughly 0.0020–0.0028 by block; mean roughly 0.0030–0.0038.

Thus the structural contrast is not simply comparing a clearly higher first-layer RF score with a lower one.

## Stage 1 — stable internal traits
47 preregistered internal features were audited. Twelve features across four families passed the frozen 6-of-8 / effect-size stability gate.

### 1. Stronger member-level past harvestability is the clearest repeated signal
Future-good RF-high sets had systematically stronger trailing member singleton distributions:
- `member_singleton_log_p10`: 7 positive blocks / 1 negative; median standardized effect +0.275.
- `member_singleton_log_p25`: 7/1; +0.303.
- `member_singleton_log_p50`: 7/1; +0.261.
- `member_singleton_log_p75`: 7/1; +0.205.
- `member_singleton_positive_frac`: 8/0; +0.231.

Interpretation: conditional on two sets looking similarly attractive to the first-layer aggregate RF, the true-good set tends to have a stronger **member quality floor / broader member-level harvestability**, rather than being supported by only a few attractive members.

This direction is not confined to one era. Median standardized effects remain positive in both 2022–24 and 2025–26 for all five member-harvestability traits.

### 2. Eligibility participation breadth is also repeated, though less uniformly late
Stable traits:
- `elig_participation_ge50_frac`: 7/1; median standardized effect +0.393.
- `elig_participation_p10`: 6/2; overall positive.
- `elig_participation_p75`: 6/2; overall positive.
- `elig_participation_p90`: 7/1; overall positive.

This is broadly consistent with the previously frozen Opportunity Coverage mechanism: true-good RF-high sets tend to contain more members that are actually able to participate in the past-only competition process.

The signal weakens for some upper eligibility quantiles in the late blocks, so it should not be promoted into a simple monotone standalone rule.

### 3. Leader structure points toward distributed relay rather than a single dominant core
Two leader-shape traits passed:
- `leader_share_nonzero_median`: 6/2, positive overall.
- `leader_share_top5`: 6/8 blocks in the negative direction overall.

The combination means good matched sets tend to give nonzero leaders a somewhat larger typical share while having **less aggregate concentration in the top five leaders**. This is compatible with a distributed relay interpretation rather than a one-or-two-leader persistence architecture.

### 4. Pair structure contributed one stable signal
- `pair_return_corr_p90`: 6/2 positive; median absolute standardized effect about 0.312.

This is not a simple 'lower pair correlation is always better' result. The high-end pair return correlation is actually larger in the matched good sets often enough to pass the frozen stability gate. Therefore broad diversification / low-correlation heuristics should not be substituted for the actual result.

### 5. Leave-one-out robustness did not survive the full 8-block stability gate
The preregistered leave-one-out family did not supply a full-history stable trait. It appeared in some earlier chronological selections but did not remain stable across all B02..B09.

This is useful negative evidence: the matched-good distinction is not cleanly reducible to a static 'every member is indispensable' robustness rule.

## Stage 1 gate
Stable traits: 12.
Stable families: A, B, C, D.

Frozen requirement was >=3 stable features spanning >=2 families.

**Stage 1 PASS.**

This is the main substantive positive result of Stage6L: first-layer RF false positives are not structurally indistinguishable noise.

## Stage 2 — chronological low-complexity residual ranker
Because Stage 1 passed, the preregistered Ridge residual model was run chronologically from B05 onward. Feature retention was recomputed using earlier blocks only, under the frozen proportional stability rule.

Per-block residual Spearman / Top50 gain vs first-layer RF:
- B05: residual IC -0.226; Top50 percentile gain +0.0768.
- B06: -0.061; gain -0.0659.
- B07: +0.138; gain +0.1476.
- B08: -0.219; gain -0.0986.
- B09: -0.0588; gain -0.1378.

Aggregate frozen metrics:
- median residual Spearman = **-0.0611** versus required > +0.10;
- positive residual IC = **1/5** versus required >=4/5;
- median second-layer Top50 actual percentile within RF-high = **0.4627** versus required >0.60;
- median Top50 percentile gain vs first-layer RF = **-0.0659** versus required >= +0.05.

All four Stage-2 primary conditions failed.

The failure is not a marginal threshold miss. The chronological second layer is directionally unstable and on median worsens the RF-high top tail.

## Interpretation
The evidence supports this decomposition:

First-layer RF high score
→ identifies a broad class of plausible K30 sets
→ inside that class, true-good vs false-positive sets have repeatable internal differences
→ strongest repeated differences are member-quality floor + eligibility participation breadth + distributed leader shape
→ but the mapping from those structural differences to residual future value is not sufficiently stable to learn chronologically with the frozen low-complexity model.

So the user's conceptual distinction was useful: **RF can know 'what kind of combination looks good' without knowing which RF-high combinations are genuinely good.** The matched audit finds evidence for the missing internal structure. What fails is the next step: converting that structure into a stable X<=t second-layer detector on the current history.

## Frozen implications
1. Do not reinterpret Stage6K as 'RF knows nothing'. Broad ranking information and matched internal structure both exist.
2. Do not reinterpret Stage6L Stage-1 PASS as deployable second-layer alpha. Stage-2 failed clearly.
3. Do not tune Ridge alpha, residual target, RF-high threshold, prediction strata, stability threshold, or feature definitions on this history.
4. Do not escalate to RF/XGBoost/neural second layers, CEM, GA, or combinatorial search.
5. The 12 stable traits may be retained as a **frozen structural hypothesis set** for genuinely new forward data. A future clean validation can ask whether the same member-quality-floor / participation-breadth / distributed-relay differences recur before any model is fitted.
6. The OURE historical-learning branch remains non-deployable for constructing K30 from scratch using current data alone.

## One-shot stopping rule
The preregistered one-shot stopping condition is met. Findings are frozen and the OURE research automation should be disabled after registry update and user notification.
