# Universe Oracle V1 — Results (2026-09-12)

## Status

**结论：Universe 质量具有实质影响，值得继续研究；但当前证据更支持“动态剔除/替换坏 incumbent”，而不是“扩大池子寻找更多强势 ETF”。**

本结果是 hindsight / Oracle 机制实验，不能直接用于实盘换池。

研究设计见 `UNIVERSE_ORACLE_V1.md`。

---

## Frozen benchmark

从 `2025-01-01` 开始比较；2021–2024 所有 variant 保持原 Fixed15 不变。

Fixed15 研究基准：

- 2025–2026 total return：**+372.46%**
- Max drawdown：**-44.72%**
- Switches：**95**
- Mean Top1 tenure：**4.34 日**
- Mean candidate count：约 **7.55**

注意：这是统一的日频研究引擎（close signal -> next open execution），不是分钟级正式策略收益。

---

## Stage A — single Oracle replacements

Stage A 根据事后 raw-episode mean Fwd20 选择：

- `513100` -> `513390`（同 `US_NASDAQ100`）
- `159529` -> `513500`（无同 `US_CONSUMER` 合格替代，因此按预先冻结规则退到新的 `US_EQUITY` risk bucket）

2025–2026：

| Variant | Return | MDD | Switches | Mean Top1 tenure |
|---|---:|---:|---:|---:|
| Fixed15 | +372.46% | -44.72% | 95 | 4.34 |
| Drop 513100 | +394.59% | -36.41% | 93 | 4.43 |
| Replace 513100 | +362.18% | -36.82% | 98 | 4.20 |
| Drop 159529 | +416.00% | -44.72% | 88 | 4.68 |
| Replace 159529 | +423.75% | -43.82% | 88 | 4.68 |
| Drop both | **+440.17%** | -36.41% | 86 | **4.79** |
| Replace both | +428.04% | **-34.84%** | 93 | 4.43 |
| Add both (17 assets) | +363.39% | -42.78% | 98 | 4.20 |

### Stage A interpretation

1. 单纯删除两个已知恶化 incumbent，就把收益从 +372.46% 提高到 +440.17%，同时 MDD 从 -44.72% 降到 -36.41%。
2. `513390` 虽然事后 episode-level Fwd20 很好，但替换 `513100` 后，组合收益反而低于直接删除 513100，甚至低于原 Fixed15。
3. `513500` 替换 159529 有正增量，但增量不大：+423.75% vs 只删除的 +416.00%。
4. 把两个 Oracle 候选直接加进原池（17 只）反而恶化到 +363.39%，Top1 tenure 进一步缩短到 4.20 日。

因此：

> **单 ETF 自身的事后 Fwd20 好，不等于加入截面 OLS 排名后能提高组合。Universe 存在强烈的交互效应。**

---

## Stage B — constrained replacement grid

为了避免单一 Oracle 组合的偶然性，Stage B 固定结构候选集合后枚举全部组合，不按组合收益筛候选。

候选集合：

### 513100 / Nasdaq replacement set（10）

`159501, 159513, 159632, 159659, 159660, 159696, 159941, 513300, 513390, 513870`

全部是满足基础约束的 `US / US_EQUITY / US_NASDAQ100` 非 Fixed15 标的。

### 159529 / consumer-fallback set（6）

`159518, 159612, 513350, 513500, 513650, 513850`

全部满足基础约束，属于 `US_EQUITY`，且 risk bucket 不与删除 159529 后剩余 Fixed15 已有桶重复。

双替换组合共 **60** 组。

---

## Distribution result

| Test | N | Beat Fixed15 | Median return | Best | Worst | Median MDD | Median Top1 tenure |
|---|---:|---:|---:|---:|---:|---:|---:|
| Replace Nasdaq only | 10 | **70.0%** | +375.17% | +394.42% | +356.35% | -37.21% | 4.20 |
| Replace consumer only | 6 | **83.3%** | +417.01% | +423.75% | +360.01% | -44.58% | 4.60 |
| Replace pair | 60 | **91.7%** | **+420.81%** | +454.37% | +340.94% | **-36.63%** | 4.43 |
| Add pair, do not delete | 60 | **35.0%** | +367.50% | +395.09% | +302.90% | -43.83% | 4.20 |

### Strong evidence

双替换的 60 个合法组合中：

- **55 / 60（91.7%）** 的收益高于原 Fixed15。
- 双替换的收益中位数为 **+420.81%**，明显高于 Fixed15 的 +372.46%。
- 双替换 median MDD 约 **-36.63%**，也明显优于 Fixed15 的 -44.72%。

所以改善不是只靠一个事后最优组合。

这足以支持：

> **固定 Universe 中保留已经恶化的 incumbent，确实会系统性拖累 OLS 截面选择。Universe 质量不是边缘问题。**

---

## But replacement is not the whole story

`drop_both`：

- Return **+440.17%**
- MDD **-36.41%**
- Mean Top1 tenure **4.79 日**

60 个双替换组合中，只有约 **21.7%** 能进一步超过 `drop_both` 的收益。

也就是说：

> 大部分收益改善来自**删除两个恶化 incumbent**，而不是必须找到两个新的“大赢家”填满 15 个位置。

这对下一阶段设计非常重要。

我们不应该先假设：

> “池子必须始终保持 15 个，因此删一个必须补一个。”

更合理的假设是：

> **Universe 应允许缩容；只有候选通过事前质量标准时才补位。**

---

## Adding more candidates is usually harmful

保留原 Fixed15，同时增加两个候选的 60 个 `add_pair` 组合：

- 只有 **35.0%** 超过 Fixed15；
- median return **+367.50%**，低于 Fixed15 的 +372.46%；
- **0%** 超过 `drop_both`；
- median Top1 tenure 降到约 **4.20 日**；
- switches 的中位数提高到约 **98**。

这与此前“2025–2026 Fixed15 候选更多、Top1 tenure 更短”的观察一致：

```text
更多候选
  -> 更多同时存在的正趋势
  -> 更多 score 交叉
  -> leader churn 增加
  -> 并不自动产生更高收益
```

因此目前证据反对：

> **简单扩大 ETF 池 = 动态 Universe。**

---

## Why episode-level 'good ETF' is insufficient

Stage A 中 `513390` 是同 Nasdaq 桶里 2025–2026 raw episode mean Fwd20 最好的候选之一，但它作为组合 replacement 并不理想。

Stage B 也显示，同一候选在不同搭档下组合结果不同。

原因是 OLS 是截面 Top1 策略：加入/替换一个 ETF 会改变的不只是它自己的收益，还会改变：

- 哪几天它压过原 Top1；
- Top1 / Top2 gap；
- leader change frequency；
- 原本应该持有的其他资产被抢走多少天；
- 交易成本和回撤路径。

所以后续 Universe 不能仅根据：

> `这个 ETF 自己的未来收益/趋势寿命高`

来判断。

必须验证：

> **这个 ETF 作为候选进入截面竞争以后，是否提高整个 selector 的质量。**

---

## Top pair is NOT a recommendation

事后最高组合：

- Nasdaq slot: `159659`
- Other US slot: `513350`
- Return：约 **+454.37%**
- MDD：约 **-35.63%**

这只是 Oracle 上限，不具有可交易含义。

我们特别不采用“最优组合”作为下一版固定池，因为这是明确的后视选择。

---

## Main conclusion

Universe Oracle V1 支持三个结论：

### 1. Universe 很重要

91.7% 的结构约束双替换组合优于原 Fixed15，说明结果并非依赖单一幸运组合。

### 2. 当前更重要的是退出坏候选，而不是不断增加新候选

`drop_both` 已经解释了大部分改善，而且比多数 replacement pair 更好。

### 3. Universe 必须考虑截面竞争

简单增加两个候选多数情况下没有帮助，并伴随更高换帅频率与更短 Top1 tenure。

因此下一阶段不应直接做：

> 全市场 -> 找历史表现最好的 Top K -> 塞进池里

而应优先研究：

> **point-in-time incumbent health / retirement -> 池子允许缩容 -> 只有满足独立质量标准的候选才替换 -> 次月冻结。**

这比 Cluster90 的“先做全市场代表性去重再排名”更贴近目前得到的实证机制。

---

## Next research stage

建议下一步冻结一个 **Monthly Universe Maintenance V1**：

1. 以 Fixed15 作为起始 benchmark，而不是把 Fixed15 当真理；
2. 每月末只使用当时历史；
3. 先决定 incumbent 是否继续有资格留在池中（retirement）；
4. 被剔除后允许空槽，不强制补满 15；
5. 若同风险桶存在满足过去数据质量/趋势适用性标准的候选，再补位；
6. 下个月候选池冻结；
7. 池内仍用完全相同的 OLS Top1，不加 V1/C2/提前入场；
8. 与 Frozen Fixed15 做 2021–2026 Walk-Forward 对照。

只有这个阶段通过，才能把 Oracle 机制转成可交易的动态 Universe 证据。
