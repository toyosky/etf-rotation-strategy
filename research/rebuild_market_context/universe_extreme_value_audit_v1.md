# ETF 重建候选池去重与极值效应对照 V1

价格来源：2026-11-11；合格研究标的 1148 只；主题代理组 158；行业组 72。

## 15 日重建事件，10 日次日开盘净收益（6bp/side）

| 候选池 | 验证期交易日 | 每日候选均值 | Top1 10日均值 | Top3 10日均值 | 日等权平均 |
|---|---:|---:|---:|---:|---:|
| ALL | 379 | 22.43 | +0.352% | +0.182% | +0.091% |
| EXPOSURE_PRE | 295 | 4.99 | +0.212% | +0.151% | +0.035% |
| SECTOR_PRE | 244 | 2.98 | +0.342% | +0.257% | +0.149% |
| EXPOSURE_POST | 308 | 5.24 | +0.562% | +0.225% | +0.141% |

## 同日匹配检验：相对于 ALL（Top1 按 slope_delta 排序）

| 收缩池 | 共同日期 | Top1 收益差 pp | 按月区块95%区间 |
|---|---:|---:|---|
| EXPOSURE_PRE | 295 | -0.2013 | [-0.9109, 0.4933] |
| SECTOR_PRE | 244 | 0.0351 | [-0.6729, 0.805] |
| EXPOSURE_POST | 308 | -0.0407 | [-0.7821, 0.6978] |

## 结论边界

- Current-taxonomy exposure keys are coarse; e.g., medical devices and biotech share CHINA_HEALTHCARE, and STAR_MARKET merges unrelated sector ETFs.
- A single ETF per sector can erase true cross-subsector exposures; sector uniqueness is a stress test, not default recommended production rule.
- Current metadata valid_from mostly 2026-09, thus 2021-2026 grouping is not historically verifiable PIT. Delisted ETFs missing; no guaranteed investable historical backtest.
- All variants intentionally use the same universe eligible with known keys: this is NOT a full 2003 ETF comparison.
- Fixed rank slope_delta or past 10d return is a diagnostic, NOT a trained optimal signal. Daily same-date return comparisons do not recreate funded overlapping open positions.
- No NAV premium filters, 09:31/14:05 intraday execution restrictions, LOF share class anomalies, or price adjustment source splice repairs.
- We estimate slope maximum across candidate pools as extreme-value diagnostic; it does not alone prove the best forecast is overfit.