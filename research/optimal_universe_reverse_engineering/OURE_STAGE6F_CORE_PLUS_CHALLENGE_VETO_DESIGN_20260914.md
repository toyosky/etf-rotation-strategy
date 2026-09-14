# OURE Stage6F — Fixed-K30 Core Formation + Challenge Veto

Date: 2026-09-14
Status: preregistered before outcome inspection

## Question
With non-cash K fixed at 30, can a low-DoF X<=t procedure form a useful K29 core and then use the already-frozen Stage6D `prior_challenge_share` only as a conditional admission veto for member 30?

This stage explicitly separates core formation from admission. It does not optimize K, use Fix15 identity, use future elite identity, train a model, search features, or tune thresholds after outcomes.

## Decision cadence and information set
- Decisions: first trading session on/after Jan 1 and Jul 1, 2022–2026.
- Every selector uses only completed observations before decision date t.
- Historical set-value windows remain frozen at 63/126/252 sessions from Stage5.
- Stage6D challenge window remains frozen at 126 completed sessions.
- The selected K30 is held for the next half-year under the frozen downstream OLS evaluator.
- Final incomplete 2026H2 is descriptive only and excluded from formal gates.

## Point-in-time pool
Reuse Stage5 point-in-time eligibility exactly: daily bars, non-leveraged/non-inverse guard, at least 240 finite closes in the trailing 252 sessions, cash 511220 handled separately. No Fix15 membership or hindsight membership is used.

## Core formation layer
Three K29 core rules are frozen before forward outcomes are inspected.

### Core A — current-state fallback
Rank point-in-time candidates by the last pre-decision frozen OLS `pool_score`; finite score first, ties by symbol. Take the first 29.

### Core B — robust historical-set consensus
Reuse Stage5 deterministic 63/126/252 candidate-library construction and its frozen robust ordering.
1. Union the three historical libraries.
2. Rank each Universe by the frozen Stage5 robust score: maximize the minimum of its 63/126/252 historical return percentiles; tie by mean percentile, then smaller K, then member string.
3. Reuse the already-frozen Stage5 `top20` robust cohort size.
4. Give each ETF one membership vote for every top20 robust Universe containing it.
5. Rank ETFs by vote count, then last pre-decision `pool_score`, then symbol; take 29. If fewer than 29 distinct symbols receive votes, fill from current-state ranking.

### Core C — frozen state-gated core (primary)
Historical transfer is ON only if:
- at least two earlier decision dates have already produced point-in-time state observations; and
- current trailing-126 eligible-share is at least the expanding median of earlier decision states; and
- current trailing-126 median Top1–Top2 score gap is at least the expanding median of earlier decision states.

Both state variables come directly from Stage6 frozen regime diagnostics. Thresholds are expanding historical medians, not fitted constants.

If transfer is ON, use Core B. Otherwise use Core A. No other fallback is allowed.

## Neutral 30th member for core audit
To evaluate core quality without using Stage6D challenge information, append the highest current-state-ranked candidate not already in the K29 core. This creates fixed-K30 versions of Core A/B/C.

## Admission/redundancy veto layer
The veto is applied only after primary Core C is fully formed.

For every candidate outside Core C, compute Stage6D-frozen `prior_challenge_share` over the trailing 126 sessions: the share of prior sessions on which the candidate's score exceeds the already-active risk leader of Core C.

Frozen veto:
1. Proposed member = neutral highest-current-score outsider.
2. Compute the cross-sectional median challenge share across all outsiders.
3. If proposed challenge share <= median, admit it unchanged.
4. If proposed challenge share > median, scan outsiders in current-score order and admit the first candidate with challenge share <= median.
5. If no such candidate exists, fall back to the original proposed member.

The median is a distribution-relative veto, not a tuned penalty weight. Challenge share is never combined with other features into a score.

## Benchmarks
For every decision period report:
- Core A + neutral admission;
- Core B + neutral admission;
- Core C + neutral admission;
- Core C + challenge veto;
- 100 deterministic same-K30 random Universes from the same point-in-time pool.

Fix15 may be reported only as an external diagnostic and cannot alter gates.

## Frozen gates
### Core gate
Promote the state-gated core only if, over completed forward periods:
1. linked forward log growth of Core C + neutral admission exceeds both Core A and Core B;
2. Core C beats both A and B in more than 50% of completed periods; and
3. Core C beats the same-K30 random median in more than 50% of completed periods.

If this fails, freeze low-DoF core formation as failed. Do not tune windows, state variables, top20, vote weights, or thresholds.

### Veto gate
Promote the challenge veto only if, over completed forward periods:
1. Core C + veto has higher linked forward log growth than Core C + neutral;
2. veto improves period log growth in more than 50% of completed periods; and
3. the median veto-minus-neutral log-growth delta is non-negative in both 2022–24 and 2025–26 (where at least two completed periods exist).

If this fails, freeze challenge veto as not executable from this core. Do not change the 126-session window, median threshold, lag, weighting, or combine it with more predictors.

## Interpretation
The two gates are independent. A veto pass cannot rescue a failed from-scratch core gate, and a core pass cannot rescue a failed veto. Negative results terminate this low-DoF branch; no random forest, boosted tree, neural network, feature search, or threshold search is authorized.