# Stage22 Opportunity Coverage Audit — Findings (2026-09-13)

## Frozen question
Does Fixed15 materially under-cover point-in-time trend-eligible ETF opportunities that subsequently deliver stronger 20-trading-day continuation, consistently across eras and without depending on Cluster90?

## Verified run
- Workflow: `MUV Stage22 Opportunity Coverage Audit`
- Run ID: `34744172137`
- Conclusion: success

## Results
Across 67 month-end observations, Fixed15 had a mean 4.73 trend-eligible non-cash candidates, versus 120.28 for the full market and 61.04 for Cluster90.

Non-tradable coverage ceilings show a large and directionally stable gap:
- Full-market minus Fixed15 oracle-best mean: +8.35 percentage points over forward 20 trading days.
- Full-market minus Fixed15 oracle-top3 mean: +9.81 pp.
- Cluster90 minus Fixed15 oracle-best mean: +6.87 pp.
- Cluster90 minus Fixed15 oracle-top3 mean: +7.54 pp.
- The full-market oracle-best ETF was outside Fixed15 in 82.09% of months.

The conclusion does not reverse by era:
- 2021–24 full-market oracle-best gap: +7.32 pp; oracle-top3 gap: +8.21 pp.
- 2025–26 full-market oracle-best gap: +10.85 pp; oracle-top3 gap: +13.70 pp.
- Cluster90 remains directionally positive in both eras.

However, simply expanding the universe and letting the existing OLS score choose Top1 is harmful:
- Overall full-market score-Top1 minus Fixed15 score-Top1: -3.03 pp.
- 2021–24: -0.79 pp.
- 2025–26: -8.44 pp.
- Cluster90 score-Top1 is also worse than Fixed15 overall (-2.83 pp) and in both eras.

## Interpretation
Stage22 supports a structural opportunity-coverage gap but rejects the naive implication that a larger eligible universe should simply be exposed to the existing OLS ranking. The full market contains materially better ex-post continuation opportunities, yet unrestricted competition degrades realized score-Top1 selection, especially in 2025–26.

This shifts the problem from `coverage exists?` to `can a conservative point-in-time admission bridge expose useful outsiders without flooding OLS with harmful competition?`

The next admissible experiment should therefore remain a mechanism audit before any admission policy backtest. It should test whether the ex-post missed strong outsiders were already near the top of the point-in-time OLS score ordering. If they were, a conservative admission gate based on existing ranking proximity may be plausible. If they were usually deep in the ordering, current OLS score state is insufficient and a different admission-state representation is required.

No eligibility threshold, asset class, ETF subset, score cutoff, or policy was tuned from these results.