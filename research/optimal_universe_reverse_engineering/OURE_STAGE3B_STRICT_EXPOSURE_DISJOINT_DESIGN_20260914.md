# OURE Stage3B — Strict Broad-Exposure-Disjoint Search

Date: 2026-09-14
Parent: OURE Stage3

## Why Stage3B exists

Stage3 completed successfully but failed the intended exposure-disjoint test because its taxonomy was too narrow. The Stage3 champion contained obvious near-family leakage such as a central-SOE dividend fund and oil/energy equity products even though the Stage1 optimum contained a SOE fund and crude oil. Stage3 is retained as an audit trail but is not promoted as valid replication evidence.

## Frozen downstream semantics

No change from Stage3:
- same daily bars and OLS features;
- same trend-eligibility semantics;
- same Top1 selection rule;
- same close(t) signal -> open(t+1) execution -> open(t+2) mark;
- same SIDE_COST;
- same 2021+ evaluation window;
- search objective is only realized frozen-OLS portfolio log growth;
- Stage2 architecture features are not used by the search objective.

## Strict excluded broad families

Keep 511220 only as the cash/carry proxy. Exclude the six risk families represented by the Stage1 best K7 at a deliberately broad level:

1. broad growth / ChiNext-style growth;
2. agriculture / soymeal;
3. precious metals, including gold and silver;
4. energy, crude oil, oil & gas, regardless of commodity/equity wrapper;
5. broad technology chain, including Nasdaq, technology, semiconductors, electronics, communications and digital-tech labels;
6. central/state-owned enterprise exposure, including Chinese-name guards for 央企/国企.

The exclusion function may use metadata name plus structural metadata. Unclassified/needs-review instruments remain excluded, as in Stage3.

## Search-capacity repair

Stage3 champion hit MAX_NONCASH=15 and therefore could not test positive additions. Stage3B raises MAX_NONCASH to 30. This is a search-boundary repair, not a research-hypothesis change. K remains endogenous; no reward or penalty for cardinality is introduced.

## Interpretation gate

Stage3B is still hindsight/mechanism research. A high-return champion is not executable evidence.

Promote to the three-group reverse-engineering comparison only if:
- no banned-family leakage is found in the champion/elite audit;
- the champion does not merely reflect the previous K cap;
- the result materially exceeds same-K random controls.

If the champion again hits the K cap, cardinality is not identified and the cap must not be interpreted as optimal K.
