# Stage26 Variable-Size Set-Value Oracle Audit — Findings

Date: 2026-09-13
Verified workflow run: `34750235471`
Status: success

## Executive conclusion

The variable-size Universe problem has substantial **future-aware structural headroom**, and the value-optimal local search does **not** want anything close to the full ETF market.

Across 44 monthly decision points, the frozen greedy add/remove oracle naturally stopped at only 1–7 ETFs, with median size 3, while the point-in-time candidate market had median size 301.5.

This strongly supports the hypothesis that Universe size is an endogenous decision variable rather than a fixed engineering choice.

However, the oracle composition is extremely unstable across adjacent months: mean Jaccard similarity is only 0.028. Therefore Stage26 does **not** establish an executable selection rule. It establishes that large set-selection value exists in hindsight, while identifying point-in-time membership/composition as the central remaining problem.

## Overall — 44 months

- median full candidate count: 301.5
- oracle size mean: 3.14
- oracle size median: 3
- oracle size min/max: 1 / 7
- distinct oracle sizes: 7
- empty oracle months: 0

Future-aware 20-day mean net return diagnostics:

- local oracle: +29.02%
- full-market OLS: +0.63%
- Fixed15 OLS: +4.59%

These oracle returns are **not executable performance** and must not be interpreted as a strategy backtest. They only measure the amount of set-selection headroom that exists if future outcomes are known.

Downstream OLS path structure:

- full-market mean switch events: 7.75
- oracle mean switch events: 4.27
- full-market mean Top1 tenure: 3.17 days
- oracle mean Top1 tenure: 6.54 days
- mean share of the full-market Top1 path covered by oracle members: 23.64%

Thus the oracle does not improve value by reproducing the full-market path with fewer symbols. It selects a different, much less competitive path with materially longer effective tenure.

Adjacent-month oracle-set mean Jaccard: 0.0281.

This is the key warning: the economically valuable set exists, but its identity changes almost completely from month to month.

## 2023–2024

- months: 25
- median candidate count: 267
- oracle size mean / median: 2.72 / 3
- oracle size range: 1–5
- oracle mean net return: +17.34%
- full-market mean net return: -3.45%
- Fixed15 mean net return: +1.07%
- full switches: 7.44
- oracle switches: 3.84
- full tenure: 3.39 days
- oracle tenure: 7.28 days
- full-path coverage: 18.20%
- adjacent-month oracle Jaccard: 0.0060

The composition is essentially disjoint month to month in this era despite the strong set-value headroom.

## 2025–2026

- months: 19
- median candidate count: 478
- oracle size mean / median: 3.68 / 3
- oracle size range: 1–7
- oracle mean net return: +44.39%
- full-market mean net return: +5.99%
- Fixed15 mean net return: +9.22%
- full switches: 8.16
- oracle switches: 4.84
- full tenure: 2.88 days
- oracle tenure: 5.57 days
- full-path coverage: 30.79%
- adjacent-month oracle Jaccard: 0.0560

The same qualitative structure survives the era split: a very small variable set, fewer switches, longer tenure, and large future-aware headroom. The optimal identities remain unstable.

## Local-search quality diagnostics

After greedy forward addition and best-improvement removal cleanup:

- months with a positive remaining single-add: 0 / 44
- months with a positive remaining single-remove: 0 / 44
- months with a positive one-for-one swap: 8 / 44
- median best swap delta is slightly negative overall and in both eras

The resulting sets are therefore genuine 1-add / 1-remove local optima, but not guaranteed global optima. Positive swap residuals in 8 months justify a separate exact/global sensitivity audit; they do not justify treating the local oracle as wrong or tuning the greedy procedure on this history.

## What Stage26 answers

Stage26 supports four structural conclusions:

1. **Full-market competition is economically costly under the frozen OLS rule.**
   A much smaller subset can generate a very different and much less frequently switching OLS path.

2. **The useful cardinality is genuinely variable.**
   No fixed K is needed to make the oracle stop; positive marginal additions terminate naturally between K=1 and K=7.

3. **The set-value problem is not equivalent to selecting individually high future-return ETFs.**
   Value comes from conditional interaction with the rest of the set and from changing who is allowed to compete for Top1.

4. **Composition identifiability is now the bottleneck.**
   The extremely low month-to-month overlap means an executable model should not simply classify `oracle_member`. Membership is too unstable and can be non-unique. The next target should be conditional marginal set value `Delta V(j | S, X_t)`.

## Stage27 branch decision

Proceed, but do **not** train a direct oracle-membership classifier and do not choose a fixed K.

The next mainline experiment should construct conditional add-value labels along a canonical set-building path and test whether those marginal values are identifiable from point-in-time ETF state plus ETF-to-current-set relational state.

The executable architecture to test is:

`full market at t -> point-in-time state -> predicted conditional DeltaV(j | S) -> add best positive candidate -> repeat until no predicted positive gain -> optional predicted removal cleanup -> variable-size U_t -> frozen OLS`

The zero threshold is structural because the target itself is incremental portfolio value; it must not be tuned on the same OOS history.

Before escalating model capacity, compare the greedy local oracle with an exact/global solver under the **same frozen next-20-day semantics**. If the exact value gap is small, the low-complexity greedy search is adequate as the label generator. If it is material, Stage27 must represent pair/set interactions more explicitly rather than merely increasing predictor capacity.
