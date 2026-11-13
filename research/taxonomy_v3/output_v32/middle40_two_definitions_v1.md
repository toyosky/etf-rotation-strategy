# 2021—2026 β中间40%两种定义回测

研究用途，非PIT或完整资金净值回测。

{
  "contract": "ETF_MIDDLE40_TWO_DEFINITIONS_V1",
  "source_sha": "7a218407280309b475998668ccd3d232cfc67efda307f97db3f76fef7324b644",
  "caveats": [
    "Retrospective 2026 taxonomy not historical PIT",
    "10d overlapping event outcomes not investable NAV",
    "Cross-sectional rank among same-day eligible deduplicated candidates, min 5",
    "Historical percentile from previous 126-252 observed betas, today excluded",
    "Middle40=30th through 70th percentile inclusive",
    "Selection within middle40 uses highest beta; signal close then next open, exit 11th open, 6bp each side",
    "Missing eligible middle40 dates are not zero-return days; paired dates reported"
  ],
  "universe": {
    "days": 1299,
    "symbols": 440,
    "daily_candidates_mean": 43.01
  },
  "strategies": {
    "original_top1": {
      "all": {
        "n": 1299,
        "mean10_pct": 0.418,
        "median10_pct": -0.12,
        "p10_pct": -7.498,
        "win_pct": 47.73,
        "funds": 146
      },
      "by_year": {
        "2021": {
          "n": 240,
          "mean10_pct": -0.18,
          "median10_pct": -0.12,
          "p10_pct": -7.744,
          "win_pct": 46.67,
          "funds": 32
        },
        "2022": {
          "n": 189,
          "mean10_pct": -0.34,
          "median10_pct": -0.9,
          "p10_pct": -7.21,
          "win_pct": 42.86,
          "funds": 33
        },
        "2023": {
          "n": 215,
          "mean10_pct": 0.216,
          "median10_pct": -0.12,
          "p10_pct": -5.86,
          "win_pct": 49.3,
          "funds": 35
        },
        "2024": {
          "n": 236,
          "mean10_pct": 0.78,
          "median10_pct": -0.743,
          "p10_pct": -6.903,
          "win_pct": 44.07,
          "funds": 51
        },
        "2025": {
          "n": 229,
          "mean10_pct": 1.967,
          "median10_pct": 1.212,
          "p10_pct": -5.968,
          "win_pct": 57.64,
          "funds": 42
        },
        "2026": {
          "n": 190,
          "mean10_pct": -0.164,
          "median10_pct": -0.997,
          "p10_pct": -11.591,
          "win_pct": 44.74,
          "funds": 45
        }
      }
    },
    "cross_section_middle40": {
      "all": {
        "n": 1104,
        "mean10_pct": 0.076,
        "median10_pct": -0.12,
        "p10_pct": -6.413,
        "win_pct": 45.83,
        "funds": 275
      },
      "by_year": {
        "2021": {
          "n": 208,
          "mean10_pct": 1.12,
          "median10_pct": 0.335,
          "p10_pct": -4.885,
          "win_pct": 53.37,
          "funds": 73
        },
        "2022": {
          "n": 139,
          "mean10_pct": -0.9,
          "median10_pct": -1.323,
          "p10_pct": -7.226,
          "win_pct": 37.41,
          "funds": 77
        },
        "2023": {
          "n": 192,
          "mean10_pct": -0.481,
          "median10_pct": -0.899,
          "p10_pct": -5.746,
          "win_pct": 40.1,
          "funds": 88
        },
        "2024": {
          "n": 208,
          "mean10_pct": -0.095,
          "median10_pct": -0.832,
          "p10_pct": -6.377,
          "win_pct": 42.79,
          "funds": 102
        },
        "2025": {
          "n": 192,
          "mean10_pct": 1.69,
          "median10_pct": 1.276,
          "p10_pct": -3.86,
          "win_pct": 59.9,
          "funds": 125
        },
        "2026": {
          "n": 165,
          "mean10_pct": -1.429,
          "median10_pct": -1.226,
          "p10_pct": -8.551,
          "win_pct": 37.58,
          "funds": 104
        }
      }
    },
    "historical_middle40": {
      "all": {
        "n": 802,
        "mean10_pct": 0.0,
        "median10_pct": -0.12,
        "p10_pct": -5.954,
        "win_pct": 48.5,
        "funds": 152
      },
      "by_year": {
        "2021": {
          "n": 104,
          "mean10_pct": -0.354,
          "median10_pct": -0.819,
          "p10_pct": -5.654,
          "win_pct": 40.38,
          "funds": 25
        },
        "2022": {
          "n": 57,
          "mean10_pct": -1.601,
          "median10_pct": -1.705,
          "p10_pct": -5.919,
          "win_pct": 29.82,
          "funds": 16
        },
        "2023": {
          "n": 153,
          "mean10_pct": -0.472,
          "median10_pct": -0.432,
          "p10_pct": -5.763,
          "win_pct": 43.79,
          "funds": 44
        },
        "2024": {
          "n": 158,
          "mean10_pct": 0.864,
          "median10_pct": 1.052,
          "p10_pct": -4.186,
          "win_pct": 60.13,
          "funds": 24
        },
        "2025": {
          "n": 189,
          "mean10_pct": 0.876,
          "median10_pct": 1.106,
          "p10_pct": -5.958,
          "win_pct": 57.67,
          "funds": 66
        },
        "2026": {
          "n": 141,
          "mean10_pct": -0.72,
          "median10_pct": -0.839,
          "p10_pct": -7.008,
          "win_pct": 41.84,
          "funds": 52
        }
      }
    }
  },
  "paired_vs_top1": {
    "cross_section_middle40": {
      "matched_days": 1104,
      "changed_days": 1104,
      "delta_pp": -0.398,
      "month_block_ci95_pp": [
        -1.077,
        0.287
      ],
      "by_year": {
        "2021": {
          "n": 208,
          "delta_pp": 1.04
        },
        "2022": {
          "n": 139,
          "delta_pp": -0.572
        },
        "2023": {
          "n": 192,
          "delta_pp": -0.585
        },
        "2024": {
          "n": 208,
          "delta_pp": -0.429
        },
        "2025": {
          "n": 192,
          "delta_pp": -0.81
        },
        "2026": {
          "n": 165,
          "delta_pp": -1.326
        }
      }
    },
    "historical_middle40": {
      "matched_days": 802,
      "changed_days": 779,
      "delta_pp": -0.512,
      "month_block_ci95_pp": [
        -1.372,
        0.351
      ],
      "by_year": {
        "2021": {
          "n": 104,
          "delta_pp": -0.482
        },
        "2022": {
          "n": 57,
          "delta_pp": 0.325
        },
        "2023": {
          "n": 153,
          "delta_pp": -0.192
        },
        "2024": {
          "n": 158,
          "delta_pp": 1.146
        },
        "2025": {
          "n": 189,
          "delta_pp": -1.527
        },
        "2026": {
          "n": 141,
          "delta_pp": -1.719
        }
      }
    }
  },
  "as_of": "2026-11-12"
}
