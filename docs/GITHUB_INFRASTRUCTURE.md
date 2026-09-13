# GitHub Research Infrastructure

This repository uses GitHub as the orchestration and reproducibility layer for ETF/LOF research.

## 1. Responsibility split

### Git repository
Stores:
- strategy source code
- research source code
- workflow definitions
- compact JSON/CSV summaries
- specifications and experiment notes

Does not store secrets or frequently-mutated large datasets directly.

### Git LFS
Use for intentionally versioned cold snapshots only, for example:
- frozen Parquet input snapshots
- reproducibility datasets for milestone experiments
- model bundles that must be tied to a commit/tag

LFS-tracked extensions are defined in `.gitattributes`.

Recommended convention:

```text
data/
  snapshots/
    YYYY-MM-DD/
      daily_bars_hfq.parquet
      universe.parquet
      manifest.json
```

A snapshot should include a manifest with source, as-of time, row count, symbol count, adjustment convention and checksum.

### Supabase PostgreSQL
Use for hot/queryable data:
- daily bars
- instrument metadata
- data quality status
- compact model/research summaries

### Supabase Storage
Use for larger research objects that should remain remotely accessible but do not need Git history:
- full feature matrices
- walk-forward details
- parameter grids
- correlation matrices
- large intermediate Parquet outputs

### GitHub Actions cache
Use for recomputable expensive intermediates. Cache is an acceleration layer, never the system of record.

Rules:
- cache keys must encode data freshness and code identity
- never restore an old market-data cache across an incompatible as-of date
- outputs needed for audit must still be uploaded as artifacts or persisted elsewhere

Current implementation:
- Stage18 MUV retention labels are cached for same-day reruns
- Python dependency cache remains enabled through `actions/setup-python`

### GitHub Actions artifacts
Use for per-run audit outputs:
- reports
- diagnostics
- small CSV extracts
- model evaluation output

Artifacts are temporary run evidence, not permanent storage.

### Codespaces
Use for interactive research/debugging with the same Python 3.12 environment as Actions.

The environment is defined in `.devcontainer/devcontainer.json` and installs `research/requirements-full-market-ols.txt` automatically.

### GitHub Releases
Use only for frozen strategy milestones.

Tag convention:

```text
strategy-vMAJOR.MINOR.PATCH
```

Pushing such a tag triggers `.github/workflows/release-strategy.yml`, which creates a release bundle containing strategy code, strategy specification, README and a machine-readable manifest.

## 2. Research output contract

Every milestone research stage should ideally produce:

```text
<experiment>-report.json
<experiment>-summary.csv
<experiment>-details.parquet   # only when needed
```

The report should include at least:
- experiment/stage ID
- git commit SHA when available
- data as-of timestamp
- sample window
- universe definition
- key parameters
- primary metrics
- conclusion/status

Recommended status values:
- exploratory
- rejected
- provisional
- validated
- frozen

## 3. Data lifecycle

Preferred flow:

```text
Public/source data
  -> ingestion Action
  -> Supabase hot store
  -> research Action / Codespace
  -> Actions cache for expensive recomputable intermediates
  -> artifact for run audit
  -> Supabase Storage for large durable research outputs
  -> Git LFS only for intentionally frozen reproducibility snapshots
  -> Release when strategy logic is formally frozen
```

## 4. MUV-specific policy

For Marginal Universe Value research:

- label datasets are treated as derived data
- same-day reruns may reuse cache
- any change to label-construction scripts must invalidate cache
- model reports remain normal GitHub artifacts unless promoted
- a dataset is committed through LFS only when it is selected as a reproducibility checkpoint
- only validated admission/retention logic is eligible for promotion into `strategy/`

This keeps exploratory iteration cheap while preserving reproducibility at decision points.
