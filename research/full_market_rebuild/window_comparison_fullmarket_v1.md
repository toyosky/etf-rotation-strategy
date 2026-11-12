# 全市场 ETF 多周期重建回测 · V1

归档截止：2026-11-11；2003 只；1,439,205 行。
原始资格事件：104,921；用于固定持有期的回测记录：350,223。

## 验证期 2025–2026

| 方案 | 5日平均净收益 | 10日平均净收益 | 20日平均净收益 | 10日事件数 | 10日胜率 |
|---|---:|---:|---:|---:|---:|
| OLS10 | +0.220% | +0.117% | -0.306% | 15992 | 44.5% |
| OLS15 | +0.025% | -0.127% | -0.679% | 13782 | 45.8% |
| OLS20 | +0.046% | -0.287% | -0.849% | 12028 | 45.6% |
| OLS26 | -0.181% | -0.324% | -0.788% | 10704 | 45.2% |
| HYBRID15_26 | +0.070% | -0.029% | +0.214% | 7281 | 49.6% |

## 2025–2026 10日收益筛选敏感性

| 方案 | 全样本 | 流动性+D2样本 |
|---|---:|---:|
| OLS10 | +0.117% (n=15992) | +0.085% (n=12552) |
| OLS15 | -0.127% (n=13782) | -0.136% (n=10854) |
| OLS20 | -0.287% (n=12028) | -0.264% (n=9418) |
| OLS26 | -0.324% (n=10704) | -0.305% (n=8321) |
| HYBRID15_26 | -0.029% (n=7281) | -0.050% (n=5698) |

## 领先26日信号

[
  {
    "segment": "VALIDATION_2025_2026",
    "variant": "OLS10",
    "events": 17088,
    "later_26_pct": 68.59,
    "lead_median_sessions": 6.0,
    "lead_mean_sessions": 8.466683730057163
  },
  {
    "segment": "VALIDATION_2025_2026",
    "variant": "OLS15",
    "events": 14466,
    "later_26_pct": 76.51,
    "lead_median_sessions": 3.0,
    "lead_mean_sessions": 5.555565594506686
  },
  {
    "segment": "VALIDATION_2025_2026",
    "variant": "HYBRID15_26",
    "events": 7792,
    "later_26_pct": 85.69,
    "lead_median_sessions": 4.0,
    "lead_mean_sessions": 6.012280964505017
  },
  {
    "segment": "VALIDATION_2025_2026",
    "variant": "OLS20",
    "events": 12633,
    "later_26_pct": 83.95,
    "lead_median_sessions": 1.0,
    "lead_mean_sessions": 3.049028851593438
  }
]

## 按月份区块重抽样区间（百分点）

{
  "all": {
    "hybrid_minus_26": {
      "months": 22,
      "replicates": 1200,
      "diff_mean_pp": 0.2946,
      "ci95_pp": [
        -0.75,
        1.072
      ]
    },
    "hybrid_minus_15": {
      "months": 22,
      "replicates": 1200,
      "diff_mean_pp": 0.0978,
      "ci95_pp": [
        -0.821,
        0.633
      ]
    }
  },
  "tradeable": {
    "hybrid_minus_26": {
      "months": 22,
      "replicates": 1200,
      "diff_mean_pp": 0.2551,
      "ci95_pp": [
        -0.868,
        1.044
      ]
    },
    "hybrid_minus_15": {
      "months": 22,
      "replicates": 1200,
      "diff_mean_pp": 0.0857,
      "ci95_pp": [
        -0.934,
        0.642
      ]
    }
  },
  "exclude_seam_2026": {
    "hybrid_minus_26": {
      "months": 19,
      "replicates": 1200,
      "diff_mean_pp": 0.0956,
      "ci95_pp": [
        -1.348,
        1.085
      ]
    },
    "hybrid_minus_15": {
      "months": 19,
      "replicates": 1200,
      "diff_mean_pp": 0.2444,
      "ci95_pp": [
        -1.045,
        0.95
      ]
    }
  }
}

## 主要风险

- Snapshot source uses currently known instruments; incomplete delisted funds cause survivorship bias
- Most index labels are current snapshots, not historical PIT; dedup by current label is only a sensitivity
- Historical NAV premium, LOF tradability, intraday opening constraints and short-selling are not modeled
- OHLC adjusted-source splice is not independently checked for every symbol; 2026 June-Aug sensitivity included
- Event averages are not capital-weighted portfolio equity curves; strategies have different signal counts
- Calendar-trading-day overlap and simultaneous ETF correlation reduce effective independent sample size
- The source archive is an already-existing private GitHub Release; not a freshly fetched delisted census