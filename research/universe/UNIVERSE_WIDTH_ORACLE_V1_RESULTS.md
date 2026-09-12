# Universe Width Oracle V1 — Results (2026-09-12)

## Status

**结论：缩小 Universe 确实能降低 Top1 rank churn、延长持有排名寿命并改善回撤，但“池越小收益越高”不成立。真正有价值的是选择性剔除错误竞争者，而不是机械缩容。**

本实验是 hindsight / Oracle 机制研究，不能直接用于实盘选池。

研究定义冻结于：`research/universe/UNIVERSE_WIDTH_ORACLE_V1.md`。

## Baseline

2025–2026 Fixed15：

- Total return: **+372.46%**
- MDD: **-44.72%**
- Top1 switches: **95**
- Mean Top1 tenure: **4.34 日**
- Mean eligible candidates/day: **7.55**
- Missing quote days in the daily research execution model: **11**

## Finding 1 — Greedy Oracle 可以通过继续删标的大幅提高收益，但这是最大后视上限

从 Fixed15 出发，每一步枚举删除一只非现金标的，并选择 2025–2026 total return 最高的删除动作：

| Pool width | 本步删除 | Return | MDD | Switches | Mean Top1 tenure | Candidate mean |
|---:|---|---:|---:|---:|---:|---:|
| 15 | — | +372.46% | -44.72% | 95 | 4.34 | 7.55 |
| 14 | 159985 | +469.76% | -43.57% | 89 | 4.63 | 6.96 |
| 13 | 159509 | +544.49% | -39.45% | 82 | 5.02 | 6.38 |
| 12 | 164824 | +616.06% | -36.93% | 78 | 5.28 | 5.98 |
| 11 | 513920 | +683.96% | -33.94% | 77 | 5.35 | 5.37 |
| 10 | 159529 | +736.44% | -34.40% | 71 | 5.80 | 5.07 |
| 9 | 159825 | +777.59% | -32.62% | 73 | 5.69 | 4.43 |
| 8 | 513100 | +817.25% | -26.63% | 71 | 5.93 | 3.88 |
| **7** | **159981** | **+851.30%** | **-27.79%** | **69** | **6.25** | **3.52** |
| 6 | 511380 | +824.74% | -27.79% | 70 | 6.28 | 2.95 |
| 5 | 513290 | +727.34% | -27.02% | 68 | 6.66 | 2.40 |

Greedy Oracle 最优宽度为 7，池为：

`159915, 161226, 501018, 511220, 511380, 513290, 518880`

但这一条路径是用 2025–2026 结果逐步选择删除对象，属于最大后视优化。它只能证明：

> 如果事后知道哪些竞争者应该删除，Universe composition 的理论影响非常大。

不能据此认为实盘池应该缩成 7 只，也不能据此删除上述 ETF。

## Finding 2 — 随机 / 枚举子池否定了“池越小收益越高”

为了区分“删对了谁”和“少本身更好”，强制保留现金 511220，对原 Fixed15 的其他 14 只做固定宽度子池测试。

组合数 <=300 时全枚举，超过 300 时使用冻结随机种子 20260912 抽样 300 个唯一子池。

| Width | N | Beat Fixed15 | Median return | P10 | P90 | Median MDD | Median tenure | Median switches |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 | 1 | 0.0% | +372.46% | +372.46% | +372.46% | -44.72% | 4.34 | 95 |
| **14** | **14** | 50.0% | **+379.21%** | +226.01% | +454.22% | -43.06% | 4.53 | 91 |
| 13 | 91 | 52.7% | +377.73% | +130.66% | +489.07% | -40.91% | 4.68 | 88 |
| 12 | 300 | 46.0% | +351.50% | +110.61% | +521.52% | -38.95% | 4.85 | 85 |
| 11 | 300 | 34.3% | +283.21% | +71.15% | +509.43% | -36.29% | 5.09 | 81 |
| 10 | 300 | 31.0% | +236.22% | +35.15% | +521.32% | -33.73% | 5.34 | 78 |
| 9 | 300 | 24.3% | +207.26% | +24.42% | +511.82% | -32.75% | 5.57 | 74 |
| 8 | 300 | 21.3% | +197.68% | +27.53% | +487.18% | -31.47% | 5.80 | 70.5 |
| 7 | 300 | 16.3% | +157.85% | +20.59% | +429.41% | -29.63% | 6.18 | 67 |
| 6 | 300 | 10.7% | +86.67% | +3.06% | +384.85% | -27.81% | 6.73 | 62 |
| 5 | 300 | 5.0% | +57.48% | -2.39% | +316.81% | -26.45% | 7.63 | 55 |

最重要的分解是：

### Rank churn 随缩容稳定下降

从 width 15 到 width 5：

- median switches：`95 → 55`
- median Top1 tenure：`4.34 → 7.63`
- median MDD：`-44.72% → -26.45%`

所以：

> 更少候选确实能让排名更稳定，并明显降低回撤。

### 但典型收益并没有随之提高

Random/subset median return：

`372% → 379% → 378% → 352% → 283% → 236% → 207% → 198% → 158% → 87% → 57%`

只有从 15 缩到约 14–13 时，中位数大致持平 / 略有改善；继续缩小后，中位收益快速下降。

因此当前证据否定：

> “Top1 切换越少，所以池应该越小。”

更准确的是：

> **减少候选会降低噪声竞争，但同时会失去真正的新趋势机会。存在明显的 stability–opportunity trade-off。**

## Finding 3 — 频繁切换更像“有好有坏的竞争”，不能全部视为问题

这次结果说明：

1. 候选越少，Top1 确实更稳定；
2. 但如果删错标的，收益损失远大于节省的换手；
3. 因而一部分 leader change 是低质量竞争造成的，另一部分 leader change 则是在捕捉真正的新机会。

所以“排名竞争变快”不能直接等价为“所有换帅都应该抑制”。

更合理的目标应是：

> **减少低质量 challenger 进入竞争，而不是机械降低 challenger 数量。**

这进一步支持动态 Universe / admission gate，而不是固定最小池。

## Finding 4 — 小池状态下，替换通常仍然不如留空

沿 Greedy drop-only 路径，在预先冻结的 width 13 / 11 / 9 上，使用上一轮 Universe Oracle 已冻结的 16 只 external candidates 做测试。

### Same-width swap

| Width | Drop-only return | Swap improve share | Median swap return | Best swap |
|---:|---:|---:|---:|---:|
| 13 | +544.49% | 27.1% | +511.29% | +634.19% |
| 11 | +683.96% | 20.6% | +604.47% | +793.89% |
| 9 | +777.59% | 18.0% | +602.96% | +898.62% |

多数 swap 都使结果变差，而且随着池子变小，成功率进一步下降。

### Add one external candidate

| Width | Drop-only return | Add-one improve share | Median add-one return | Best add-one |
|---:|---:|---:|---:|---:|
| 13 | +544.49% | 12.5% | +529.74% | +556.59% |
| 11 | +683.96% | 25.0% | +661.12% | +704.98% |
| 9 | +777.59% | 25.0% | +754.84% | +837.87% |

同样，多数“补一个新 ETF”都不如保持空缺。

虽然存在极少数非常好的 Oracle swap，例如 width 9 最佳可达 +898.62%，但命中率不足 20%，这是典型的 hindsight selection，不具备直接可交易性。

这进一步支持：

> **Universe 不应有强制补满固定槽位的要求。**

## Finding 5 — Greedy 第一批删除对象与单 ETF 后验诊断并不相同

Greedy Oracle 最先删除的是：

`159985 → 159509 → 164824 → 513920 ...`

而此前单 ETF Post-OLS 诊断突出的是 513100 / 159529。

这不是矛盾，而是说明：

> 单 ETF 自己的 future return / remaining life，与它进入一个截面 Top1 selector 后产生的**边际组合价值**不是同一个问题。

一个 ETF 自己可以有正收益，但仍可能在某些时点成为错误 challenger，抢走另一个更好的 Top1；反之，一个单独统计一般的 ETF 也可能提供独特的趋势机会。

因此未来动态 Universe 不能只按单 ETF 历史收益排序。

## Data-quality limitation

Fixed15 baseline 在本日频研究执行模型中有 11 个 missing-quote days。随着池子缩小，随机子池的 missing-quote days 也总体减少。

这意味着部分 Greedy 改善可能混有 quote-availability 的影响。但值得注意的是：

- 随机池越小，missing quote 问题总体更少；
- 可 median return 仍然在 width <13 后显著下降。

所以“继续缩容损失机会”的方向并不是由 missing quotes 制造出来的；若有影响，它反而使小池看起来更有利一些。

## Main conclusion

当前证据最支持的 Universe 机制不是：

`固定 15 → 固定 7 / 9`

也不是：

`固定 15 → 不断添加更多强 ETF`

而是：

```text
较宽的候选资产覆盖
        ↓
严格的 point-in-time admission / retention gate
        ↓
只有健康、具有增量趋势机会的 ETF 才进入竞争
        ↓
坏 incumbent 可以退出，槽位允许空缺
        ↓
没有足够证据时不强制补位
        ↓
池内继续用相同 OLS Top1
```

换句话说：

> **问题主要是 Universe quality，而不是一个固定的 Universe size。**

宽度本身依然重要，因为更多候选会提高 rank churn；但正确做法不是预设“7只最好”，而是让 point-in-time quality gate 内生决定当月有效池宽。

## Next research implication

下一阶段应该把 Oracle 结果转成一个严格 past-only 的问题：

> 月末时，能否使用截至当时的历史信息判断某 incumbent / challenger 是否值得进入下个月 OLS 竞争池？

第一版应优先研究 **retention / admission**，而不是预测一个固定 Top-K：

- incumbent health / remaining-trend quality；
- challenger 是否显著优于被替代者；
- candidate crowding / score gap / breadth；
- 保留“no replacement / vacancy”状态。

最终必须 monthly freeze + walk-forward，并与原 Fixed15 使用完全相同的 OLS 与执行假设比较。
