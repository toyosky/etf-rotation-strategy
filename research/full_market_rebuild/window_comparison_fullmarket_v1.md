# 全市场 ETF 多周期重建回测 · V1

归档截止：2026-11-11；2003 只；1,439,205 行。
原始资格事件：106,940；用于固定持有期的回测记录：356,591。

## 验证期 2025–2026

| 方案 | 5日平均净收益 | 10日平均净收益 | 20日平均净收益 | 10日事件数 | 10日胜率 |
|---|---:|---:|---:|---:|---:|
| OLS10 | +0.216% | +0.114% | -0.303% | 16201 | 44.0% |
| OLS15 | +0.022% | -0.127% | -0.671% | 13978 | 45.1% |
| OLS20 | +0.044% | -0.285% | -0.838% | 12226 | 44.8% |
| OLS26 | -0.180% | -0.321% | -0.778% | 10875 | 44.5% |
| HYBRID15_26 | +0.069% | -0.030% | +0.213% | 7323 | 49.3% |

## 2025–2026 10日收益筛选敏感性

| 方案 | 全样本 | 流动性+D2样本 |
|---|---:|---:|
| OLS10 | +0.114% (n=16201) | +0.083% (n=12700) |
| OLS15 | -0.127% (n=13978) | -0.136% (n=10989) |
| OLS20 | -0.285% (n=12226) | -0.262% (n=9557) |
| OLS26 | -0.321% (n=10875) | -0.303% (n=8440) |
| HYBRID15_26 | -0.030% (n=7323) | -0.050% (n=5720) |

## 领先26日信号

[
  {
    "segment": "VALIDATION_2025_2026",
    "variant": "OLS10",
    "events": 17308,
    "later_26_pct": 68.65,
    "lead_median_sessions": 6.0,
    "lead_mean_sessions": 8.449924255175896
  },
  {
    "segment": "VALIDATION_2025_2026",
    "variant": "OLS15",
    "events": 14675,
    "later_26_pct": 76.57,
    "lead_median_sessions": 3.0,
    "lead_mean_sessions": 5.557889116312183
  },
  {
    "segment": "VALIDATION_2025_2026",
    "variant": "HYBRID15_26",
    "events": 7846,
    "later_26_pct": 85.6,
    "lead_median_sessions": 4.0,
    "lead_mean_sessions": 6.031119714115545
  },
  {
    "segment": "VALIDATION_2025_2026",
    "variant": "OLS20",
    "events": 12846,
    "later_26_pct": 83.93,
    "lead_median_sessions": 1.0,
    "lead_mean_sessions": 3.0616768688555
  }
]

## 按月份区块重抽样区间（百分点）

{
  "all": {
    "hybrid_minus_26": {
      "months": 22,
      "replicates": 1200,
      "diff_mean_pp": 0.291,
      "ci95_pp": [
        -0.754,
        1.061
      ]
    },
    "hybrid_minus_15": {
      "months": 22,
      "replicates": 1200,
      "diff_mean_pp": 0.0973,
      "ci95_pp": [
        -0.821,
        0.628
      ]
    }
  },
  "tradeable": {
    "hybrid_minus_26": {
      "months": 22,
      "replicates": 1200,
      "diff_mean_pp": 0.2522,
      "ci95_pp": [
        -0.874,
        1.042
      ]
    },
    "hybrid_minus_15": {
      "months": 22,
      "replicates": 1200,
      "diff_mean_pp": 0.0853,
      "ci95_pp": [
        -0.931,
        0.644
      ]
    }
  },
  "exclude_seam_2026": {
    "hybrid_minus_26": {
      "months": 19,
      "replicates": 1200,
      "diff_mean_pp": 0.0961,
      "ci95_pp": [
        -1.335,
        1.081
      ]
    },
    "hybrid_minus_15": {
      "months": 19,
      "replicates": 1200,
      "diff_mean_pp": 0.2425,
      "ci95_pp": [
        -1.045,
        0.949
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