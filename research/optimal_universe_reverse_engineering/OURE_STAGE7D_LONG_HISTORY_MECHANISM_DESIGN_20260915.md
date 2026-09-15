# OURE Stage7D — Why Long Robustness History Helps

Date: 2026-09-15
Status: preregistered before outcome inspection

## Question
Stage7C found that the frozen long specification A (`3 x 126-session robustness history -> Robust30 -> hold 126 sessions`) remains strongest, and that long history is the dominant average factor. Stage7D asks why the 3x126 history helps without changing the deployed A specification.

## Frozen setup
- Same Stage7A/7B/7C eligibility rules, candidate-family generation, K=30, seed semantics, robust score, downstream OLS logic and 126-session target blocks.
- Same six OOS target blocks from 2023-07-27 through 2026-09-07.
- No tuning of horizon, K, robust-score weights, thresholds, or candidate-family size.

## Mechanism diagnostics
For every target block and every candidate K30 Universe, compute the three historical 126-session rank percentiles r1,r2,r3 already used by the frozen robust score.

### 1. Cross-block rank persistence
Measure Spearman(r1,r2), Spearman(r2,r3), Spearman(r1,r3), plus their median per target block.

Interpretation: persistently positive cross-block rank correlation supports persistent set quality across regimes; near-zero correlations with successful aggregation supports variance reduction / diversification across historical states instead.

### 2. Candidate instability / dispersion
For each candidate compute:
- rank_mean
- rank_std
- rank_range
- robust_score (frozen)

Measure whether future set value is associated more with high rank_mean or low rank_std after controlling only descriptively through rank correlations; no new deployable model is fitted.

### 3. Leave-one-history-block-out sensitivity
Recompute the same frozen robust formula using each pair among {r1,r2,r3}:
`robust_LOO = 0.5 * median(two ranks) + 0.5 * q25(two ranks)`.

For each omitted block:
- Spearman between full robust score and LOO robust score;
- Jaccard overlap between full-score Top50 and LOO Top50;
- whether the selected full-score Top1 remains inside LOO Top50;
- percentile rank of the full-score Top1 under the LOO score.

This tests whether the full Robust30 winner depends critically on one historical block.

### 4. Block contribution / regime diversification
For the full-score Top50 and selected Top1, report their percentile within each individual historical block. Measure how often the winner is strong in all three blocks versus being rescued by two strong blocks and one weak block.

## Preregistered interpretation
### Persistent-quality dominant
Supported if cross-block rank correlations are consistently and materially positive, LOO stability is high, and future value correlates mainly with rank_mean rather than low dispersion.

### Variance-reduction / regime-diversification dominant
Supported if cross-block rank correlations are weak or mixed, while the full robust aggregation materially outperforms individual-block ranks in future Spearman and the selected winner is LOO-stable despite individual block rank variation.

### Mixed
Supported if cross-block persistence is positive but incomplete and LOO diagnostics show that aggregation also materially stabilizes selection.

### Fragile / unresolved
If selected winners depend heavily on one block or effects are dominated by one target period, freeze as unresolved.

## Primary outputs
- per-target cross-block rank correlations;
- future Spearman of each individual historical rank, rank_mean, rank_std sign-adjusted, and frozen robust score;
- LOO score correlation and Top50 overlap;
- selected winner LOO sensitivity;
- winner historical rank profile;
- explicit verdict among `persistent_quality`, `variance_reduction`, `mixed`, `unresolved`.

## Guardrails
No post-hoc thresholds, no new model, no parameter optimization, no deployment change. Stage7D is mechanism-only.