# D2 Forced Switch Mechanism Audit: Non-Void, 2021–2026

Research-only extension of the [formal non-Void transition extraction](baseline_nonvoid_switches.csv). No production rule changed.

## Scope / method

- 39 daily-bar-confirmed D2 cases among 45 prior `SWITCH_OLD_INVALID` non-Void events; exclude 5 missing-signal-bar events and 1 other invalidation.
- Bars: `public.daily_bars`, 14 fixed risk ETFs plus 511220 cash, through 2026-11-17. Event date T is signal-day **close**, not the following trade's executable open.
- Recomputed formal 26-observation weighted log-price OLS: 10-day weight half-life for fitting, squared weights in regression/R², 250 trading days annualization; Score = positive annualized slope × positive R².
- D2 rule: min of three trailing observed daily close-to-close returns < -3%. Eligibility additionally requires positive annualized return, R² and Score.
- Future day indices use the market trading calendar of 511220, not the old instrument's event count. A missing old instrument day yields missing point-in-time metrics rather than silently advancing to the next available old observation.
- Candidate leadership on T+3/T+5 means the old instrument is D2-eligible and highest-scoring across all 14 eligible risk ETFs **and its Score exceeds the cash comparator**. This is not identical to V1's retained incumbent or the Void-routed portfolio target.
- Classification is **descriptive ex post**, using observed closes and Score at T+3, not a causal proof nor an executable signal. Price/Score trends can differ because the 26-day window slides.
- Classification (mutually exclusive): `PRICE_SCORE_RECOVER`: T+3 price > T and Score > T; `PRICE_UP_SCORE_NOT`: T+3 price > T but Score <= T; `CONTINUED_DECLINE`: T+3 and T+5 price both below T; `FLAT_OR_MIXED`: remaining non-rising/mixed cases.
- Actual next return to old target means the **very next** formal strategy transition is to that old symbol. It does not prove actual executed trade or establish that D2 expiry alone causally drove the action.
- No historical point-in-time Premium10, intraday execution gate, historical slippage or broker fill validation.

## Summary

```json
{
  "total": 39,
  "types": {
    "CONTINUED_DECLINE": 11,
    "PRICE_UP_SCORE_NOT": 21,
    "FLAT_OR_MIXED": 4,
    "PRICE_SCORE_RECOVER": 3
  },
  "raw_top1_despite_d2": 30,
  "old_score_gt_new": 33,
  "price_up3": 24,
  "score_up3": 3,
  "clear3": 25,
  "clear5": 23,
  "clear_by5": 31,
  "ready_top1_day3": 13,
  "ready_top1_day5": 10,
  "top1_day3_with_price_gain": 10,
  "top1_day3_without_price_gain": 3,
  "continue3and5": 11,
  "reentries": 8,
  "reentries3": 5,
  "reentries5": 7,
  "reentries_score_up3": 2,
  "reentries_price_up3": 7,
  "reentries_d2_clear_at_next": 8,
  "old_f3_mean_pct": 0.6093076923076923,
  "old_f5_mean_pct": -1.1096410256410254,
  "old_new_f3_mean_excess_pp": -0.15494871794871812,
  "old_new_f5_mean_excess_pp": -2.4511282051282057,
  "by_year": {
    "2021": {
      "total": 3,
      "reentries": 0,
      "price_up_score_up": 0,
      "price_up_score_down": 1,
      "decline": 2
    },
    "2022": {
      "total": 5,
      "reentries": 2,
      "price_up_score_up": 1,
      "price_up_score_down": 2,
      "decline": 1
    },
    "2023": {
      "total": 1,
      "reentries": 1,
      "price_up_score_up": 0,
      "price_up_score_down": 1,
      "decline": 0
    },
    "2024": {
      "total": 11,
      "reentries": 3,
      "price_up_score_up": 0,
      "price_up_score_down": 7,
      "decline": 3
    },
    "2025": {
      "total": 7,
      "reentries": 1,
      "price_up_score_up": 0,
      "price_up_score_down": 2,
      "decline": 4
    },
    "2026": {
      "total": 12,
      "reentries": 1,
      "price_up_score_up": 2,
      "price_up_score_down": 8,
      "decline": 1
    }
  },
  "by_type": {
    "recovered": {
      "n": 3,
      "reentries": 2,
      "rawtop1": 2,
      "readyTop1day3": 2,
      "clear3": 3,
      "old_return3_mean_pct": 14.756,
      "old_return5_mean_pct": 7.485
    },
    "reboundWeakScore": {
      "n": 21,
      "reentries": 5,
      "rawtop1": 15,
      "readyTop1day3": 8,
      "clear3": 16,
      "old_return3_mean_pct": 3.034,
      "old_return5_mean_pct": 1.438
    },
    "continued": {
      "n": 11,
      "reentries": 0,
      "rawtop1": 10,
      "readyTop1day3": 2,
      "clear3": 3,
      "old_return3_mean_pct": -7.365,
      "old_return5_mean_pct": -8.99
    },
    "flat": {
      "n": 4,
      "reentries": 1,
      "rawtop1": 3,
      "readyTop1day3": 1,
      "clear3": 3,
      "old_return3_mean_pct": -0.802,
      "old_return5_mean_pct": 0.739
    }
  }
}
```

## Direct A→B→A reversal cases

| D2 Signal | Sold Asset | Price T→T+3 | Score Change T→T+3 | First D2 Clear | Formal Next Switch Back |
|---|---|---:|---:|---|---|
| 2022-02-25 | 159985 豆粕 | 0% | -4.42 | 2022-03-02 | 2022-03-04 (5日) |
| 2022-03-04 | 501018 原油 | 26.05% | 87.543 | 2022-03-09 | 2022-03-09 (3日) |
| 2023-08-03 | 501018 原油 | 2.46% | -0.176 | 2023-08-08 | 2023-08-08 (3日) |
| 2024-01-31 | 159509 纳指科技 | 3.42% | -0.756 | 2024-02-05 | 2024-02-06 (4日) |
| 2024-03-05 | 159509 纳指科技 | 4.38% | -0.215 | 2024-03-08 | 2024-03-08 (3日) |
| 2024-12-02 | 159529 标普消费 | 1.43% | -9.855 | 2024-12-05 | 2024-12-24 (16日) |
| 2025-09-04 | 159957 创业板 | 3.87% | -2.204 | 2025-09-09 | 2025-09-09 (3日) |
| 2026-02-11 | 501018 原油 | 7.41% | 0.457 | 2026-02-24 | 2026-02-24 (3日) |

Key diagnostic: price rises at T+3 in 7/8 direct reversals, but OLS Score rises in only 2/8. All 8 have cleared D2 by the actual next-signal return date. This pattern is consistent with **D2 eligibility resumption plus retained relative OLS leadership**, not general immediate OLS slope reconstruction.

## Individual events

[See the detailed 39-row audit CSV](d2_event_mechanism_39.csv).
