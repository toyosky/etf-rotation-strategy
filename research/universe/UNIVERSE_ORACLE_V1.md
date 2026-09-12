# Universe Oracle V1 — Fixed15 Replacement Upper-Bound Test

## Research question

核心问题：

> 如果我们事后知道 Fixed15 中哪些标的在 2025–2026 变差，并用同期表现更好的同类 ETF 替换，原 OLS Top1 轮动能改善多少？

这不是可交易策略，而是一个 **hindsight / Oracle 上限实验**。它只回答：

> Universe 质量是否足够重要，值得进入下一阶段的 point-in-time / walk-forward 动态候选池研究？

## Why this test comes first

此前诊断已经发现：

- 全市场 raw OLS episode 在 2025–2026 没有整体缩短；
- Fixed15 的 daily Top1 tenure 却从 2021–2024 的约 5.84 日下降到 2025–2026 的约 4.34 日；
- Fixed15 内部同时处于正趋势的候选数量增加；
- 个别标的（尤其 513100、159529）在 2025–2026 的剩余收益质量明显变差。

因此先做一个最小化的 Oracle 实验，判断“池子质量”本身有没有足够大的经济影响。

## Frozen deteriorated symbols

本实验在看替换回测结果之前冻结以下两个对象：

- `513100` 纳指 ETF：此前独立 Post-OLS 诊断显示 2025–2026 raw life / Fwd20 相较 2021–2024 明显恶化。
- `159529` 标普消费 ETF：2025–2026 raw-start mean Fwd20 明显为负。

不再根据本实验回测结果追加第三、第四个“坏标的”。

## Oracle replacement rule

替代候选必须：

1. 不属于原 Fixed15；
2. 当前 taxonomy `needs_review=false`；
3. 最迟在 `2024-01-01` 已存在，即 2025 年开始时至少约有一年历史；
4. 2025–2026 至少有 5 个完整 raw OLS episodes；
5. Oracle 排名指标只使用 `2025–2026 mean fwd20`，不做参数扫描。

### 513100

优先限定：

- 同 `region_primary`
- 同 `exposure_level1`
- 同 `risk_bucket = US_NASDAQ100`

在满足条件的候选中取 2025–2026 mean Fwd20 第一名。

### 159529

先尝试同 risk bucket。如果没有合格候选，则放宽为：

- 同 region / exposure (`US / US_EQUITY`)
- 排除剩余 Fixed15 已经代表的 risk buckets
- 排除第一个 Oracle replacement 的 risk bucket

再取 2025–2026 mean Fwd20 第一名。

这个 fallback 的目的是避免用一个已经存在的科技/生物/纳指暴露去重复堆叠同一类风险。

## Pool change date

所有池子修改只从 `2025-01-01` 开始。

2021–2024 所有 variant 都使用完全相同的原 Fixed15，因此 2021–2024 只作为代码一致性检查，不用于评价 Oracle 替换。

## Daily ranking contract

为了避免全市场 infrastructure eligibility 把原 Fixed15 中的 LOF/债券等意外剔除，本实验的 Fixed15-style ranking 不使用 `universe_eligible`。

每日候选只要求：

- `annual > 0`
- `r2 > 0`
- `score > 0`
- D2 最近 3 日急跌过滤通过

然后按冻结 OLS `score` 选 Top1。

`511220` 如果成为 rank Top1，映射为现金。

执行模型沿用研究基准：

- close(t) 生成信号
- open(t+1) 执行
- open(t+1) → open(t+2) 计日收益
- 单边成本沿用现有研究引擎

## Frozen variants

- `fixed15`：原池，不变。
- `drop_513100`：2025 起只删除 513100。
- `replace_513100`：删除 513100 + Oracle 同桶替代。
- `drop_159529`：2025 起只删除 159529。
- `replace_159529`：删除 159529 + Oracle 替代。
- `drop_both`：2025 起删除两只，不加新人。
- `replace_both`：2025 起同时替换两只。
- `add_both`：保留原 Fixed15，再额外加入两个 Oracle 候选。

## Interpretation

三个关键消融：

1. `drop` vs `fixed15`：坏 incumbent 本身是否拖累策略？
2. `replace` vs `drop`：新 ETF 是否真的提供增量机会？
3. `add_both` vs `fixed15`：只是扩大池子就有帮助，还是会因为增加截面竞争而恶化？

如果 `replace_both` 明显优于 `fixed15`，且优于 `drop_both`，说明 Universe 质量具有实质经济意义。

如果 `drop_both` 已经解释几乎全部改善，而 replacement 没有额外贡献，那么更像“删除坏标的”问题，而不是主动寻找新机会。

如果 `add_both` 反而恶化，则说明 Universe 不是越大越好，候选质量/竞争结构本身很重要。

## Anti-overfitting guardrail

本实验允许后视，只因为它是上限/机制测试。

任何正结果都 **不能** 直接把 Oracle 替代 ETF 加入实盘池。正结果最多允许进入下一阶段：

> monthly point-in-time universe selection → freeze next month → same OLS ranking → walk-forward comparison.

## Research log

- 2026-09-12：冻结 Universe Oracle V1 设计、坏标的、替代约束、消融 variants 和解释规则。