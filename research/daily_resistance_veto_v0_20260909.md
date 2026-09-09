# Daily Resistance Veto V0 — 2026-09-09

## Question

Can the daily Volume Profile proxy be used as a minimal trading overlay that vetoes a new Top1 when the candidate faces unusually high overhead trading density?

## Scope

This is a deliberately simplified daily backtest intended to isolate the incremental value of the resistance veto. It does **not** reproduce the full intraday execution stack (09:31 gap checks, 14:00/14:05 gates, etc.) and it does **not** use C2. The baseline is the C0 daily Top1 path with the existing 511220 keep-position behavior.

- Source signals: `C0@20260906T_preregistered_primary_v1`
- Signal convention: `signal_date` is known at the prior close; `date` is the next execution day.
- Approximate transaction cost: 6 bp per side (0.05% commission + 0.01% slippage), therefore 12 bp for a switch.
- Daily return approximation: close-to-close while the selected holding is active.

## Resistance definition

For each candidate ETF on each signal date:

1. Look back up to 120 prior trading days.
2. Approximate each historical day's turnover as uniformly distributed across that day's `[low, high]` range.
3. Compute `UpperShare` = historical amount in `[P, P×1.05]` divided by historical amount in `[P×0.95, P×1.05]`, where `P` is the current close.
4. Convert `UpperShare` into a rolling, point-in-time percentile using up to the previous 252 daily profile observations for that ETF.
5. V0 veto condition: `ResistancePct252 >= 75%` with at least 60 historical profile observations.

No future information is used.

## V0 trading rule

- New Top1 is not high resistance -> switch normally.
- New Top1 is high resistance -> keep the current holding.
- Re-evaluate every day from scratch.
- 511220 keeps the current holding, matching the simplified baseline convention.

No Score-delta condition is used in V0.

## Main result

### 2021–2024

- Baseline cumulative return: **+260.75%**
- V0 cumulative return: **+254.84%**
- Difference: **-5.91 pp**
- Baseline switches: 139
- V0 switches: 133
- Veto days: 21

### 2025–2026

- Baseline cumulative return: **+181.07%**
- V0 cumulative return: **+194.56%**
- Difference: **+13.49 pp**
- Baseline switches: 81
- V0 switches: 75
- Veto days: 14

### Full 2021–2026

- Baseline cumulative return: **+913.98%**
- V0 cumulative return: **+945.23%**
- Difference: **+31.26 pp**
- Baseline switches: 220
- V0 switches: 208
- Veto days: 35
- Baseline max drawdown: **-32.92%**
- V0 max drawdown: **-33.85%**

Thus V0 improves total compounded return but slightly worsens maximum drawdown.

## Year-by-year result for the 75% rule

- 2021: baseline +22.05%, V0 +22.23% (`+0.18 pp`)
- 2022: baseline +38.89%, V0 +37.29% (`-1.60 pp`)
- 2023: baseline +25.67%, V0 +21.86% (`-3.81 pp`)
- 2024: baseline +69.34%, V0 +73.52% (`+4.18 pp`)
- 2025: baseline +115.30%, V0 +112.28% (`-3.02 pp`)
- 2026 partial: baseline +30.55%, V0 +38.76% (`+8.21 pp`)

The apparent 2025–2026 improvement is therefore driven primarily by 2026. V0 is not uniformly beneficial year by year.

## Threshold robustness (not parameter optimization)

A limited robustness check used 70%, 75%, and 80% rolling percentiles, all with at least 60 historical profile observations.

### 2021–2024

- 70%: -12.20 pp vs baseline
- 75%: -5.91 pp
- 80%: +0.47 pp

### 2025–2026

- 70%: +12.76 pp
- 75%: +13.49 pp
- 80%: +8.52 pp

All three thresholds improve 2025–2026 combined, while the earlier period becomes less damaged as the veto becomes more selective. This supports a high-resistance-tail interpretation but does not justify choosing the best threshold ex post.

## Independent veto episodes

Repeated veto days within the same Top1 tenure were collapsed into one episode.

### 2021–2024

- 8 veto episodes
- Average Top1-tenure intervals: 6.88
- Baseline return during those tenures: +2.29%
- V0 return during those tenures: +1.99%
- Average V0 alpha per veto tenure: **-0.30 pp**
- V0 wins / losses: 4 / 4

### 2025–2026

- 6 veto episodes
- Average Top1-tenure intervals: 2.50
- Baseline return during those tenures: +0.59%
- V0 return during those tenures: +1.37%
- Average V0 alpha per veto tenure: **+0.77 pp**
- V0 wins / losses: 4 / 2

This is consistent with the prior mechanism finding: resistance matters more when Top1 tenures are short.

## Important diagnostic correction

Forward 10-day candidate return is **not** the correct way to judge a veto because the baseline may stop holding the candidate long before day 10.

Example: 2025-04-29 gold (518880) was vetoed at a 92.1% resistance percentile. Gold's later 10-day return was negative, but it remained Top1 for only two execution days. During that short tenure gold initially outperformed the old holding, so the veto hurt the actual strategy despite the poor later 10-day return.

Therefore future diagnostics must compare realized returns over the candidate's actual Top1 tenure, not a fixed 10-day horizon alone.

## Interpretation

The daily resistance veto is **promising but not production-ready**.

Evidence in favor:

- It reduces turnover.
- It improves 2025–2026 combined across 70/75/80 percentile definitions.
- Its realized veto alpha is positive in the short-Top1 2025–2026 regime.
- The underlying resistance -> shorter price-trend-lifetime mechanism was already confirmed independently of Rank1.

Evidence against immediate deployment:

- It damages 2022, 2023, and 2025 under the 75% rule.
- Maximum drawdown is slightly worse.
- There are only 14 independent veto episodes in the 75% test, so sample size is small.
- High resistance alone sometimes blocks genuinely strong new leaders.

## Next test

Before moving to minute-level Volume Profile, test a conservative daily V1 that uses the previously identified independent signal:

`high resistance AND weak/non-positive new-Top1 Score delta -> veto`

The economic roles remain separate:

- Volume Profile: how difficult is the path ahead?
- Score delta: is the new leader still strengthening enough to justify crossing that resistance?

Use a natural sign threshold (`Score delta <= 0`) first rather than optimizing a numerical cutoff.

Formal strategy code remains unchanged.
