# 2026-11-20 — volume result sensitivity to event thinning

## Context and nonduplication

Continues PR #7 after commit `bbc4d0a0` (annual next-open, prior-path breakdown). This run checked the existing audit files and recent GitHub Actions: the latest `Qualified Rebuild Premium Sync` is failing; `Research Rebuild Market Context Indicators` succeeded. No production workflows were changed.

## New executed diagnostic

SQL: `research/top1_downside/sql/thinned_next_open_volume.sql`.

For each ETF, retain **every fifth qualifying down-day event** in chronological order, with the first event selected (rank % 5 = 1). Event qualifies if signal day close-to-close <= -2%; prior 20-session mean turnover is available; future 5 lows and next opening price are available. Relative amount <0.8 is LOW and >1.5 HIGH. Outcome is whether min(low[t+1:t+5]) / open[t+1] - 1 <= -5%.

Observed:

| Period | LOW n | LOW event rate | HIGH n | HIGH event rate | LOW minus HIGH |
|---|---:|---:|---:|---:|---:|
| 2021–2024 | 29 | 13.79% | 47 | 8.51% | +5.28pp |
| 2025–2026 | 28 | 28.57% | 33 | 27.27% | +1.30pp |

This is an **exploratory sensitivity check**, NOT a formal independent-event analysis. Selecting every fifth *event* does not guarantee >=5 trading sessions between events, and can retain overlapping labels. The samples are small, unbalanced across ETFs and years, and the deterministic offset is arbitrary. No confidence intervals, statistical significance, or independent predictive increment are asserted.

The 2025–26 LOW minus HIGH gap becomes only +1.30pp under thinning (versus +4.47pp in the previous unthinned next-open aggregate), showing instability under sampling. This is consistent with **not adopting any standalone volume trigger**. It is NOT evidence for or against a true conditional volume effect.

## Remaining high-priority tasks

- Reconstruct historical position-level Top1 from period-specific executable code and PIT-gated premium/intraday data; otherwise clearly separate daily approximation and live-forward validation.
- Recover and inspect the archived full-market Parquet (found in the release but not yet parsed), and check delisting, date availability, raw turnover vs adjusted prices.
- Fit five pre-registered feature blocks on truly chronological OOS folds with purge/embargo, compare Brier/log loss/PR-AUC and calibrated quantiles. Do **not** call these exploratory screens a model.
- Perform a genuine event-cluster/block bootstrap or exact >=5-session event de-overlap on a separate robustness pass; the thinning result is not a substitute.
- No dynamic sizing backtest is justified yet. Formal strategy stays unchanged.

**Run status:** partial research progress, not complete. Automation remains active.
