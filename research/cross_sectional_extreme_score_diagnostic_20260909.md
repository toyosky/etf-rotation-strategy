# Cross-sectional extreme OLS Score diagnostic — 2026-09-09

## Question

After monthly liquidity-first correlation deduplication (`Cluster90`), why does the same daily raw OLS Top1 rule behave very differently in 2021–2024 and 2025–2026?

This is a mechanism diagnostic only. No trading threshold or production rule is fitted.

## Design

- Universe: monthly frozen liquidity-first 120-day correlation representatives, rho >= 0.90 treated as duplicates.
- Daily eligibility/ranking: unchanged `trend_eligible`, then raw OLS Score descending.
- Daily diagnostics: Top1/Top2/Top3 Score, Top1/Top2 gap, Top1 relative to candidate median, raw OLS episode age, remaining raw/MA10 life, forward 5/10-day close return, Top1 survival for 1/3/5 trading days.
- Two samples:
  1. all daily Top1 observations;
  2. leadership-entry dates only, to reduce serial repetition.
- Quartiles are within-period descriptive quartiles, not optimized thresholds.

## Main result 1 — a large Top1 gap by itself is not the explanation

The monotonic relationship between `Top1 / Top2 Score` and future return is essentially absent in both periods.

On leadership-entry dates:

- 2021–2024 Spearman(`score_ratio12`, Top1 forward-10d) = +0.023.
- 2025–2026 Spearman = -0.065.

The highest gap quartile is not a robust good state in either period:

- 2021–2024 entry Q4: forward-10d = -0.83%.
- 2025–2026 entry Q4: forward-10d = -2.50%.

Therefore the earlier hypothesis “2021–24 extreme champions are fake, while 2025–26 extreme champions are reliable” is too simple and is rejected.

## Main result 2 — the whole top-ranked opportunity set changed

Average forward-10d return across all daily rank observations:

| Period | Top1 | Top2 | Top3 |
|---|---:|---:|---:|
| 2021–2024 | -0.06% | -0.15% | +0.11% |
| 2025–2026 | +0.81% | +1.17% | +2.16% |

This is the strongest result. In 2021–24 the top three OLS candidates as a group had approximately zero forward drift. In 2025–26 all three ranks had materially positive forward drift; Top3 even exceeded Top1.

So the 2025–26 benefit of expanding the universe is not evidence that raw Score rank ordering became especially accurate. It is more consistent with the expanded universe containing many more genuinely profitable trend opportunities.

## Main result 3 — Top1 ordering within the top cohort is weak

In 2025–26 Top2 and Top3 had higher average forward-10d returns than Top1. This means raw OLS Score is useful for locating the strong-trend cohort, but the exact `argmax(Score)` is not a clean forward-return ranking inside that cohort.

This is consistent with winner's-curse / extreme-value noise in a larger cross-section.

## Main result 4 — “old + very dominant” has an interesting but fragile regime interaction

Using the natural upper quartile of both trend age and Top1/Top2 Score ratio:

All daily observations:

- 2021–2024 (n=65): forward-10d -2.32%, Top1 minus Top2 -1.74pp, 5-day leadership survival 16.9%.
- 2025–2026 (n=27): forward-10d +2.70%, Top1 minus Top2 +3.88pp, 5-day leadership survival 59.3%.

However leadership-entry-only results are much weaker and the 2025–26 corner contains only 7 entries:

- 2021–2024 (n=19): forward-10d -1.52%.
- 2025–2026 (n=7): forward-10d -1.46%.

Therefore the spectacular all-day reversal is likely amplified by repeated observations during a small number of already-surviving long leadership runs. It is not yet a valid entry signal.

## Main result 5 — opportunity-set breadth also changed materially

Mean eligible Cluster90 candidate count:

- 2021–2024: 23.8.
- 2025–2026: 48.8.

The current full-market master universe also has more historically available ETFs in later years. Therefore the apparent period regime can be a mixture of:

1. market trend regime;
2. broader ETF product coverage / sector-theme opportunity set.

These must be separated before calling the effect a pure market-regime shift.

## Current interpretation

The data do **not** support adding a simple “Top1 must not be too extreme” veto.

A better description is:

`OLS identifies a strong-trend cohort -> exact Top1 ordering is noisy -> 2025–26 had a much richer positive-trend opportunity set than 2021–24.`

The next clean robustness test is to equalize opportunity-set breadth across periods (for example fixed breadth / common historical ETF cohort) and re-run Top1/Top2/Top3 forward-return diagnostics. That test can distinguish a genuine time-regime effect from expansion of ETF coverage.

## Reproducibility

Code: `research/cross_sectional_extreme_score_diagnostic.py`

Workflow: `.github/workflows/cross-sectional-extreme-score-diagnostic.yml`

Successful workflow run: `34329063781`.
