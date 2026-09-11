# Tencent HFQ daily-bar sync

The workflow .github/workflows/tencent-daily-bars-sync.yml runs every day at
23:30 Asia/Shanghai and can also be started manually.

It refetches an overlapping 14-calendar-day window for the committed ETF/LOF
universe, requests Tencent hfq bars through westock-data-skillhub@1.0.5,
validates OHLCV, converts Tencent volume from lots to shares, and idempotently
upserts public.daily_bars by (symbol, date).

## Required repository secret

- ETF_DAILY_BARS_DATABASE_URL: the Supabase Postgres connection string.

The secret is read only by the workflow process. It must never be committed,
printed, embedded in artifacts, or exposed to pull requests from forks.

## Manual recovery

Use Actions -> Tencent HFQ Daily Bars Sync -> Run workflow and increase
lookback_days when the schedule has been unavailable for longer than two weeks.
The job fails instead of silently succeeding when any universe symbol is more
than seven calendar days stale after the upsert.

The committed universe contains 1,078 ETFs and 12 passive
index/commodity/cross-border LOFs. Tencent K-line data is delayed historical
market data, not a real-time quote feed.
