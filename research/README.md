# Research

这里保存尚未进入正式策略的研究与验证记录。

建议每个实验单独建 Markdown 文档，至少记录：

- 假设与经济含义
- 使用的数据区间
- 与当前正式版的唯一差异
- 触发次数 / 样本量
- 收益、回撤、换手和交易成本变化
- 是否存在明显过拟合风险
- 最终结论：保留 / 放弃 / 继续观察

当前 `main` 分支中的 `strategy/main.py` 只保存已经认可的正式逻辑，实验信号不要直接混入正式代码。

## Asset Health Monitor

`asset_health.py` 是独立于交易逻辑的候选资产健康监控器。它只诊断历史 Top1 状态的后续延续性，不自动修改 ETF 池，也不生成交易指令。

V1 方法与冻结规则见 `docs/ASSET_HEALTH_MONITOR_V1.md`；Supabase 表结构见 `research/sql/asset_health_snapshots.sql`。
