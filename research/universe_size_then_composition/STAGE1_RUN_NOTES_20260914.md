# New Stage 1 run notes — 2026-09-14

## Frozen first batch

Primary configuration remains unchanged:
- samples_per_k = 180
- nested_paths = 36
- seed = 20260914
- corr_threshold = 0.95
- K = 3..30 subject to parent-pool size

Runs 34768593513 and 34768608428 used the same configuration. The second is a duplicate operational run and is not independent robustness evidence.

## Deterministic persistence failure

Both runs completed compilation and entered the full-history batch, then failed after `monthly_parent_pool_snapshots.csv` had been written. The two residual snapshot artifacts are byte-identical in size (623,497 bytes), ruling out a transient runner failure.

Static code audit shows snapshots are written only after the full monthly Monte Carlo and nested-path loops and after aggregation. The first subsequent persistence step is `sampled_universe_detail.parquet`.

The output metadata field `combination_space = C(N-1,K-1)` can exceed Arrow/int64 range. From the frozen residual parent-pool snapshots, 67 of 68 months have at least one K with combination_space > 2^63-1; the maximum is approximately 2.8826e43. This field is metadata only and is not used for sampling or any return/statistical calculation.

## Mechanical repair

Added `stage1_oracle_size_mc_safe.py`, which delegates to the frozen Stage1 runner and changes only the persisted representation of `combination_space` from Python integer to exact decimal text. Sampling, random seeds, parent pools, Frozen OLS evaluation, K range and all research statistics are unchanged.

Repair workflow: `.github/workflows/universe-size-stage1-repair.yml`
Repair run: 34772895471

No Stage1 scientific conclusion is drawn from the failed runs. The first successful repair artifact remains the primary first-batch evidence.
