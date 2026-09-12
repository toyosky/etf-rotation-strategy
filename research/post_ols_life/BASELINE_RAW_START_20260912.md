# Post-OLS Life — Raw-start Baseline (2026-09-12)

## Purpose

这是正式 V1 多 detection 研究运行前的 baseline，只使用数据库中已经存在的 `research.ols_episodes` raw-start contract。

它的作用不是产生交易规则，而是先检查：

1. raw OLS 正趋势本身在不同年份是否真的变短；
2. detection 当日的 OLS/价格状态与后续 OLS 状态寿命是否存在稳定关系；
3. “OLS 状态持续更久”是否同时意味着“未来收益更高”。

## Sample

仅使用：

- `start_date >= 2021-01-01`
- `right_censored = false`

样本数：

- 2021–2024：4,691 个 raw-start episodes
- 2025–2026：4,295 个 raw-start episodes
- 合计：8,986

现有 baseline 的 `ols_life20` 最多截断在 20 个交易日；正式 V1 将扩展为 60 日，并同时加入 MA10、3% peak drawdown、MFE/MAE 和未来收益标签。

## Finding 1 — raw OLS episode 在 2025–2026 没有变短

| Period | N | Median OLS life20 | Survive >=5d | >=10d | >=20d | Mean fwd20 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021–2024 | 4,691 | 13 | 76.23% | 59.69% | 32.66% | +0.24% |
| 2025–2026 | 4,295 | 17 | 84.59% | 69.24% | 44.47% | +1.19% |
| ALL | 8,986 | 15 | 80.22% | 64.26% | 38.30% | +0.69% |

### Interpretation

这与此前固定池/Top1 研究中“2025–2026 Top1 持续期更短”的观察相反。

因此目前更合理的机制假设是：

> **近两年不一定是底层 OLS 正趋势寿命缩短，而可能是截面排名/领头羊切换加快。**

也就是说：

```text
raw trend episode life
    ≠
Top1 tenure
```

这正是正式 V1 必须分别研究 `raw_start`、`tradable_start`、`leader10_start`、`top3_start` 的原因。

## Finding 2 — 强启动状态与 raw OLS 持续性高度相关

下面比较每个特征在各自时期内的最低 20%（Q1）与最高 20%（Q5）。

### `slope_delta`

- 2021–2024：median life `4 → 20`；10日生存率 `32.27% → 87.53%`
- 2025–2026：median life `7 → 19`；10日生存率 `40.16% → 90.45%`

### `current_resid`

- 2021–2024：median life `4 → 20`；10日生存率 `33.44% → 87.53%`
- 2025–2026：median life `8 → 20`；10日生存率 `41.68% → 87.89%`

### `score`

- 2021–2024：median life `5 → 18`；10日生存率 `40.04% → 82.20%`
- 2025–2026：median life `9 → 19`；10日生存率 `49.01% → 85.68%`

### `r2`

- 2021–2024：median life `8 → 16`；10日生存率 `48.14% → 75.69%`
- 2025–2026：median life `13 → 19`；10日生存率 `57.86% → 79.28%`

### `ret5`

- 2021–2024：median life `5 → 20`；10日生存率 `36.42% → 86.14%`
- 2025–2026：median life `9 → 19`；10日生存率 `49.24% → 86.85%`

### `xpercentile`

注意：raw-start 当天很多 ETF 还没有进入真正的截面强者区，因此这里的 percentile 本身通常不高。

- 2021–2024：median life `7 → 16`
- 2025–2026：median life `11 → 20`

### Interpretation

方向在两个时期相当一致：一个 raw trend 刚形成时，如果 OLS slope 正在明显增强、当前价格位于拟合线上方、score/R²/短期动量更强，那么 raw OLS 状态更不容易马上重新跌回非正。

但这存在明显的**机械相关风险**：target 本身就是“OLS 还能保持正多久”，而这些 feature 又直接参与或接近 OLS 状态定义。

因此不能据此宣布这些就是可交易 alpha。

## Finding 3 — OLS 状态更持久，不等于未来收益单调更高

这是 baseline 最重要的约束。

例如 2025–2026：

- `score` Q4 的 mean fwd20 ≈ **+2.30%**，但 Q5 只有约 **+0.22%**。
- `r2` Q4 ≈ **+2.21%**，Q5 约 **+0.02%**。
- `ret5` Q4 ≈ **+1.61%**，Q5 约 **+0.06%**。

所以存在一个很可能的形态：

```text
趋势启动太弱
→ 容易很快消失

趋势适度强
→ 有持续性，也仍有后续收益

趋势已经极强
→ OLS 状态仍会持续，但价格可能已经过熟
```

这说明我们的真正目标不能简化成：

> “最大化 OLS remaining life”

而应该同时约束：

> **状态寿命 + 未来可实现收益 + 下行风险。**

正式 V1 已因此冻结多个 label：`raw_survival_days_60`、`tradable_survival_days_60`、`ma10_survival_days_60`、`days_to_dd3_60`、未来收益、MFE/MAE。

## Finding 4 — 当前资产类别结果只能描述，不能用于筛选

按当前 taxonomy 的 raw-start baseline：

| Asset class | N | Median life20 | Survive >=10d | Mean fwd20 |
| --- | ---: | ---: | ---: | ---: |
| EQUITY | 8,071 | 16 | 67.02% | +0.70% |
| COMMODITY | 315 | 15 | 70.48% | +1.79% |
| CASHLIKE | 600 | 4 | 23.83% | ~0.00% |

但当前 `historical_safe=true` 的 raw-start 样本只有 292 / 8,986，因此这里的资产分类结果只能作为结构性描述，不能直接转成 point-in-time 选择规则。

## What is *not* concluded yet

本 baseline **没有**证明：

- 应该偏好某个资产类别；
- 应该剔除某些 ETF；
- `slope_delta` / `ret5` / `R²` 应设某个阈值；
- Top1 的问题已经解释完毕；
- 极强趋势应该被排除。

这些都要等 Leader10/Top3 detection 的 60 日事件级结果和跨时期稳定性分析。

## Next step already encoded in GitHub

正式 V1 pipeline：`research/post_ols_life/build_study_v1.py`

它将生成：

```text
Supabase Storage / etf-research-archive
  post_ols_life/v1/asof=YYYY-MM-DD/
    events_v1.parquet
    detection_summary_v1.parquet
    asset_class_summary_v1.parquet
    symbol_summary_v1.parquet
    feature_quintiles_v1.parquet
    feature_correlations_v1.parquet
    report_v1.md
    summary_v1.json
```

完整研究定义和反过拟合约束见本目录 `README.md`。
