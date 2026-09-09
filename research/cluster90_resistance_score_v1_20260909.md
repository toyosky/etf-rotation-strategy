# Cluster90 × Resistance + ScoreDelta V1

日期：2026-09-09  
状态：**预注册，结果待填**

## 研究问题

检验此前固定池中表现较好的 V1 换帅确认机制，能否抑制 Cluster90 的短暂/提前 Top1：

`ResistancePct252 >= 75% AND ScoreDelta_new <= 0 -> veto new Top1`

这里的成交额不是绝对流动性门槛，而是历史成交额在当前价格上方区域的 Volume Profile 阻力。

## 冻结 V1 定义

对新 Top1 候选 B：

1. 使用候选当日收盘价 P；
2. 回看此前最多120个交易日，把每个历史日的 amount 均匀分布在该日 `[low, high]`；
3. `UpperShare = Amount[P,1.05P] / Amount[0.95P,1.05P]`；
4. `ResistancePct252` = 当前 UpperShare 相对于该 ETF 此前最多252个日度 UpperShare 观测的 point-in-time 百分位；至少60个历史 profile 观测；
5. `ScoreDelta_new = Score_t - Score_{t-1}`；
6. 仅当 `ResistancePct252 >= 75% AND ScoreDelta_new <= 0` 时 veto；否则按 raw OLS Top1 换帅。

不搜索 70/80 阈值，不搜索 ScoreDelta 数值阈值。

## Cluster90 适配

- Universe：每月冻结 Cluster90（120日相关性 >=0.90 去重，流动性优先代表）。
- OLS：冻结 26-price / nominal HL10 / exact score / D2 trend_eligible。
- V1 **仅作用于纯排名换帅**：旧持仓仍是当日 Cluster90 的 `trend_eligible` 候选时，才允许 veto 新 Top1。
- 若旧持仓已失去 trend eligibility、当日无候选、或因 Cluster90 月度代表变化不再属于当日候选，则不允许 V1 延长持有，按基线切换/退出。
- 这是为了只测试“提前换帅”机制，不让 V1 覆盖风险/Universe 硬失效。

## 对照

- A_CLUSTER90_RAW：Cluster90 raw OLS Top1。
- B_CLUSTER90_V1：A + 冻结 Resistance/ScoreDelta V1，仅纯排名换帅应用。

## 执行与样本

- 数据：ETF_daily_bars Supabase `public.daily_bars`。
- close(t) 产生目标，open(t+1) 执行，open(t+2) 标记日收益；每买/卖一边成本6bp。
- 主样本：2021-01-01~2024-12-31。
- 后验：2025-01-01~2026-09-08。
- 不加 C2/Premium/minute execution。

## 主要评价

1. 2021–2024 净收益、CAGR、MDD；
2. 2025–2026 后验一致性；
3. 换帅次数与实际连续持有期；
4. V1 veto 次数与独立分歧区段 alpha；
5. veto 后旧持仓相对 raw 新 Top1 的实际分歧期表现。

判定：若只在后验期改善、主样本恶化，则拒绝；不根据结果调阈值。
