# OURE Stage3 — Exposure-Disjoint Static Universe Search

Date: 2026-09-14
Status: preregistered before viewing Stage3 returns
Parent: OURE Stage1–2

## Question

Can the frozen OLS engine produce a static Universe with value comparable to or higher than the Fix15-internal oracle while excluding the broad economic exposures represented by the Stage1 best K7?

This is a hindsight mechanism-search stage. It is not executable and does not claim that the Universe could have been known at the time.

## Frozen downstream engine

Reuse the same Stage1 semantics:

- same daily bars and `build_features`;
- same trend-eligible OLS score;
- signal close(t) -> execute open(t+1) -> mark open(t+2);
- `SIDE_COST = 0.0006` per turnover side;
- evaluation starts 2021-01-01;
- 511220 remains the cash/carry signal and is always present;
- no C2/V1 or other execution overlay.

## Exposure exclusion

The Stage1 best K7 was:

`511220 + 159915 + 159985 + 161226 + 501018 + 513100 + 513920`.

511220 is retained only as the cash proxy. The six risk-exposure families are excluded at the metadata level, not merely by symbol code.

Primary exclusion families:

1. China growth-board exposure: `CHINA_GROWTH*` / ChiNext-like growth-board buckets.
2. Agriculture exposure: metadata containing `AGRICULTURE` in exposure/risk/style.
3. Precious metals: metadata containing `PRECIOUS_METALS`.
4. Energy commodities: commodity exposures whose exposure/risk bucket begins with or contains `ENERGY` (including crude-oil/energy-chemical commodity baskets).
5. US Nasdaq / growth-tech exposure: `US_LARGE_GROWTH`, `US_TECH`, `US_NASDAQ*`, or US technology/growth-tech style buckets.
6. SOE exposure: exposure/risk/style containing `SOE`, including central-SOE variants.

The six original risk symbols are explicitly excluded even if metadata later changes.

Primary candidate pool additionally requires current metadata with a non-null `risk_bucket` and `needs_review = false`. This is an anti-leakage guard against an unclassified ETF silently reproducing a prohibited exposure.

The metadata taxonomy is structural only; no returns are used to assign exposure labels.

## Search objective

Primary objective is full-2021–2026 frozen-OLS log portfolio growth. No risk penalty, cardinality reward, era weight, or feature weight is added after seeing results.

K is variable. Search permits 1–15 non-cash members plus 511220. The Stage1 K7 is not imposed.

## Why heuristic search is necessary

The post-exclusion market remains combinatorially too large for exhaustive subset enumeration. Stage3 therefore uses an optimizer ensemble and reports the result as `best found`, not as a certified global optimum.

Search ensemble:

1. evaluate every singleton;
2. multi-start greedy forward construction from strong and category-diverse singleton seeds;
3. iterative best-improvement add/drop/swap local search;
4. stochastic mutation/restart around elite solutions;
5. deduplicate all visited sets and retain an elite archive.

A solution is stronger evidence when rediscovered from multiple independent starts.

No architecture feature from Stage2 is used to score or filter candidates in the primary search. Stage2 features are reserved for the later three-group comparison. This prevents circularly forcing the new pool to look like the Fix15 optimum.

## Required outputs

- candidate/excluded symbol audit with exclusion reasons;
- all singleton values;
- elite unique Universes with full-period and era-split values;
- best-found Universe and K;
- number of independent rediscoveries;
- local 1-add / 1-drop / 1-swap residual improvements for the champion;
- same-K random benchmark distribution from the allowed candidate pool;
- target path diagnostics: switches, mean Top1 tenure, invested ratio, MDD.

## Three-group reverse-engineering comparison

Stage4 will compare:

A. Fix15-internal high-value group: Stage1 Top1% subsets plus the Stage1 best K7.

B. Exposure-disjoint high-value group: Stage3 elite/top solutions from the allowed market.

C. Controls: same-K random and low-value Universes from the Stage3 allowed market.

Original Fix15 remains an external benchmark, not one of the three structural groups.

The reverse-engineering target is not symbol identity. It is architecture shared by A and B but absent/weaker in C, with era-split direction checks.

## Anti-overfit rules

- Do not alter the exclusion families after seeing Stage3 returns.
- Do not re-admit a prohibited exposure because a replacement ETF performs well.
- Do not tune K to the result; K remains variable.
- Do not use Stage2 architecture features in the Stage3 primary search objective.
- Do not promote the champion as executable.
- Do not call the heuristic champion a global optimum.
