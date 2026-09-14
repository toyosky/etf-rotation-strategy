# OURE Stage1 — Fix15 Exhaustive Static-Subset Reverse Engineering

Date: 2026-09-14
Status: preregistered

## Question

Fix15 is a strong but known non-optimal engineering Universe. Before learning any executable selector, exhaustively enumerate every static subset of its 14 non-cash ETFs while always retaining cash signal 511220, under the frozen daily OLS ranking engine.

The purpose is not to promote a hindsight subset. It is to identify what distinguishes high-value Universes from low-value Universes and to generate structural hypotheses that can later be tested on symbols outside Fix15.

## Frozen downstream engine

Reuse `universe_size_then_composition.stage1_oracle_size_mc.build_wides` and the existing research semantics:

- signal state: annual > 0, r2 > 0, score > 0, and no recent_drop3 veto;
- within the static Universe, select the highest OLS score each signal day;
- 511220 is always retained and is interpreted as cash when it wins;
- close(t) signal -> open(t+1) execution -> open(t+2) mark;
- side cost = 0.0006, with existing one-side/two-side turnover semantics;
- evaluation begins 2021-01-01 and uses all available dates through the database end.

No C2/V1, no new threshold, no feature search, and no change to OLS score is allowed.

## Exact search space

Fix15 contains 511220 plus 14 non-cash symbols. Enumerate all 2^14 = 16,384 possible non-cash subsets, including the cash-only Universe.

Primary hindsight objective: terminal net log growth over the full evaluation sample. This is equivalent to ranking by terminal wealth and makes marginal/interaction decomposition additive.

For every subset retain at least:

- K including cash;
- members;
- full-period terminal return and log growth;
- 2021-24 and 2025-26 terminal return/log growth;
- max drawdown;
- switch count and turnover sides;
- invested ratio.

## Structural decomposition

Using the complete set-value table, compute without model fitting:

1. exact best subset overall and exact best subset for every K;
2. Fix15 and Fix15-minus-each-member leave-one-out deltas;
3. the specific Fix15-minus-159825 agriculture result;
4. exact context-averaged Banzhaf-style marginal log value for every ETF;
5. marginal value by context size;
6. pairwise average second-difference interaction in log value;
7. membership enrichment in the top 1% and top 5% of all subsets;
8. local path-role diagnostics around Fix15: coverage days versus competition/displacement days;
9. symbol-level OLS traits: trend-eligible share, score distribution, singleton value, Fix15 Top1 tenure/short-run propensity, and selection frequency.

## Interpretation discipline

Stage1 is deliberately hindsight/explanatory. A symbol appearing in the best subset, having high Banzhaf value, or being enriched in top subsets is not an executable selection rule.

The next stage may only promote a structural characteristic if it also separates high-value from low-value Universes more generally and can be defined without ETF identity.

The intended replication challenge is stricter than reproducing Fix15: after freezing the structural hypotheses, construct a Symbol-disjoint Universe that excludes all Fix15 codes, then an Exposure-disjoint Universe that also excludes obvious near-substitutes. Only those later tests can support a general Universe architecture claim.
