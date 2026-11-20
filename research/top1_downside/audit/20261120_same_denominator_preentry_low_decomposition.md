# 2026-11-20 14:05 标签偏差分解：固定同一参考价格

状态：实际执行的 Supabase 只读 SQL；不是 Top1 可执行持仓、不是新的 OOS 预测或组合回测。延续上一轮 570 条分钟线配对审计；先核对 PREREGISTRATION 和季度滚动报告。

## 研究问题与方法
上一轮比较 t+1 开盘基准与 t+1 14:05 基准，混合了两个效应：入场价格改变，以及 t+1 14:05 之前不可持有的低点。此次统一分母为 t+1 14:05 分钟收盘价：
- full_same = max(0,1-min(t+1整日low,t+2..t+5整日low)/t+1 14:05价)
- after_same = max(0,1-min(t+1 14:05以后low,t+2..t+5整日low)/t+1 14:05价)
- contamination = full_same-after_same >=0；这是错误纳入入场前低点对回撤标签的影响。
- original_difference = 开盘价基准L5-after_same；价格变化与入场前低点效应混合。

2026-09-14以来 15 个代码×各38个可观察信号日，570条重叠样本。仅要求t+1分钟数>=200，未来四天分钟完整性未审计；14:05价非真实成交价。

## 本轮实际SQL结果（单位：平均损失%，差值百分点）
| ETF | n | full_same | after_same | contamination | 开盘基准减after_same | 受影响日比例 |
|---|---:|---:|---:|---:|---:|---:|
| 501018 |38|4.025|3.863|0.162|-0.470|26.32%|
| 159981 |38|3.306|3.177|0.129|-0.231|21.05%|
| 513100 |38|2.423|2.238|0.185|+0.218|31.58%|
| 159509 |38|4.237|3.771|0.467|+0.325|31.58%|
| 511220 |38|0.315|0.287|0.028|+0.019|26.32%|
| 159529 |38|1.697|1.542|0.155|-0.061|26.32%|
| 159934 |38|2.593|2.523|0.070|+0.067|7.89%|
| 159957 |38|6.100|5.939|0.161|+0.093|13.16%|
| 159985 |38|2.052|2.022|0.030|-0.085|5.26%|
| 161226 |38|5.078|4.936|0.142|-0.029|7.89%|
| 164824 |38|1.538|1.349|0.189|+0.052|23.68%|
| 511380 |38|2.604|2.433|0.170|+0.106|21.05%|
| 513290 |38|2.878|2.728|0.150|-0.171|23.68%|
| 513500 |38|2.213|2.101|0.112|-0.018|23.68%|
| 513530 |38|1.528|1.433|0.095|-0.055|26.32%|

解释：固定同一14:05参考价后，入场前低点纳入的损失偏差始终非负；但开盘参考价对比14:05可交易区间，差异可正可负。501018平均标签污染0.162pp，不足以解释其原开盘与14:05标签-0.470pp的反向差异。159509标签污染0.467pp，高于原开盘与14:05差异0.325pp，价格效应抵消部分污染。不要将“上午最低价低于下午最低价”的日数误当成“未来5日MAE被污染”的日数。

## 实际执行的可复现 SQL
```sql
WITH s AS (
 SELECT symbol,trade_date,
 min(open) FILTER (WHERE bar_time::time >= time '09:30' AND bar_time::time < time '09:35') op,
 max(close) FILTER (WHERE bar_time::time >= time '14:05' AND bar_time::time < time '14:06') p14,
 min(low) FILTER (WHERE bar_time::time < time '14:05') pre,
 min(low) FILTER (WHERE bar_time::time >= time '14:05') post,
 min(low) ful,count(*) n
 FROM public.minute_bars WHERE interval_min=1 AND trade_date>='2026-09-14'
 GROUP BY 1,2
), f AS (
 SELECT *,lead(op) OVER w eo,lead(p14) OVER w e14,
 lead(pre) OVER w pre1,lead(post) OVER w post1,lead(n) OVER w n1,
 lead(ful,1) OVER w l1,lead(ful,2) OVER w l2,
 lead(ful,3) OVER w l3,lead(ful,4) OVER w l4,lead(ful,5) OVER w l5
 FROM s WINDOW w AS (PARTITION BY symbol ORDER BY trade_date)
), x AS (
 SELECT symbol,
 greatest(0,1-least(l1,l2,l3,l4,l5)/e14) full_same,
 greatest(0,1-least(post1,l2,l3,l4,l5)/e14) after_same,
 greatest(0,1-least(l1,l2,l3,l4,l5)/eo) open_original
 FROM f WHERE e14>0 AND eo>0 AND pre1>0 AND post1>0 AND l5>0 AND n1>=200
)
SELECT symbol,count(*) n,
 round((avg(full_same)*100)::numeric,3) full_pct,
 round((avg(after_same)*100)::numeric,3) after_pct,
 round((avg(full_same-after_same)*100)::numeric,3) contamination_pp,
 round((avg(open_original-after_same)*100)::numeric,3) total_difference_pp,
 round((avg((full_same>after_same)::int)*100)::numeric,2) affected_pct
FROM x GROUP BY symbol ORDER BY symbol;
```

## 限制与下一步
- 570条不是独立事件，也没有经过冻结V1/Void/防御/PIT溢价和真实成交验证；不得用于证明连续撤出收益。
- 现有季度滚动OOS预测使用开盘日线标签，2026年Q90覆盖84.80%，不能拿14:05标签诊断冒充模型重新校准。
- 下一步验证分钟时间戳及t+2..t+5覆盖、价格复权与LOF溢价；将同一口径应用于冻结可持仓路由后重新训练OOS。
- 研究仍为统一上涨过热+下跌延续预测，正常风险持仓100%；退出连续且仅研究撤出，5日机械归位仅为归因约定。生产策略未改。
