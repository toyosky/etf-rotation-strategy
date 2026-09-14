# OURE Stage6C — Full-Market 2022–2024 K Frontier Findings

Date: 2026-09-14
Run: `34849477779`
Artifact: `oure-stage6c-fullmarket-k-frontier-34849477779`
Status: frozen
Decision: `fullmarket_2022_2024_large_k_frontier_reappears`

## Question
Without using Fix15 membership, does the 2022–2024 market favor a small static ETF Universe, or does a large-K solution reappear?

## Candidate universe and caveat
The search used 265 noncash ETFs that had sufficient pre-2022 history and passed non-leveraged/non-inverse/data guards. No Fix15 inclusion or exclusion rule was used. The full subset lattice is intractable, so this is a strong heuristic searched frontier, not an exact/global optimum.

## Main K-frontier result
At the preregistered anchor noncash K values, the best searched 2022–2024 returns were:
- K5: +455.96%
- K10: +691.55%
- K15: +721.66%
- K20: +853.57%
- K25: +889.17%
- K30: +898.97% (best searched anchor/global searched result)
- K40: +829.13%
- K50: +873.85%
- K60: +849.48%

Thus the full-market result does **not** support the claim that 2022–2024 intrinsically prefers small K. The searched frontier rises materially beyond K15 and reaches a broad high plateau around K20–K30, with the best searched point at K30. K25 and K30 are nearly tied, so the defensible conclusion is `large/intermediate K plateau`, not an exact magical K=30 optimum.

The K30 champion has 30 noncash ETFs plus cash, log growth 2.30156, total return +898.97%, max drawdown -21.89%, 113 switches, mean Top1 tenure 6.46 days, and effective leader count 12.51.

## Same-K random controls
Random same-K universes are extremely weak, so the large-K result is not simply a generic benefit of adding members. Random median returns were approximately:
- K10: -17.93%
- K15: -14.29%
- K20: -17.37%
- K25: -22.78%
- K30: -28.41%
- K40: -36.13%
- K50: -37.82%
- K60: -39.64%

Therefore large nominal K without composition control is harmful; the high-value large-K universes are special compositions.

## K30 elite vs same-K random structure
Using top discovered K30 elites versus 100 deterministic random K30 controls, medians are:
- switch rate: 0.154 vs 0.228 (elite lower)
- mean Top1 tenure: 6.52d vs 4.43d (elite longer)
- <=2d short-run share: 0.364 vs 0.448 (elite lower)
- productive-switch share: 0.589 vs 0.422 (elite higher)
- switch counterfactual gain mean: +0.00721 vs -0.00152 (elite strongly higher)
- effective leader count: 11.48 vs 11.58 (similar)

So high-value K30 does preserve part of the Stage6B persistence signature despite large nominal K: leaders persist longer and switching is less frequent than in random large-K sets, while the switches that do occur are much more productive.

However, several Fix15-lattice Stage6B directions do **not** replicate:
- mean pair trend Jaccard is slightly higher in elite K30 (0.442 vs 0.425), not lower;
- max pair Jaccard is slightly higher (0.967 vs 0.960), not lower;
- mean eligible count / competitors are slightly higher, not lower;
- coverage efficiency is slightly lower, not higher.

Thus Stage6B's broad `low overlap / low simultaneous eligibility / high coverage efficiency` package is not a universal explanation of 2022–2024 high-value universes.

## Revised interpretation
The Fix15 exact lattice made small K look optimal because that restricted member family contains many harmful additions. In the full market, a large K can remain excellent if composition controls *effective* competition.

The stronger general statement is:

`High Universe value = enough opportunity coverage + productive replacement - harmful top-rank competition`

Nominal K is not the core state variable. In 2022–2024, high-value universes still show longer leader tenure and lower switch rate than random same-K sets, but this can coexist with K20–K30 nominal size. This is better described as a `large-K controlled-competition / productive-relay hybrid` than a pure small-K persistence regime.

## What is rejected
- Reject: `2022–2024 generally favors small K <=15`.
- Reject: `low pairwise trend overlap is necessary for a high-value 2022–2024 Universe`.
- Reject: interpreting the Fix15 K7 optimum as a full-market cardinality law.

## What remains
- Composition matters enormously at every K.
- High-value universes have much lower harmful switching and much higher replacement quality than random same-K universes.
- The best searched K range is broad around K20–K30; exact K30 should not be overinterpreted because the search is heuristic.

Next work should focus on identifying X<=t proxies for effective competition / replacement quality, not on imposing a small-K cap.