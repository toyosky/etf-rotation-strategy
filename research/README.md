# Research

这里保存尚未进入正式策略的研究与验证。

## 当前研究主线

研究优先级按层次推进：

1. `Universe / MUV`：研究哪些 ETF 应获得 OLS 竞争资格，以及它们进入/退出 Universe 后的边际组合价值。
2. `OLS`：在冻结 benchmark 上验证趋势识别和剩余趋势寿命。
3. `Takeover / V1`：研究 Top1 接管、score 变化和成交额确认。
4. `Execution`：最后处理分钟级买卖时点、滑点、QDII/LOF 溢价等。

固定 15 池及现有 OLS 逻辑作为 benchmark，不因全历史表现好坏直接删改资产。

## 当前进行中的正式研究

### Marginal Universe Value (MUV)

核心问题：一个 ETF 是否应该获得 OLS Universe 的竞争资格，能否被形式化为一个可估计的 counterfactual 数学经济问题？

入口：`research/marginal_universe_value/README.md`

核心对象：

- `Retention Value`：现有成员保留 vs 删除，对下一期策略产生的边际价值。
- `Admission Value`：外部 challenger 加入 vs 不加入，对下一期策略产生的边际价值。
- V1 先保存多维 counterfactual labels，不提前用人为权重压成单一 utility。
- 目标是最终形成 monthly past-only `retention + admission` gate，而不是固定 Top-K 或固定池宽。

本项目是当前 Universe 研究的长期数学建模主线。

### Post-OLS Remaining Trend Life V1

核心问题：ETF 在被 OLS 识别为趋势以后，什么样的 ETF / 什么样的当时状态拥有更长、且仍具经济价值的剩余趋势寿命？

入口：`research/post_ols_life/README.md`

当前文件：

- `research/post_ols_life/README.md`：冻结研究定义、detection contracts、labels、feature set、反过拟合约束与数据 lineage。
- `research/post_ols_life/BASELINE_RAW_START_20260912.md`：正式 V1 运行前的 raw-start baseline 与初步机制发现。
- `research/post_ols_life/build_study_v1.py`：V1 事件构建、60 日标签、分期诊断、Parquet/Storage 归档脚本。
- `.github/workflows/post-ols-life-v1.yml`：研究运行入口。

本研究的事件级大数据不写入 PostgreSQL；输出到 Supabase Storage：`etf-research-archive/post_ols_life/v1/`。

## 新研究目录约定

后续新增脚本优先按主题进入子目录：

```text
research/
  asset_class/              资产大类筛选、类内状态和趋势生存分析
  universe/                 候选池、Oracle、池宽、去重、月度冻结池、Walk-Forward
  marginal_universe_value/  MUV counterfactual target、retention/admission 建模
  ols/                      OLS episode、Top1 寿命和排序诊断
  execution/                V1、切换、分钟级执行
  post_ols_life/            剩余趋势寿命研究
  archive/                  已终止且不再被 workflow 引用的历史实验
```

目前已有大量历史脚本仍位于 `research/` 根目录，因为现有 GitHub Actions 直接引用这些路径。为避免破坏复现性，暂不强制搬迁；只有在确认 workflow 引用同步更新后才归档。

## 实验记录最低要求

每个重要实验至少记录：

- 假设及经济含义
- 数据源和数据区间
- 与 benchmark 的唯一差异
- 是否严格 past-only / walk-forward
- 样本量 / 触发次数
- 收益、回撤、换手、交易成本
- 稳健性 / 分时期结果
- 过拟合风险
- 最终结论：保留 / 放弃 / 继续观察

## 数据输出原则

不要把所有研究中间结果长期写进 PostgreSQL。

建议：

- 小型摘要、状态、最终指标 -> PostgreSQL `research` schema
- 大型逐日特征矩阵、相关性矩阵、参数扫描、Walk-Forward 明细 -> Parquet / Supabase Storage
- 临时 Actions 输出 -> artifact，必要时设置较短 retention

## 已有研究组件

`asset_health.py` 是独立于交易逻辑的候选资产健康监控器，只诊断历史 Top1 后续延续性，不自动修改 ETF 池或生成交易指令。

V1 方法与冻结规则见 `docs/ASSET_HEALTH_MONITOR_V1.md`。

仓库总体边界和存储规范见 `docs/REPOSITORY_ARCHITECTURE.md`。
