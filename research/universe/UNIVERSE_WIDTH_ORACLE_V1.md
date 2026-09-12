# Universe Width Oracle V1 — Pool-Size / Competition Diagnostic

## Research question

在 Universe Oracle V1 已发现“删掉两个恶化 incumbent 比直接扩池更有效”之后，本实验进一步回答：

> Fixed15 的 2025–2026 收益下滑，是否存在一个结构性的 **Universe 过宽 / 截面竞争过强** 问题？

以及：

> 当池子已经缩小时，用外部 ETF 做同宽度替换，是否比继续缩容更好？

本实验仍然是 hindsight / Oracle 机制研究，不是可交易规则。

## Frozen engine

- 数据：当前 `public.daily_bars`，HFQ。
- 特征：`research/full_market_ols_storage.py` 冻结 26 日加权 OLS。
- Fixed15-style eligibility：`annual>0`, `r2>0`, `score>0`, D2 通过。
- 不使用 full-market `universe_eligible`，避免把原池 LOF/债券意外剔除。
- `511220` 始终作为 cash signal 保留。
- close(t) signal -> open(t+1) execution -> open(t+2) mark。
- 单边成本沿用现有研究引擎。
- 只评价 2025-01-01 以后；2021–2024 不参与选择。

## Stage A — Greedy Oracle deletion path

从完整 Fixed15 开始，`511220` 不允许删除。

对每一步：

1. 枚举删除当前池内每一只非现金 ETF；
2. 分别运行 2025–2026 OLS Top1 回测；
3. 选择 total return 最高的删除动作；
4. 依次把池宽从 15 降到 5。

这是**最大后视上限**，不能用于实盘。它只用于观察：

- 理论最优缩容路径；
- 收益是否持续增加，还是存在最佳宽度；
- Top1 tenure / switch / candidate count 是否随缩容系统变化。

## Stage B — Random subset width distribution

Greedy 路径可能只是“删对了谁”，不能证明“少就是好”。因此每个宽度同时做子池分布：

- `511220` 强制保留；
- 其余从原 Fixed15 的 14 只非现金资产中抽取；
- pool size = 15, 14, 13, ..., 5；
- 组合数 <= 300 时全枚举；超过 300 时使用固定随机种子 `20260912` 抽取最多 300 个唯一子池；
- 不按回测结果重新抽样。

主要看：

- median / P10 / P90 total return；
- beat-Fixed15 share；
- median MDD；
- median Top1 tenure；
- median switches；
- candidate mean。

解释：

- 如果只有 Greedy 改善、随机中位数不改善：关键是 **删对标的**，不是“池越小越好”。
- 如果随机中位数也随缩容明显改善：说明 **Universe 宽度本身** 存在结构性竞争成本。
- 如果缩到某个宽度后中位数重新恶化：说明存在 diversity / opportunity loss，可能有最佳宽度区间。

## Stage C — Smaller-pool replacement

只在结果出来前预先冻结的三个宽度测试：`13 / 11 / 9`。

基准池使用 Stage A 的 Greedy drop-only pool（这是 Oracle 上限基准）。外部候选集合**不新增**，沿用 Universe Oracle V1 constrained grid 已冻结的：

- 10 只 `US_NASDAQ100` structural candidates；
- 6 只 diversified US-equity fallback candidates。

合并去重后形成 external candidate set。

对每个宽度：

1. `swap`：枚举“删除当前池内一只非现金 incumbent + 加入一只 external candidate”，保持池宽不变；
2. `add_one`：在当前缩小池基础上只加入一只 external candidate，观察轻度扩容是否恢复机会、还是重新加剧竞争。

不根据结果修改 external candidate set。

主要看：

- swap 中有多少比例优于该宽度 drop-only baseline；
- swap 的 median / best return；
- add-one 中有多少比例优于 drop-only；
- 对 Top1 tenure / switches 的影响。

## Anti-overfitting guardrails

1. 本实验明确允许 hindsight，只研究机制和理论上限。
2. Greedy deletion 结果本身不能证明某 ETF 应实盘删除。
3. Random subset 分布是判断“宽度效应”的主要证据，不能只看 Greedy 最优路径。
4. 关键 replacement widths 固定为 13 / 11 / 9，不根据结果追加漂亮宽度。
5. external candidate set 沿用上一轮已冻结候选，不再扩大。
6. 任何正结论最终仍需 monthly point-in-time / walk-forward 验证。

## Research log

- 2026-09-12：冻结 V1 设计、宽度范围、随机种子、抽样数、replacement widths 与解释规则。
