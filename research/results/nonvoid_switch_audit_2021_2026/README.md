# Non-Void switch extraction, 2021–2026

- Market data: Supabase public.daily_bars through 2026-11-17; all 16 ETF symbols
- Current strategy: 14-risk universe (incl 512800 bank), 26-day weighted OLS (half-life 10), recent 3-day -3% exclusion, V1 ResistancePct252 >= 75 AND ScoreDelta <=0 veto, 511220 comparator, Void freeze + deepening/invalid route.
- Normal (non-Void) state: anything except DEFENSIVE_VOID, requiring a valid quadrant. StateMap breadth of the fixed 14, gap rolling-252 percentile (inclusive current), both thresholds 50.
- Strict consecutive next change: the first subsequent change anywhere in the path, including Void. Repeat_n = a subsequent change within N trading days of the signal, not necessarily a reversal. Reversal_n = that next change restores the immediately previous target. Only rows with N future trading days available enter the N-day denominator (observed_n).
- Net holding return: next session open entry to the open following the next change signal, minus 6 bp entry and 6 bp exit, no slippage or premium/NAV protection. Rates are unweighted per switch and may be affected by fund-specific price adjustments. Total portfolio four-side turnover on two consecutive risk-to-risk switches is higher than a single-position entry/exit.
- Baseline CSV: actual frozen-Void route model target changes on non-Void signal dates; it applies the recorded 2026-09-29 model execution override (not a broker-fill confirmation).
- V1 CSV: V1 shadow target changes on non-Void signal dates, ignoring Void restrictions. Differences are expected after Void exits.
- Historical fund premiums and 09:31 / 14:05 intraday execution vetoes are not PIT-validated. Therefore signals/model returns are not broker transactions.
- Baseline 2026-10-12/15/16 and 2026-11-17 matched live-forward; map 2026-10-12/15/16 gap/breadth matched stored state-map.

## Baseline non-Void transitions

```json
{
  "total": 196,
  "per_year": {
    "2021": {
      "total": 20,
      "risk_to_risk": 18,
      "repeat_1": 2,
      "repeat_3": 3,
      "repeat_5": 8
    },
    "2022": {
      "total": 26,
      "risk_to_risk": 22,
      "repeat_1": 7,
      "repeat_3": 9,
      "repeat_5": 11
    },
    "2023": {
      "total": 24,
      "risk_to_risk": 22,
      "repeat_1": 3,
      "repeat_3": 5,
      "repeat_5": 10
    },
    "2024": {
      "total": 42,
      "risk_to_risk": 40,
      "repeat_1": 8,
      "repeat_3": 23,
      "repeat_5": 28
    },
    "2025": {
      "total": 41,
      "risk_to_risk": 39,
      "repeat_1": 6,
      "repeat_3": 19,
      "repeat_5": 22
    },
    "2026": {
      "total": 43,
      "risk_to_risk": 41,
      "repeat_1": 14,
      "repeat_3": 30,
      "repeat_5": 32
    }
  },
  "risk_to_risk": 182,
  "by_reason": {
    "SWITCH_NORMAL": 107,
    "HOLD": 39,
    "SWITCH_OLD_INVALID": 45,
    "EXIT_CASH": 3,
    "ENTER": 1,
    "VETO_V1": 1
  },
  "mean_short_net": null,
  "h1": {
    "observed": 196,
    "repeat": 40,
    "repeat_pct": 20.408163265306122,
    "direct_reversal": 13,
    "short_return_n": 37,
    "mean_short_net_pct": -0.9257186145430495,
    "short_loss_rate_pct": 67.56756756756756
  },
  "h3": {
    "observed": 196,
    "repeat": 89,
    "repeat_pct": 45.40816326530612,
    "direct_reversal": 27,
    "short_return_n": 86,
    "mean_short_net_pct": -0.2667656828313866,
    "short_loss_rate_pct": 61.627906976744185
  },
  "h5": {
    "observed": 196,
    "repeat": 111,
    "repeat_pct": 56.63265306122449,
    "direct_reversal": 34,
    "short_return_n": 107,
    "mean_short_net_pct": -0.24485136415617598,
    "short_loss_rate_pct": 61.6822429906542
  }
}
```

## V1-only non-Void transitions

```json
{
  "total": 157,
  "per_year": {
    "2021": {
      "total": 12,
      "risk_to_risk": 12,
      "repeat_1": 1,
      "repeat_3": 2,
      "repeat_5": 6
    },
    "2022": {
      "total": 19,
      "risk_to_risk": 18,
      "repeat_1": 7,
      "repeat_3": 9,
      "repeat_5": 11
    },
    "2023": {
      "total": 13,
      "risk_to_risk": 13,
      "repeat_1": 1,
      "repeat_3": 4,
      "repeat_5": 5
    },
    "2024": {
      "total": 36,
      "risk_to_risk": 36,
      "repeat_1": 8,
      "repeat_3": 24,
      "repeat_5": 28
    },
    "2025": {
      "total": 38,
      "risk_to_risk": 37,
      "repeat_1": 8,
      "repeat_3": 19,
      "repeat_5": 21
    },
    "2026": {
      "total": 39,
      "risk_to_risk": 37,
      "repeat_1": 13,
      "repeat_3": 29,
      "repeat_5": 33
    }
  },
  "risk_to_risk": 153,
  "by_reason": {
    "SWITCH_NORMAL": 108,
    "SWITCH_OLD_INVALID": 45,
    "EXIT_CASH": 3,
    "ENTER": 1
  },
  "mean_short_net": null,
  "h1": {
    "observed": 157,
    "repeat": 38,
    "repeat_pct": 24.203821656050955,
    "direct_reversal": 14,
    "short_return_n": 35,
    "mean_short_net_pct": -1.35986927460113,
    "short_loss_rate_pct": 71.42857142857143
  },
  "h3": {
    "observed": 157,
    "repeat": 87,
    "repeat_pct": 55.4140127388535,
    "direct_reversal": 29,
    "short_return_n": 83,
    "mean_short_net_pct": -0.3066694969943998,
    "short_loss_rate_pct": 62.65060240963855
  },
  "h5": {
    "observed": 157,
    "repeat": 104,
    "repeat_pct": 66.24203821656052,
    "direct_reversal": 33,
    "short_return_n": 100,
    "mean_short_net_pct": -0.3268671698780541,
    "short_loss_rate_pct": 64
  }
}
```
