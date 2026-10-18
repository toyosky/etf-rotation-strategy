# Sector exposure incremental admission study (2026-10-18)

## Status and boundary

Research only. This directory **does not** modify the official JoinQuant strategy,
the existing Top1 risk pool, PushPlus, or the historical strategy registry.

GitHub workflow: `.github/workflows/sector-exposure-increment.yml`.

## Research assets

- 512800: bank / domestic value and dividend exposure
- 512660: military / defence thematic equity
- 159825: agriculture / FuGuo ETF; formerly retired from the historic strategy candidate universe
- 516550: JiaShi broad agricultural equity; alternative representative; observe liquidity

The last two are **alternative agriculture carriers**, not two independent risk factors.

## Market data

- Historic bank, defence and 159825: 2026-09-17 frozen S3 year-partitioned
  dataset (`etf-research-archive/raw_daily_bars/frozen_20260917/`).
  SHA-256 is checked against the frozen manifest.
- Recent bars: Tencent Westock HFQ, overlapping the historical frozen archive.
- 516550 not present in the frozen archive: fetch each 150-calendar-day
  interval from its verified listing date (2021-04-08) through present.
  Never use a single Tencent call to infer all-time completeness: the
  provider caps result length at around 250 bars.
- Do not fabricate missing history from index proxies.
- Prices at the archived/Tencent overlap are compared after a common level
  ratio adjustment; reject an inconsistent adjustment seam.
- Store these candidates **only** in
  `research.sector_candidate_bars`; do not alter
  `public.daily_bars` or membership of the live risk pool.

## Frozen tests

Same baseline risk pool, same features and entry logic:
- 26-close, half-life 10 weighted OLS as defined in
  `research/full_market_ols_storage.py`.
- Existing `universe_eligible` and `trend_eligible` guards:
  200 trading bars, 365 calendar days since listing,
  60-day average amount >= 20m CNY, 60-day median amount >= 10m CNY,
  60-day nonzero volume share >=95%, and D2 filter.
- At close(t), rank highest positive annual * R²,
  buy at open(t+1), value at open(t+2).
- Per-side backtest friction = 6 bps.
- Discovery period: 2021-2024; unchanged validation period: 2025-2026.
- Variants: BASE, ADD_BANK, ADD_DEFENSE, ADD_AGRICULTURE
  (516550), ADD_AGRICULTURE_RETIRED (159825),
  ADD_ALL (one agriculture representative 159825),
  ADD_ALL_WITH_BOTH_AGRI (diagnostic only).

Rebuilding is independent of Top1:
- First annual slope <=0 to >0 cross
- First age 1-3 with annual>0, R² above cross and one-day R² increasing
- Next-session open to close at horizons 5, 10, 20, 40 trading days
- Report unfiltered event counts **and** independently track universe eligibility

## Limitations

This is the structural OLS research model, **not** full production
FixV2/C2/Void/State Map/09:31/14:05 minute execution nor full NAV
premium-veto backtest. It uses historical point-in-time prices and rolling
liquidity but excludes historical investability suspensions and point-in-time
fund premium history. For any new candidate, the expanding universe
can affect switch frequency. Multiple signals overlap; event samples are not
independent. Missing quote days and unusual early provider bar histories
must be reported rather than silently filled.

Review portfolio return, MDD, switch count, candidate exposure days,
R² event returns and validation-period stability **together** before
promoting any candidate to live status.
