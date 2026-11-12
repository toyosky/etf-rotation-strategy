# 重建环境指标连续量化研究 V3

来源：2026-11-11，全市场 2003 ETF/LOF 归档代码。
时间切分：训练期 552 信号日、验证期 295 信号日；后者含 1474 次重建事件。

## 完整固定区间的扩散率剂量响应（按信号交易日等权）

| 扩散率 | 验证天数 | 事件数 | 10日净收益 | 10日地区超额 | 2025超额 | 2026超额 |
|---|---:|---:|---:|---:|---:|---:|
| [0,10) | 147 | 331 | +0.054% | -0.225% | +0.041% | -0.533% |
| [10,20) | 67 | 340 | +0.785% | +0.726% | +0.737% | +0.717% |
| [20,30) | 28 | 218 | -0.152% | +0.491% | +0.582% | +0.351% |
| [30,40) | 23 | 251 | -3.701% | -1.648% | -2.134% | -1.274% |
| [40,50) | 12 | 69 | -0.538% | -1.105% | -1.233% | -0.724% |
| [50,100] | 18 | 265 | +2.474% | +0.030% | -0.135% | +0.608% |

## 连续量回归：每单位变化，对10日地区超额收益的关联

| 因子 | 单位 | 训练原始 | 验证原始 | 验证控制后 | 验证控制后月度95%区间 |
|---|---:|---:|---:|---:|---:|
| rebuild_diffusion5_pct | 10 | +0.0810 | -0.0803 | +0.0394 | [-0.228, +0.292] |
| diffusion_lag1_pct | 10 | +0.1124 | -0.0573 | +0.0757 | [-0.212, +0.398] |
| diffusion_delta5_pp | 10 | +0.0223 | +0.0278 | +0.0676 | [-0.165, +0.220] |
| trend_breadth15_pct | 10 | -0.0237 | -0.1043 | — | — |
| breadth_delta5_pp | 10 | -0.0177 | -0.1233 | -0.0638 | [-0.263, +0.118] |
| persistence_d5_pct | 10 | -0.0649 | +0.1163 | +0.1824 | [-0.119, +0.491] |
| sector_rs10_pp | 1 | +0.1784 | -0.0224 | +0.0632 | [-0.199, +0.255] |

## 冻结模型的 2025–2026 样本外均方根误差

| 模型 | RMSE pp | OOS R²（对训练均值） |
|---|---:|---:|
| 00_baseline_constant | 3.6390 | +0.0000 |
| 01_market_price_controls | 3.7138 | -0.0416 |
| 02_plus_diffusion_level | 3.7061 | -0.0372 |
| 03_plus_diffusion_velocity | 3.7121 | -0.0406 |
| 04_plus_breadth_velocity | 3.7172 | -0.0435 |
| 05_level_and_velocity | 3.7183 | -0.0440 |
| 06_lagged_diffusion_and_velocity | 3.7151 | -0.0423 |
| 07_all_context | 3.7107 | -0.0398 |

## 非线性（冻结二次项，训练后样本外）

线性模型 RMSE: 3.7061 pp；加入二次项: 3.70759 pp。

## 局限

- Current classifications underlie proxy grouping; 2021-2025 taxonomy not point-in-time; incomplete delisted instruments.
- Using a cross-sectional future median as a reference outcome is not a realistic investable strategy benchmark.
- Same-date events are correlated, and 10-session holding periods overlap; daily results have month-block bootstrap only.
- Continuous linear slopes can be misleading if dose response is nonlinear; bands and OOS quadratic sensitivity must be consulted.
- This is signal-event evaluation with next-session open, not a fully-funded portfolio. No historical QDII/LOF premium or intraday veto.
- Multiple features and variants tested retrospectively; select new rules only after a fresh walk-forward period.