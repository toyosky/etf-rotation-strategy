# OURE Stage7D — Long-History Mechanism Audit Findings

Date: 2026-09-15
Authoritative run: `34924269667`
Artifact: `oure-stage7d-long-history-mechanism-34924269667`
Status: frozen diagnostic
Preregistered verdict: `unresolved`

## Purpose
Stage7D did not alter the deployed Stage7C/A specification. It audited why `3 x 126-session robustness history` appears useful.

## 1. Broad cross-block rank persistence is absent
Across all candidate K30 Universes, the median within-target cross-history pairwise Spearman is only `-0.037`.

Per target block median pair correlations:
- B04: -0.075
- B05: +0.088
- B06: -0.026
- B07: -0.048
- B08: +0.169
- B09: -0.079

Thus candidate-set quality is not broadly persistent from one 126-session historical block to the next. This rejects a simple story in which the same Universes rank well across regimes.

## 2. Aggregation is modestly better than individual historical blocks, but not enough for the preregistered variance-reduction verdict
Median future Spearman by historical signal:
- r1: -0.115
- r2: +0.178
- r3: +0.180
- rank mean: +0.200
- frozen robust score: +0.203
- negative rank std: +0.062
- negative rank range: +0.066

The robust score is better than any single block, but only by about +0.023 versus the best individual-block median IC, below the preregistered +0.03 aggregation-gain threshold. Low historical dispersion by itself has only weak future association.

Therefore the formal `variance_reduction` condition is not met.

## 3. Leave-one-out broad rankings are unstable, but the selected winner is exceptionally stable
Across 18 leave-one-history-block-out evaluations:
- median full-vs-LOO score Spearman: 0.774;
- median full-vs-LOO Top50 Jaccard: 0.274;
- selected full-score winner remains inside the LOO Top50: 18/18 = 100%;
- in practice the winner's LOO percentile is approximately 0.991 to 1.000.

This is the key structural finding. Removing one historical block changes a large fraction of the broad Top50 list, yet it does not dislodge the final winner from the extreme tail.

The preregistered LOO-stability gate nevertheless fails because it required both median score correlation >=0.80 and Top50 Jaccard >=0.50. Therefore the formal Stage7D verdict remains `unresolved`.

## 4. The winner shows an extreme three-block consensus pattern
For every one of the six OOS target blocks, the frozen Robust30 winner ranks above the median in all three historical blocks. More strongly, all six winners are above roughly the 90th percentile in every historical block.

Winner minimum historical percentile by block:
- B04: 0.925
- B05: 0.906
- B06: 0.969
- B07: 0.915
- B08: 0.957
- B09: 0.903

Median minimum historical percentile: `0.920`.

Thus the selected winner is not being rescued by one exceptional historical period. The full candidate population has little cross-block persistence, but the final winner lies in the rare intersection of the extreme upper tails of all three blocks.

## 5. Exploratory tail-consensus audit
This section is explicitly exploratory and was not part of the preregistered verdict.

Because broad pairwise rank correlations are near zero, requiring a candidate to rank extremely well in all three blocks acts approximately like combining multiple partially independent pieces of evidence. The observed count of candidates with all three historical ranks >=0.90 is very small: roughly 1 to 9 out of ~2,496 candidates per target block.

A pure `min(r1,r2,r3)` score has median future Spearman about +0.210 in this exploratory check, similar to the frozen robust score (+0.203), but its Top50 future-percentile quality is weaker than the frozen robust score. This suggests the frozen median+q25 formula is not merely a hard minimum rule; it balances broad strength with protection against a weak historical block.

The emerging mechanism hypothesis is therefore:

`independent-ish historical regimes -> broad ranks differ -> robust aggregation suppresses one-period false positives -> only candidates strong across several distinct histories reach the extreme tail`.

This is better described as **tail consensus / false-positive suppression** than as broad rank persistence.

## Frozen conclusion
The preregistered Stage7D mechanism verdict is `unresolved` and must not be upgraded post hoc.

What Stage7D does establish:
1. Broad candidate rankings are not persistent across 126-session historical blocks.
2. Simply preferring low rank variance is not enough.
3. The deployed winner is highly robust to omitting any one historical block.
4. Every deployed winner is simultaneously extreme in all three historical blocks.

This creates a new, narrower hypothesis: the value of 3x126 history may come from **extreme-tail consensus across weakly correlated historical regimes**, which filters transient false positives.

## Recommended next stage
A separately preregistered Stage7E should test the tail-consensus hypothesis without changing deployment. It should compare, on the same six OOS target blocks:
- frozen robust score;
- rank mean;
- minimum historical rank;
- second-worst / q25 historical rank;
- count of historical blocks above fixed ex-ante percentiles;

and measure whether future value is concentrated specifically among candidates that are simultaneously strong across all three histories. No thresholds should be chosen after inspecting Stage7D outcomes, and Stage7E should remain diagnostic rather than replacing the frozen Stage7C/A baseline.