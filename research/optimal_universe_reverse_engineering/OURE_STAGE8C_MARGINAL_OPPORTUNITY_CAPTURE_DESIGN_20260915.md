# OURE Stage8C — Marginal Opportunity Capture redesign

Date: 2026-09-15
Status: preregistered before run

## Question
Is the Stage8A Opportunity Coverage definition itself too weak because it uses fixed 21-session windows, cross-sectional percentile ranks, and standalone ETF performance rather than the ETF's actual marginal contribution to the frozen OLS system?

## Point-in-time repair
`gross[t] = open[t+2]/open[t+1]-1`. Therefore the last historical signal immediately before a Universe decision can require a post-decision open. Stage8C excludes any training signal whose holding return is not fully realized by the decision date. With the same 378-session lookback start, the usable realized-history signal path is 377 sessions. This repair is applied to BOTH the old Opportunity comparator and the new algorithm.

## New algorithm: Marginal Opportunity Capture (MOC)
No Fix15 identity, future target-block returns, amount/volume, or post-hoc thresholds are used in selection.

At each 126-session Universe decision date:
1. Build the same point-in-time common eligible ETF pool.
2. Use the immediately preceding fully-realized historical signal path.
3. Evaluate opportunity at three frozen horizons: 21, 63 and 126 sessions, with rolling starts every 7 sessions. Each horizon family receives equal weight.
4. For every historical window, define available opportunity as the best positive net log-growth produced by any SINGLE eligible ETF under the same frozen OLS/cash rule and 6 bp per-side cost.
5. For a candidate Universe U, run the actual frozen OLS Top1 path for U. In every window, captured opportunity is clipped to [0, available opportunity]. Larger historical opportunities therefore carry more weight, while negative/no-opportunity windows do not create a reward.
6. MOC(U) is the mean, across the three horizon families, of total captured opportunity divided by total available opportunity.
7. Build one greedy order. At each step add the ETF maximizing MOC(U + ETF). Because MOC evaluates the actual OLS path with 6 bp costs, redundant ETFs that only create unnecessary rank switching can reduce or fail to improve the objective.

This directly tests marginal system value rather than standalone ETF rank.

## Frozen comparisons
Evaluate only K=15 and K=30:
- OLD_SAFE_K15 / OLD_SAFE_K30: Stage8A-style best-two percentile-rank coverage, recomputed with the same point-in-time history repair.
- MOC_K15 / MOC_K30: new algorithm.
- FIX15_BENCHMARK: benchmark only; never used in selection.

Use the same OOS 126-session deployment calendar, frozen OLS target rule, next-open accounting and 6 bp per-side cost. Report 2021–2026 partial annual return, full compounded return, MDD, turnover, switch events and Top1 tenure.

## Interpretation
Primary question is whether MOC improves the opportunity-selection architecture, not whether it beats Fix15 on this historical sample. Evidence in favor requires improvement versus the repaired old Opportunity comparator on economically meaningful OOS dimensions without merely exploding turnover or drawdown. K15-vs-K30 capture ratios are structural diagnostics only; do not tune horizons, stride, cost, K, or capture formula after observing this run.
