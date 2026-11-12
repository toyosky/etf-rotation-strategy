# 重建扩散率：增量收益与稳健性审计 V2

快照 2026-11-11；研究期事件 2037，验证期事件 1474。
研究目的：检验扩散率是否提供超越市场涨跌和重建自身动量的未来净收益。

## 时间样本外检验（2025–2026）

| 变量 | 验证原始高-低 pp | 日期等权高-低 pp | 地区相对收益高-低 pp | 地区超额日等权 pp |
|---|---:|---:|---:|---:|
| rebuild_diffusion5_pct | +1.811 | +0.446 | +0.417 | -0.301 |
| diffusion_lag1_pct | +0.713 | -0.908 | +0.010 | -0.778 |
| diffusion_peer_ex_sector_pct | +1.683 | +0.458 | +0.392 | -0.148 |

## 重建扩散率详情

训练阈值：P25=11.6667%，P75=37.2549%。
- 2025: 事件平均高-低 1.0221 pp；地区超额 0.356 pp。
- 2026: 事件平均高-低 1.5771 pp；地区超额 0.5783 pp。

## 区块重抽样（同一个月视为整体）

- raw_event_net10: [-1.0713, 4.0767] pp；有效复制 2500。
- equal_day_net10: [-1.5176, 2.2742] pp；有效复制 2500。
- raw_event_excess: [-0.7732, 1.4515] pp；有效复制 2500。
- equal_day_excess: [-1.4782, 0.8082] pp；有效复制 2500。

## 控制过去价格与市场宽度的 OOS 岭回归

{
  "without_diffusion": {
    "n_train": 2037,
    "n_test": 1474,
    "rmse_pct": 5.5178,
    "mae_pct": 3.9381,
    "prediction_corr": -0.0579,
    "baseline_mean_prediction_rmse_pct": 5.3709,
    "year": {
      "2025": {
        "n": 813,
        "rmse_pct": 4.987
      },
      "2026": {
        "n": 661,
        "rmse_pct": 6.1077
      }
    },
    "diffusion_coef_pp_per_train_sd": null
  },
  "with_diffusion": {
    "n_train": 2037,
    "n_test": 1474,
    "rmse_pct": 5.492,
    "mae_pct": 3.9026,
    "prediction_corr": 0.0,
    "baseline_mean_prediction_rmse_pct": 5.3709,
    "year": {
      "2025": {
        "n": 813,
        "rmse_pct": 4.9454
      },
      "2026": {
        "n": 661,
        "rmse_pct": 6.0975
      }
    },
    "diffusion_coef_pp_per_train_sd": 0.6041
  },
  "rmse_gain_pct": 0.0258
}

## 稳健性与边界

- Current (2026) taxonomy is not historical point-in-time: all proxy-level event counts are retrospective.
- ETF archive omits historical delisted/closed funds; 200-bar and 3M amount filters bias cohorts.
- Signals share a MARKET date: effective N is dates/months rather than 1,474 independent ETF events.
- Market-relative benchmark is post-hoc contemporaneous median of observed regional proxy carriers, not an investable index.
- No historical premium series or intraday next-open veto; open-to-open fixed 10 session period only.
- Multiplicative testing of 3 related features, control strata and periods means a few positive cells could be chance.
- Current-date new signal contributes to 5-day diffusion; lag-one-day and sector-excluded diffusion are separate sensitivity tests.