# A-share value / drawdown research (pilot)

Pilot launched: 2026-10-28. Push-triggered run enabled on the research branch.

**Status:** experimental, isolated from production ETF/LOF strategies. Do not use as a buy signal.

## Scope
Initial seven symbols: 002353, 688059, 300308, 300502, 300394, 603986, 001309.
Tencent Westock explicitly unadjusted (`--fq bfq`) daily OHLCV from 2026-08-01 to an explicit as-of date.
Comparisons use the max **intraday high** from 2026-09-01 through as-of versus the latest available close. This is not the peak-close drawdown, 60-day max drawdown, or fundamental undervaluation.

## Data
- `data/daily/<symbol>.csv.gz` — bounded, gzip-compressed per-symbol data, committed to GitHub for the pilot only.
- `results/latest.json` — traceable source/price basis/as-of/individual data status.
- `data/finance/<symbol>.json.gz` and `results/financial-source-status.json` — raw Tencent finance snapshots and their acquisition status. These are **not** validated earnings, cash flow or publication-time-safe historical records.
- No writes to Supabase or production OLS universe.
- Financial quality, PE, earnings revisions, historical as-of financial availability, ST/delist status **not yet fetched or validated**. Financial evaluation must be a separate stage before recommending securities.
- For full A-shares, **do not** commit all daily versioned snapshots to Git history. Evaluate Git LFS quota and split sharded Parquet snapshots, GitHub Release assets or off-repo object storage before scaling. Existing `.gitignore` excludes Parquet; `.gitattributes` tracks it via LFS. Do not remove ignores without a migration plan.

## Run
```sh
python research/stock_value/scan_pilot.py --as-of 2026-10-28
```
Requires Node.js `npx` and network access; tool `westock-data-skillhub@1.0.5`. Pushes to this isolated research branch automatically trigger the pilot (only source/workflow changes, not output commits). Scan fails when even one requested symbol is missing; inspect `results/latest.json` for per-symbol errors. Workflow is not scheduled daily, avoiding unbounded daily Git history. A financial snapshot step is best-effort and does not block price screening.

## Follow-up
1. Verify vendor values and corporate-action handling against a second source.
2. Build announcement-time-stamped 2023–2026 financial history with reliable official disclosure sources; check Tencent fundamentals endpoint availability separately.
3. Compute valuation with shares outstanding and actual earnings; flag stale prices and low-quality earnings.
4. Expand universe only after archive quota and incremental update tests.
