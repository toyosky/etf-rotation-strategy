# Stage8U — US Hierarchical Routing Pilot — 2026-09-17

## Purpose
Follow Stage8T/strict cross-region audit. Test whether a broad US health gate can improve Defensive/Void routing by opening a small US sub-exposure universe instead of buying the US broad index directly.

## Frozen pilot
- Events: 40 Defensive/Void first-entry events in 2023–2026 from the existing State Map event set.
- Formal OLS: 26 trading days, weighted log-price regression, half-life 10; Score = positive annualized slope × weighted R², otherwise 0.
- Historical availability: candidate requires >=365 calendar days since first available bar.
- Hurdle: 511220.
- Region gate: US broad 513500 Score > 511220 Score.
- If gate opens, sub-exposures compete: 513100 Nasdaq100, 159509 Nasdaq technology, 513290 Nasdaq biotech, 159529 S&P consumer. Highest eligible sub-exposure must also beat 511220; otherwise stay 511220.
- Comparator: broad-US route = 513500 whenever its Score beats 511220.
- This is an event-level 20-day pilot, not yet a full portfolio/backtest or friction-adjusted promotion test.

## Results
2023 (N=12): hierarchy excess +1.71%, broad-US +0.52%; hierarchy 20d win rate 41.7%; active 6; selected Nasdaq100 4, biotech 2.

2024 (N=13): hierarchy excess -1.19%, broad-US +1.35%; hierarchy win rate 23.1%; active 10; Nasdaq100 6, biotech 4.

2025 (N=8): hierarchy excess +1.87%, broad-US +0.40%; hierarchy win rate 25.0%; active 4; technology 1, biotech 2, consumer 1.

2026 (N=7): hierarchy excess +2.10%, broad-US +1.11%; hierarchy win rate 20.0% among events with available 20d forward data; active 1; technology 1.

## Interpretation
The US hierarchy changes the payoff distribution but does not solve robustness. It improves mean 20-day excess in 2023, 2025 and 2026, but fails badly in 2024 while the broad-US route was positive. Win rates remain low and medians are mostly zero because the gate frequently stays in 511220 and active trades are concentrated.

Therefore the hypothesis `healthy US broad market -> choose strongest US sub-exposure` is NOT promoted. The failure is informative: simple Top1 competition inside a healthy region can reintroduce the same competition/late-trend problem seen in large universes. A hierarchical router needs a second-layer admission rule based on sub-exposure health/remaining trend life, not merely the highest OLS Score.

## Next experiment
Before adding Japan/Europe sub-exposures, diagnose US active events: compare winning vs losing sub-exposure selections on Score gap to broad US, Score delta, R², residual/overextension, recent 3/5-day return, and resistance/volume features. Test a small predeclared admission gate and require improvement over both 511220 and broad-US route in walk-forward/OOS. Do not expand the second-layer universe until this gate shows transferable value.

Status: substantive narrowing; cross-region research continues. Simple two-level US Top1 hierarchy is rejected.