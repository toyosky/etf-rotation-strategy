# OURE Stage6J — Chronological Mapping Transfer Design

Date: 2026-09-14
Status: preregistered

## Frozen question
Stage6I established that, within a given half-year, the frozen 19-feature K30 value surface often contains strong cross-sectional signal for the next 126 sessions. Stage6J asks the missing executable question:

> Can a mapping estimated only from completed earlier half-years rank K30 Universes in the next half-year?

This is a mapping-transfer experiment, not a new Oracle search and not an RF tuning experiment.

## Data and labels
Everything inherited from Stage6I is frozen:
- K = 30;
- X(U): the same 19 whole-Universe features computed over the 126 sessions strictly before each Jan/Jul decision date;
- Y(U): frozen downstream OLS log wealth over the next 126 sessions;
- the same deterministic K30 family-library builder and seed 20260914;
- approximately 2496 K30 samples / 676 combination families per half-year;
- no member identity enters X;
- 2026H2 excluded because a complete future-126 label is unavailable.

Primary chronological evaluation uses target periods with at least three fully completed prior half-years: 2023H2, 2024H1, 2024H2, 2025H1, 2025H2, 2026H1. Current-period future labels are used only for final scoring, never fitting, feature selection, weighting, thresholds, or model choice.

## Frozen transfer rules
No hyperparameter search is allowed.

### R1 — previous-period RF
Fit the exact frozen Stage6I RF on the immediately previous completed half-year and predict the current half-year K30 samples.

RF remains exactly:
- 800 trees;
- max_depth = 7;
- min_samples_leaf = 10;
- max_features = sqrt;
- bootstrap = true;
- random_state = 20260914.

This is a recency diagnostic, not the primary gate.

### R2 — last-3 RF rank ensemble — PRIMARY
Fit three separate copies of the same frozen RF, one on each of the previous three completed half-years.

For the current target-period K30 cross-section:
1. obtain predictions from each historical RF;
2. convert each prediction vector into within-target percentile ranks;
3. average the three percentile ranks with equal weight 1/3.

No performance weighting, decay weighting, regime weighting, or current-period calibration is allowed.

### R3 — last-3 unanimous directional score
This is the low-DoF sub-mapping diagnostic.

For each of the frozen 19 features:
1. calculate feature-vs-Y Spearman separately in each of the previous three completed periods;
2. retain the feature only when all three finite correlations have the same strict sign;
3. use only that sign, not correlation magnitude;
4. in the current target cross-section, percentile-rank the feature and center at 0.5;
5. equally average signed centered ranks across retained features.

No minimum-correlation threshold, importance filter, feature subset search, or unequal weight is permitted. If no feature has unanimous sign, the score is constant and its IC is recorded as unavailable/zero for summary purposes.

## Metrics
For every target period and rule report:
- Spearman(predicted score, future 126-session log wealth);
- whether Spearman > 0;
- mean actual future percentile of predicted Top50;
- predicted top-decile future-log lift vs the full target cross-section.

Also report R3 retained-feature count and names as diagnostics only.

## Primary gate — frozen before results
Only R2 determines Stage6J pass/fail. Across the six chronological OOS target periods, all conditions must hold:
1. median period Spearman > +0.10;
2. at least 4 of 6 period Spearmans are positive;
3. median predicted-Top50 actual percentile > 0.55;
4. median Spearman over 2023H2–2024H2 > 0;
5. median Spearman over 2025H1–2026H1 > 0.

R1 and R3 cannot rescue a failed R2 gate. They diagnose whether any transfer is mainly one-period recency or a stable directional sub-mapping.

## Interpretation rules
- If R2 passes, freeze low-DoF chronological mapping transfer as supported. Only then may a later stage preregister an RF-guided K30 searcher; the search algorithm and OOD safeguards must be frozen before seeing its future-period result.
- If R2 fails, freeze the current data as insufficient for stable historical-to-next-period K30 mapping under these low-DoF transfer rules. Do not tune RF parameters, feature subsets, lookback, ensemble weights, or thresholds to rescue it.
- A strong R3 result with failed R2 is evidence for stable directional components, not authorization for a new high-capacity model. Any follow-up must be separately preregistered and chronological.

## Leakage guards
- No current-target future Y is used before evaluation.
- No member identity is a model feature.
- No result-conditioned choice among R1/R2/R3.
- Stage6I same-period grouped CV remains a learnability ceiling/diagnostic, not OOS evidence.
