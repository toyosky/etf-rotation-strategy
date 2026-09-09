# Daily Resistance + Score Delta V1 — 2026-09-09

## Purpose

Test whether the daily Volume Profile resistance veto becomes more selective when it only vetoes a new Top1 that is both overhead-congested and no longer strengthening.

This is a research-only experiment. It does not modify `strategy/main.py`.

## Frozen V1 rule

On a new Top1 candidate B:

- Daily Volume Profile proxy: prior 120 trading days, historical `amount` distributed uniformly across each day's `[low, high]` range.
- `UpperShare`: historical amount in `[P, 1.05P]` / historical amount in `[0.95P, 1.05P]`.
- `ResistancePct252`: point-in-time percentile of current `UpperShare` versus that ETF's prior 252 profile observations.
- Minimum profile history: 60 observations.
- `ScoreDelta = score_t - score_{t-1}` for candidate B on `signal_date`.
- Veto only when `ResistancePct252 >= 75% AND ScoreDelta <= 0`.
- Otherwise follow the simplified C0 Top1 switch.
- `511220` remains the cash-proxy/keep-position state in this diagnostic harness.
- Transaction-cost approximation is unchanged from V0: 6 bp one-way, 12 bp for a full switch.
- No threshold search was performed.

## Important harness note

For this V1 comparison, Baseline / V0 / V1 were recomputed together in one common daily close-to-close diagnostic engine. Therefore these absolute returns differ slightly from the previously archived V0 report, whose implementation path produced Baseline +260.75% / +181.07% for the two main periods. The present report should be read primarily as a same-engine incremental comparison between Baseline, V0 and V1.

## Same-engine results

### 2021–2024

- Baseline: +255.89%
- V0 (resistance-only veto): +252.19%  (−3.71 pp vs baseline)
- V1 (resistance + ScoreDelta <= 0): +273.66%  (+17.77 pp vs baseline)
- V0 veto days: 22
- V1 veto days: 10

V1 removes the V0 damage in 2022 and 2023 and improves 2024 materially.

### 2025–2026

- Baseline: +184.57%
- V0: +198.23%  (+13.66 pp)
- V1: +193.02%  (+8.45 pp)
- V0 veto days: 14
- V1 veto days: 4

V1 retains a meaningful recent-period improvement, but less than V0 because it allows high-resistance candidates whose scores are still increasing.

## Year-by-year

- 2021: Baseline +19.69%, V0 +19.87%, V1 +19.87%  (+0.18 pp vs baseline)
- 2022: Baseline +41.27%, V0 +39.64%, V1 +41.27%  (0.00 pp)
- 2023: Baseline +26.43%, V0 +22.59%, V1 +26.43%  (0.00 pp)
- 2024: Baseline +66.47%, V0 +71.62%, V1 +74.52%  (+8.05 pp)
- 2025: Baseline +111.92%, V0 +108.95%, V1 +108.95%  (−2.97 pp)
- 2026 partial: Baseline +34.28%, V0 +42.73%, V1 +40.23%  (+5.95 pp)

The 2025 weakness is the same gold episode retained by V1 because the candidate had high resistance and negative ScoreDelta; on its actual Top1 tenure, vetoing it hurt.

## V1 independent divergence episodes

Seven independent holding-path divergences occurred.

1. 2021-03-22 — 164824 vs old 501018
   - Resistance percentile 75.7%
   - ScoreDelta −0.154
   - V1 alpha over the actual divergence segment: +0.15%

2. 2024-04-24 — 518880 vs old 161226
   - Resistance percentile 99.6%
   - ScoreDelta −1.142
   - V1 alpha: +0.46%

3. 2024-05-27 — 513920 vs old 159509
   - Resistance percentile 100.0%
   - ScoreDelta −1.138
   - V1 alpha: +1.44%

4. 2024-12-06 — 159529 vs old 513100
   - Resistance percentile 81.6%
   - ScoreDelta −0.717
   - V1 alpha: +2.87%

5. 2025-04-29 — 518880 vs old 164824
   - Resistance percentile 92.1%
   - ScoreDelta −0.826
   - V1 alpha: −1.40%

6. 2026-02-02 — 511380 vs old 518880
   - Resistance percentile 86.1%
   - ScoreDelta −0.554
   - V1 alpha: +2.67%

7. 2026-07-17 — 513290 vs old 159985
   - Resistance percentile 77.0%
   - ScoreDelta −0.415
   - V1 alpha: +1.72%

Six of seven independent V1 divergence episodes had positive relative contribution in this diagnostic harness.

## Interpretation

V1 is materially cleaner than a resistance-only veto.

The two signals have complementary roles:

- Volume Profile resistance asks: is the path immediately ahead congested?
- ScoreDelta asks: is the new leader still strengthening enough to push through that congestion?

This prevents V0 from vetoing several strong high-resistance leaders, notably the 2022 oil and 2023 soybean-meal switches whose ScoreDelta was positive.

The mechanism remains consistent with prior findings: overhead congestion primarily shortens trend continuation / causes stalling, rather than directly predicting a sharp drawdown.

## Limitations

- Only seven independent V1 divergence episodes occurred at the frozen 75% threshold.
- 2025 still has a negative case, so the rule is not universally beneficial.
- The daily Volume Profile is a coarse approximation because daily turnover is spread uniformly through each day's high-low range.
- This is not a fresh out-of-sample test; the broader historical period has already been inspected during related strategy research.
- Do not promote V1 directly into live trading from this result alone.

## Decision

Status: **KEEP AS A CANDIDATE; MOVE TO MINUTE-LEVEL PROFILE VALIDATION.**

The daily mechanism is strong enough to justify the next stage, but the next step should improve measurement quality rather than tune thresholds. Rebuild the same frozen V1 logic using minute-level Volume Profile on historical Top1 switch events, and check whether the separation between veto / allowed switches strengthens without changing the 75% resistance percentile or ScoreDelta <= 0 rule.
