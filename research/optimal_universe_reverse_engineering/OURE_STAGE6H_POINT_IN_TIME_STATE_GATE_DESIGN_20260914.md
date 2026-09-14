# OURE Stage6H — Point-in-Time Transfer-State Gate Design

Date: 2026-09-14
Status: preregistered before outcome inspection

## Question
Can a fixed, low-DoF market-state rule built only from information available at decision time identify when historical Universe structure is more likely to transfer into the next half-year?

This stage does **not** train or retune the Stage6G random forest. It tests the prerequisite state-gating idea first.

## Frozen cadence and downstream target
- Reuse Stage5/Stage6 Jan/Jul decision dates, point-in-time candidate-pool rules, frozen 63/126/252 search library, and frozen downstream OLS/cost semantics.
- Primary future transfer target at each decision date is the already-defined Stage6 quantity:
  - `robust_future_spearman` = Spearman across the frozen current library between the Stage5 robust 3/6/12 historical score and the next half-year OLS log-growth ranking.
- Secondary, non-gating target:
  - `past6_future_spearman`.
- The final incomplete half-year is excluded from primary evaluation.

## X<=t state variables
At decision date t, compute each state variable on the **trailing 126 trading sessions ending immediately before t**, using the complete point-in-time risk pool available at t:
1. `eligible_fraction_126`: average fraction of the pool with finite frozen OLS score;
2. `top1_top2_gap_median_126`: median Top1 minus Top2 score gap on days with >=2 eligible assets;
3. `leader_switch_rate_126`: risk-leader switch count divided by possible transitions;
4. `mean_leader_tenure_126`: mean run length of the risk leader.

No future-period state variable from Stage6 may enter the gate.

## Frozen gate
For each decision date, compare the four current trailing-126 state variables with their expanding medians across **strictly earlier decision dates only**.

A directional vote is positive when:
- eligible fraction >= its expanding historical median;
- Top1-Top2 gap >= its expanding historical median;
- leader switch rate >= its expanding historical median;
- mean leader tenure <= its expanding historical median.

Define:
- `state_vote_count` = number of positive directional votes, 0..4;
- `transfer_on = 1` iff `state_vote_count >= 3`.

No weights, fitted coefficients, percentile search, or post-outcome threshold changes are allowed.

## Burn-in
- A decision enters primary evaluation only after at least 3 strictly earlier decision states exist.
- Earlier decisions may be used only to build expanding state medians.
- The final incomplete forward period is excluded.

## Primary preregistered gate
Call the X<=t state gate successful only if **all** conditions hold on evaluable completed periods:
1. both states are represented: at least 2 `transfer_on` and at least 2 `transfer_off` periods;
2. sign classification accuracy for `robust_future_spearman > 0` is > 0.60;
3. median `robust_future_spearman` is > 0 in transfer-on periods and <= 0 in transfer-off periods;
4. transfer-on minus transfer-off median `robust_future_spearman` is >= +0.20.

Because the number of half-year periods is small, this is a frozen descriptive/OOS gate, not a significance test.

## Secondary diagnostics
Report without changing the primary decision:
- the same sign accuracy / on-off medians for `past6_future_spearman`;
- per-period state values, expanding thresholds, and vote flags;
- 20,000 resamples of the difference in mean `robust_future_spearman` between transfer-on and transfer-off periods, only as uncertainty description;
- era labels 2022-24 vs 2025-26 for interpretation only.

## Interpretation constraints
- If the primary gate fails, freeze that the current four-variable low-DoF X<=t market-state rule is insufficient. Do not tune vote threshold, lookback, variable set, or weights to rescue it.
- If the primary gate passes, this authorizes only a later preregistration of a state-conditioned surrogate/search experiment. It does not retroactively convert Stage6G into a pass.
- Stage6G RF hyperparameters, feature set, 0.65 threshold, and era endpoints remain frozen.
- Any later RF-guided K30 search must freeze the search algorithm before evaluation and must ultimately be judged on a genuinely later unseen period.
