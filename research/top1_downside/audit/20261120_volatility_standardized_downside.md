# 2026-11-20: 20-day volatility-standardized future downside diagnostic

**Executed SQL:** `../sql/volatility_standardized_downside.sql` against Supabase `gsyziuzezmmnvgdoazkg`, `public.daily_bars`. This follows, but does not rerun or replace, the earlier absolute-threshold volatility screen.

**Question:** Is the positive relation between vol20 and future 5-day >=5% absolute declines evidence of additional deterioration, or primarily the scale of the instrument's daily volatility?

**Design:** 2021–2026, all 19 available symbols, signal-day decline >=2%; vol20 = standard deviation of prior 20 sessions' log returns (signal day excluded); future excursion = min adjusted lows over t+1..t+5 relative to adjusted t+1 open. Vol20 bins: low <1.5%, middle 1.5–<3%, high >=3%. Outcome `P(MAE<=-2*vol20)` or `P(MAE<=-3*vol20)` compares like-for-like in *daily-volatility units* (not a five-day-volatility-normalized metric). Signal-close, true 14:05 execution, realized strategy holdings and true P&L are separate.

## Results (all events; overlapping)
| Period | vol20 bin | n | P(MAE<=-5%) | P(MAE<=-2 vol20) | P(MAE<=-3 vol20) | Mean MAE / vol20 |
|---|---|---:|---:|---:|---:|---:|
| 2021–24 | low | 327 | 7.65% | 33.94% | 19.27% | -1.72 |
| 2021–24 | mid | 320 | 13.75% | 21.88% | 10.63% | -1.30 |
| 2021–24 | high | 36 | 33.33% | 19.44% | 11.11% | -1.17 |
| 2025–26 | low | 161 | 11.80% | 37.27% | 24.84% | -2.10 |
| 2025–26 | mid | 223 | 17.94% | 27.35% | 13.45% | -1.48 |
| 2025–26 | high | 146 | 47.26% | 19.86% | 8.22% | -1.28 |

Total **1,213 events**: 683 in 2021–24 and 530 in 2025–26. **Key sign reversal:** fixed 5% loss is most common in the high-vol bin, but standardized 2x or 3x historical daily-vol losses are **most common in the low-vol bin**, both periods. The 2025–26 low vs high gap in P(MAE<=-2 vol20) is +17.41 percentage points, opposite to the absolute-loss ordering (11.80% vs 47.26%). This suggests the previous absolute-threshold relation is at least strongly confounded by the instrument's risk scale; it does NOT establish low volatility as a causal hazard or an OOS predictor.

**Important limitations:** vol20 is backward-looking and lagged, but MAE uses HFQ-adjusted OHLC; ratios can be affected by historical adjustments. Threshold in daily-vol units is not scaled by sqrt(5), and the event condition of -2% is itself volatility-dependent (low-vol bin experiences a larger standardized initial shock). This selection effect alone may explain part of the reversal. Repeated overlapping events, changing ETF composition, small 2021–24 high-vol n=36, and no independent uncertainty estimates preclude a statistical significance claim. This is an exploratory all-symbol screen, NOT held Top1 and NOT true 14:05 executable MAE.

**Next:** control standardized signal-day return `r1/vol20`, prior five-day standardized path, ETF/year, and market state; compare model OOS calibration of raw and standardized MAE using PIT reconstructed held Top1; do not make volatility sizing decisions based on fixed 5% label alone. No production changes. Full study incomplete.
