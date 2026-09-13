# New Stage 1 Findings — Universe Size Monte Carlo

Date: 2026-09-14
Status: frozen structural evidence

## Scope

Stage1 is hindsight mechanism research only. It does not select an executable K. The downstream OLS rule, parent-pool construction, K range and sampling design remain frozen.

Primary batch:
- run: `34772895471`
- seed: `20260914`
- corr threshold: `0.95`
- samples per K per month: `180`
- nested deletion paths per month: `36`
- K: `3..30`
- months: `68`
- sampled universes: `374,544`

Predeclared robustness batch:
- run: `34775534691`
- alt-seed arm: seed `20260915`, corr `0.95`
- corr-sensitivity arm: seed `20260914`, corr `0.90`

The duplicate same-configuration workflow runs are not counted as independent evidence.

## Primary result: no globally stable K effect

The relation between Universe size and Frozen-OLS value is strongly regime-dependent.

### 2021–2024

Base batch:
- mean monthly Spearman(K, MC mean return): `-0.8757`
- share of months with negative Spearman: `87.5%`
- K30 - K3 mean monthly return contrast: `-1.3862 percentage points`
- month-cluster bootstrap 95% interval: approximately `[-2.31, -0.44] pp`

Alt-seed:
- mean monthly Spearman: `-0.8844`
- K30 - K3: `-1.3501 pp`
- bootstrap 95%: approximately `[-2.33, -0.35] pp`

Corr threshold 0.90:
- mean monthly Spearman: `-0.8722`
- K30 - K3: `-1.4080 pp`
- bootstrap 95%: approximately `[-2.34, -0.45] pp`

Interpretation: larger K is robustly harmful in this era under the frozen downstream rule.

### 2025–2026

Base batch:
- mean monthly Spearman(K, MC mean return): `+0.0817`
- K30 - K3: `+1.1655 pp`
- month-cluster bootstrap 95%: approximately `[-1.56, +3.96] pp`

Alt-seed:
- mean monthly Spearman: `+0.0731`
- K30 - K3: `+1.2836 pp`
- bootstrap 95%: approximately `[-2.15, +4.65] pp`

Corr threshold 0.90:
- mean monthly Spearman: `+0.0947`
- K30 - K3: `+1.3632 pp`
- bootstrap 95%: approximately `[-1.99, +4.69] pp`

Interpretation: the point estimate reverses positive, but with only 20 months it is not statistically precise enough to claim a positive population effect.

## Monte Carlo convergence and parent-pool sensitivity

Base versus alt-seed, merged month x K cells:
- return_mean correlation: `0.9989`
- return_median correlation: `0.9989`
- monthly K-shape Spearman correlation: `0.9719`
- monthly slope-sign agreement: `92.65%`
- K30-K3 monthly contrast correlation: `0.9716`

Base versus corr=0.90:
- return_mean correlation: `0.9972`
- return_median correlation: `0.9974`
- monthly K-shape Spearman correlation: `0.9556`
- monthly slope-sign agreement: `95.59%`
- K30-K3 monthly contrast correlation: `0.9384`

The corr=0.90 representative pool is materially smaller but does not remove the era reversal:
- base parent pool mean / median: about `218.3 / 240`
- corr=0.90 mean / median: about `178.4 / 197`

Therefore the reversal is not explained by one Monte Carlo seed or by the predeclared correlation-dedup sensitivity.

## Paired nested 15 -> 3 evidence

This is secondary evidence only.

2021–2024:
- base mean K->K-1 deletion delta: `+0.1505 pp`
- alt-seed: `+0.1418 pp`
- corr=0.90: `+0.1383 pp`
- all 12 average deletion steps are positive in each arm

2025–2026:
- base mean deletion delta: `-0.1579 pp`
- alt-seed: `-0.1536 pp`
- corr=0.90: `-0.1840 pp`
- most average deletion steps are negative

Many individual deletion deltas are exactly zero, so this path evidence does not replace the independent same-K Monte Carlo result.

## Stable geometry, reversing economic payoff

The mechanical consequences of increasing K are stable across eras.

Base 2021–2024, K3 -> K15 -> K30:
- switches median: `2.05 -> 4.51 -> 5.42`
- observed Top1 tenure median: `7.90 -> 4.50 -> 3.87 days`
- winner coverage median: `0.241 -> 0.732 -> 0.913`
- dormant share median: `0.884 -> 0.921 -> 0.931`
- effective N median: `2.53 -> 3.88 -> 4.42`
- mean return: `4.20% -> 3.02% -> 2.81%`

Base 2025–2026, K3 -> K15 -> K30:
- switches median: `2.35 -> 4.90 -> 5.80`
- observed Top1 tenure median: `8.75 -> 4.48 -> 3.65 days`
- winner coverage median: `0.159 -> 0.583 -> 0.816`
- dormant share median: `0.866 -> 0.910 -> 0.923`
- effective N median: `2.50 -> 4.08 -> 4.86`
- mean return: `2.33% -> 3.31% -> 3.49%`

The same geometry is present under corr=0.90.

Thus Stage1 supports a coverage-versus-competition interpretation:
- larger K raises opportunity/winner coverage;
- larger K also raises competition and switching while shortening observed Top1 tenure;
- in 2021–24 the competition/redundancy cost dominates;
- in 2025–26 the extra coverage has a positive point estimate large enough to offset that cost, although statistical uncertainty remains.

## Counterexamples and non-monotonicity

The monthly optimum is not stable. Positive-K-slope examples include 2026-04, 2026-02 and 2025-08. Strong negative examples include 2022-04, 2026-07 and 2025-03.

Therefore neither a global monotone law nor a single exact optimal K is supported.

## Data-quality note

`stage1_summary.json.representative_pool_stats` is invalid because an upstream summary includes zero-count calendar buckets. Recalculation from `monthly_parent_pool_snapshots.csv` gives 68 nonempty months with base pool mean about 218.29, median 240, min 65, max 383. The Monte Carlo samples themselves are unaffected; no rerun is warranted.

## Frozen Stage1 conclusion

**Universe size effect is regime-dependent.**

Stage1 does not justify freezing a precise K or a global K range. The robust next question is mechanistic: why does the same increase in coverage/competition have opposite payoff across eras?

Proceed to New Stage2. Do not proceed directly to Stage3 K selection.
