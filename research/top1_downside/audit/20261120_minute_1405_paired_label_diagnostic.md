# 2026-11-20 分钟线配对：次日开盘代理 vs 14:05入场后的5日MAE（run 12）

状态：**实际执行的分钟线SQL诊断**，不是正式Top1持仓重建、不是已通过路由的可成交样本、不是新的模型OOS结果。数据源：Supabase `gsyziuzezmmnvgdoazkg.public.minute_bars`，查询日期2026-11-20。此前已阅读 PREREGISTRATION、上一轮 execution_low_label_integrity 及季度滚动报告。生产规则未改。

## 样本与定义
2026-09-14起的1分钟线；15只标的，每只38个具有后续5个完整交易日的配对信号日，合计570个**symbol×signal_date**，高度重叠，不能当570个独立风险事件。信号t收盘，比较t+1开盘入场与t+1 14:05分钟bar收盘入场的两个假想5日持仓风险。对14:05口径，t+1仅使用14:05及之后分钟bar最低价，t+2至t+5使用整日最低价；开盘口径使用t+1至t+5整日最低价。两个口径的分母不同，因此MAE差异不能全部归因于“上午低点污染”，也可能来自14:05相对开盘的价格变化。未验证09:31/14:05是否符合原策略买入许可，未验证PIT溢价，故属于**minute-price proxy**。

## 实测摘要
- 501018：n=38；开盘基准平均L5=3.392%，14:05基准=3.863%，差(open-minus-14:05)=-0.470个百分点；>=5%比例28.95% vs31.58%；t+1上午最低价低于14:05后最低价的比例68.42%。
- 159981：n=38；2.946% vs3.177%，差=-0.231个百分点；>=5%比例21.05% vs18.42%；上午最低价更低比例73.68%。
- 513100：n=38；2.456% vs2.238%，差=+0.218个百分点；>=5%比例均10.53%；上午最低价更低78.95%。
- 159509：n=38；4.096% vs3.771%，差=+0.325个百分点；>=5%比例36.84% vs34.21%；上午最低价更低81.58%。
- 511220：n=38；0.306% vs0.287%；均无>=5%事件；上午最低价更低47.37%。
- 其余10只同样完成配对；每只38个。**方向不一致**：501018和159981的14:05基准平均L5反而高于开盘基准，证实不能简单假定旧标签总是高估风险。对开盘价/14:05价的同分母比较与严格可执行路由过滤仍是下一步。

## 重现SQL
以下为本轮Supabase实际执行SQL（只读），不依赖未来数据作为特征；这里仅事后计算标签。

```sql
WITH sessions AS (
 SELECT symbol,trade_date,
 min(open) FILTER (WHERE bar_time::time >= time '09:30' AND bar_time::time < time '09:35') AS open_0930,
 max(close) FILTER (WHERE bar_time::time >= time '14:05' AND bar_time::time < time '14:06') AS close_1405,
 min(low) FILTER (WHERE bar_time::time >= time '09:30' AND bar_time::time < time '14:05') AS pre_low,
 min(low) FILTER (WHERE bar_time::time >= time '14:05') AS post_low,
 min(low) AS full_low, count(*) AS n
 FROM public.minute_bars
 WHERE interval_min=1 AND trade_date >= '2026-09-14'
 GROUP BY 1,2
), future AS (
 SELECT s.*,
 lead(open_0930,1) OVER w AS next_open,
 lead(close_1405,1) OVER w AS next_1405,
 lead(pre_low,1) OVER w AS next_pre_low,
 lead(post_low,1) OVER w AS next_post_low,
 lead(n,1) OVER w AS next_n,
 lead(full_low,1) OVER w AS low1,
 lead(full_low,2) OVER w AS low2,
 lead(full_low,3) OVER w AS low3,
 lead(full_low,4) OVER w AS low4,
 lead(full_low,5) OVER w AS low5
 FROM sessions s WINDOW w AS (PARTITION BY symbol ORDER BY trade_date)
), paired AS (
 SELECT *,
 greatest(0,1-least(next_post_low,low2,low3,low4,low5)/next_1405) AS loss_1405,
 greatest(0,1-least(low1,low2,low3,low4,low5)/next_open) AS loss_open,
 (next_pre_low < next_post_low) AS trough_pre_1405
 FROM future
 WHERE next_open>0 AND next_1405>0 AND next_pre_low>0
 AND next_post_low>0 AND low5>0 AND next_n>=200
)
SELECT symbol,count(*) AS paired_n,
 round(avg(loss_open)::numeric,5) AS mean_open_loss,
 round(avg(loss_1405)::numeric,5) AS mean_1405_loss,
 round(avg(loss_open-loss_1405)::numeric,5) AS mean_diff,
 round(avg(trough_pre_1405::int)::numeric,4) AS pre_lower_share,
 round(avg((loss_open>=0.05)::int)::numeric,4) AS open_5pct,
 round(avg((loss_1405>=0.05)::int)::numeric,4) AS after1405_5pct
FROM paired GROUP BY symbol ORDER BY paired_n DESC;
```

## 方法限制与下一步
1. 14:05 bar的close并非实际委托成交价，且当前仅检查t+1 1分钟bar数>=200；需要验证t+2至t+5分钟覆盖、分钟bar时间标记含义、交易时段和复权价格口径（分钟与日线hfq不直接混比）。
2. 单次最低价落在上午不代表5日总体最低价也落在上午。应固定同一14:05参考价，分别比较包含与剔除t+1 14:05前低点的L5，隔离标签泄漏效应。
3. 通过冻结V1/Void、防御、PIT溢价与09:31/14:05门槛后再做持仓条件配对；不能将本报告570条全ETF事件说成Top1实盘。
4. 既有季度滚动统一模型2026年Q90覆盖约84.8%，尾部失校准，尚无可部署连续撤出比例。撤仓研究不与买回择时联合优化。
