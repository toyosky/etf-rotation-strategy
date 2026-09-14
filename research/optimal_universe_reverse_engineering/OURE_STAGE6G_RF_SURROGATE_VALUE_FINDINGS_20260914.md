# OURE Stage6G — RF Surrogate Value Function Findings

Date: 2026-09-14
Run: `34860161276`
Artifact: `oure-stage6f-rf-surrogate-value-34860161276`
Status: frozen
Decision: `era_specific_signal_but_preregistered_gate_not_passed`

> Numbering note: the experiment was preregistered before outcome inspection under a Stage6F-RF filename. A concurrent scheduled Stage6F core/veto experiment already occupied the canonical 6F registry slot, so this completed RF-surrogate experiment is archived as Stage6G without changing any preregistered rule.

## Question
Can a random forest learn a **whole-K30 value function** from the 126 sessions available before an era begins?

The RF target is continuous final OLS value:

`Y(U) = future_log_growth(U)`

for the entire era, not a Top50 class label and not a single-ETF return.

If learnable, this is the prerequisite for later using the RF as a surrogate objective inside a combinatorial K30 search.

## Data and leakage control
Each era contains `2496` unique K30 samples and `676` family IDs.

- 2022–2024: point-in-time pool frozen at the era start.
- 2025–2026: point-in-time pool frozen at the era start.
- X: 19 whole-Universe features measured only over the 126 sessions before the era.
- Y: downstream frozen-OLS final log wealth over the whole era.
- Validation: 5-fold GroupKFold by mutation-family ID.
- Mutation-family bases were required to be structurally diverse; near-local descendants never cross train/validation boundaries.
- No hyperparameter search.

Frozen RF:
- 800 trees;
- max depth 7;
- min leaf 10;
- sqrt feature sampling;
- bootstrap on;
- seed 20260914.

## Primary grouped-validation results

### 2022–2024
Fold Spearman:
- F1 `+0.0129`
- F2 `+0.0160`
- F3 `+0.1059`
- F4 `-0.1179`
- F5 `-0.0105`

Summary:
- median fold Spearman: **`+0.0129`**;
- positive folds: **3/5**;
- median predicted-Top50 actual future percentile: **`0.5399`**;
- median predicted-top-decile future-log lift versus validation mean: **`+0.0529`**.

Preregistered era gate: **FAIL**.

Interpretation: the model can weakly separate some broad value level in a few folds, but it cannot reliably rank unseen K30 families. There is no evidence here that the pre-2022 126-session whole-set state provides a stable surrogate objective for 2022–2024 K30 value.

### 2025–2026
Fold Spearman:
- F1 `+0.3326`
- F2 `+0.3888`
- F3 `-0.0078`
- F4 `+0.4017`
- F5 `+0.2527`

Summary:
- median fold Spearman: **`+0.3326`**;
- positive folds: **4/5**;
- median predicted-Top50 actual future percentile: **`0.6366`**;
- median predicted-top-decile future-log lift versus validation mean: **`+0.1124`**.

Preregistered era gate: **FAIL narrowly**.

Three of four frozen criteria pass. The only failed condition is predicted-Top50 actual percentile: `0.6366` versus the preregistered `>0.65` threshold.

This result must not be relabeled as a pass after seeing it. However, it is materially different from 2022–2024: within the later regime, the pre-era K30 structure contains substantial learnable information about whole-era OLS value.

## Cross-era transfer — secondary only
Training on all 2022–2024 samples and predicting 2025–2026 K30 values:
- Spearman `+0.0839`.

Training on all 2025–2026 samples and predicting 2022–2024 K30 values:
- Spearman `+0.1167`.

These are weak relative to the within-2025–2026 grouped-validation IC. Therefore the useful mapping is not a stable cross-era value function.

## Descriptive feature importance
Feature importance cannot rescue a failed gate, but the contrast is informative.

2022–2024 leading mean importances:
- past126 log growth `0.203`;
- max pair trend Jaccard `0.094`;
- past126 max drawdown `0.087`;
- mean pair trend Jaccard `0.069`;
- Top1–Top2 gap median `0.062`.

2025–2026 leading mean importances:
- max pair trend Jaccard `0.149`;
- invested ratio `0.095`;
- past126 log growth `0.074`;
- mean eligible count `0.069`;
- Top1–Top2 gap median `0.064`;
- mean competitors when covered `0.060`;
- coverage efficiency `0.058`.

The importance profile itself changes substantially, consistent with the broader OURE regime evidence that the balance among opportunity, replacement, and competition is not stationary.

## Frozen conclusion
1. The user's proposed formulation is technically coherent: RF can be trained as a continuous **K30 final-value surrogate**, while a separate combinatorial search chooses the 30 members.
2. Under grouped unseen-family validation, 2022–2024 shows essentially no stable learnability from the frozen pre-era 126-session set features.
3. 2025–2026 shows meaningful same-regime learnability: median rank IC `+0.333`, 4/5 positive folds and positive top-decile lift; nevertheless it narrowly fails the preregistered full gate and must remain a non-pass.
4. Cross-era transfer is weak (`+0.084` / `+0.117`), so a single stationary RF objective is not supported.
5. Do not tune the 0.65 threshold, RF parameters, feature set, or era endpoints to convert 2025–2026 into a pass.
6. The next informative test, if pursued, is not generic RF hyperparameter optimization. It is a **state-conditioned surrogate objective** or a carefully preregistered RF-guided search evaluated in a genuinely later period.

## Limitations
- This is within-era grouped validation, not chronological OOS. The entire era outcome supplies Y labels for train and validation families.
- Candidate pools still use current metadata guards and inherit the known survivorship-metadata caveat.
- The K30 sample library is large but finite and generated by a frozen mixture of past-only greedy, mutation-family, and broad-random construction; it does not enumerate all combinations.
