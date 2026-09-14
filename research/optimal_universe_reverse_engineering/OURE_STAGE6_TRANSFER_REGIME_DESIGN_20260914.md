# OURE Stage6 — Historical-Universe Transfer Regime Audit

Date: 2026-09-14
Status: preregistered before outcome inspection

## Question
Why does historical-Universe transfer fail in 2022–2024 but work much better in 2025–2026? Is there evidence that the *ordering* of candidate Universes became more persistent across adjacent half-years, rather than this being driven only by one lucky selected set?

## Frozen data and cadence
- Reuse Stage5 Jan/Jul decision dates, point-in-time pool rules, 63/126/252-day deterministic local-search library, frozen downstream OLS and cost semantics.
- Use only completed forward half-years for the primary regime comparison. 2026H2 partial is reported but excluded from the old/new regime medians.
- Old regime: decision dates 2022-01 through 2024-07 (six completed forward half-years).
- New regime: decision dates 2025-01 through 2026-01 (three completed forward half-years).
- No search parameter, lookback, or era boundary may be changed after outcome inspection.

## Primary transfer-persistence diagnostics
At each decision point, reconstruct the Stage5 union library generated using only past information. For every candidate Universe in that library, evaluate:
1. past-126d net log growth;
2. frozen robust 3/6/12 score from Stage5;
3. future half-year net log growth.

Report within-decision rank persistence:
- Spearman rank correlation: past-126d log growth vs future log growth;
- Spearman rank correlation: robust 3/6/12 score vs future log growth;
- future percentile rank of the past-6M winner within the same frozen library;
- future regret of past-6M winner relative to the future-best member of that same library.

This tests whether the entire Universe ordering transfers, not just whether one chosen Universe earns money.

## Relay-quality persistence diagnostic
For every library Universe, calculate the three already-frozen Stage5 mechanism metrics on past 126d and future half-year:
- coverage_efficiency;
- productive_switch_share;
- switch_counterfactual_gain_mean.
Convert each metric to within-library percentile ranks and average the three percentiles into a simple equal-weight relay-quality rank. Report past-vs-future relay-quality Spearman correlation. No fitted weights.

## Market-state diagnostics
For each future half-year, using the complete point-in-time risk pool, report:
- fraction of pool OLS-eligible per day, averaged across days;
- mean count of OLS-eligible assets;
- median Top1–Top2 OLS score gap on days with >=2 eligible assets;
- risk-leader switch rate;
- mean risk-leader tenure;
- active-leader share.
These are descriptive state variables only and are not used to redefine the transfer rules.

## Fix15 diagnostics
Evaluate Fix15 over the same future half-years and report:
- return;
- switch count / switch rate;
- mean Top1 tenure;
- coverage efficiency;
- productive-switch share;
- switch counterfactual-gain mean.
This separates raw return from structural stability. In particular, a period may have higher Fix15 return while still having shorter leader life / faster competition.

## Frozen interpretation gate
Call the transfer environment a materially different regime only if at least two of the following three comparisons show the preregistered direction:
1. median past6M→future rank correlation is <=0 in 2022–24 and >0 in 2025–26, with new-minus-old >=0.20;
2. median robust-score→future rank correlation is higher in 2025–26 by >=0.20;
3. median future percentile of the past6M winner is <0.50 in 2022–24 and >0.50 in 2025–26.

The small number of half-year periods means this gate is descriptive mechanism evidence, not a significance claim.

## Interpretation constraints
- If the transfer-rank gate passes but market-state diagnostics do not isolate one simple variable, freeze only the existence of a transfer-persistence regime shift; do not invent a causal explanation.
- If Fix15 earns more in 2025–26 but has shorter tenure / faster switching, explicitly distinguish higher raw opportunity from lower trend persistence.
- Do not use realized future return to choose or fit a regime classifier in this stage. A later X<=t classifier/proxy is allowed only after the state difference is frozen here.
