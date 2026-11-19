# 全市场重建环境三指标 · 研究 V1

数据日期：2026-11-19；全市场原始代码：2003；
研究代理主题组：158；去重合格事件：3596。

## 三指标

- 过去 5 日重建扩散率：2.67%（4/150 组）
- 既往成熟事件 D5 存续率：58.62%（51/87）
- 行业相对强度：按日/地区分别计算 10 日主题组中位涨幅减地区中位涨幅，行业排序见 JSON。
- 附加观察：15 日正趋势宽度 12.00%。

## 样本外按研究期四分位阈值筛选（仅描述）

| 指标 | 高组 n / 10日平均净收益 | 低组 n / 10日平均净收益 | 高-低 pp |
|---|---|---|---:|
| rebuild_diffusion5_pct | 396 / +1.572% | 434 / -0.279% | +1.851 |
| persistence_d5_pct | 762 / +0.107% | 317 / +0.722% | -0.614 |
| sector_rs10_pp | 248 / -0.640% | 201 / -0.273% | -0.367 |

## 方法注意

- Current taxonomy not PIT before 2026-09; historical RS and proxy grouping are exploratory and must not be used for live decision backtests as validated factors.
- Current-listed ETF archive omits complete historical liquidations; ratio denominators only include archive-known survivors with at least 200 past bars.
- underlying_key coarsely combines different tracked indices; CHINA_EQUITY_OTHER omitted, so these are proxies not verified independent indices.
- Sector strength uses style_sector current label and representative ETF returns, not officially published index returns.
- Persistence uses matured episodes only; 20-session maturity window; no look-ahead from still-unmatured event outcomes.
- ETF premium, NAV, live order execution and factor stability by regime have not yet been verified.