# Fixed15 vs Market — Raw OLS Baseline (2026-09-12)

## Question

检验假设：

> 固定池在 2021–2024 的趋势持续较长，但 2025–2026 相对全市场明显缩短；若成立，可能说明固定池本身逐渐失去代表性。

本文件只记录第一阶段 `raw OLS episode` 对照，不等同于 Top1 排名寿命研究。

## Important coverage caveat

现有 `research.ols_episodes` 的 episode 起点要求 point-in-time universe eligibility，因此 Fixed15 中以下 5 只在该表里没有 2021+ 完整事件：

- `161226` 白银 LOF
- `501018` 南方原油 LOF
- `164824` 印度基金 LOF
- `511220` 城投债 ETF
- `511380` 转债 ETF

因此本 baseline 实际覆盖 Fixed15 中 10 只，而不是完整 15 只。这个限制意味着：本结果只能判断“被全市场资格规则覆盖的 Fixed15 子集”，不能作为 Fixed15 最终结论。

## Aggregate raw-episode comparison

仅使用 `start_date >= 2021-01-01` 且 `right_censored=false`。

| Period | Group | N | Median life20 | Survive >=10d | Mean fwd20 | Mean MFE20 | Mean MAE20 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021–2024 | Fixed15-covered | 141 | 14 | 65.96% | +0.55% | +3.80% | -3.51% |
| 2021–2024 | Non-Fixed15 | 4,550 | 13 | 59.49% | +0.23% | +4.85% | -3.97% |
| 2025–2026 | Fixed15-covered | 97 | 16 | 65.98% | +1.44% | +5.10% | -3.26% |
| 2025–2026 | Non-Fixed15 | 4,198 | 17 | 69.32% | +1.18% | +5.75% | -3.69% |

### First implication

Fixed15-covered 子集的 raw OLS episode **没有**出现 2025–2026 明显寿命塌缩：

- median life20：`14 -> 16`
- survive >=10d：`65.96% -> 65.98%`

所以“固定池底层趋势寿命整体变短”这一简单解释目前不成立。

## Matched comparison: same period + asset class + score quintile

为了排除 Fixed15 资产构成与全市场不同，按以下 cell 做描述性匹配：

- period：2021–2024 / 2025–2026
- asset class
- 当期同资产类别内 score quintile

以 Fixed15 事件数作为 cell 权重。

| Period | Matched Fixed N | Mean life diff | Survive10 diff | Fwd20 diff | MFE20 diff | MAE20 diff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021–2024 | 141 | -1.13d | -6.09pp | -0.06pp | -0.18pp | -0.57pp |
| 2025–2026 | 97 | -0.44d | +0.06pp | -0.70pp | -0.46pp | -0.36pp |

在这个粗匹配下，2025–2026 Fixed15 的 raw life 基本与同类同强度市场 ETF 相当，但未来 20 日收益略差。

## More restrictive match: + region_primary

进一步加入 `region_primary` 后，只保留控制组至少 5 个事件的 cell：

| Period | Matched Fixed N | Mean life diff | Survive10 diff | Fwd20 diff | MFE20 diff | MAE20 diff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021–2024 | 102 | -1.13d | -7.04pp | -0.72pp | -0.27pp | -0.65pp |
| 2025–2026 | 73 | +0.15d | +0.05pp | +0.36pp | +0.04pp | -0.08pp |

加入 region 后，2025–2026 的收益差异反而消失并轻微翻正。

因此当前不能稳健地说：

> “Fixed15 在 2025–2026 相对同类市场 ETF 的剩余收益明显恶化。”

至少 raw-start 层面，这个结论对匹配口径不稳定。

## Constituent heterogeneity

Fixed15 内部并不是所有标的方向一致。

几个代表：

- `513100` 纳指 ETF：median life `20 -> 10`；mean fwd20 `+2.18% -> +0.56%`，明显变弱。
- `159985` 豆粕：median life `18 -> 16`；mean fwd20 `+2.37% -> +0.12%`，寿命仍在但剩余收益明显减少。
- `159529` 标普消费：2025–2026 mean fwd20 `-2.92%`，表现较差。
- `513290` 纳指生物：median life `8 -> 20`；mean fwd20 `-2.00% -> +3.23%`，反而明显改善。
- `159915` 创业板：median life `13.5 -> 15`；mean fwd20 `-0.31% -> +2.78%`，改善。
- `518880` 黄金：median life `19 -> 15`，但 mean fwd20 `+1.18% -> +3.38%`，寿命略降但剩余收益更好。

所以 Fixed15 的变化更像是**标的间分化**，而不是整个池统一衰退。

## Current conclusion

第一阶段证据支持：

1. 全市场 raw OLS episode 在 2025–2026 没有整体变短。
2. Fixed15 已覆盖子集的 raw OLS episode 也没有整体变短。
3. 因此此前观察到的 Fixed15 Top1 tenure `6.66d -> 4.01d`，更可能发生在**截面排名 / Top1 竞争层**，而不是底层趋势 episode 层。
4. 某些 Fixed15 成员确实出现剩余收益或寿命恶化，但另一些明显改善，不能据此直接宣布整个固定池失效。
5. 由于 5 只 Fixed15 未进入当前全市场 episode 表，必须用“不套全市场资格门槛”的完整 Fixed15 日频排名测试做最终核验。

## Next diagnostic

下一步应直接比较同一 OLS engine 下：

- 完整 Fixed15（不施加全市场 universe eligibility）的每日 Top1 tenure；
- 全市场 point-in-time eligible Universe 的每日 Top1 tenure；
- 同期候选数、Top1/Top2 score gap、leader-change rate。

这能区分：

- 固定池本身老化；
- 市场整体 leader competition 加剧；
- 固定池内部候选过于拥挤导致换帅更快。

本 baseline 不修改策略，不引入止盈、V1、C2 或新的筛选阈值。
