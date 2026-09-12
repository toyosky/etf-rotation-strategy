# Universe Research

用于候选池构建、流动性筛选、去重和 Walk-Forward Universe 研究。

原则：

- 只使用当时可获得的信息；
- 候选池在月末生成并冻结到下月；
- Cluster/correlation 只作为去重工具，不再作为 Universe 的核心优化目标；
- 与固定池 benchmark 比较时保持 OLS、交易成本和 execution 一致。

大型候选池明细和诊断结果优先写 Parquet；数据库只保留当前池、月度快照索引和摘要指标。
