# OURE Stage6K — Strict Adjacent 126→126 RF Transfer Findings

Date: 2026-09-14
Run: `34865276309`
Artifact: `oure-stage6k-adjacent-126-transfer-34865276309`
Status: frozen failed primary gate
Decision: `adjacent_mapping_transfer_not_supported`

## Why this stage supersedes Stage6J for deployability
Stage6J used calendar half-year boundaries with future126 labels and therefore had a small label-availability timing confound. Stage6K fixes this by using consecutive non-overlapping 126-session blocks. For every transition, the previous block's complete future126 outcome is fully realized before the next decision date.

Everything else remains frozen: K=30, downstream OLS, point-in-time candidate pool, deterministic K30 family library, the same 19 whole-set features, and the same RF hyperparameters.

## Sample
Nine complete 126-session blocks were available, giving eight strict adjacent OOS transitions:
- B01: 2022-01-04 → 2022-07-13
- B02: 2022-07-14 → 2023-01-16
- B03: 2023-01-17 → 2023-07-26
- B04: 2023-07-27 → 2024-01-29
- B05: 2024-01-30 → 2024-08-08
- B06: 2024-08-09 → 2025-02-20
- B07: 2025-02-21 → 2025-08-22
- B08: 2025-08-25 → 2026-03-06
- B09: 2026-03-09 → 2026-09-07

Each block contains 2496 K30 samples across 676 combination families.

## Primary previous-block RF — formal FAIL
Frozen aggregate results across the eight transitions:
- median Spearman = **+0.10917**;
- positive Spearman share = **7/8 = 87.5%**;
- median predicted-Top50 actual percentile = **0.53005**;
- median predicted-top-decile log lift = **+0.00487**.

Frozen gates:
1. median Spearman > +0.10: PASS;
2. positive Spearman share >= 2/3: PASS;
3. median predicted-Top50 actual percentile > 0.60: **FAIL**;
4. median predicted-top-decile log lift > 0: PASS.

All gates were required, so Stage6K is a formal non-pass.

## Transition-level primary behavior
Previous-block RF Spearman / Top50 percentile / top-decile lift:
- B02: +0.074 / 0.659 / +0.0082
- B03: +0.182 / 0.652 / +0.0485
- B04: +0.072 / 0.513 / +0.0188
- B05: +0.118 / 0.488 / +0.0015
- B06: +0.100 / 0.566 / +0.0279
- B07: -0.107 / 0.368 / -0.0484
- B08: +0.124 / 0.547 / -0.0020
- B09: +0.345 / 0.472 / -0.0050

The key failure mode is visible directly: broad IC can be positive while the extreme top tail is mediocre or negative. B09 is the clearest example: IC +0.345, yet predicted Top50 percentile only 0.472 and top-decile lift is negative. That is unsafe for a combinatorial optimizer, which would deliberately exploit the surrogate's extreme tail.

## Frozen secondary diagnostics
### Simple current past126 growth rank
- median Spearman = +0.11868;
- positive share = 62.5%;
- median Top50 percentile = 0.53024;
- median top-decile lift = +0.00391.

Against this much simpler X<=t baseline, previous-block RF has essentially the same median Top50 quality and slightly lower median IC. On the eight transitions the RF beats the simple baseline in only 4/8 periods for IC, 4/8 for Top50 percentile, and 4/8 for top-decile lift. There is no robust incremental-value claim for the nonlinear transferred mapping.

### Expanding-history RF
- median Spearman = -0.04545;
- positive share = 37.5%;
- median Top50 percentile = 0.45102;
- median top-decile lift = -0.00981.

Pooling stale historical mappings is actively harmful on aggregate, consistent with mapping drift and with Stage6-era regime instability.

## Frozen interpretation
Stage6I remains valid evidence that a contemporaneous 126-session K30 value surface often contains substantial cross-sectional structure. Stage6K answers the deployability question more narrowly:

> **The immediately previous 126-session mapping carries weak broad-ranking persistence, but not enough stable top-tail precision to support RF-guided K30 construction. It also does not robustly improve on a simple current past126 set-return rank.**

Therefore the bottleneck is not existence of a value surface. It is the inability to estimate its extreme high-value region at t using the frozen historical mapping-transfer rules.

## Final gate for this research branch
Per the preregistered program, mapping-transfer failure must be frozen rather than rescued with higher model capacity, feature search, result-conditioned thresholds, or RF-guided combinatorial optimization.

Current evidence supports:
- K30 / large-K relay as a real hindsight mechanism;
- contemporaneous future126 K30 value surfaces as often learnable in same-period grouped CV;
- some adjacent broad rank persistence;

but does **not** support:
- a stable X<=t top-tail surrogate for dynamically constructing the next K30;
- RF-guided argmax / swap search;
- increasing model capacity on this same history.

The defensible conclusion is: **with the current historical data and frozen low-/moderate-DoF mappings, dynamic K30 construction is not yet identified well enough for deployment.** A new research branch would require a genuinely new hypothesis or genuinely new forward data, not further tuning of this mapping family.
