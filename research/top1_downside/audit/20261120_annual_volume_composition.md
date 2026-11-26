# Downside research — execution 3: year and instrument composition (2026-11-20)

Status: descriptive robustness audit only; **not** an OOS test or Top1 held-position result.

## Method
Re-ran `research/top1_downside/sql/exploratory_volume_path.sql` with a per-year breakdown and an ETF×year×amount group composition query. Event: symbol-day close return <= -2%, at least 20 prior turnover observations. Low amount <0.8× preceding 20-session mean; normal 0.8–1.5×; high >1.5×. Label: subsequent five-session minimum adjusted low <= signal-close×0.95. These observations are highly overlapping. All-symbol diagnostic, **not** actual Top1 held events.

## Annual results

| Year | Low n / deep fall % | Normal n / deep fall % | High n / deep fall % |
|---|---|---|---|
| 2021 | 42 / 9.52% | 72 / 18.06% | 44 / 15.91% |
| 2022 | 54 / 11.11% | 98 / 15.31% | 69 / 15.94% |
| 2023 | 11 / 9.09% | 45 / 6.67% | 38 / 5.26% |
| 2024 | 33 / 12.12% | 107 / 15.89% | 65 / 9.23% |
| 2025 | 31 / 45.16% | 73 / 20.55% | 58 / 15.52% |
| 2026 | 128 / 32.81% | 157 / 27.39% | 81 / 27.16% |

The low-volume disadvantage **reverses across eras**; it is not stable enough for a universal rule. In 2025, 18 of 31 low-volume events were 159529 (10/18 had a >=5% additional five-day fall); in 2026, 27 of 128 low-volume events were 501018 (15/27), 22 were 161226 (13/22), 21 were 520870 (6/21). Therefore symbol/asset composition and overlapping drawdown clusters are plausible sources of the apparent 2025–26 effect. 520870 and 159100 were not in the frozen Top1 risk pool, further demonstrating why this diagnostic cannot be used as a held-Top1 forecast.

The signal-day average fall also differs: in 2025 low group -4.47% vs normal -3.07%; in 2026 low -4.04% vs normal -3.27%. Prior five-day return in 2026 low group -5.32% vs high -1.26%. Raw differences conflate severity, path, asset mix, and regime.

## Interpretation and next gate

**Negative robustness finding:** a static 'low turnover after a -2% day => reduce exposure' rule is unsupported. No conditional model, clustering, confidence interval, or OOS ablation has been fitted. No trading rule should change.

Next: validate release Parquet and historical PIT availability, build instrument-year fixed-effect / event-cluster analysis, and prioritize a reconstructable Top1 holding trace. The production implementation is V1+Void without retired C2; the historical 14:05 execution and premium gates cannot be inferred from daily HFQ alone.

No production files, DB schemas, or scheduled trading jobs were changed.
