# OURE Stage7E — Tail-Consensus Mechanism Findings

Date: 2026-09-15
Authoritative run: `34925412235`
Artifact: `oure-stage7e-tail-consensus-34925412235`
Status: frozen diagnostic
Verdict: `tail_consensus_supported`

## Primary result
All four preregistered support criteria passed.

Using the weakest of the three historical 126-session rank percentiles (`min_rank`) and fixed within-block deciles:

- decile-level Spearman between D1...D10 and mean future-rank percentile: `+0.9879`;
- D1 mean future-rank percentile: `0.4331`;
- D10 mean future-rank percentile: `0.5727`;
- D1 future-top-decile hit share: `0.1005`;
- D10 future-top-decile hit share: `0.1113`;
- candidate-level min-rank IC was positive in 5 of 6 OOS target blocks.

The aggregate mean future-rank percentile rises from roughly 0.43 in the weakest historical-consensus decile to roughly 0.57 in the strongest decile. The gradient is not perfectly point-by-point monotonic at D1/D2, but from D2 onward is strongly increasing and the fixed decile-level Spearman is nearly +1.

## Aggregate decile profile

| min-rank decile | mean future rank pct | mean future log growth |
|---:|---:|---:|
| D1 | 0.4331 | -0.0010 |
| D2 | 0.4325 | +0.0045 |
| D3 | 0.4560 | +0.0193 |
| D4 | 0.4789 | +0.0322 |
| D5 | 0.4963 | +0.0388 |
| D6 | 0.5150 | +0.0537 |
| D7 | 0.5328 | +0.0702 |
| D8 | 0.5372 | +0.0740 |
| D9 | 0.5458 | +0.0795 |
| D10 | 0.5727 | +0.0865 |

This is direct evidence that candidates whose *worst* historical regime rank is stronger tend to have better future set value.

## Cross-block consistency
`min_rank` future Spearman by target block:

- B04: -0.1900
- B05: +0.4049
- B06: +0.0659
- B07: +0.1682
- B08: +0.2554
- B09: +0.2516

Thus the relation is not universal; the first OOS block is a clear exception. Nevertheless 5/6 blocks are positive, satisfying the preregistered stability condition.

## Signal comparison
Median future Spearman across six OOS blocks:

- frozen robust score: `+0.2028`
- rank mean: `+0.1996`
- min rank: `+0.2099`
- q25 rank: `+0.2169`
- all-three geometric strength: `+0.2223`
- second-worst / median rank: `+0.1864`

These differences are descriptive only. Stage7E does **not** replace the frozen robust score with another formula because all were inspected on the same six OOS blocks.

The frozen robust score also retains the best mean Top50 future percentile among the listed signals at about `0.6079`, supporting continued use of the existing formula rather than post-hoc replacement.

## Alignment with the frozen robust score
Median Spearman between frozen robust score and min-rank is `0.7263`.

For every one of the six target blocks, the frozen robust winner is essentially at the very top of the `min_rank` distribution; median winner min-rank percentile is `1.000`.

Across blocks, 88%-100% of the frozen robust Top50 also fall inside the min-rank top decile.

Therefore the frozen robust rule is strongly aligned with the tail-consensus mechanism even though it is not simply a hard minimum rule.

## Interpretation
Stage7D showed that broad candidate rankings differ substantially across 126-session histories. Stage7E now shows that a candidate's weakest historical rank contains meaningful information about future set value.

The supported mechanism is:

`multiple weakly aligned historical regimes -> transient one-regime winners are penalized -> candidates strong even in their weakest regime move to the top -> future Universe quality improves on average`.

In simple terms, the long-history Robust30 process is not mainly asking, "Who was the single best historical winner?" It is asking, "Who remained strong even when the market environment changed?"

This is a form of cross-regime false-positive suppression / tail consensus.

## Limits
- only six OOS 126-session target blocks are available in the frozen Stage7A-7E calendar;
- Stage7E reuses those blocks for mechanism diagnosis and is not an independent new deployment sample;
- one of six target blocks has a negative min-rank IC;
- signal-formula comparisons must not be used to retune the deployed score.

## Frozen conclusion
`tail_consensus_supported`.

The current frozen specification remains unchanged:

`3 x 126-session history -> 0.5*median rank + 0.5*q25 rank -> Robust30 -> freeze 126 sessions -> downstream OLS Top1`.

Stage7E strengthens the economic/statistical rationale for this design, but does not constitute a reason to alter it.
