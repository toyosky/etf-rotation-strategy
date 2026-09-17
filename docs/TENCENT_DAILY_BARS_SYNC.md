# Tencent HFQ daily-bar sync

The workflow `.github/workflows/tencent-daily-bars-sync.yml` runs every day at
23:30 Asia/Shanghai, can be started manually, and also validates itself when the
production data-sync configuration changes.

It refetches an overlapping 14-calendar-day window for the committed production
ETF/LOF universe, requests Tencent HFQ bars through
`westock-data-skillhub@1.0.5`, validates OHLCV, converts Tencent volume from lots
to shares, and idempotently upserts `public.daily_bars` by `(symbol,date)`.

## Production universe frozen 2026-09-17

`public.daily_bars` is now the hot production store for the frozen strategy, not
the full-market research store. It contains the complete available daily history
for these 15 instruments only:

- FixV2 risk pool: 159934, 159985, 161226, 513100, 159957, 159509, 513290,
  159529, 159981, 501018, 513530, 511380, 164824
- defensive comparator / route: 511220
- US carrier: 513500

The pre-shrink full-market raw snapshot (1,090 symbols) is preserved in Supabase
Storage bucket `etf-research-archive` under:

`raw_daily_bars/frozen_20260917/`

The archive is partitioned by year as Zstandard-compressed Parquet and includes
`manifest.json` with source row count, source symbol count, date span, partition
row counts, SHA-256 metadata and per-symbol row counts. It is the restore source
for legacy full-market Universe/MUV research; those jobs must not assume that
`public.daily_bars` still contains the full market.

## Required repository secret

- `ETF_DAILY_BARS_DATABASE_URL`: the Supabase Postgres connection string.

The secret is read only by the workflow process. It must never be committed,
printed, embedded in artifacts, or exposed to pull requests from forks.

## Manual recovery

Use Actions -> Tencent HFQ Daily Bars Sync -> Run workflow and increase
`lookback_days` when the schedule has been unavailable for longer than two weeks.
The job fails instead of silently succeeding when any production-universe symbol
is more than seven calendar days stale after the upsert.

Tencent K-line data is delayed historical market data, not a real-time quote
feed. Minute forward execution data uses the separate `public.minute_bars`
pipeline.
