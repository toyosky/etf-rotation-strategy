# Post-OLS Remaining Trend Life Study

## Research question

核心问题：

> ETF 在被 OLS 识别为趋势以后，哪些当时可观察的特征能够解释更长的**剩余趋势寿命**？

本研究先回答机制问题，不直接修改正式策略，也不在第一阶段加入 V1、C2、提前入场或分钟执行规则。

## Why this study exists

当前已知问题不是 OLS 完全无法识别趋势，而是“强趋势被识别时可能已经走过一段”。因此，比继续优化 Top1 排名更基础的问题是：

1. OLS 第一次识别趋势时，后面还剩多少寿命？
2. 剩余寿命主要由 ETF 自身价格状态解释，还是由所属资产类别/同类 breadth 解释？
3. 这种关系在 2021–2024 与 2025–2026 是否稳定？
4. 是否存在可用于未来 Universe 筛选的、事前可观察且跨时期稳定的特征？

## V1 frozen definitions

为了避免用一个人为阈值定义“被 OLS 发现”，V1 同时保留多个 detection contract。所有 contract 都基于同一套冻结 OLS feature engine（`research/full_market_ols_storage.py`）。

### Detection A — `raw_start`

同一 ETF 的 raw OLS 从非正状态转为正状态，且该日满足 point-in-time universe eligibility。

Raw OLS positive：

- `annual > 0`
- `r2 > 0`
- `score > 0`

这是最早、最宽的趋势识别基线。

### Detection B — `tradable_start`

在同一 raw OLS 正趋势 episode 内，第一次进入当前全市场研究管线的 `trend_eligible` 状态：

- point-in-time universe eligible
- raw OLS positive
- D2 最近三日急跌过滤通过

### Detection C — `leader10_start`

在同一 raw OLS episode 内，第一次进入可交易趋势标的的截面 Top 10%（`xpercentile >= 0.90`）。

这是 V1 的主要“强趋势被发现”诊断口径，因为它使用相对排名而不是额外拟合一个绝对阈值。

### Detection D — `top3_start`

在同一 raw OLS episode 内，第一次进入当日可交易趋势集合的 Top 3。

它最接近真正的高排名候选，但样本数较少，只作为稳健性对照，不作为第一阶段唯一研究口径。

## Labels: what is “remaining trend life”?

V1 不用单一标签决定答案，而是同时保存多种结果：

- `raw_survival_days_60`：从 detection 日之后开始，raw OLS 连续保持正状态的未来交易日数，最多记 60 日。
- `tradable_survival_days_60`：当前 trend-eligible 状态连续维持的未来交易日数，最多 60 日。
- `ma10_survival_days_60`：收盘维持在 MA10 之上的未来连续交易日数，最多 60 日。
- `days_to_dd3_60`：从 detection 起按后续新高更新峰值，到首次回撤 3% 的交易日距离；60 日内未发生则记 60，并另存 hit 标记。
- `fwd5 / fwd10 / fwd20 / fwd40`：未来收益。
- `mfe20 / mae20 / mfe40 / mae40`：未来窗口最大有利/不利变动。

主研究目标是 `raw_survival_days_60`，其他标签用于确认结果不是某一种“趋势死亡”定义制造的。

## Features frozen before looking at results

ETF 自身状态：

- `score`, `annual`, `r2`, `slope`
- `score_delta`, `r2_delta`, `slope_delta`
- `current_resid`
- `ret3`, `ret5`, `ret10`, `ret20`, `ret60`
- `dist_high20`, `dist_high60`, `dist_high120`
- `vol20`, `vol60`
- `efficiency10`, `efficiency20`
- `ma10_dist`
- 当时的流动性质量

截面状态：

- `xrank`, `xpercentile`
- `trend_count / universe_count`

资产类别状态：

- `asset_class`, `region_primary`, `exposure_level1`, `risk_bucket`
- 同一资产类别当日 universe 数量
- 同类 trend 数量与 trend breadth
- 同类 median `r2`, `score`, `slope`

资产分类使用当前 taxonomy 作为**结构性描述标签**。第一阶段不会把后验统计得到的“某类表现好”直接变成交易规则；后续 Walk-Forward 只允许使用当时可观察的动态价格特征。

## Anti-overfitting rules

1. V1 特征集合在查看结果前冻结，不根据结果追加“刚好有效”的指标。
2. 先看单变量分位与 Spearman 关系，不直接做复杂 ML。
3. 结果必须拆分 `2021–2024` 与 `2025–2026`；方向反转的特征不进入下一阶段。
4. 单 ETF / 单资产类别排名只作描述，不能直接据此删除或加入标的。
5. Top3 样本少，不允许只用 Top3 得出规则。
6. 后续任何筛选规则必须 Walk-Forward：月末只用当时历史数据，冻结到下月。

## Data lineage

```text
Supabase public.daily_bars
        ↓
research/full_market_ols_storage.py  (frozen OLS feature engine)
        ↓
research/post_ols_life/build_study_v1.py
        ↓
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

GitHub 只保存代码、研究定义与最终复盘 Markdown；大型事件级和中间结果保存在 Supabase Storage 的 Parquet 中。

## Fixed15 vs market rank-tenure diagnostic

为区分“底层趋势寿命”和“Top1 排名寿命”，另建：

`research/post_ols_life/fixed15_vs_market_rank_v1.py`

固定定义：

- Fixed15：完整 15 只，不施加全市场流动性/上市期 universe gate，只使用同一 OLS 正趋势条件 + D2；
- Market：使用冻结的 point-in-time `trend_eligible`；
- 两侧每天按同一 `score` 排 Top1；
- 分别统计 2021–2024、2025–2026 的 Top1 run length；
- 同时记录 candidate count、Top1/Top2 relative score gap、leader change rate；
- 仅把紧凑摘要写入 PostgreSQL `research`，不持久化日频大矩阵。

该诊断直接检验：此前 Fixed15 Top1 tenure 缩短究竟是固定池特有问题，还是市场整体截面竞争变化。

## Versioning

- `v1`：多 detection contract + 60 日剩余寿命诊断；不拟合模型。
- 如果未来修改 detection、label 或 OLS feature engine，必须新建 `v2`，不得覆盖 v1 定义。

## Stage plan

1. **Stage 1 — Descriptive diagnostics**：比较 detection 时点、资产类别、ETF 自身状态与剩余寿命。
2. **Stage 2 — Stability**：2021–24 / 2025–26 分段，检查方向稳定性。
3. **Stage 3 — Walk-Forward**：只把稳定特征转成月度 Universe 筛选候选。
4. **Stage 4 — Strategy comparison**：固定池 Benchmark vs 动态 Universe，同一 OLS，不加入 V1/C2。

## Research log

- 2026-09-12：冻结 V1 研究问题、detection contracts、labels、feature set、反过拟合约束与存储路径。开始 Stage 1。
- 2026-09-12：完成 raw-start baseline，并发现全市场 raw OLS episode 在 2025–2026 并未缩短；新增 Fixed15 vs full-market rank-tenure diagnostic，以定位 Top1 寿命缩短发生在哪一层。
