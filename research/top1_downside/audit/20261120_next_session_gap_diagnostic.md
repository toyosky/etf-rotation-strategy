# Next-session gap audit — 2026-11-20

Read-only query: `sql/next_session_gap_diagnostic.sql`. Fixed 19-symbol Supabase daily-bar universe, 2021–2026, **not** executable Top1 positions. A down-day event is adjusted close / prior adjusted close - 1 <= -2%. Gap is next-session adjusted open / signal-day adjusted close - 1. Overlapping observations, survivor/selection effects and adjustment artifacts remain.

| Year | Events | Gap <= -3% | Gap >= +3% | Mean abs gap |
|---|---:|---:|---:|---:|
| 2021 | 158 | 3.16% | 0.63% | 0.919% |
| 2022 | 225 | 1.78% | 2.22% | 1.018% |
| 2023 | 96 | 0.00% | 0.00% | 0.682% |
| 2024 | 205 | 5.37% | 3.90% | 1.014% |
| 2025 | 166 | 5.42% | 5.42% | 1.516% |
| 2026 | 366 | 9.84% | 7.10% | 1.702% |

Largest negative gaps by year: -9.76%, -9.63%, -2.59%, -5.41%, -10.27%, -10.18%. **Interpretation:** open-price proxy is not a trivial substitution for signal close; particularly 2025–2026 have materially larger gaps and more extreme tails. But HFQ-adjusted open/close can produce artificial gaps across corporate actions, so this is not an empirical estimate of *tradable* overnight gap risk until unadjusted prices/corporate actions are reconciled.

This diagnostic is an **execution-label audit**, not a new predictive signal: next-session gap is future information relative to close t and cannot enter X_t. The current strategy may execute at 14:05 with a 09:31 gate; neither signal close nor next open is a universal valid executable fill. Do not infer a position sizing benefit from this screen.

No primary Top1 holding reconstruction, walk-forward five-block model or dynamic sizing test is completed. Existing premium-history PIT and historical intraday coverage limitations persist. Research continues; production untouched.
