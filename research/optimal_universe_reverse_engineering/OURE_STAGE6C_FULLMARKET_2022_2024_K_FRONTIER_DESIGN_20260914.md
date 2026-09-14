# OURE Stage6C — Full-Market 2022–2024 K Frontier

Date: 2026-09-14
Status: preregistered before outcome inspection

## Question
Without using Fix15 membership, does the 2022–2024 market still favor a small static ETF Universe, or does a large-K relay solution (similar to the later K30/K60 elites) reappear?

This is a hindsight mechanism study. It is not a deployable rule and does not use future information for live decisions. The purpose is to identify the shape of the 2022–2024 static-Universe value frontier across K.

## Candidate pool
- Full ETF daily-bar universe from the database; cash proxy 511220 handled separately.
- No Fix15 inclusion/exclusion rule and no banned-symbol list based on prior OURE winners.
- Exclude leveraged/inverse instruments and instruments without daily-bar data.
- To avoid later-listing hindsight inside a static 2022 Universe, a risk ETF must have at least 240 finite closes in the 252 trading days immediately before the first 2022 evaluation date and a finite latest pre-period close.
- Current metadata is used only for leverage/inverse/data guards; this remains a documented survivorship-metadata limitation.

## Evaluation period and frozen downstream engine
- Signal/evaluation period: first available trading day in 2022 through 2024-12-31, with the same close(t) -> next-open execution semantics and side cost used in prior OURE stages.
- Cash 511220 competes as the cash signal exactly as in the frozen OLS engine.
- Objective: net log growth over 2022–2024.

## K range
Evaluate noncash K=1..60 (reported K including cash = 2..61). K is not selected in advance.

## Search protocol
The full-market subset lattice is too large for exact enumeration. Results must be called a `searched frontier`, never a global optimum.

1. Evaluate every eligible singleton.
2. Build deterministic greedy add-only paths from the top 12 singleton seeds. At every K retain each path's set and its objective value.
3. For every K, take the best set observed from the greedy paths and perform deterministic fixed-K 1-swap refinement against the top 120 singleton symbols, max 3 improving rounds.
4. For anchor K in {5,10,15,20,25,30,40,50,60}, run deterministic fixed-K stochastic swap search from the refined incumbent and from 4 additional seeded random starts; 4000 proposals per start. The objective and acceptance schedule are frozen before outcomes.
5. Save all discovered sets and the best found set at every K.

## Required diagnostics
For every best-by-K set report:
- total return / log growth / max drawdown;
- switch events / switch rate;
- mean and median Top1 tenure / <=2-day short-run share;
- coverage share, mean eligible count, mean competitors when covered, coverage efficiency;
- mean/max pair trend-eligible Jaccard;
- active leader count / effective leader count (HHI inverse);
- productive-switch share and switch counterfactual gain mean.

Also report same-K random controls (100 deterministic random Universes at anchor K) to determine whether any apparent K optimum is merely a search artifact.

## Interpretation gates
Primary question is the shape of the searched K frontier, not the identity of the winning ETFs.

- `small-K supported`: frontier reaches its broad plateau/maximum at K<=15 and adding many more members produces material deterioration.
- `large-K supported`: K>=25 materially exceeds all K<=15 solutions after search and diagnostics show relay-style productive replacement rather than mere extra competition.
- `mixed/plateau`: K range is broad/flat enough that nominal K is not identified; inspect persistence vs relay structure instead.

No thresholds, search widths, K anchors, or diagnostics may be changed after outcome inspection to rescue a preferred conclusion.

## Stage6B external replication
Separately assess whether high-value 2022–2024 full-market sets reproduce the frozen Fix15-lattice directions: longer leader tenure, lower switch rate, lower short-run share, lower pair trend overlap, lower simultaneous eligible competition, and higher coverage efficiency. Failure to reproduce means Stage6B remains a Fix15-specific result.