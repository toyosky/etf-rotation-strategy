# New Stage 1A — Structure and robustness audit

Date: 2026-09-14
Parent: New Stage 1 first successful batch, run `34772895471`
Source artifact: `universe-size-stage1-repair-34772895471`

## Purpose

Analyze the already-frozen first Stage1 Monte Carlo batch without changing Universe generation, OLS, K range, parent-pool rule, execution costs, horizon, thresholds, or labels.

The first descriptive read showed a material era contrast, so this audit must determine whether the apparent K effect is stable enough to justify a Stage2 mechanism study or whether Stage1 needs additional predeclared robustness evidence first.

## Frozen analyses

1. Equal-month-weighted K curves overall, by calendar year, and by eras 2021–24 / 2025–26.
2. Per-month linear K slope over K=3..30, broad-range means for K=3..7, 8..15, 16..30, and counterexample months.
3. Month-cluster bootstrap with 2,000 resamples and fixed seed 20260914 for:
   - era-specific mean K slope;
   - era-specific high-minus-low broad-range return difference, where low=K3..7 and high=K16..30.
4. Nested random-delete evidence: each K->K-1 paired delta and telescoping K3 minus K15 delta, overall and by era.
5. Using `sampled_universe_detail.parquet`, summarize K and return relationships for:
   - winner coverage;
   - dormant-member share;
   - switches;
   - observed Top1 tenure;
   - mean pairwise correlation;
   - effective N.
   For each mechanism variable, report K-level means and the distribution of within-month Spearman correlations with total return, overall/by era. These are diagnostics, not causal estimates.
6. Sampling stability diagnostic using deterministic hash halves of the existing 180 same-K universes. This does not replace the predeclared alternative-seed replication.

## Interpretation rule

Do not select a precise optimal K from the full history.

- If the K effect has the same sign/shape across eras and month bootstrap supports a stable broad range, Stage1 can move toward freeze after predeclared seed/0.90 checks.
- If the K effect reverses across eras, Stage1 remains open. The next batch should prioritize determining whether the reversal survives alternative seed and corr_threshold=0.90 before freezing any K range.
- If K mainly changes switching/tenure while coverage moves oppositely, Stage2 should focus on the predeclared remaining-trend-life mechanism; observed Top1 tenure is not the Stage2 lifetime label.

No new threshold search, feature tuning, K tuning, or Stage2 lifetime definition is allowed in this audit.