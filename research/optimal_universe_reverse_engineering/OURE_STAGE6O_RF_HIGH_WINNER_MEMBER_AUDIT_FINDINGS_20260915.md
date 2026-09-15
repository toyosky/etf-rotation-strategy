# OURE Stage6O — RF-high Winner-Member Audit and Chronological Admission Test Findings

Date: 2026-09-15
Run: `34914650531`
Artifact: `oure-stage6o-rf-high-winner-member-audit-34914650531`
Status: frozen partial pass / predictive fail
Decision: `member_traits_exist_but_admission_not_oos_supported`

## Frozen question
Inside the K30 sets already admitted to the previous-block RF top 20%, which ETF members are associated with the next 126-session winner combinations, what did those members look like at decision time, and can those past-only member traits identify better members in the next block?

The design was preregistered before outcome inspection. No symbol identity was allowed into the predictive model and no future member path entered X.

## Construction actually evaluated
- Strict Stage6K non-overlapping 126-session blocks.
- Target blocks B02..B09.
- First-layer RF unchanged; each target block is scored by the immediately previous completed block RF.
- RF-high fixed at top 20% (~500 K30 sets per block).
- Member rows retained only when the ETF appeared in at least 20 RF-high sets.
- Total member-period rows: 1,439.
- Future winners / losers are top / bottom 20% of RF-high K30 by realized next-126-session OLS log-growth.
- Primary member future-value label is a first-layer-RF-stratified conditional association: within ten RF-score strata, compare future K30 value when the ETF is present versus absent, then aggregate valid stratum deltas. It is an association label, not a causal effect.

## Stage 1 — future winner members do have repeatable past-only traits
Six of 21 preregistered member features pass the frozen 6-of-8 direction + effect-size stability rule, spanning A/B/C/D families. The mechanism gate therefore PASSES.

| Feature | Direction in future-high-marginal members | Blocks in dominant direction | Median standardized effect | Median abs effect |
|---|---|---:|---:|---:|
| `elig_participation126` | higher | 7/8 | +0.196 | 0.220 |
| `rfhigh_presence_rate` | lower | 7/8 | -0.485 | 0.485 |
| `rfhigh_mean_past126_set_when_present` | lower | 6/8 | -0.505 | 0.505 |
| `dist_high21` | lower / further below recent high | 6/8 | -0.162 | 0.209 |
| `singleton_log126` | lower | 6/8 | -0.124 | 0.176 |
| `rfhigh_comember_corr_mean` | higher overall | 6/8 | +0.090 | 0.301 abs |

### Main structural interpretation
The strongest repeated member-level pattern is not "pick the historically hottest ETF".

Future-useful members tend to be:
1. **qualified / repeatedly eligible** — trailing126 eligibility participation is higher in 7/8 blocks;
2. **less ubiquitous in the RF-high candidate family** — RF-high presence rate is lower in 7/8 blocks;
3. **embedded in weaker trailing126 K30 contexts** — the average past126 whole-set value of RF-high sets containing the member is lower in 6/8 blocks, with a large median standardized effect around -0.50;
4. **somewhat pulled back from the recent 21-session high** — `dist_high21` is more negative in 6/8 blocks;
5. **not necessarily a strong trailing standalone OLS winner** — singleton past126 value is lower in 6/8 blocks;
6. **not simply a low-correlation diversifier** — co-member return correlation is actually higher in the dominant direction in 6/8 blocks.

A useful shorthand is therefore **qualified but under-represented / non-exhausted challenger**, not "current strongest standalone member". This is consistent with the broader OURE relay mechanism: value can come from members that preserve future replacement optionality rather than members already dominating the historical candidate family.

This should not be over-read as a causal rule. In particular, low RF-high presence can also increase estimation variance of a member's conditional marginal, so it is a mechanism hypothesis that requires prospective validation.

## Descriptive identity examples are period-specific only
The top conditional-marginal members change substantially by block. Examples of the top member in each block include:
- B02 `162719`;
- B03 `159985`;
- B04 `513520`;
- B05 `513300`;
- B06 `159731`;
- B07 `516800`;
- B08 `513230`;
- B09 `159886`.

This identity turnover is exactly why ticker codes were excluded from the model. No specific ticker is promoted as a persistent winner.

## Stage 2 — strict chronological member admission model fails
A fixed RandomForest member model used all 21 preregistered past-only member features and trained only on earlier completed member blocks. Tests were B05..B09.

Aggregate RF member model:
- median member-rank Spearman: **+0.0713**;
- positive IC: **3/5** blocks;
- median predicted-top10 actual future-member percentile: **0.4284**;
- median top10 conditional-future-marginal lift: **-0.0230**.

All five preregistered predictive gates FAIL.

Per-block member-RF IC:
- B05: -0.091;
- B06: +0.127;
- B07: +0.193;
- B08: +0.071;
- B09: -0.187.

The model has some broad signal in B06-B08 but does not transfer stably to the extreme member tail.

## Simple baselines
Median OOS member-rank IC across B05..B09:
- `ret126`: **+0.1293**, positive 3/5, but median top10 marginal lift is negative (-0.0054);
- `elig_participation126`: **+0.1028**, positive 4/5, median top10 marginal lift +0.0051, but top10 actual percentile only 0.5145;
- `singleton_log126`: +0.0149;
- `rfhigh_mean_past126_set_when_present`: -0.1146.

Thus the complex member RF does not beat the best simple baseline. Eligibility participation is the cleanest directionally repeated simple signal, while raw trailing return has the highest median broad IC but does not identify a profitable extreme top10.

## Interpretation relative to Stage6L / Stage6N
Stage6O materially sharpens the earlier whole-set result.

- Stage6L: RF-high future-good and false-positive K30 sets have repeatable aggregate internal differences.
- Stage6O: those differences can be pushed down to the **member level**; future-useful members are not structurally arbitrary.
- However, just as whole-set second-layer prediction was unstable, a chronological member-admission RF still cannot reliably identify the next period's top members.

So the current bottleneck is no longer "we do not know what useful members look like at all." We now have a candidate member mechanism. The bottleneck is converting that mechanism into a stable X<=t admission score without amplifying top-tail noise.

## Frozen conclusion
**Stage 1 mechanism PASS; Stage 2 predictive FAIL.**

Current supported mechanism hypothesis:

`RF coarse-plausible K30 family -> future valuable members tend to be repeatedly eligible, less ubiquitous / less historically exhausted, and often in a short-term pullback rather than being the strongest trailing standalone winner.`

Current unsupported claim:

`the frozen member RF can prospectively choose the next best ETF admissions.`

Do not tune the 20% RF-high threshold, 20-appearance rule, future winner cutoff, member-feature definitions, RF hyperparameters, or top10 rule on this history. A continuation should test a genuinely new member-admission hypothesis or new forward blocks, not rescue this model by post-hoc tuning.
