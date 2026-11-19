# Top1 downside risk: preregistration and run ledger

Status: IN PROGRESS — design frozen before model experiments.
Created 2026-11-20. Research branch only. No production strategy modifications.

## Research question
For the actual frozen Top1 executable holding at decision time t, do path, trend, volume, volatility and market-context features improve out-of-sample prediction of future adverse excursions, and can risk-based sizing improve realized portfolio drawdown without unacceptable opportunity cost?

## Dataset and audit gates
- Primary: reconstruct the *executable* historical Top1 holding with the frozen 26-day half-life-10 log-price OLS, C2, Void and defensive routing. Distinguish original challenger, final target, actual human holdings.
- Secondary: all ETF down-day events, explicitly not equated to held Top1.
- Verify as-of adjusted OHLC, volume units, ETF inception, gaps, splits, NAV/premium availability, slippage, delistings and survivorship. Current public.daily_bars coverage is only 19 symbols (2021–2026), not full market. Investigate historic Parquet/Release/Storage.
- If executable historical holding cannot be reconstructed, do NOT claim primary validation.

## Outcomes and information cutoff
End-of-day t features only; t+1 opening executable decision. At horizons 3, 5, 10 sessions: min subsequent executable-period low relative to execution price (MAE); binary loss thresholds 3%, 5%, 8%; conditional quantiles, duration to trough and recovery, missed rebounds. Explicitly label the alternative signal-close-relative descriptive outcome and never conflate it with executable MAE. Mark censored episodes.

## Prespecified feature blocks
B0 OLS-only: beta, R², fitted deviation, score/gap where available.
B1 price path: returns 1/3/5/10/20, downside streak, speed, prior peak drawdown, rebound age, gap, range.
B2 volume: lagged 20-session relative volume and turnover, price-volume interaction, OBV proxies, liquidity. Independently test B0+B1+B2 vs B0+B1.
B3 volatility: 5/10/20 realized and downside vol, ATR, semivariance, expansion, extreme moves.
B4 market: point-in-time breadth/regime, cross-sectional dispersion, risk-relative bond/market proxies, correlation.
No future index membership, delayed NAV, news or fundamentals allowed in X.

## Statistical protocol
- Purged chronological walk-forward, 10-session minimum label embargo at train/test boundaries; first viable OOS block determined by data availability. Report 2021–24 vs 2025–26 and annual slices without implying 2021–24 were all out-of-sample.
- Baseline constant event-rate and OLS-only; sequential ablation B0, B0+B1, +B2, +B3, +B4; test interactions on training folds only.
- Models: regularized logistic and quantile regression first; shallow gradient-boosted trees only as complexity check. Preprocessing and missing-value policy fit on train only.
- Brier, log loss, PR-AUC, ROC-AUC secondary, calibration, pinball loss, risk stratification; cluster/block bootstrap for dependent events and uncertainty; control comparisons/multiple testing; by-year, by-asset, leave-one-ETF-out sensitivity.
- Compare portfolio with unchanged frozen baseline, fixed fractional exposure, volatility targeting and fixed stop. Dynamic risk-based 100/70/40/0 sizing tested only after predictive OOS increment established; transaction costs, next-open fills, turnover, gap, rebound opportunity costs included. No production deployment without user approval.

## Stop / acceptance criteria
Archive exact inputs, provenance, code, reproducible commands, year/event counts, feature ablations, robustness and honest null results. Explicit decision: accepted, rejected or insufficient evidence. Stop automation after final report; if irrecoverable access/coverage failure, document limitation and stop rather than looping indefinitely.

## Run ledger
2026-11-20 initial run:
- Checked repository research root: no existing research/downside_risk directory, avoiding duplication.
- Current production Actions latest run was Fundamental Audit Trigger #44576203650, unrelated to this experiment.
- Created isolated research branch research/top1-downside-20261120.
- This file is the preregistration; no model fitting, historical execution reconstruction, or strategy performance result is claimed.
- Next: audit historical data sources and frozen execution code, implement reproducible feature/label construction and chronological tests.
