# Cluster90 × V1 成交额 / Score-gap 迟滞实验

日期：2026-09-09  
状态：**预注册，结果待填**

## 研究问题

Cluster90 的单个 OLS 正趋势寿命并不短，但 Top1 领导持续期明显较短。检验原 V1 的两个思想是否能抑制“大池子中刚刚超过一点就换帅”的极值竞争：

1. 成交额门槛；
2. 现任持仓排名缓冲 + score 差迟滞。

## 固定引擎

- 数据：ETF_daily_bars Supabase `public.daily_bars`。
- Universe：每月冻结 Cluster90；过去120日收益相关系数 >=0.90 视为重复，优先保留更高流动性代表。
- OLS：冻结 26-price、nominal HL10、当前 exact score 与 `trend_eligible`。
- 信号/执行：close(t) 产生目标，open(t+1) 执行；研究成本每买/卖一边 6bp。
- 主样本：2021-01-01~2024-12-31。
- 后验：2025-01-01~2026 最新可用数据。
- 不改 OLS，不加 C2/Premium/minute execution。

## V1 规则的移植

原 V1：

- 20日平均成交额 >= 1亿元；
- 现持仓只要仍为有效趋势且综合排名 <=5，可以保留；
- 新旧标准化 FinalScore 差 >0.30 才允许正常替换；若旧趋势失效则立即退出。

当前 Cluster90 使用 raw OLS Score，不能直接把 raw score 差 `0.30` 当成原 V1 的 `0.30 FinalScore`。因此本实验做**唯一一次、预先固定的量纲对齐**：

- 每日对 Cluster90 当日 eligible 候选的 OLS Score 做横截面 z-score；
- 挑战者必须满足 `z_new - z_old > 0.30`；
- 旧标的若 rank>5 或不再 `trend_eligible` / 不再当月 Cluster90 候选，则不受迟滞保护，立即切换。

不搜索 0.1/0.2/0.4/0.5，不搜索 rank3/rank10，不搜索成交额阈值。

## 四个固定变体

- A_CLUSTER90_RAW：原 Cluster90 raw Top1。
- B_LIQ20_RAW：A + 20日平均成交额 >=1亿元，只改变候选池，不加迟滞。
- C_V1_HYST：A + rank<=5 + 标准化 score gap >0.30 的 V1 式持仓迟滞。
- D_LIQ20_V1_HYST：B + 同一 V1 式持仓迟滞。

## 主要评价

优先观察：

1. Top1/实际目标连续持有期均值、中位数、>=5日比例；
2. switch events / turnover sides；
3. 2021-2024 净收益、MDD；
4. 2025-2026 作为后验一致性；
5. score-gap veto 次数，以及多少挑战者被小 gap 拦截。

判定原则：若只在 2025-2026 改善而 2021-2024 明显恶化，不晋级；不根据结果再调整阈值。
