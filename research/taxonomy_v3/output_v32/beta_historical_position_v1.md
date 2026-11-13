# β历史位置与价格路径：独立审计V1

数据SHA: 7a218407280309b475998668ccd3d232cfc67efda307f97db3f76fef7324b644
历史分类非PIT；后10日收益重叠，非实际组合回测。

## 样本
{"top1_dates": 414, "with_percentile": 338}

## 分年历史β分位
{
  "2025:50-80": {
    "n": 18,
    "mean10_pct": -0.703,
    "p10_pct": -8.153,
    "win_pct": 55.56
  },
  "2025:80-90": {
    "n": 67,
    "mean10_pct": 0.112,
    "p10_pct": -7.997,
    "win_pct": 47.76
  },
  "2025:90-95": {
    "n": 50,
    "mean10_pct": 7.172,
    "p10_pct": -0.859,
    "win_pct": 80.0
  },
  "2025:95-100": {
    "n": 59,
    "mean10_pct": 0.247,
    "p10_pct": -6.373,
    "win_pct": 44.07
  },
  "2026:50-80": {
    "n": 23,
    "mean10_pct": 1.581,
    "p10_pct": -8.127,
    "win_pct": 52.17
  },
  "2026:80-90": {
    "n": 21,
    "mean10_pct": 0.059,
    "p10_pct": -13.958,
    "win_pct": 47.62
  },
  "2026:90-95": {
    "n": 24,
    "mean10_pct": 1.962,
    "p10_pct": -5.424,
    "win_pct": 62.5
  },
  "2026:95-100": {
    "n": 76,
    "mean10_pct": 0.539,
    "p10_pct": -9.702,
    "win_pct": 44.74
  }
}

## 价格路径条件和月份区块区间
{
  "pct95": {
    "n_high": 136,
    "n_low": 202,
    "high_mean_pct": 0.435,
    "low_mean_pct": 2.151,
    "difference_pp": -1.716,
    "month_block_ci95_pp": [
      -5.064,
      1.465
    ],
    "by_year": {
      "2025": {
        "n_high": 59,
        "n_low": 135,
        "high_mean_pct": 0.247,
        "low_mean_pct": 2.618,
        "difference_pp": -2.371,
        "month_block_ci95_pp": [
          -6.409,
          0.87
        ]
      },
      "2026": {
        "n_high": 77,
        "n_low": 67,
        "high_mean_pct": 0.579,
        "low_mean_pct": 1.21,
        "difference_pp": -0.631,
        "month_block_ci95_pp": [
          -4.144,
          4.436
        ]
      }
    }
  },
  "pct90": {
    "n_high": 209,
    "n_low": 129,
    "high_mean_pct": 2.207,
    "low_mean_pct": 0.252,
    "difference_pp": 1.955,
    "month_block_ci95_pp": [
      -1.035,
      4.847
    ],
    "by_year": {
      "2025": {
        "n_high": 109,
        "n_low": 85,
        "high_mean_pct": 3.423,
        "low_mean_pct": -0.06,
        "difference_pp": 3.484,
        "month_block_ci95_pp": [
          -1.023,
          7.541
        ]
      },
      "2026": {
        "n_high": 100,
        "n_low": 44,
        "high_mean_pct": 0.881,
        "low_mean_pct": 0.855,
        "difference_pp": 0.026,
        "month_block_ci95_pp": [
          -3.614,
          4.462
        ]
      }
    }
  },
  "burst5": {
    "n_high": 62,
    "n_low": 276,
    "high_mean_pct": 0.745,
    "low_mean_pct": 1.621,
    "difference_pp": -0.876,
    "month_block_ci95_pp": [
      -5.051,
      3.557
    ],
    "by_year": {
      "2025": {
        "n_high": 30,
        "n_low": 164,
        "high_mean_pct": 3.526,
        "low_mean_pct": 1.599,
        "difference_pp": 1.927,
        "month_block_ci95_pp": [
          -3.984,
          8.517
        ]
      },
      "2026": {
        "n_high": 32,
        "n_low": 112,
        "high_mean_pct": -1.861,
        "low_mean_pct": 1.654,
        "difference_pp": -3.515,
        "month_block_ci95_pp": [
          -8.851,
          1.254
        ]
      }
    }
  },
  "prior_deep": {
    "n_high": 1,
    "n_low": 337,
    "insufficient": true,
    "by_year": {
      "2025": {
        "n_high": 0,
        "n_low": 194,
        "insufficient": true
      },
      "2026": {
        "n_high": 1,
        "n_low": 143,
        "insufficient": true
      }
    }
  },
  "decelerating": {
    "n_high": 114,
    "n_low": 224,
    "high_mean_pct": 1.357,
    "low_mean_pct": 1.513,
    "difference_pp": -0.156,
    "month_block_ci95_pp": [
      -3.387,
      3.757
    ],
    "by_year": {
      "2025": {
        "n_high": 71,
        "n_low": 123,
        "high_mean_pct": 0.492,
        "low_mean_pct": 2.708,
        "difference_pp": -2.216,
        "month_block_ci95_pp": [
          -4.656,
          0.773
        ]
      },
      "2026": {
        "n_high": 43,
        "n_low": 101,
        "high_mean_pct": 2.786,
        "low_mean_pct": 0.058,
        "difference_pp": 2.727,
        "month_block_ci95_pp": [
          -4.739,
          9.656
        ]
      }
    }
  },
  "high_and_burst": {
    "n_high": 48,
    "n_low": 290,
    "high_mean_pct": 0.548,
    "low_mean_pct": 1.612,
    "difference_pp": -1.064,
    "month_block_ci95_pp": [
      -5.953,
      4.106
    ],
    "by_year": {
      "2025": {
        "n_high": 25,
        "n_low": 169,
        "high_mean_pct": 3.715,
        "low_mean_pct": 1.628,
        "difference_pp": 2.087,
        "month_block_ci95_pp": [
          -5.013,
          9.677
        ]
      },
      "2026": {
        "n_high": 23,
        "n_low": 121,
        "high_mean_pct": -2.894,
        "low_mean_pct": 1.589,
        "difference_pp": -4.483,
        "month_block_ci95_pp": [
          -8.904,
          -0.25
        ]
      }
    }
  },
  "high_and_decelerating": {
    "n_high": 55,
    "n_low": 283,
    "high_mean_pct": 1.809,
    "low_mean_pct": 1.393,
    "difference_pp": 0.416,
    "month_block_ci95_pp": [
      -3.135,
      5.156
    ],
    "by_year": {
      "2025": {
        "n_high": 26,
        "n_low": 168,
        "high_mean_pct": 1.771,
        "low_mean_pct": 1.916,
        "difference_pp": -0.145,
        "month_block_ci95_pp": [
          -2.567,
          2.273
        ]
      },
      "2026": {
        "n_high": 29,
        "n_low": 115,
        "high_mean_pct": 1.843,
        "low_mean_pct": 0.628,
        "difference_pp": 1.216,
        "month_block_ci95_pp": [
          -4.266,
          10.53
        ]
      }
    }
  },
  "high_and_deep": {
    "n_high": 0,
    "n_low": 338,
    "insufficient": true,
    "by_year": {
      "2025": {
        "n_high": 0,
        "n_low": 194,
        "insufficient": true
      },
      "2026": {
        "n_high": 0,
        "n_low": 144,
        "insufficient": true
      }
    }
  }
}

## Top1候选更换
{
  "pct95": {
    "matched_dates": 326,
    "changed_dates": 124,
    "mean_delta_pp": -0.194,
    "warning": "Only high-percentile Top1 dates eligible for flag; all candidate rows retained otherwise; candidate ban applied per date"
  },
  "high_and_burst": {
    "matched_dates": 337,
    "changed_dates": 47,
    "mean_delta_pp": 0.135,
    "warning": "Only high-percentile Top1 dates eligible for flag; all candidate rows retained otherwise; candidate ban applied per date"
  },
  "high_and_decelerating": {
    "matched_dates": 336,
    "changed_dates": 53,
    "mean_delta_pp": -0.07,
    "warning": "Only high-percentile Top1 dates eligible for flag; all candidate rows retained otherwise; candidate ban applied per date"
  },
  "high_and_deep": {
    "matched_dates": 338,
    "changed_dates": 0,
    "mean_delta_pp": 0.0,
    "warning": "Only high-percentile Top1 dates eligible for flag; all candidate rows retained otherwise; candidate ban applied per date"
  }
}
