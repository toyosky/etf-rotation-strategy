# OURE Stage6B — 2022–2024 Good-Universe Traits

Date: 2026-09-14
Status: preregistered before outcome inspection

## Question
Even though Stage5/6 showed that past Universe rankings did not transfer well in 2022–2024, hindsight-good static Universes clearly existed. What structural/compositional traits distinguished them?

## Layer 1: exact Fix15 subset lattice
Use the exact 2^14 Fix15 noncash subset lattice, always retaining cash proxy 511220. Re-evaluate every subset only over execution dates 2022-01-01 through 2024-12-31 under the frozen daily OLS engine and transaction-cost semantics.

Primary comparisons control for nominal K:
- within-K return percentile;
- top-decile versus bottom-decile architecture;
- feature/return within-K rank association.

Frozen identity-free features are reused from Stage2 without adding features after outcome inspection:
coverage_share, mean_eligible_count, mean_competitors_when_covered, coverage_efficiency, selected_noncash_share, leader_switch_rate, mean_top1_tenure, median_top1_tenure, short_run_le2_share, leader_hhi, active_member_share, mean_pair_trend_jaccard, max_pair_trend_jaccard, mean_member_trend_episode_length.

Composition audit:
- top-1% and top-10% inclusion rate for each Fix15 member;
- exact best subset by K and exact global best within this Fix15 lattice;
- Banzhaf-style mean marginal log value over 2022–24.

## Contrast
Repeat the same architecture association for 2025-01-01 onward only as a contrast, not to redefine the 2022–24 traits.

## Interpretation
A 2022–24 trait is considered strong only if it has a material within-K association and top-vs-bottom separation, not merely because one champion contains it. Member identity is descriptive and cannot be promoted as a point-in-time rule.

This stage is hindsight/explanatory only. “Global best” means global only within the Fix15 14-risk subset lattice.