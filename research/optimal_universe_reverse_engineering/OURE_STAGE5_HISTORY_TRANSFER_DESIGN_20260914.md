# OURE Stage5 — Historical Universe Transfer Walk-Forward

Date: 2026-09-14
Status: preregistered before outcome inspection

## Question
Can a high-value ETF Universe discovered only from past data retain value over the next half-year, and do simple historical relay-quality metrics improve that transfer?

This is the first executable X<=t bridge. It does **not** assume that the historical optimum is the future optimum and does not train a return-prediction model.

## Decision cadence and information set
- Decisions: first trading day on/after Jan 1 and Jul 1, starting 2022-01 and continuing through available 2026 data.
- At each decision index d, every selector may use only signal/bar information strictly before d.
- Lookbacks are frozen at 63 / 126 / 252 trading days (~3 / 6 / 12 months).
- The selected Universe is frozen until the next half-year decision; the final 2026H2 period is partial if data end earlier.
- Downstream OLS target selection and transaction-cost semantics remain frozen.

## Point-in-time candidate pool
- Start from symbols with daily bars and not marked leveraged/inverse; cash proxy 511220 is handled separately.
- At decision d, a risk symbol must have at least 240 finite closes in the previous 252 trading days and a finite latest pre-decision close.
- No future return, future relay metric, or future taxonomy state is used in selection.
- Current metadata is used only for the leverage/inverse/data-availability guard, not as a ranking feature. This leaves a documented residual survivorship-metadata limitation.

## Deterministic historical search
For each 63/126/252-day window separately:
1. Evaluate all point-in-time candidates as singleton Universes under the frozen OLS engine.
2. Keep the top 180 singleton symbols as the deterministic search shortlist.
3. Start greedy add-only paths from the top 8 singleton seeds; add the member that most increases historical net log growth until no positive increment or noncash K=60.
4. Keep every intermediate greedy set, not only the endpoint.
5. Apply deterministic 1-drop / 1-swap local refinement to the best four greedy endpoints, with swap-ins limited to the top 80 singletons, maximum five refinement rounds.
6. The union of all generated sets is the candidate Universe library.

The resulting set is a deterministic local-search solution only. Never call it an exact/global optimum.

## Three frozen selectors
### Rule A — Past6M Winner
Choose the candidate library member with the highest past-126-day net log growth.

### Rule B — Robust Historical Winner
For every candidate in the union library, compute its percentile rank of historical net log growth over 63, 126 and 252 days. Define:
- primary robust score = minimum of the three percentiles;
- tie-break 1 = mean percentile;
- tie-break 2 = smaller noncash K;
- tie-break 3 = lexicographic member string.
Choose the maximum robust score. No fitted weights.

### Rule C — Mechanism-Assisted
1. Take the top 20 Rule-B candidates by the frozen robust ordering.
2. On the past 126 trading days only, compute the already-frozen relay mechanism metrics:
   - coverage_efficiency (higher better),
   - productive_switch_share (higher better),
   - switch_counterfactual_gain_mean (higher better).
3. Convert each to within-top20 percentile ranks; missing values receive the bottom rank.
4. mechanism score = equal-weight mean of the three percentiles.
5. Tie-break by Rule-B ordering.

Stage4F exposure diversification is reported diagnostically only and is not used by the selector.

## Forward evaluation
For each selected Universe, evaluate the next non-overlapping half-year using the frozen downstream OLS engine. Report:
- future net log growth / total return / max drawdown / switches;
- selected noncash K;
- future coverage_efficiency, productive_switch_share and counterfactual gain mean;
- original Fix15 future result;
- full point-in-time candidate-pool future result;
- 100 deterministic same-K random Universes from the same point-in-time pool: return median/mean and future relay-metric medians.

Link half-year forward returns to obtain cumulative walk-forward wealth for each rule. Do not optimize on these outcomes.

## Interpretation gates
1. **Persistence gate:** Rule A has evidence of historical-Universe persistence only if its linked forward log growth exceeds the median same-K random baseline and it beats the same-K random median in >50% of completed half-years. This is descriptive evidence, not significance proof.
2. **Robustness increment:** Rule B is promoted only if it improves linked forward log growth over Rule A without materially worsening same-K-random hit rate.
3. **Mechanism increment:** Rule C is promoted only if it improves future relay quality versus Rule B (at least 2 of the 3 frozen relay metrics have better period-median relative-to-random deltas) and does not reduce linked forward log growth below Rule B.
4. If Rule A fails, do not rescue it by changing the six-month window. If B/C fail, freeze the failure; do not tune lookbacks, weights, top20, shortlist size, or mechanism metrics on these outcomes.

## Purpose
The stage distinguishes three possibilities:
- historical set value itself persists;
- persistence exists only after multi-window stabilization;
- past return is weak, but frozen relay-structure metrics transfer better.
If none passes, the next step is not a more complex predictor; freeze half-year historical transfer as non-identifiable under these low-DoF rules.
