# OURE Stage8B — Opportunity Coverage K Frontier

Date: 2026-09-15
Status: preregistered before run

## Question
Under the frozen Stage8A Opportunity Coverage construction, is K=30 too large once Top1 competition is taken into account?

## Frozen construction
No Fix15 identity is used in selection. Fix15 remains benchmark only.

For each 126-session deployment block, use only the immediately preceding 378 sessions, split into 18 non-overlapping 21-session windows. For every point-in-time eligible ETF, run the frozen single-asset OLS engine in every window and convert window log-growth to cross-sectional percentile ranks. Build one greedy Opportunity order by repeatedly adding the ETF that maximizes Stage8A best-two window coverage; ties use mean historical rank and stable symbol order exactly as Stage8A. The K universe is the prefix of this single frozen greedy order.

Test K = 8, 10, 12, 15, 20, 25, 30. No K-specific tuning.

## Historical structural diagnostics at each selection date
For every K report:
- Stage8A best-two opportunity coverage across the 18 historical windows;
- marginal coverage gain versus the previous tested K;
- mean pairwise Spearman correlation of selected ETFs' 18-window rank profiles (higher = more synchronized opportunity states / more potential competition);
- number of distinct ETFs that are the best-ranked selected member across the 18 windows;
- effective winner count = exp(entropy of the 18 window-winner shares), a continuous diversity measure.

These are diagnostics only and do not alter selection.

## OOS economic diagnostics
Using the same frozen OLS target-state rule, same next-open holding convention and 6 bp per-side cost as Stage8A, report for 2021–2026 partial:
- annual and compounded return;
- maximum drawdown;
- turnover sides;
- mean Top1 tenure;
- number of switch events.

Primary interpretation is not `pick the K with the highest historical return`. Look for an elbow where additional K provides little historical opportunity-coverage gain while realized competition (shorter tenure / more turnover) continues to worsen. Any preferred K emerging here remains a historical research candidate, not fresh OOS proof.

## Controls
- Stage8A Opportunity30 must reproduce exactly at K=30.
- Current dynamic Robust30 and Fix15 are comparison benchmarks only; they do not influence Opportunity K selection.
- Amount/volume features are excluded from Stage8B so only K changes relative to Stage8A Opportunity30.
- No parameter or K grid changes after observing results.
