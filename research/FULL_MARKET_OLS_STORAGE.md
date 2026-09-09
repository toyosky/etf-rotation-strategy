# Full-market OLS Storage pipeline

Date: 2026-09-09

## Goal

Keep Supabase Free Postgres below its 500 MB database limit while preserving the full-market ETF research workflow.

## Data placement

- `public.daily_bars`: keep in Postgres as the source of truth.
- Full daily OLS feature matrix: compute outside Postgres and archive as compressed Parquet in Supabase Storage.
- `research.ols_episodes`: keep only the compact episode-level dataset in Postgres.
- Large intermediate sequence/feature tables: do not persist in Postgres.

## Current cleanup

The following fully rebuildable tables were removed after their rebuild recipe was saved in `research/sql/full_market_ols_rebuild_20260909.sql`:

- `research.ols_daily_features` (~459 MB)
- `research.daily_seq` (~147 MB)

After cleanup the database measured about 172 MB; `public.daily_bars` remained intact with 726,035 rows.

## GitHub Action

Workflow: `.github/workflows/full-market-ols-storage.yml`

Script: `research/full_market_ols_storage.py`

The workflow is manual (`workflow_dispatch`) and does the following:

1. Reads `public.daily_bars` from the ETF_daily_bars Supabase project.
2. Recomputes the frozen 26-price, half-life-10 OLS features locally in the GitHub runner.
3. Applies point-in-time universe eligibility rules.
4. Builds independent OLS trend episodes and their future-life/return labels.
5. Writes daily feature partitions as ZSTD-compressed Parquet to Supabase Storage by year/quarter.
6. Writes the compact episode table back to Postgres.

## Required GitHub repository secrets

Add these under repository **Settings → Secrets and variables → Actions**:

- `ETF_DAILY_BARS_DATABASE_URL`
  - Use the connection string for project `ETF_daily_bars`.
  - A Supavisor/pooler connection string is appropriate for a GitHub-hosted runner.
- `SUPABASE_STORAGE_S3_ACCESS_KEY_ID`
- `SUPABASE_STORAGE_S3_SECRET_ACCESS_KEY`

Generate the S3 key pair in the ETF_daily_bars project under **Storage → S3 Configuration**.

Do not commit or paste these credentials into source files or chat.

The Storage endpoint and region are non-secret and are already fixed in the workflow:

- endpoint: `https://gsyziuzezmmnvgdoazkg.storage.supabase.co/storage/v1/s3`
- region: `ap-southeast-1`
- bucket: `etf-research-archive`

The script creates the bucket if it does not already exist.

## Storage layout

```text
etf-research-archive/
  full_market_ols/
    manifest.json
    episodes/
      ols_episodes.parquet
    daily_features/
      year=2021/quarter=Q1/features.parquet
      ...
      year=2026/quarter=Q3/features.parquet
```

Quarter partitioning is intentional so each object stays comfortably below the Supabase Free single-file upload limit.

## Research contract

This pipeline is not a production strategy change. It preserves the frozen OLS calculation and generates a research dataset for the dynamic-universe question:

> Which observable states, at the moment an ETF first becomes an eligible OLS uptrend, predict longer remaining trend life?
