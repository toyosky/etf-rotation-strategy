# Next-open versus signal-close MAE — sensitivity audit, 2026-11-20

This is a **new execution-price sensitivity test**, not a Top1 held-position study and not a predictive model. Reproducible SQL: `sql/next_open_mae_sensitivity.sql`.

## Data integrity gate
Read-only `public.daily_bars` audit over 2021–2026: 21,223 bars; 2021–24 n=13,407, 2025–26 n=7,816. No nonpositive OHLC, no invalid high/low containment, and no overnight open-to-previous-close gaps >25%. 19 latest bars (one per symbol) lack a subsequent opening price. 99th percentile absolute overnight gap is 3.64% (2021–24) and 6.04% (2025–26). **These are internal consistency checks, not proof that adjusted daily lows and opens correspond to an actually tradable fill.**

## Conditional events
Signal: adjusted daily close decline >=2%; valid preceding 20-day turnover mean; t+1..t+5 lows available. `close_MAE = min(low[t+1..t+5])/close[t]-1`; `nextopen_MAE = min(low[t+1..t+5])/open[t+1]-1`. The latter is a *hypothetical next-open reference*, **not** production 14:05 buy. Turnover amount ratio thresholds: <0.8 low, 0.8–1.5 normal, >1.5 high. All event windows can overlap.

| Era | Amount | Events | Signal-close 5d deep fall >=5% | Next-open reference 5d deep fall >=5% | Mean overnight gap |
|---|---|---:|---:|---:|---:|
| 2021–24 | low | 140 | 10.71% | 9.29% | -0.15% |
| 2021–24 | normal | 322 | 14.91% | 12.73% | 0.00% |
| 2021–24 | high | 216 | 12.04% | 12.50% | +0.21% |
| 2025–26 | low | 159 | 35.22% | 28.93% | -0.32% |
| 2025–26 | normal | 230 | 25.22% | 20.87% | -0.12% |
| 2025–26 | high | 139 | 22.30% | 24.46% | +0.60% |

2025–26 low-minus-high deep-fall difference changes from **+12.92pp** using signal-close to **+4.47pp** using next-open reference. For 2021–24 it changes from **-1.33pp** to **-3.21pp**. Thus a substantial part of the apparent difference is **reference-price sensitive**, even before controlling ETF, year, prior path and severity. Do not promote the raw 2025–26 signal to risk sizing.

**Critical next gate:** execute period-correct 14:05 holdings with contemporaneous premium and gap gates wherever possible. Where not possible, explicitly label simulated approximate prices. Next fit chronological purged models and report incremental information of amount beyond OLS + price path, not more ad hoc thresholds.

## Research status
No actual-held Top1 sample, OOS forecast, confidence interval or dynamic sizing test was produced here. This is a distinct new measurement sensitivity audit. Keep research automation enabled; no production edits.
