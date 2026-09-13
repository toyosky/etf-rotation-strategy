# GitHub Research Infrastructure

This repository uses GitHub as the orchestration and reproducibility layer for ETF/LOF research.

## 1. Responsibility split

### Git repository
Stores strategy/research source code, workflow definitions, compact summaries, specifications and experiment notes. Secrets and frequently-mutated large datasets do not belong in normal Git history.

### Git LFS
Use only for intentionally versioned cold snapshots such as frozen Parquet inputs, reproducibility checkpoints and model bundles tied to a commit/tag. LFS-tracked extensions are defined in `.gitattributes`.

Recommended convention:

```text
data/snapshots/YYYY-MM-DD/
  daily_bars_hfq.parquet
  universe.parquet
  manifest.json
```

A snapshot manifest should record source, as-of time, row count, symbol count, adjustment convention and checksum.

### Supabase PostgreSQL
Use for hot/queryable facts: daily bars, instrument metadata, data-quality status and compact model/research summaries.

### Supabase Storage
Use for large durable research objects that do not need Git history: feature matrices, walk-forward details, parameter grids, correlation matrices and large intermediate Parquet outputs.

### GitHub Actions cache
Use for expensive but reproducible intermediates. Cache is acceleration only, never the system of record.

MUV retention-label caches encode:
- label schema/version
- operating system
- market-data freshness bucket
- hash of the label-construction code chain

The freshness bucket separates runs before and after 16:00 UTC so a post-market-data-sync run does not normally reuse a pre-sync label cache.

### GitHub Actions artifacts
Use for per-run audit evidence: reports, diagnostics, CSV extracts and evaluation outputs. Artifacts are temporary evidence, not permanent storage.

### Codespaces
Use for interactive research/debugging with the same Python 3.12 research environment as Actions. Environment definition: `.devcontainer/devcontainer.json`.

### GitHub Releases
Use only for frozen strategy milestones. Tag convention:

```text
strategy-vMAJOR.MINOR.PATCH
```

Such tags trigger `.github/workflows/release-strategy.yml` and create a reproducibility bundle.

## 2. Governed MUV workflow architecture

MUV workflows from Stage13 onward use shared local Composite Actions.

```text
checkout
  -> .github/actions/muv-bootstrap
       -> Python 3.12
       -> pip cache
       -> dependency install
       -> label cache restore
       -> label build on cache miss
       -> output validation
  -> stage-specific model commands
  -> .github/actions/muv-publish
       -> GitHub Step Summary
       -> run artifact
```

Shared actions:
- `.github/actions/muv-bootstrap/action.yml`
- `.github/actions/muv-publish/action.yml`

A stage workflow should contain only:
1. trigger/path dependencies
2. label version and builder
3. stage-specific model commands
4. report/artifact file declaration

Do not copy Python setup, dependency installation, cache implementation or upload boilerplate into new MUV stage workflows.

### Label version contract

A stage must explicitly declare the label schema it consumes.

Current lineage:
- Stage13–16 -> V1.4
- Stage17 -> V1.5
- Stage18 -> V1.6

A model stage may not silently switch label versions. A label schema change is an experimental change and must be visible in the workflow and research design note.

### Stage19+ template

```yaml
- uses: actions/checkout@v4

- name: Prepare MUV labels
  uses: ./.github/actions/muv-bootstrap
  env:
    ETF_DAILY_BARS_DATABASE_URL: ${{ secrets.ETF_DAILY_BARS_DATABASE_URL }}
  with:
    label-version: vX.Y
    builder: research/marginal_universe_value/build_retention_labels_vX_Y.py

- name: Stage N model
  run: python research/marginal_universe_value/model_retention_stageN.py

- name: Publish Stage N
  if: always()
  uses: ./.github/actions/muv-publish
  with:
    report-file: muv-retention-stageN-report.json
    artifact-name: muv-retention-stageN-${{ github.run_id }}
    paths: |
      muv-retention-v1-summary.json
      muv-retention-labels-v1.parquet
      muv-retention-stageN-report.json
```

## 3. Research output contract

Every milestone stage should ideally produce:

```text
<experiment>-report.json
<experiment>-summary.csv
<experiment>-details.parquet   # when needed
```

Reports should include experiment/stage ID, Git commit SHA when available, data as-of timestamp, sample window, universe definition, key parameters, primary metrics and conclusion/status.

Recommended status values: exploratory, rejected, provisional, validated, frozen.

## 4. Data lifecycle

```text
Public/source data
  -> ingestion Action
  -> Supabase hot store
  -> research Action / Codespace
  -> Actions cache for expensive reproducible intermediates
  -> artifact for run audit
  -> Supabase Storage for large durable research outputs
  -> Git LFS only for intentionally frozen reproducibility snapshots
  -> Release when strategy logic is formally frozen
```

## 5. MUV-specific policy

- Label datasets are derived data, not source-of-truth market data.
- Compatible reruns should reuse cache rather than re-query and rebuild unnecessarily.
- Label-code changes invalidate cache automatically.
- Model reports remain GitHub artifacts unless deliberately promoted.
- A dataset enters Git LFS only when selected as a reproducibility checkpoint.
- Only validated admission/retention logic may be promoted into `strategy/`.
- Older experimental stages remain reproducible; governance refactoring must not change model semantics.

This separation keeps exploratory iteration cheap while preserving auditability and reproducibility at decision points.
